//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use sha2::{Digest, Sha256};
use usb2ble_app::App;
use usb2ble_contracts::{
    BleActionResponse, BleAdvertisingInfoResponse, BleCompatibilityVariant, BleTransport,
    BleTransportError, BridgeStatusResponse, CONTRACT_VERSION, ConfigActionResponse,
    ConfigImportResponse, ControlCommand, ControlError, ControlPlane, ControlResponse,
    DescriptorKey, EncodedBleReport, JsonResponse, MAX_RUNTIME_CONFIG_JSON_BYTES,
    NormalizedControlValue, PersonaEncoder, PersonaId, PersonaInputFrame,
    PersonaLogicalControlValue, RuntimeConfig, UsbIngress,
};
use usb2ble_control::SerialControlPlane;
use usb2ble_personas::{
    GENERIC_GAMEPAD_PERSONA_ID, GenericGamepadEncoder, XBOX_INPUT_REPORT_ID,
    XBOX_INPUT_REPORT_PAYLOAD_LEN, XBOX_MODEL_1914_REPORT_MAP_LEN, XBOX_RUMBLE_OUTPUT_PAYLOAD_LEN,
    XBOX_RUMBLE_REPORT_ID, XBOX_STICK_LOGICAL_MAX, XBOX_TRIGGER_LOGICAL_MAX,
    XBOX_WIRELESS_CONTROLLER_PERSONA_ID, XboxWirelessControllerEncoder,
};
use usb2ble_platform_esp32::{
    self as platform, EspUsbIngress, PlatformStore, Uart, UartReadResult, ble_hid::BleHidTransport,
};

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

#[derive(Debug, Default)]
struct ConfigImportRuntime {
    total_chunks: usize,
    checksum: Option<String>,
    received_chunks: usize,
    bytes: Vec<u8>,
}

#[derive(Debug)]
struct PendingConfigJson {
    bytes: Vec<u8>,
    checksum: Option<String>,
}

impl ConfigImportRuntime {
    fn active(&self) -> bool {
        self.total_chunks > 0
    }

    fn begin(
        &mut self,
        total_chunks: usize,
        checksum: Option<String>,
    ) -> Result<ConfigImportResponse, ControlError> {
        if total_chunks == 0 {
            return Err(ControlError::ConfigChunkMissing);
        }
        self.total_chunks = total_chunks;
        self.checksum = checksum;
        self.received_chunks = 0;
        self.bytes.clear();
        Ok(self.response("started"))
    }

    fn push_chunk(
        &mut self,
        index: usize,
        data: &str,
    ) -> Result<ConfigImportResponse, ControlError> {
        if !self.active() {
            return Err(ControlError::NoConfigImportActive);
        }
        if index != self.received_chunks {
            return Err(ControlError::ConfigChunkOutOfOrder);
        }
        let chunk = URL_SAFE_NO_PAD
            .decode(data.as_bytes())
            .map_err(|_| ControlError::InvalidBase64)?;
        if self.bytes.len().saturating_add(chunk.len()) > MAX_RUNTIME_CONFIG_JSON_BYTES {
            return Err(ControlError::ConfigTooLarge);
        }
        self.bytes.extend_from_slice(&chunk);
        self.received_chunks += 1;
        Ok(self.response("chunk"))
    }

    fn commit(&mut self) -> Result<PendingConfigJson, ControlError> {
        if !self.active() {
            return Err(ControlError::NoConfigImportActive);
        }
        if self.received_chunks != self.total_chunks {
            return Err(ControlError::ConfigChunkMissing);
        }
        let pending = PendingConfigJson {
            bytes: self.bytes.clone(),
            checksum: self.checksum.clone(),
        };
        self.clear();
        Ok(pending)
    }

    fn clear(&mut self) {
        self.total_chunks = 0;
        self.checksum = None;
        self.received_chunks = 0;
        self.bytes.clear();
    }

    fn response(&self, state: &'static str) -> ConfigImportResponse {
        ConfigImportResponse {
            state,
            total_chunks: self.total_chunks,
            received_chunks: self.received_chunks,
            bytes: self.bytes.len(),
        }
    }
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
        S: usb2ble_contracts::ProfileStore
            + usb2ble_contracts::BondStore
            + usb2ble_contracts::ConfigStore,
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
    let storage = PlatformStore::new();

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
    let mut config_import = ConfigImportRuntime::default();
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
                            &mut config_import,
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

#[allow(clippy::too_many_arguments)]
fn handle_control_command<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    xbox_encoder: &impl PersonaEncoder,
    cmd: &ControlCommand,
    self_test: &mut SelfTestState,
    bridge: &mut BridgeRuntime,
    config_import: &mut ConfigImportRuntime,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    app.set_ble_state(ble.current_state());

