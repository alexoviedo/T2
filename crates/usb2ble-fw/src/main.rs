//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use usb2ble_app::App;
use usb2ble_contracts::{
    CONTRACT_VERSION, ControlPlane, ControlResponse, DescriptorKey, UsbIngress,
};
use usb2ble_control::SerialControlPlane;
use usb2ble_platform_esp32::{self as platform, EspUsbIngress, Uart, UartReadResult};
use usb2ble_storage::InMemoryStore;

/// Firmware name.
pub const FIRMWARE_NAME: &str = "usb2ble";
/// Firmware version.
pub const FIRMWARE_VERSION: &str = "0.4.0-m4";

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
    let mut report_log_micros: Vec<(DescriptorKey, u64)> = Vec::new();

    // 4. Print startup banner
    platform::trace_printf(b"--- USB2BLE FIRMWARE BOOT ---\n\0");
    uart.write_all(format!("Name: {}\n", FIRMWARE_NAME).as_bytes());
    uart.write_all(format!("Version: {}\n", FIRMWARE_VERSION).as_bytes());
    uart.write_all(format!("Contract Version: {}\n", CONTRACT_VERSION).as_bytes());
    uart.write_all(b"Status: M4 Code-path (Normalized Input Witness)\n");
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
                        let resp = app.handle_control_command(&cmd);
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
