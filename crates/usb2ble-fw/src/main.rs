//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use usb2ble_app::App;
use usb2ble_contracts::{
    BleActionResponse, BleTransport, CONTRACT_VERSION, ControlCommand, ControlError, ControlPlane,
    ControlResponse, DescriptorKey, NormalizedControlValue, PersonaEncoder, PersonaInputFrame,
    PersonaLogicalControlValue, UsbIngress,
};
use usb2ble_control::SerialControlPlane;
use usb2ble_personas::{GENERIC_GAMEPAD_PERSONA_ID, GenericGamepadEncoder};
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
    let encoder = GenericGamepadEncoder;
    let mut report_log_micros: Vec<(DescriptorKey, u64)> = Vec::new();
    let mut ble_self_test_pressed = false;

    // 4. Print startup banner
    platform::trace_printf(b"--- USB2BLE FIRMWARE BOOT ---\n\0");
    uart.write_all(format!("Name: {}\n", FIRMWARE_NAME).as_bytes());
    uart.write_all(format!("Version: {}\n", FIRMWARE_VERSION).as_bytes());
    uart.write_all(format!("Contract Version: {}\n", CONTRACT_VERSION).as_bytes());
    uart.write_all(b"Status: BLE HID Demo Path (Generic Gamepad Persona)\n");
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
                            &encoder,
                            &cmd,
                            &mut ble_self_test_pressed,
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
    encoder: &impl PersonaEncoder,
    cmd: &ControlCommand,
    ble_self_test_pressed: &mut bool,
) -> ControlResponse
where
    S: usb2ble_contracts::ProfileStore + usb2ble_contracts::BondStore,
{
    app.set_ble_state(ble.current_state());

    let resp = match cmd {
        ControlCommand::StartBleGenericGamepad => {
            match encoder.descriptor(GENERIC_GAMEPAD_PERSONA_ID) {
                Ok(descriptor) => match ble.activate_persona(&descriptor) {
                    Ok(()) => {
                        app.set_active_persona(Some(GENERIC_GAMEPAD_PERSONA_ID));
                        ControlResponse::BleAction(BleActionResponse {
                            action: "start_generic_gamepad",
                            state: ble.current_state(),
                            report: None,
                        })
                    }
                    Err(_) => ControlResponse::Error(ControlError::Generic),
                },
                Err(_) => ControlResponse::Error(ControlError::Generic),
            }
        }
        ControlCommand::PublishGenericGamepadReport => match app.generic_gamepad_report() {
            Ok(report) => match ble.publish_report(&report) {
                Ok(()) => ControlResponse::BleAction(BleActionResponse {
                    action: "publish_generic_gamepad",
                    state: ble.current_state(),
                    report: Some(report),
                }),
                Err(_) => ControlResponse::Error(ControlError::Generic),
            },
            Err(err) => ControlResponse::Error(err),
        },
        ControlCommand::SendBleSelfTestReport => {
            match self_test_report(encoder, ble_self_test_pressed) {
                Ok(report) => match ble.publish_report(&report) {
                    Ok(()) => ControlResponse::BleAction(BleActionResponse {
                        action: "send_self_test",
                        state: ble.current_state(),
                        report: Some(report),
                    }),
                    Err(_) => ControlResponse::Error(ControlError::Generic),
                },
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

fn self_test_report(
    encoder: &impl PersonaEncoder,
    ble_self_test_pressed: &mut bool,
) -> Result<usb2ble_contracts::EncodedBleReport, usb2ble_contracts::PersonaError> {
    *ble_self_test_pressed = !*ble_self_test_pressed;
    let axis = if *ble_self_test_pressed {
        i32::from(i16::MAX)
    } else {
        i32::from(i16::MIN)
    };

    encoder.encode(&PersonaInputFrame {
        persona_id: GENERIC_GAMEPAD_PERSONA_ID,
        logical_controls: vec![
            PersonaLogicalControlValue {
                control_id: "button_1".to_string(),
                value: NormalizedControlValue::Button(*ble_self_test_pressed),
            },
            PersonaLogicalControlValue {
                control_id: "hat".to_string(),
                value: NormalizedControlValue::Hat(if *ble_self_test_pressed { 0 } else { 8 }),
            },
            PersonaLogicalControlValue {
                control_id: "x".to_string(),
                value: NormalizedControlValue::Axis(axis),
            },
        ],
    })
}