    let resp = match cmd {
        ControlCommand::StartBleGenericGamepad => start_ble_persona(
            app,
            ble,
            generic_encoder,
            GENERIC_GAMEPAD_PERSONA_ID,
            None,
            "start_generic_gamepad",
        ),
        ControlCommand::StartBleGenericGamepadVariant(variant_id) => {
            start_ble_generic_variant(app, ble, generic_encoder, variant_id)
        }
        ControlCommand::StartBleXboxController => start_ble_persona(
            app,
            ble,
            xbox_encoder,
            XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            None,
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
        ControlCommand::PublishXboxTestReport(scenario) => {
            if app.state().active_persona != Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID) {
                ControlResponse::Error(ControlError::PersonaMismatch)
            } else {
                match xbox_test_report(xbox_encoder, scenario) {
                    Ok(report) => publish_ble_report(ble, report, "publish_xbox_test_report"),
                    Err(_) => ControlResponse::Error(ControlError::Generic),
                }
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
        ControlCommand::GetBleAdvertisingInfo => {
            ble_advertising_info(app, ble, generic_encoder, xbox_encoder)
        }
        ControlCommand::ListBleCompatibilityVariants => {
            ControlResponse::Json(ble_compatibility_variants_json())
        }
        ControlCommand::GetBleCompatProfile => {
            ble_compat_profile_json(app, ble, generic_encoder, xbox_encoder)
        }
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
        ControlCommand::GetConfigStatus => {
            ControlResponse::ConfigStatus(app.config_status(config_import.active()))
        }
        ControlCommand::BeginConfigJson {
            total_chunks,
            checksum,
        } => match config_import.begin(*total_chunks, checksum.clone()) {
            Ok(resp) => ControlResponse::ConfigImport(resp),
            Err(err) => ControlResponse::Error(err),
        },
        ControlCommand::ConfigJsonChunk { index, data } => {
            match config_import.push_chunk(*index, data) {
                Ok(resp) => ControlResponse::ConfigImport(resp),
                Err(err) => ControlResponse::Error(err),
            }
        }
        ControlCommand::CommitConfigJson => match config_import.commit() {
            Ok(pending) => {
                let json_len = pending.bytes.len();
                match parse_runtime_config_json(pending) {
                    Ok(config) => match app.set_runtime_config(config) {
                        Ok(()) => ControlResponse::ConfigImport(ConfigImportResponse {
                            state: "committed",
                            total_chunks: 0,
                            received_chunks: 0,
                            bytes: json_len,
                        }),
                        Err(err) => ControlResponse::Error(err),
                    },
                    Err(err) => ControlResponse::Error(err),
                }
            }
            Err(err) => ControlResponse::Error(err),
        },
        ControlCommand::StartConfigured => {
            start_configured(app, ble, generic_encoder, xbox_encoder, bridge)
        }
        _ => app.handle_control_command(cmd),
    };

    app.set_ble_state(ble.current_state());
    resp
}

fn ble_advertising_info<S>(
    app: &mut App<S>,
    ble: &impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    xbox_encoder: &impl PersonaEncoder,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    let active_persona = app.state().active_persona;
    let active_variant = app.state().active_ble_variant;
    let descriptor = active_persona.and_then(|persona| {
        let encoder: &dyn PersonaEncoder = if persona == GENERIC_GAMEPAD_PERSONA_ID {
            generic_encoder
        } else if persona == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
            xbox_encoder
        } else {
            return None;
        };
        encoder.descriptor(persona).ok()
    });
    let (device_name, appearance) = descriptor
        .as_ref()
        .map(|descriptor| {
            (
                Some(nul_terminated_bytes_to_string(
                    descriptor.identity.device_name,
                )),
                Some(descriptor.identity.appearance),
            )
        })
        .unwrap_or((None, None));
    let bonds_present = match app.handle_control_command(&ControlCommand::GetStatus) {
        ControlResponse::Status(status) => status.bonds_present,
        _ => false,
    };

    ControlResponse::BleAdvertisingInfo(BleAdvertisingInfoResponse {
        active_persona,
        state: ble.current_state(),
        compatibility_variant: active_variant,
        device_name,
        appearance,
        advertised_uuids: advertised_uuids_for_variant(active_variant),
        scan_response_uuids: scan_response_uuids_for_variant(active_variant),
        advertisement_includes_name: active_variant
            == Some(BleCompatibilityVariant::GenericHogpStrict),
        scan_response_includes_name: active_variant
            != Some(BleCompatibilityVariant::GenericHogpStrict),
        flags: 0x06,
        advertising_type: "ADV_TYPE_IND",
        own_address_type: "public",
        security: "bond",
        io_capability: "none",
        bonds_present,
        raw_advertisement_bytes_available: false,
    })
}

fn nul_terminated_bytes_to_string(bytes: &[u8]) -> String {
    let end = bytes
        .iter()
        .position(|byte| *byte == 0)
        .unwrap_or(bytes.len());
    String::from_utf8_lossy(&bytes[..end]).into_owned()
}

fn advertised_uuids_for_variant(variant: Option<BleCompatibilityVariant>) -> Vec<String> {
    match variant {
        Some(BleCompatibilityVariant::GenericHogpStrict)
        | Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => Vec::new(),
        _ => vec!["1812".to_string()],
    }
}

fn scan_response_uuids_for_variant(variant: Option<BleCompatibilityVariant>) -> Vec<String> {
    match variant {
        Some(BleCompatibilityVariant::GenericHogpStrict) => vec!["1812".to_string()],
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => Vec::new(),
        _ => Vec::new(),
    }
}

fn variant_profile_family(variant: Option<BleCompatibilityVariant>) -> &'static str {
    match variant {
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => "keyboard_fallback",
        _ => "hogp_hids",
    }
}

