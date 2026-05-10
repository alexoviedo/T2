//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use usb2ble_app::App;
use usb2ble_contracts::{
    BleActionResponse, BleTransport, BleTransportError, BridgeStatusResponse, CONTRACT_VERSION,
    ControlCommand, ControlError, ControlPlane, ControlResponse, DescriptorKey, EncodedBleReport,
    NormalizedControlValue, PersonaEncoder, PersonaId, PersonaInputFrame,
    PersonaLogicalControlValue, UsbIngress,
};
use usb2ble_control::SerialControlPlane;
use usb2ble_personas::{
    GENERIC_GAMEPAD_PERSONA_ID, GenericGamepadEncoder, XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
    XboxWirelessControllerEncoder,
};
use usb2ble_platform_esp32::{
    self as platform, EspUsbIngress, Uart, UartReadResult, ble_hid::BleHidTransport,
};
use usb2ble_storage::InMemoryStore;

/// Firmware name.
pub const FIRMWARE_NAME: &str = "usb2ble";
/// Firmware version.
pub const FIRMWARE_VERSION: &str = "0.4.2-ble-hid-demo";

const DEFAULT_BRIDGE_RATE_HZ: u16 = 50;
const MIN_BRIDGE_RATE_HZ: u16 = 1;
const MAX_BRIDGE_RATE_HZ: u16 = 200;
const BRIDGE_HEARTBEAT_MS: u64 = 1_000;

#[derive(Debug, Default)]
struct SelfTestState {
    generic_pressed: bool,
    xbox_pressed: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum BridgePollOutcome {
    Noop,
    FirstPublish,
    DisabledPersonaMismatch,
}

#[derive(Debug, Clone)]
struct BridgeRuntime {
    enabled: bool,
    rate_hz: u16,
    min_interval_ms: u64,
    heartbeat_ms: u64,
    last_attempt_ms: Option<u64>,
    last_publish_ms: Option<u64>,
    last_report: Option<EncodedBleReport>,
    first_success_logged: bool,
    published: u64,
    skipped_duplicate: u64,
    skipped_rate: u64,
    skipped_not_connected: u64,
    skipped_not_ready: u64,
    last_error: Option<&'static str>,
}

impl BridgeRuntime {
    fn new() -> Self {
        let mut runtime = Self {
            enabled: false,
            rate_hz: DEFAULT_BRIDGE_RATE_HZ,
            min_interval_ms: 0,
            heartbeat_ms: BRIDGE_HEARTBEAT_MS,
            last_attempt_ms: None,
            last_publish_ms: None,
            last_report: None,
            first_success_logged: false,
            published: 0,
            skipped_duplicate: 0,
            skipped_rate: 0,
            skipped_not_connected: 0,
            skipped_not_ready: 0,
            last_error: None,
        };
        runtime.update_min_interval();
        runtime
    }

    fn start(&mut self, active_persona: Option<PersonaId>) -> Result<(), ControlError> {
        if active_persona.is_none() {
            self.last_error = Some("no_active_persona");
            return Err(ControlError::BridgeNoActivePersona);
        }

        if !self.enabled {
            self.last_publish_ms = None;
            self.last_attempt_ms = None;
            self.last_report = None;
            self.first_success_logged = false;
        }
        self.enabled = true;
        self.last_error = None;
        Ok(())
    }

    fn stop(&mut self) {
        self.enabled = false;
        self.last_error = None;
    }

    fn set_rate_hz(&mut self, rate_hz: u16) -> Result<(), ControlError> {
        if !(MIN_BRIDGE_RATE_HZ..=MAX_BRIDGE_RATE_HZ).contains(&rate_hz) {
            self.last_error = Some("invalid_rate");
            return Err(ControlError::InvalidBridgeRate);
        }
        self.rate_hz = rate_hz;
        self.update_min_interval();
        self.last_error = None;
        Ok(())
    }

    fn status(&self, active_persona: Option<PersonaId>) -> BridgeStatusResponse {
        BridgeStatusResponse {
            enabled: self.enabled,
            active_persona,
            rate_hz: self.rate_hz,
            last_publish_ms: self.last_publish_ms,
            published: self.published,
            skipped_duplicate: self.skipped_duplicate,
            skipped_rate: self.skipped_rate,
            skipped_not_connected: self.skipped_not_connected,
            skipped_not_ready: self.skipped_not_ready,
            last_error: self.last_error,
        }
    }

