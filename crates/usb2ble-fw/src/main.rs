//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use usb2ble_app::App;
use usb2ble_contracts::{
    BleActionResponse, BleTransport, BleTransportError, CONTRACT_VERSION, ControlCommand,
    ControlError, ControlPlane, ControlResponse, DescriptorKey, EncodedBleReport,
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
    let mut generic_self_test_pressed = false;
    let mut xbox_self_test_pressed = false;

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
        while let Some(event) = usb.poll_event() {
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
                            &mut generic_self_test_pressed,
                            &mut xbox_self_test_pressed,
                        );
                        if let Ok(resp_bytes) = control.encode_response(&resp) {
                            uart.write_all(&resp_bytes);
                        }
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

fn handle_control_command<S>(
    app: &mut App<S>,
    ble: &mut impl BleTransport,
    generic_encoder: &impl PersonaEncoder,
    xbox_encoder: &impl PersonaEncoder,
    cmd: &ControlCommand,
    generic_self_test_pressed: &mut bool,
    xbox_self_test_pressed: &mut bool,
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
            match generic_self_test_report(generic_encoder, generic_self_test_pressed) {
                Ok(report) => publish_ble_report(ble, report, "send_self_test"),
                Err(_) => ControlResponse::Error(ControlError::Generic),
            }
        }
        ControlCommand::SendXboxSelfTestReport => {
            match xbox_self_test_report(xbox_encoder, xbox_self_test_pressed) {
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
        ConnectionTopology, DeviceId, InputReportPacket, InterfaceId, ReportDescriptorBlob,
        ReportId, UsbDeviceRef, UsbIngressEvent, UsbInterfaceRef,
    };
    use usb2ble_storage::InMemoryStore;

    struct Runtime {
        app: App<InMemoryStore>,
        ble: BleHidTransport,
        generic_encoder: GenericGamepadEncoder,
        xbox_encoder: XboxWirelessControllerEncoder,
        generic_self_test_pressed: bool,
        xbox_self_test_pressed: bool,
    }

    impl Runtime {
        fn new() -> Self {
            Self {
                app: App::new(InMemoryStore::new()),
                ble: BleHidTransport::new(),
                generic_encoder: GenericGamepadEncoder,
                xbox_encoder: XboxWirelessControllerEncoder,
                generic_self_test_pressed: false,
                xbox_self_test_pressed: false,
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
                &mut self.generic_self_test_pressed,
                &mut self.xbox_self_test_pressed,
            )
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