fn variant_intended_host_target(variant: Option<BleCompatibilityVariant>) -> &'static str {
    match variant {
        Some(BleCompatibilityVariant::GenericDefault) => "macos_chrome_proven_default",
        Some(BleCompatibilityVariant::GenericHogpStrict) => "apple_ios_discovery_experiment",
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => "ios_keyboard_fallback_planned",
        Some(BleCompatibilityVariant::XboxCompatibility) => "xbox_like_hosts_experimental",
        None => "none",
    }
}

fn primary_advertisement_fields(variant: Option<BleCompatibilityVariant>) -> Vec<&'static str> {
    match variant {
        Some(BleCompatibilityVariant::GenericHogpStrict) => {
            vec!["flags", "appearance", "complete_local_name"]
        }
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => vec!["flags", "appearance"],
        _ => vec!["flags", "appearance", "complete_128bit_service_uuid"],
    }
}

fn scan_response_fields(variant: Option<BleCompatibilityVariant>) -> Vec<&'static str> {
    match variant {
        Some(BleCompatibilityVariant::GenericHogpStrict) => vec!["complete_128bit_service_uuid"],
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => Vec::new(),
        _ => vec!["complete_local_name"],
    }
}

fn estimated_primary_adv_len(
    variant: Option<BleCompatibilityVariant>,
    device_name: Option<&str>,
) -> usize {
    let flags_len = 3;
    let appearance_len = 4;
    let name_len = device_name.map_or(0, |name| 2 + name.len());
    let uuid_128_len = 18;
    match variant {
        Some(BleCompatibilityVariant::GenericHogpStrict) => flags_len + appearance_len + name_len,
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => flags_len + appearance_len,
        _ => flags_len + appearance_len + uuid_128_len,
    }
}

fn estimated_scan_rsp_len(
    variant: Option<BleCompatibilityVariant>,
    device_name: Option<&str>,
) -> usize {
    let name_len = device_name.map_or(0, |name| 2 + name.len());
    let uuid_128_len = 18;
    match variant {
        Some(BleCompatibilityVariant::GenericHogpStrict) => uuid_128_len,
        Some(BleCompatibilityVariant::IosKeyboardIcadeFallback) => 0,
        _ => name_len,
    }
}

fn ble_compatibility_variants_json() -> JsonResponse {
    let json = serde_json::json!({
        "variants": [
            {
                "id": "generic_default",
                "persona": "generic_gamepad",
                "implemented": true,
                "experimental": false,
                "description": "Current proven Generic Gamepad advertising/report-map path."
            },
            {
                "id": "generic_hogp_strict",
                "persona": "generic_gamepad",
                "implemented": true,
                "experimental": true,
                "description": "HOGP-conservative advertisement experiment: complete local name in primary advertisement and HID UUID in scan response."
            },
            {
                "id": "ios_keyboard_icade_fallback",
                "persona": "keyboard_icade",
                "implemented": false,
                "experimental": true,
                "description": "Planned keyboard/iCade-style fallback. Not a true gamepad and not currently implemented."
            },
            {
                "id": "xbox_compatibility",
                "persona": "xbox_wireless_controller",
                "implemented": true,
                "experimental": false,
                "description": "Existing Xbox compatibility persona; broad Xbox compatibility is not claimed."
            }
        ]
    })
    .to_string();
    JsonResponse {
        prefix: "BLE_COMPAT_VARIANTS_JSON",
        json,
    }
}