    fn poll<S>(
        &mut self,
        app: &App<S>,
        ble: &mut impl BleTransport,
        now_ms: u64,
    ) -> BridgePollOutcome
    where
        S: usb2ble_contracts::ProfileStore + usb2ble_contracts::BondStore,
    {
        if !self.enabled {
            return BridgePollOutcome::Noop;
        }

        let active_persona = app.state().active_persona;
        let Some(persona_id) = active_persona else {
            self.skipped_not_ready = self.skipped_not_ready.saturating_add(1);
            self.last_error = Some("no_active_persona");
            return BridgePollOutcome::Noop;
        };

        if let Some(last_ms) = self.last_attempt_ms
            && now_ms.saturating_sub(last_ms) < self.min_interval_ms
        {
            self.skipped_rate = self.skipped_rate.saturating_add(1);
            return BridgePollOutcome::Noop;
        }
        self.last_attempt_ms = Some(now_ms);

        let report = match bridge_report_for_persona(app, persona_id) {
            Ok(report) => report,
            Err(ControlError::NotFound) => {
                self.skipped_not_ready = self.skipped_not_ready.saturating_add(1);
                return BridgePollOutcome::Noop;
            }
            Err(ControlError::PersonaMismatch) => {
                self.enabled = false;
                self.last_error = Some("persona_mismatch");
                return BridgePollOutcome::DisabledPersonaMismatch;
            }
            Err(_) => {
                self.last_error = Some("report_error");
                return BridgePollOutcome::Noop;
            }
        };

        if self.last_report.as_ref() == Some(&report)
            && self
                .last_publish_ms
                .is_some_and(|last_ms| now_ms.saturating_sub(last_ms) < self.heartbeat_ms)
        {
            self.skipped_duplicate = self.skipped_duplicate.saturating_add(1);
            return BridgePollOutcome::Noop;
        }

        match ble.publish_report(&report) {
            Ok(()) => {
                self.published = self.published.saturating_add(1);
                self.last_publish_ms = Some(now_ms);
                self.last_report = Some(report);
                self.last_error = None;
                if self.first_success_logged {
                    BridgePollOutcome::Noop
                } else {
                    self.first_success_logged = true;
                    BridgePollOutcome::FirstPublish
                }
            }
            Err(BleTransportError::NotConnected) => {
                self.skipped_not_connected = self.skipped_not_connected.saturating_add(1);
                self.last_error = Some("not_connected");
                BridgePollOutcome::Noop
            }
            Err(BleTransportError::PersonaMismatch) => {
                self.enabled = false;
                self.last_error = Some("persona_mismatch");
                BridgePollOutcome::DisabledPersonaMismatch
            }
            Err(_) => {
                self.last_error = Some("ble_error");
                BridgePollOutcome::Noop
            }
        }
    }