fn ble_compat_profile_json<S>(
    app: &mut App<S>,
    ble: &impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    xbox_encoder: &impl PersonaEncoder,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    let active_persona = app.state().active_persona;
    let active_variant = app.state().active_ble_variant;
    let descriptor = active_persona.and_then(|persona| {
        let encoder: &dyn PersonaEncoder = if persona == GENERIC_GAMEPAD_PERSONA_ID {
            generic_encoder
        } else if persona == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
            xbox_encoder
        } else {
            return None;
        };
        let mut descriptor = encoder.descriptor(persona).ok()?;
        if let Some(variant) = active_variant {
            descriptor.compatibility_variant = variant;
        }
        Some(descriptor)
    });
    let bonds_present = match app.handle_control_command(&ControlCommand::GetStatus) {
        ControlResponse::Status(status) => status.bonds_present,
        _ => false,
    };
    let report_map_len = descriptor
        .as_ref()
        .map(|descriptor| descriptor.report_map.len())
        .unwrap_or(0);
    let report_ids = if active_persona == Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID) {
        vec![XBOX_INPUT_REPORT_ID.0, XBOX_RUMBLE_REPORT_ID.0]
    } else if report_map_len > 0 {
        vec![1]
    } else {
        Vec::<u8>::new()
    };
    let xbox_reference = (active_persona == Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)).then(|| {
        serde_json::json!({
            "reference_model": "Xbox Wireless Controller model 1914 / Series X|S BLE",
            "vid": "0x045e",
            "pid": "0x0b13",
            "descriptor_reference": "xpadneo captured 0005:045E:0B13 BLE HID report descriptor",
            "input_report_id": XBOX_INPUT_REPORT_ID.0,
            "input_payload_len": XBOX_INPUT_REPORT_PAYLOAD_LEN,
            "output_report_id": XBOX_RUMBLE_REPORT_ID.0,
            "output_payload_len": XBOX_RUMBLE_OUTPUT_PAYLOAD_LEN,
            "report_map_len_expected": XBOX_MODEL_1914_REPORT_MAP_LEN,
            "stick_logical_min": 0,
            "stick_logical_max": XBOX_STICK_LOGICAL_MAX,
            "trigger_logical_min": 0,
            "trigger_logical_max": XBOX_TRIGGER_LOGICAL_MAX,
            "hat_logical_min": 1,
            "hat_logical_max": 8,
            "hat_null": 0,
            "button_count": 15,
            "share_usage": "consumer_record",
            "rumble_output_behavior": "descriptor_exposes_report_id_3; firmware parses as safe no-op only if surfaced by host stack",
            "claim_boundary": "BLE HID profile target, not Xbox console or proprietary Xbox Wireless compatibility"
        })
    });
    let device_name = descriptor
        .as_ref()
        .map(|descriptor| nul_terminated_bytes_to_string(descriptor.identity.device_name));
    let device_name_for_json = device_name.clone();
    let json = serde_json::json!({
        "active_persona": active_persona.map(|persona| persona.0).unwrap_or("none"),
        "active_variant": active_variant.map(BleCompatibilityVariant::id).unwrap_or("none"),
        "profile_family": variant_profile_family(active_variant),
        "intended_host_target": variant_intended_host_target(active_variant),
        "connection_state": format!("{:?}", ble.current_state()),
        "advertising_active": ble.current_state() == usb2ble_contracts::BleLinkState::Advertising,
        "device_name": device_name_for_json,
        "manufacturer": descriptor.as_ref().map(|descriptor| nul_terminated_bytes_to_string(descriptor.identity.manufacturer_name)),
        "vendor_id": descriptor.as_ref().map(|descriptor| descriptor.identity.vendor_id),
        "product_id": descriptor.as_ref().map(|descriptor| descriptor.identity.product_id),
        "appearance": descriptor.as_ref().map(|descriptor| format!("0x{:04x}", descriptor.identity.appearance)),
        "address_type": "public",
        "ble_address": "unavailable",
        "raw_advertisement_bytes_available": false,
        "primary_advertisement": {
            "flags": "0x06",
            "fields": primary_advertisement_fields(active_variant),
            "complete_local_name": active_variant == Some(BleCompatibilityVariant::GenericHogpStrict),
            "uuids": advertised_uuids_for_variant(active_variant),
            "appearance": true,
            "estimated_payload_len": estimated_primary_adv_len(active_variant, device_name.as_deref()),
            "raw_bytes": "unavailable"
        },
        "scan_response": {
            "fields": scan_response_fields(active_variant),
            "complete_local_name": active_variant != Some(BleCompatibilityVariant::GenericHogpStrict),
            "uuids": scan_response_uuids_for_variant(active_variant),
            "estimated_payload_len": estimated_scan_rsp_len(active_variant, device_name.as_deref()),
            "raw_bytes": "unavailable"
        },
        "hids": {
            "service_uuid": "1812",
            "service_present": "intended_by_esp_hidd_dev_init",
            "hid_information": "unknown",
            "report_map": if report_map_len > 0 { "intended" } else { "unknown" },
            "hid_control_point": "unknown",
            "protocol_mode": "unknown",
            "input_reports": if report_map_len > 0 { 1 } else { 0 },
            "report_reference_descriptors": "unknown",
            "cccd_notify": "unknown",
            "output_reports": if active_persona == Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID) { 1 } else { 0 },
            "service_changed": "unknown"
        },
        "device_information_service": "unknown",
        "battery_service": "unknown",
        "services_present_intended": ["hid_service_via_esp_hidd_dev_init"],
        "services_not_verified_by_command": ["device_information_service", "battery_service", "cccd_notify", "service_changed"],
        "report_map_len": report_map_len,
        "report_ids": report_ids,
        "xbox_reference": xbox_reference,
        "security": {
            "mode": "bond",
            "pairing_policy": "just_works",
            "io_capability": "none",
            "encryption_keys": true,
            "identity_keys": true,
            "bond_storage_enabled": true,
            "bonds_present": bonds_present,
            "bond_count": if bonds_present { "present_count_unknown" } else { "0" },
            "last_bonded_host": "unavailable"
        },
        "claim_boundary": "intended target-side profile diagnostics only; not raw over-the-air advertisement capture"
    })
    .to_string();
    ControlResponse::Json(JsonResponse {
        prefix: "BLE_COMPAT_PROFILE_JSON",
        json,
    })
}

fn parse_runtime_config_json(pending: PendingConfigJson) -> Result<RuntimeConfig, ControlError> {
    #[cfg(target_os = "espidf")]
    {
        let handle = std::thread::Builder::new()
            .name("config-json".to_string())
            .stack_size(32 * 1024)
            .spawn(move || parse_runtime_config_json_inner(pending))
            .map_err(|_| ControlError::Generic)?;
        handle.join().map_err(|_| ControlError::Generic)?
    }
    #[cfg(not(target_os = "espidf"))]
    {
        parse_runtime_config_json_inner(pending)
    }
}

fn parse_runtime_config_json_inner(
    pending: PendingConfigJson,
) -> Result<RuntimeConfig, ControlError> {
    if let Some(expected) = &pending.checksum {
        let digest = Sha256::digest(&pending.bytes);
        let actual = digest
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        if expected != &actual {
            return Err(ControlError::ConfigChecksumMismatch);
        }
    }
    let json = String::from_utf8(pending.bytes).map_err(|_| ControlError::InvalidJson)?;
    serde_json::from_str::<RuntimeConfig>(&json).map_err(|_| ControlError::InvalidJson)
}

fn start_ble_persona<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    encoder: &(impl PersonaEncoder + ?Sized),
    persona_id: PersonaId,
    variant_override: Option<BleCompatibilityVariant>,
    action: &'static str,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    match encoder.descriptor(persona_id) {
        Ok(mut descriptor) => {
            if let Some(variant) = variant_override {
                descriptor.compatibility_variant = variant;
            }
            match ble.activate_persona(&descriptor) {
                Ok(()) => {
                    app.set_active_persona(Some(persona_id));
                    app.set_active_ble_variant(Some(descriptor.compatibility_variant));
                    ControlResponse::BleAction(BleActionResponse {
                        action,
                        state: ble.current_state(),
                        report: None,
                    })
                }
                Err(err) => ControlResponse::Error(control_error_from_ble(err)),
            }
        }
        Err(_) => ControlResponse::Error(ControlError::Generic),
    }
}

fn start_ble_generic_variant<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    variant_id: &str,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    let Some(variant) = BleCompatibilityVariant::from_id(variant_id) else {
        return ControlResponse::Error(ControlError::Generic);
    };
    if !matches!(
        variant,
        BleCompatibilityVariant::GenericDefault | BleCompatibilityVariant::GenericHogpStrict
    ) {
        return ControlResponse::Error(ControlError::UnknownPersona);
    }
    start_ble_persona(
        app,
        ble,
        generic_encoder,
        GENERIC_GAMEPAD_PERSONA_ID,
        Some(variant),
        "start_generic_gamepad_variant",
    )
}

fn start_configured<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    xbox_encoder: &impl PersonaEncoder,
    bridge: &mut BridgeRuntime,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    let config = app.runtime_config().clone();
    let persona_id = match persona_id_from_config(&config.selected_persona) {
        Ok(persona_id) => persona_id,
        Err(err) => return ControlResponse::Error(err),
    };

    if config.bridge.auto_start_persona {
        let encoder: &dyn PersonaEncoder = if persona_id == GENERIC_GAMEPAD_PERSONA_ID {
            generic_encoder
        } else if persona_id == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
            xbox_encoder
        } else {
            return ControlResponse::Error(ControlError::UnknownPersona);
        };
        let response = start_ble_persona(app, ble, encoder, persona_id, None, "start_configured");
        if matches!(response, ControlResponse::Error(_)) {
            return response;
        }
    }

    if let Err(err) = bridge.set_rate_hz(config.bridge.rate_hz) {
        return ControlResponse::Error(err);
    }
    if config.bridge.auto_start_bridge
        && let Err(err) = bridge.start(app.state().active_persona)
    {
        return ControlResponse::Error(err);
    }

    ControlResponse::ConfigAction(ConfigActionResponse {
        action: "start_configured",
        state: "ok",
        detail: Some(format!(
            "persona={};bridge={};",
            persona_id.0, config.bridge.auto_start_bridge
        )),
    })
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
    S: usb2ble_contracts::ProfileStore
        + usb2ble_contracts::BondStore
        + usb2ble_contracts::ConfigStore,
{
    if persona_id == GENERIC_GAMEPAD_PERSONA_ID {
        app.generic_gamepad_report()
    } else if persona_id == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
        app.xbox_gamepad_report()
    } else {
        Err(ControlError::PersonaMismatch)
    }
}