    fn update_min_interval(&mut self) {
        self.min_interval_ms = u64::from(1_000_u16.saturating_add(self.rate_hz - 1) / self.rate_hz);
    }
}

/// Main firmware entrypoint.
pub fn main() {
    // 1. Initialize platform
    platform::init();

    // Raw printf to bypass any Rust std::io VFS issues during early boot
    platform::trace_printf(b"[TRACE] ENTERED main()\n\0");

    let uart = Uart::new();
    platform::trace_printf(b"[TRACE] Uart initialized\n\0");

    let mut usb = EspUsbIngress::new();
    platform::trace_printf(b"[TRACE] UsbIngress initialized\n\0");

    // Start USB host stack witness path on target
    #[cfg(target_os = "espidf")]
    {
        platform::trace_printf(b"[TRACE] Calling usb.init_host()\n\0");
        if let Err(err) = usb.init_host() {
            uart.write_all(format!("ERROR: USB host init failed: {err}\n").as_bytes());
        }
        platform::trace_printf(b"[TRACE] usb.init_host() returned\n\0");
    }

    // Trigger witness events for host simulation/test
    #[cfg(not(target_os = "espidf"))]
    usb.simulate_events_for_test();

    // 2. Initialize storage (In-memory for M1/M2)
    platform::trace_printf(b"[TRACE] Initializing storage\n\0");
    let storage = InMemoryStore::new();

    // 3. Initialize app
    platform::trace_printf(b"[TRACE] Initializing app\n\0");
    let mut app = App::new(storage);
    let control = SerialControlPlane::new();
    let mut ble = BleHidTransport::new();
    let generic_encoder = GenericGamepadEncoder;
    let xbox_encoder = XboxWirelessControllerEncoder;
    let mut report_log_micros: Vec<(DescriptorKey, u64)> = Vec::new();
    let mut self_test = SelfTestState::default();
    let mut bridge = BridgeRuntime::new();
    let bridge_clock = std::time::Instant::now();

    // 4. Print startup banner
    platform::trace_printf(b"--- USB2BLE FIRMWARE BOOT ---\n\0");
    uart.write_all(format!("Name: {}\n", FIRMWARE_NAME).as_bytes());
    uart.write_all(format!("Version: {}\n", FIRMWARE_VERSION).as_bytes());
    uart.write_all(format!("Contract Version: {}\n", CONTRACT_VERSION).as_bytes());
    uart.write_all(b"Status: BLE HID Demo Path (Selectable Generic/Xbox Personas)\n");
    uart.write_all(b"Ready for commands.\n");

    platform::trace_printf(b"[TRACE] ENTERED MAIN LOOP\n\0");

    // 5. Main loop
    let mut buf = [0u8; 128];
    loop {
        #[cfg(target_os = "espidf")]
        {
            if let Err(err) = usb.service_host() {
                uart.write_all(format!("ERROR: USB host service failed: {err}\n").as_bytes());
            }
        }
        #[cfg(not(target_os = "espidf"))]
        usb.service_host();

        // Poll USB events
        let mut bridge_polled_this_loop = false;
        while let Some(event) = usb.poll_event() {
            let is_input_report = matches!(
                &event,
                usb2ble_contracts::UsbIngressEvent::InputReportReceived(_)
            );
            match &event {
                usb2ble_contracts::UsbIngressEvent::DeviceAttached(dev) => {
                    uart.write_all(
                        format!(
                            "[ATTACH] Device: ID={}, VID={:04x}, PID={:04x}\n",
                            dev.device_id.0, dev.vendor_id, dev.product_id
                        )
                        .as_bytes(),
                    );
                }
                usb2ble_contracts::UsbIngressEvent::DeviceDetached { source } => {
                    uart.write_all(
                        format!("[DETACH] Device: ID={}\n", source.device_id.0).as_bytes(),
                    );
                    report_log_micros.retain(|(k, _)| k.device_id != source.device_id);
                }
                usb2ble_contracts::UsbIngressEvent::InterfaceDiscovered {
                    source,
                    class_code,
                    subclass_code,
                    protocol_code,
                } => {
                    uart.write_all(
                        format!(
                            "[INTERFACE] Device: ID={}, IFACE={}, CLASS={:02x}, SUBCLASS={:02x}, PROTOCOL={:02x}\n",
                            source.device.device_id.0,
                            source.interface_id.0,
                            class_code,
                            subclass_code,
                            protocol_code
                        )
                        .as_bytes(),
                    );
                }
                usb2ble_contracts::UsbIngressEvent::ReportDescriptorReceived(blob) => {
                    uart.write_all(
                        format!(
                            "[DESCRIPTOR] Device: ID={}, IFACE={}, BYTES={}\n",
                            blob.source.device.device_id.0,
                            blob.source.interface_id.0,
                            blob.bytes.len()
                        )
                        .as_bytes(),
                    );
                }
                usb2ble_contracts::UsbIngressEvent::InputReportReceived(packet) => {
                    let key = DescriptorKey {
                        device_id: packet.source.device.device_id,
                        interface_id: Some(packet.source.interface_id),
                    };
                    let should_log = if let Some((_, last_micros)) =
                        report_log_micros.iter_mut().find(|(k, _)| *k == key)
                    {
                        if packet.timestamp_micros.saturating_sub(*last_micros) >= 1_000_000 {
                            *last_micros = packet.timestamp_micros;
                            true
                        } else {
                            false
                        }
                    } else {
                        report_log_micros.push((key, packet.timestamp_micros));
                        true
                    };
                    if should_log {
                        uart.write_all(
                            format!(
                                "[REPORT] Device: ID={}, IFACE={}, REPORT_ID={}, BYTES={}\n",
                                packet.source.device.device_id.0,
                                packet.source.interface_id.0,
                                packet.report_id.0,
                                packet.payload.len()
                            )
                            .as_bytes(),
                        );
                    }
                }
                _ => {}
            }
            app.handle_usb_event(event);
            if is_input_report {
                let now_ms = elapsed_ms(bridge_clock);
                let outcome = bridge.poll(&app, &mut ble, now_ms);
                write_bridge_poll_outcome(&uart, outcome);
                bridge_polled_this_loop = true;
            }
        }

        if !bridge_polled_this_loop {
            let now_ms = elapsed_ms(bridge_clock);
            let outcome = bridge.poll(&app, &mut ble, now_ms);
            write_bridge_poll_outcome(&uart, outcome);
        }

        match uart.read_line(&mut buf) {
            UartReadResult::Frame(n) => {
                match control.decode_command(&buf[..n]) {
                    Ok(cmd) => {
                        let resp = handle_control_command(
                            &mut app,
                            &mut ble,
                            &generic_encoder,
                            &xbox_encoder,
                            &cmd,
                            &mut self_test,
                            &mut bridge,
                        );
                        if let Ok(resp_bytes) = control.encode_response(&resp) {
                            uart.write_all(&resp_bytes);
                        }
                        write_bridge_command_outcome(&uart, &cmd, &resp);
                    }
                    Err(err) => {
                        // Send explicit error response for undecodable commands
                        let resp = ControlResponse::Error(err);
                        if let Ok(resp_bytes) = control.encode_response(&resp) {
                            uart.write_all(&resp_bytes);
                        }
                    }
                }
            }
            UartReadResult::Pending => {
                // Continue looping, wait for more data
                #[cfg(target_os = "espidf")]
                std::thread::sleep(std::time::Duration::from_millis(10));
            }
            UartReadResult::Eof => {
                // On host, stdin closed.
                #[cfg(not(target_os = "espidf"))]
                break;
            }
            UartReadResult::Error => {
                // uart.write_all(b"ERROR: UART Read Error\n");
                #[cfg(target_os = "espidf")]
                std::thread::sleep(std::time::Duration::from_millis(100));
            }
        }
    }
}

fn elapsed_ms(start: std::time::Instant) -> u64 {
    start.elapsed().as_millis().min(u128::from(u64::MAX)) as u64
}

fn write_bridge_poll_outcome(uart: &Uart, outcome: BridgePollOutcome) {
    match outcome {
        BridgePollOutcome::Noop => {}
        BridgePollOutcome::FirstPublish => {
            uart.write_all(b"[BRIDGE] first auto-publish succeeded\n");
        }
        BridgePollOutcome::DisabledPersonaMismatch => {
            uart.write_all(b"[BRIDGE] disabled: persona mismatch\n");
        }
    }
}

fn write_bridge_command_outcome(uart: &Uart, cmd: &ControlCommand, resp: &ControlResponse) {
    match (cmd, resp) {
        (ControlCommand::StartBridge, ControlResponse::BridgeStatus(status)) if status.enabled => {
            uart.write_all(b"[BRIDGE] started\n");
        }
        (ControlCommand::StopBridge, ControlResponse::BridgeStatus(status)) if !status.enabled => {
            uart.write_all(b"[BRIDGE] stopped\n");
        }
        _ => {}
    }
}

fn handle_control_command<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    xbox_encoder: &impl PersonaEncoder,
    cmd: &ControlCommand,
    self_test: &mut SelfTestState,
    bridge: &mut BridgeRuntime,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore + usb2ble_contracts::BondStore,
{
    app.set_ble_state(ble.current_state());

    let resp = match cmd {
        ControlCommand::StartBleGenericGamepad => start_ble_persona(
            app,
            ble,
            generic_encoder,
            GENERIC_GAMEPAD_PERSONA_ID,
            "start_generic_gamepad",
        ),
        ControlCommand::StartBleXboxController => start_ble_persona(
            app,
            ble,
            xbox_encoder,
            XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            "start_xbox_controller",
        ),
        ControlCommand::PublishGenericGamepadReport => match app.generic_gamepad_report() {
            Ok(report) => publish_ble_report(ble, report, "publish_generic_gamepad"),
            Err(err) => ControlResponse::Error(err),
        },
        ControlCommand::PublishXboxGamepadReport => match app.xbox_gamepad_report() {
            Ok(report) => publish_ble_report(ble, report, "publish_xbox_gamepad"),
            Err(err) => ControlResponse::Error(err),
        },
        ControlCommand::SendBleSelfTestReport => {
            match generic_self_test_report(generic_encoder, &mut self_test.generic_pressed) {
                Ok(report) => publish_ble_report(ble, report, "send_self_test"),
                Err(_) => ControlResponse::Error(ControlError::Generic),
            }
        }
        ControlCommand::SendXboxSelfTestReport => {
            match xbox_self_test_report(xbox_encoder, &mut self_test.xbox_pressed) {
                Ok(report) => publish_ble_report(ble, report, "send_xbox_self_test"),
                Err(_) => ControlResponse::Error(ControlError::Generic),
            }
        }
        ControlCommand::ForgetBleBonds => match ble.forget_bonds() {
            Ok(()) => ControlResponse::BleAction(BleActionResponse {
                action: "forget_bonds",
                state: ble.current_state(),
                report: None,
            }),
            Err(_) => ControlResponse::Error(ControlError::Generic),
        },
        ControlCommand::StartBridge => match bridge.start(app.state().active_persona) {
            Ok(()) => ControlResponse::BridgeStatus(bridge.status(app.state().active_persona)),
            Err(err) => ControlResponse::Error(err),
        },
        ControlCommand::StopBridge => {
            bridge.stop();
            ControlResponse::BridgeStatus(bridge.status(app.state().active_persona))
        }
        ControlCommand::GetBridgeStatus => {
            ControlResponse::BridgeStatus(bridge.status(app.state().active_persona))
        }
        ControlCommand::SetBridgeRateHz(rate_hz) => match bridge.set_rate_hz(*rate_hz) {
            Ok(()) => ControlResponse::BridgeStatus(bridge.status(app.state().active_persona)),
            Err(err) => ControlResponse::Error(err),
        },
        _ => app.handle_control_command(cmd),
    };

    app.set_ble_state(ble.current_state());
    resp
}

fn start_ble_persona<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    encoder: &impl PersonaEncoder,
    persona_id: PersonaId,
    action: &'static str,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore + usb2ble_contracts::BondStore,
{
    match encoder.descriptor(persona_id) {
        Ok(descriptor) => match ble.activate_persona(&descriptor) {
            Ok(()) => {
                app.set_active_persona(Some(persona_id));
                ControlResponse::BleAction(BleActionResponse {
                    action,
                    state: ble.current_state(),
                    report: None,
                })
            }
            Err(err) => ControlResponse::Error(control_error_from_ble(err)),
        },
        Err(_) => ControlResponse::Error(ControlError::Generic),
    }
}

fn publish_ble_report(
    ble: &mut impl BleTransport,
    report: EncodedBleReport,
    action: &'static str,
) -> ControlResponse {
    match ble.publish_report(&report) {
        Ok(()) => ControlResponse::BleAction(BleActionResponse {
            action,
            state: ble.current_state(),
            report: Some(report),
        }),
        Err(err) => ControlResponse::Error(control_error_from_ble(err)),
    }
}

fn bridge_report_for_persona<S>(
    app: &App<S>,
    persona_id: PersonaId,
) -> Result<EncodedBleReport, ControlError>
where
    S: usb2ble_contracts::ProfileStore + usb2ble_contracts::BondStore,
{
    if persona_id == GENERIC_GAMEPAD_PERSONA_ID {
        app.generic_gamepad_report()
    } else if persona_id == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
        app.xbox_gamepad_report()
    } else {
        Err(ControlError::PersonaMismatch)
    }
}