fn persona_id_from_config(persona: &str) -> Result<PersonaId, ControlError> {
    match persona {
        "generic" | "generic_gamepad" => Ok(GENERIC_GAMEPAD_PERSONA_ID),
        "xbox" | "xbox_wireless_controller" => Ok(XBOX_WIRELESS_CONTROLLER_PERSONA_ID),
        _ => Err(ControlError::UnknownPersona),
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

fn xbox_test_report(
    encoder: &impl PersonaEncoder,
    scenario: &str,
) -> Result<usb2ble_contracts::EncodedBleReport, usb2ble_contracts::PersonaError> {
    let logical_controls = match scenario {
        "neutral" | "left_trigger_min" | "right_trigger_min" => Vec::new(),
        "left_stick_left" => xbox_axis("left_x", i32::from(i16::MIN)),
        "left_stick_right" => xbox_axis("left_x", i32::from(i16::MAX)),
        "left_stick_up" => xbox_axis("left_y", i32::from(i16::MIN)),
        "left_stick_down" => xbox_axis("left_y", i32::from(i16::MAX)),
        "right_stick_left" => xbox_axis("right_x", i32::from(i16::MIN)),
        "right_stick_right" => xbox_axis("right_x", i32::from(i16::MAX)),
        "right_stick_up" => xbox_axis("right_y", i32::from(i16::MIN)),
        "right_stick_down" => xbox_axis("right_y", i32::from(i16::MAX)),
        "left_trigger_max" => xbox_trigger("left_trigger", 1_023),
        "right_trigger_max" => xbox_trigger("right_trigger", 1_023),
        "hat_up" => xbox_hat(0),
        "hat_right" => xbox_hat(2),
        "hat_down" => xbox_hat(4),
        "hat_left" => xbox_hat(6),
        "button_a" => xbox_button("a"),
        "button_b" => xbox_button("b"),
        "button_x" => xbox_button("x"),
        "button_y" => xbox_button("y"),
        "button_lb" => xbox_button("lb"),
        "button_rb" => xbox_button("rb"),
        "button_view" => xbox_button("view"),
        "button_menu" => xbox_button("menu"),
        "button_nexus" => xbox_button("nexus"),
        "button_left_stick_press" => xbox_button("left_stick_press"),
        "button_right_stick_press" => xbox_button("right_stick_press"),
        "button_paddle_1" => xbox_button("paddle_1"),
        "button_paddle_2" => xbox_button("paddle_2"),
        "button_paddle_3" => xbox_button("paddle_3"),
        "button_share" => xbox_button("share"),
        _ => return Err(usb2ble_contracts::PersonaError::Generic),
    };

    encoder.encode(&PersonaInputFrame {
        persona_id: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
        logical_controls,
    })
}

fn xbox_axis(control_id: &str, value: i32) -> Vec<PersonaLogicalControlValue> {
    vec![PersonaLogicalControlValue {
        control_id: control_id.to_string(),
        value: NormalizedControlValue::Axis(value),
    }]
}

fn xbox_trigger(control_id: &str, value: i32) -> Vec<PersonaLogicalControlValue> {
    vec![PersonaLogicalControlValue {
        control_id: control_id.to_string(),
        value: NormalizedControlValue::Trigger(value),
    }]
}

fn xbox_button(control_id: &str) -> Vec<PersonaLogicalControlValue> {
    vec![PersonaLogicalControlValue {
        control_id: control_id.to_string(),
        value: NormalizedControlValue::Button(true),
    }]
}

fn xbox_hat(value: i8) -> Vec<PersonaLogicalControlValue> {
    vec![PersonaLogicalControlValue {
        control_id: "hat".to_string(),
        value: NormalizedControlValue::Hat(value),
    }]
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
        config_import: ConfigImportRuntime,
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
                config_import: ConfigImportRuntime::default(),
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
                &mut self.config_import,
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
    fn ble_advertising_info_reports_generic_identity() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        match runtime.run(ControlCommand::GetBleAdvertisingInfo) {
            ControlResponse::BleAdvertisingInfo(info) => {
                assert_eq!(info.active_persona, Some(GENERIC_GAMEPAD_PERSONA_ID));
                assert_eq!(info.state, usb2ble_contracts::BleLinkState::Advertising);
                assert_eq!(
                    info.compatibility_variant,
                    Some(BleCompatibilityVariant::GenericDefault)
                );
                assert_eq!(info.device_name.as_deref(), Some("USB2BLE Gamepad"));
                assert_eq!(info.appearance, Some(0x03c4));
                assert_eq!(info.advertised_uuids, vec!["1812".to_string()]);
                assert!(!info.advertisement_includes_name);
                assert!(info.scan_response_includes_name);
                assert_eq!(info.flags, 0x06);
                assert_eq!(info.security, "bond");
                assert_eq!(info.io_capability, "none");
            }
            other => panic!("expected BLE advertising info, got {other:?}"),
        }
    }

    #[test]
    fn generic_hogp_strict_variant_reports_primary_name_layout() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepadVariant(
                "generic_hogp_strict".to_string(),
            )),
            "start_generic_gamepad_variant",
        );
        match runtime.run(ControlCommand::GetBleAdvertisingInfo) {
            ControlResponse::BleAdvertisingInfo(info) => {
                assert_eq!(
                    info.compatibility_variant,
                    Some(BleCompatibilityVariant::GenericHogpStrict)
                );
                assert_eq!(info.active_persona, Some(GENERIC_GAMEPAD_PERSONA_ID));
                assert!(info.advertisement_includes_name);
                assert!(!info.scan_response_includes_name);
                assert!(info.advertised_uuids.is_empty());
                assert_eq!(info.scan_response_uuids, vec!["1812".to_string()]);
                assert!(!info.raw_advertisement_bytes_available);
            }
            other => panic!("expected BLE advertising info, got {other:?}"),
        }
    }

    #[test]
    fn ble_compatibility_profile_commands_return_json() {
        let mut runtime = Runtime::new();

        match runtime.run(ControlCommand::ListBleCompatibilityVariants) {
            ControlResponse::Json(resp) => {
                assert_eq!(resp.prefix, "BLE_COMPAT_VARIANTS_JSON");
                assert!(resp.json.contains("generic_hogp_strict"));
                assert!(resp.json.contains("ios_keyboard_icade_fallback"));
            }
            other => panic!("expected variants JSON, got {other:?}"),
        }

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepadVariant(
                "generic_hogp_strict".to_string(),
            )),
            "start_generic_gamepad_variant",
        );
        match runtime.run(ControlCommand::GetBleCompatProfile) {
            ControlResponse::Json(resp) => {
                assert_eq!(resp.prefix, "BLE_COMPAT_PROFILE_JSON");
                assert!(resp.json.contains("generic_hogp_strict"));
                assert!(resp.json.contains("USB2BLE Gamepad"));
                assert!(resp.json.contains("raw over-the-air advertisement"));
            }
            other => panic!("expected profile JSON, got {other:?}"),
        }

        let mut runtime = Runtime::new();
        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        match runtime.run(ControlCommand::GetBleCompatProfile) {
            ControlResponse::Json(resp) => {
                assert_eq!(resp.prefix, "BLE_COMPAT_PROFILE_JSON");
                assert!(resp.json.contains("xbox_compatibility"));
                assert!(resp.json.contains("0x0b13"));
                assert!(resp.json.contains("\"report_ids\":[1,3]"));
                assert!(resp.json.contains("consumer_record"));
                assert!(resp.json.contains("safe no-op"));
            }
            other => panic!("expected Xbox profile JSON, got {other:?}"),
        }
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
        assert_eq!(&pressed.bytes[0..2], &65_535_u16.to_le_bytes());
        assert_eq!(&released.bytes[0..2], &0_u16.to_le_bytes());
        assert_eq!(&pressed.bytes[13..15], &1_u16.to_le_bytes());
        assert_eq!(&released.bytes[13..15], &0_u16.to_le_bytes());
    }

    #[test]
    fn xbox_test_report_requires_active_xbox_persona() {
        let mut runtime = Runtime::new();

        assert_eq!(
            runtime.run(ControlCommand::PublishXboxTestReport("neutral".to_string())),
            ControlResponse::Error(ControlError::PersonaMismatch)
        );
    }

    #[test]
    fn xbox_test_report_scenarios_publish_deterministic_values() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        let neutral = assert_ble_report(
            runtime.run(ControlCommand::PublishXboxTestReport("neutral".to_string())),
            "publish_xbox_test_report",
        );
        let right = assert_ble_report(
            runtime.run(ControlCommand::PublishXboxTestReport(
                "left_stick_right".to_string(),
            )),
            "publish_xbox_test_report",
        );
        let left_trigger = assert_ble_report(
            runtime.run(ControlCommand::PublishXboxTestReport(
                "left_trigger_max".to_string(),
            )),
            "publish_xbox_test_report",
        );
        let share = assert_ble_report(
            runtime.run(ControlCommand::PublishXboxTestReport(
                "button_share".to_string(),
            )),
            "publish_xbox_test_report",
        );
        let left_stick_press = assert_ble_report(
            runtime.run(ControlCommand::PublishXboxTestReport(
                "button_left_stick_press".to_string(),
            )),
            "publish_xbox_test_report",
        );

        assert_eq!(neutral.report_id.0, 1);
        assert_eq!(neutral.bytes.len(), 16);
        assert_eq!(&neutral.bytes[0..2], &32_768_u16.to_le_bytes());
        assert_eq!(&right.bytes[0..2], &65_535_u16.to_le_bytes());
        assert_eq!(&left_trigger.bytes[8..10], &1_023_u16.to_le_bytes());
        assert_eq!(&left_stick_press.bytes[13..15], &(1_u16 << 8).to_le_bytes());
        assert_eq!(share.bytes[15], 1);
    }

    #[test]
    fn xbox_test_report_rejects_unknown_scenario() {
        let mut runtime = Runtime::new();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleXboxController),
            "start_xbox_controller",
        );
        assert_eq!(
            runtime.run(ControlCommand::PublishXboxTestReport(
                "not_a_scenario".to_string()
            )),
            ControlResponse::Error(ControlError::Generic)
        );
    }

    #[test]
    fn chunked_config_import_commits_valid_json() {
        let mut runtime = Runtime::new();
        let json = serde_json::to_string(&RuntimeConfig::flight_pack_xbox_preset()).unwrap();
        let chunk = URL_SAFE_NO_PAD.encode(json.as_bytes());

        assert_eq!(
            runtime.run(ControlCommand::BeginConfigJson {
                total_chunks: 1,
                checksum: None,
            }),
            ControlResponse::ConfigImport(ConfigImportResponse {
                state: "started",
                total_chunks: 1,
                received_chunks: 0,
                bytes: 0,
            })
        );
        assert_eq!(
            runtime.run(ControlCommand::ConfigJsonChunk {
                index: 0,
                data: chunk,
            }),
            ControlResponse::ConfigImport(ConfigImportResponse {
                state: "chunk",
                total_chunks: 1,
                received_chunks: 1,
                bytes: json.len(),
            })
        );
        assert!(matches!(
            runtime.run(ControlCommand::CommitConfigJson),
            ControlResponse::ConfigImport(ConfigImportResponse {
                state: "committed",
                ..
            })
        ));
        assert_eq!(
            runtime.app.runtime_config().selected_persona,
            "xbox_wireless_controller"
        );
    }

    #[test]
    fn chunked_config_import_rejects_missing_out_of_order_invalid_base64_and_json() {
        let mut runtime = Runtime::new();
        assert_eq!(
            runtime.run(ControlCommand::BeginConfigJson {
                total_chunks: 2,
                checksum: None,
            }),
            ControlResponse::ConfigImport(ConfigImportResponse {
                state: "started",
                total_chunks: 2,
                received_chunks: 0,
                bytes: 0,
            })
        );
        assert_eq!(
            runtime.run(ControlCommand::ConfigJsonChunk {
                index: 1,
                data: "e30".to_string(),
            }),
            ControlResponse::Error(ControlError::ConfigChunkOutOfOrder)
        );
        assert_eq!(
            runtime.run(ControlCommand::ConfigJsonChunk {
                index: 0,
                data: "@@@".to_string(),
            }),
            ControlResponse::Error(ControlError::InvalidBase64)
        );
        assert_eq!(
            runtime.run(ControlCommand::CommitConfigJson),
            ControlResponse::Error(ControlError::ConfigChunkMissing)
        );

        let mut runtime = Runtime::new();
        assert!(matches!(
            runtime.run(ControlCommand::BeginConfigJson {
                total_chunks: 1,
                checksum: None,
            }),
            ControlResponse::ConfigImport(_)
        ));
        assert!(matches!(
            runtime.run(ControlCommand::ConfigJsonChunk {
                index: 0,
                data: URL_SAFE_NO_PAD.encode(b"{not-json"),
            }),
            ControlResponse::ConfigImport(_)
        ));
        assert_eq!(
            runtime.run(ControlCommand::CommitConfigJson),
            ControlResponse::Error(ControlError::InvalidJson)
        );
    }

    #[test]
    fn start_configured_starts_selected_xbox_persona_and_bridge() {
        let mut runtime = Runtime::with_button_input();
        let mut config = RuntimeConfig::flight_pack_xbox_preset();
        config.bridge.auto_start_bridge = true;
        config.bridge.rate_hz = 25;
        runtime.app.set_runtime_config(config).unwrap();

        match runtime.run(ControlCommand::StartConfigured) {
            ControlResponse::ConfigAction(action) => {
                assert_eq!(action.action, "start_configured");
                assert_eq!(action.state, "ok");
            }
            other => panic!("expected config action, got {other:?}"),
        }

        assert_eq!(
            runtime.app.state().active_persona,
            Some(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
        );
        let status = runtime.bridge.status(runtime.app.state().active_persona);
        assert!(status.enabled);
        assert_eq!(status.rate_hz, 25);
    }

    #[test]
    fn bridge_uses_configured_mapping() {
        let mut runtime = Runtime::with_button_input();
        let config = RuntimeConfig {
            selected_profile: "custom_runtime".to_string(),
            mappings: vec![usb2ble_contracts::SourceMappingRule {
                source_vendor_id: Some(0x1234),
                source_product_id: Some(0x5678),
                source_interface_id: Some(0),
                source_control_id: "button_1".to_string(),
                target_control_id: "button_2".to_string(),
                invert: false,
                deadzone: None,
                transform: None,
            }],
            ..RuntimeConfig::default()
        };
        runtime.app.set_runtime_config(config).unwrap();

        assert_ble_action(
            runtime.run(ControlCommand::StartBleGenericGamepad),
            "start_generic_gamepad",
        );
        assert_bridge_status(runtime.run(ControlCommand::StartBridge));
        assert_eq!(runtime.poll_bridge(0), BridgePollOutcome::FirstPublish);

        let report = runtime.ble.published_reports().last().unwrap();
        assert_eq!(report.bytes[0], 0b0000_0010);
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