fn control_error_from_ble(err: BleTransportError) -> ControlError {
    match err {
        BleTransportError::Generic => ControlError::Generic,
        BleTransportError::PersonaAlreadyActive => ControlError::PersonaAlreadyActive,
        BleTransportError::PersonaMismatch => ControlError::PersonaMismatch,
        BleTransportError::NotConnected => ControlError::BleNotConnected,
    }
}

fn generic_self_test_report(
    encoder: &impl PersonaEncoder,
    generic_self_test_pressed: &mut bool,
) -> Result<usb2ble_contracts::EncodedBleReport, usb2ble_contracts::PersonaError> {
    *generic_self_test_pressed = !*generic_self_test_pressed;
    let axis = if *generic_self_test_pressed {
        i32::from(i16::MAX)
    } else {
        i32::from(i16::MIN)
    };

    encoder.encode(&PersonaInputFrame {
        persona_id: GENERIC_GAMEPAD_PERSONA_ID,
        logical_controls: vec![
            PersonaLogicalControlValue {
                control_id: "button_1".to_string(),
                value: NormalizedControlValue::Button(*generic_self_test_pressed),
            },
            PersonaLogicalControlValue {
                control_id: "hat".to_string(),
                value: NormalizedControlValue::Hat(if *generic_self_test_pressed { 0 } else { 8 }),
            },
            PersonaLogicalControlValue {
                control_id: "x".to_string(),
                value: NormalizedControlValue::Axis(axis),
            },
        ],
    })
}

fn xbox_self_test_report(
    encoder: &impl PersonaEncoder,
    xbox_self_test_pressed: &mut bool,
) -> Result<usb2ble_contracts::EncodedBleReport, usb2ble_contracts::PersonaError> {
    *xbox_self_test_pressed = !*xbox_self_test_pressed;
    let axis = if *xbox_self_test_pressed {
        i32::from(i16::MAX)
    } else {
        i32::from(i16::MIN)
    };

    encoder.encode(&PersonaInputFrame {
        persona_id: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
        logical_controls: vec![
            PersonaLogicalControlValue {
                control_id: "a".to_string(),
                value: NormalizedControlValue::Button(*xbox_self_test_pressed),
            },
            PersonaLogicalControlValue {
                control_id: "left_x".to_string(),
                value: NormalizedControlValue::Axis(axis),
            },
        ],
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::{
        BleLinkState, ConnectionTopology, DeviceId, InputReportPacket, InterfaceId,
        PersonaDescriptor, ReportDescriptorBlob, ReportId, UsbDeviceRef, UsbIngressEvent,
        UsbInterfaceRef,
    };
    use usb2ble_storage::InMemoryStore;

    struct Runtime {
        app: App<InMemoryStore>,
        ble: BleHidTransport,
        generic_encoder: GenericGamepadEncoder,
        xbox_encoder: XboxWirelessControllerEncoder,
        self_test: SelfTestState,
        bridge: BridgeRuntime,
    }

    impl Runtime {
        fn new() -> Self {
            Self {
                app: App::new(InMemoryStore::new()),
                ble: BleHidTransport::new(),
                generic_encoder: GenericGamepadEncoder,
                xbox_encoder: XboxWirelessControllerEncoder,
                self_test: SelfTestState::default(),
                bridge: BridgeRuntime::new(),
            }
        }

        fn with_button_input() -> Self {
            let mut runtime = Self::new();
            inject_button_input(&mut runtime.app);
            runtime
        }

        fn run(&mut self, cmd: ControlCommand) -> ControlResponse {
            handle_control_command(
                &mut self.app,
                &mut self.ble,
                &self.generic_encoder,
                &self.xbox_encoder,
                &cmd,
                &mut self.self_test,
                &mut self.bridge,
            )
        }

        fn poll_bridge(&mut self, now_ms: u64) -> BridgePollOutcome {
            self.bridge.poll(&self.app, &mut self.ble, now_ms)
        }
    }

    #[test]
    fn generic_start_is_idempotent() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_eq!(
            runtime.app.state().active_persona,
            Some(GENERIC_GAMEPAD_PERSONA_ID)
        );
    }

    #[test]
    fn xbox_start_is_idempotent() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        assert_eq!(
            runtime.app.state().active_persona,
            Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
        );
        match runtime.run(ControlCommand::GetStatus) {
            ControlResponse::Status(status) => {
                assert_eq!(
                    status.active_persona,
                    Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
                );
            }
            other => panic!("expected status response, got {other:?}"),
        }
    }

    #[test]
    fn generic_then_xbox_returns_persona_already_active() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_eq!(
            runtime.run(ControlCommand::StartBleXboxController),
            ControlResponse::Error(ControlError::PersonaAlreadyActive)
        );
        assert_eq!(
            runtime.app.state().active_persona,
            Some(GENERIC_GAMEPAD_PERSONA_ID)
        );
    }

    #[test]
    fn xbox_then_generic_returns_persona_already_active() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        assert_eq!(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            ControlResponse::Error(ControlError::PersonaAlreadyActive)
        );
        assert_eq!(
            runtime.app.state().active_persona,
            Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
        );
    }

    #[test]
    fn generic_publish_still_publishes_latest_usb_derived_report() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        let report = assert_ble_report(
            runtime.run(ControlCommand::PublishGenericGamepadReport),
            "publish_generic_gamepad",
        );

        assert_eq!(report.persona_id, GENERIC_GAMEPAD_PERSONA_ID);
        assert_eq!(report.report_id.0, 1);
        assert_eq!(report.bytes.len(), 15);
        assert_eq!(runtime.ble.published_reports().len(), 1);
    }

    #[test]
    fn xbox_publish_publishes_latest_usb_derived_report() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        let report = assert_ble_report(
            runtime.run(ControlCommand::PublishXboxGamepadReport),
            "publish_xbox_gamepad",
        );

        assert_eq!(report.persona_id, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(report.report_id.0, 1);
        assert_eq!(report.bytes.len(), 16);
        assert_eq!(runtime.ble.published_reports().len(), 1);
    }

    #[test]
    fn mismatched_publish_returns_persona_mismatch() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_eq!(
            runtime.run(ControlCommand::PublishXboxGamepadReport),
            ControlResponse::Error(ControlError::PersonaMismatch)
        );
        assert!(runtime.ble.published_reports().is_empty());
    }

    #[test]
    fn start_bridge_without_active_persona_returns_explicit_error() {
        let mut runtime = Runtime::new();

        assert_eq!(
            runtime.run(ControlCommand::StartBridge),
            ControlResponse::Error(ControlError::BridgeNoActivePersona)
        );
    }

    #[test]
    fn generic_persona_can_start_bridge() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        let status = assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert!(status.enabled);
        assert_eq!(status.active_persona, Some(GENERIC_GAMEPAD_PERSONA_ID));
        assert_eq!(status.rate_hz, DEFAULT_BRIDGE_RATE_HZ);
    }

    #[test]
    fn xbox_persona_can_start_bridge() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        let status = assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert!(status.enabled);
        assert_eq!(
            status.active_persona,
            Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
        );
    }

    #[test]
    fn stop_bridge_disables_and_is_idempotent() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));
        let stopped = assert_bridge_status(runtime.run(ControlCommand::StopBridge));
        let stopped_again = assert_bridge_status(runtime.run(ControlCommand::StopBridge));

        assert!(!stopped.enabled);
        assert!(!stopped_again.enabled);
    }

    #[test]
    fn get_bridge_status_returns_stable_fields() {
        let mut runtime = Runtime::new();

        let status = assert_bridge_status(runtime.run(ControlCommand::GetBridgeStatus));

        assert!(!status.enabled);
        assert_eq!(status.active_persona, None);
        assert_eq!(status.rate_hz, DEFAULT_BRIDGE_RATE_HZ);
        assert_eq!(status.last_publish_ms, None);
        assert_eq!(status.published, 0);
        assert_eq!(status.skipped_duplicate, 0);
        assert_eq!(status.skipped_rate, 0);
        assert_eq!(status.skipped_not_connected, 0);
        assert_eq!(status.skipped_not_ready, 0);
        assert_eq!(status.last_error, None);
    }

    #[test]
    fn automatic_bridge_publish_emits_generic_reports() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert_eq!(runtime.poll_bridge(0), BridgePollOutcome::FirstPublish);
        let report = runtime
            .ble
            .published_reports()
            .last()
            .expect("bridge should publish a report");
        assert_eq!(report.persona_id, GENERIC_GAMEPAD_PERSONA_ID);
        assert_eq!(report.bytes.len(), 15);
    }

    #[test]
    fn automatic_bridge_publish_emits_xbox_reports() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert_eq!(runtime.poll_bridge(0), BridgePollOutcome::FirstPublish);
        let report = runtime
            .ble
            .published_reports()
            .last()
            .expect("bridge should publish a report");
        assert_eq!(report.persona_id, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(report.bytes.len(), 16);
    }

    #[test]
    fn bridge_rate_limiting_suppresses_too_frequent_reports() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert_eq!(runtime.poll_bridge(0), BridgePollOutcome::FirstPublish);
        assert_eq!(runtime.poll_bridge(10), BridgePollOutcome::Noop);

        let status = runtime.bridge.status(runtime.app.state().active_persona);
        assert_eq!(runtime.ble.published_reports().len(), 1);
        assert_eq!(status.skipped_rate, 1);
    }

    #[test]
    fn bridge_duplicate_suppression_suppresses_until_heartbeat() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert_eq!(runtime.poll_bridge(0), BridgePollOutcome::FirstPublish);
        assert_eq!(runtime.poll_bridge(20), BridgePollOutcome::Noop);

        let status = runtime.bridge.status(runtime.app.state().active_persona);
        assert_eq!(runtime.ble.published_reports().len(), 1);
        assert_eq!(status.skipped_duplicate, 1);
    }

    #[test]
    fn bridge_heartbeat_republishes_stable_state() {
        let mut runtime = Runtime::with_button_input();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));

        assert_eq!(runtime.poll_bridge(0), BridgePollOutcome::FirstPublish);
        assert_eq!(
            runtime.poll_bridge(BRIDGE_HEARTBEAT_MS),
            BridgePollOutcome::Noop
        );

        let status = runtime.bridge.status(runtime.app.state().active_persona);
        assert_eq!(runtime.ble.published_reports().len(), 2);
        assert_eq!(status.published, 2);
        assert_eq!(status.last_publish_ms, Some(BRIDGE_HEARTBEAT_MS));
    }

    #[test]
    fn bridge_ble_not_connected_increments_skip_without_disabling() {
        let mut app = App::new(InMemoryStore::new());
        inject_button_input(&mut app);
        app.set_active_persona(Some(GENERIC_GAMEPAD_PERSONA_ID));
        let mut bridge = BridgeRuntime::new();
        bridge.start(app.state().active_persona).unwrap();
        let mut ble = TestBleTransport::new(Some(GENERIC_GAMEPAD_PERSONA_ID));
        ble.next_error = Some(BleTransportError::NotConnected);

        assert_eq!(bridge.poll(&app, &mut ble, 0), BridgePollOutcome::Noop);

        let status = bridge.status(app.state().active_persona);
        assert!(status.enabled);
        assert_eq!(status.skipped_not_connected, 1);
        assert_eq!(status.last_error, Some("not_connected"));
    }

    #[test]
    fn bridge_persona_mismatch_disables_bridge() {
        let mut app = App::new(InMemoryStore::new());
        inject_button_input(&mut app);
        app.set_active_persona(Some(GENERIC_GAMEPAD_PERSONA_ID));
        let mut bridge = BridgeRuntime::new();
        bridge.start(app.state().active_persona).unwrap();
        let mut ble = TestBleTransport::new(Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID));

        assert_eq!(
            bridge.poll(&app, &mut ble, 0),
            BridgePollOutcome::DisabledPersonaMismatch
        );

        let status = bridge.status(app.state().active_persona);
        assert!(!status.enabled);
        assert_eq!(status.last_error, Some("persona_mismatch"));
    }

    #[test]
    fn set_bridge_rate_updates_status() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        let status = assert_bridge_status(runtime.run(ControlCommand::SetBridgeRateHz(25)));

        assert_eq!(status.rate_hz, 25);
        assert_eq!(
            runtime.run(ControlCommand::SetBridgeRateHz(0)),
            ControlResponse::Error(ControlError::InvalidBridgeRate)
        );
    }

    #[test]
    fn xbox_self_test_toggles_a_button_and_left_x_with_sixteen_bytes() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        let pressed = assert_ble_report(
            runtime.run(ControlCommand::SendXboxSelfTestReport),
            "send_xbox_self_test",
        );
        let released = assert_ble_report(
            runtime.run(ControlCommand::SendXboxSelfTestReport),
            "send_xbox_self_test",
        );

        assert_eq!(pressed.persona_id, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(pressed.report_id.0, 1);
        assert_eq!(pressed.bytes.len(), 16);
        assert_eq!(released.bytes.len(), 16);
        assert_ne!(pressed.bytes, released.bytes);
        assert_eq!(&pressed.bytes[0..2], &65_534_u16.to_le_bytes());
        assert_eq!(&released.bytes[0..2], &0_u16.to_le_bytes());
        assert_eq!(&pressed.bytes[13..15], &1_u16.to_le_bytes());
        assert_eq!(&released.bytes[13..15], &0_u16.to_le_bytes());
    }

    fn inject_button_input(app: &mut App<InMemoryStore>) {
        let dev = UsbDeviceRef {
            device_id: DeviceId(1),
            topology: ConnectionTopology::Direct,
            vendor_id: 0x1234,
            product_id: 0x5678,
        };
        let iface = UsbInterfaceRef {
            device: dev.clone(),
            interface_id: InterfaceId(0),
        };
        let report_descriptor = vec![
            0x05, 0x09, // Usage Page (Button)
            0x19, 0x01, // Usage Minimum (1)
            0x29, 0x01, // Usage Maximum (1)
            0x15, 0x00, // Logical Minimum (0)
            0x25, 0x01, // Logical Maximum (1)
            0x75, 0x01, // Report Size (1)
            0x95, 0x01, // Report Count (1)
            0x81, 0x02, // Input (Data, Variable, Absolute)
        ];

        app.handle_usb_event(UsbIngressEvent::DeviceAttached(dev));
        app.handle_usb_event(UsbIngressEvent::InterfaceDiscovered {
            source: iface.clone(),
            class_code: 3,
            subclass_code: 0,
            protocol_code: 0,
        });
        app.handle_usb_event(UsbIngressEvent::ReportDescriptorReceived(
            ReportDescriptorBlob {
                source: iface.clone(),
                bytes: report_descriptor,
            },
        ));
        app.handle_usb_event(UsbIngressEvent::InputReportReceived(InputReportPacket {
            source: iface,
            report_id: ReportId(0),
            payload: vec![0x01],
            timestamp_micros: 100,
        }));
    }

    struct TestBleTransport {
        state: BleLinkState,
        active_persona: Option<PersonaId>,
        next_error: Option<BleTransportError>,
        published_reports: Vec<EncodedBleReport>,
    }

    impl TestBleTransport {
        fn new(active_persona: Option<PersonaId>) -> Self {
            Self {
                state: if active_persona.is_some() {
                    BleLinkState::Connected
                } else {
                    BleLinkState::Idle
                },
                active_persona,
                next_error: None,
                published_reports: Vec::new(),
            }
        }
    }

    impl BleTransport for TestBleTransport {
        fn current_state(&self) -> BleLinkState {
            self.state
        }

        fn activate_persona(
            &mut self,
            descriptor: &PersonaDescriptor,
        ) -> Result<(), BleTransportError> {
            self.active_persona = Some(descriptor.persona_id);
            self.state = BleLinkState::Advertising;
            Ok(())
        }

        fn publish_report(&mut self, report: &EncodedBleReport) -> Result<(), BleTransportError> {
            if let Some(err) = self.next_error.take() {
                return Err(err);
            }
            if self.active_persona != Some(report.persona_id) {
                return Err(BleTransportError::PersonaMismatch);
            }
            self.published_reports.push(report.clone());
            Ok(())
        }

        fn forget_bonds(&mut self) -> Result<(), BleTransportError> {
            Ok(())
        }
    }

    fn assert_ble_action(resp: ControlResponse, action: &str) {
        match resp {
            ControlResponse::BleAction(resp) => {
                assert_eq!(resp.action, action);
                assert!(matches!(
                    resp.state,
                    usb2ble_contracts::BleLinkState::Advertising
                        | usb2ble_contracts::BleLinkState::Connected
                ));
                assert!(resp.report.is_none());
            }
            other => panic!("expected BLE action {action}, got {other:?}"),
        }
    }

    fn assert_bridge_status(resp: ControlResponse) -> BridgeStatusResponse {
        match resp {
            ControlResponse::BridgeStatus(status) => status,
            other => panic!("expected bridge status response, got {other:?}"),
        }
    }

    fn assert_ble_report(resp: ControlResponse, action: &str) -> EncodedBleReport {
        match resp {
            ControlResponse::BleAction(resp) => {
                assert_eq!(resp.action, action);
                assert_eq!(resp.state, usb2ble_contracts::BleLinkState::Connected);
                resp.report.expect("BLE action should include report")
            }
            other => panic!("expected BLE report action {action}, got {other:?}"),
        }
    }
}
