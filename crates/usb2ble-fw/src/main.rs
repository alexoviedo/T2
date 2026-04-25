//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use usb2ble_app::App;
use usb2ble_contracts::{CONTRACT_VERSION, ControlPlane, ControlResponse, UsbIngress};
use usb2ble_control::SerialControlPlane;
use usb2ble_platform_esp32::{self as platform, EspUsbIngress, Uart, UartReadResult};
use usb2ble_storage::InMemoryStore;

/// Firmware name.
pub const FIRMWARE_NAME: &str = "usb2ble";
/// Firmware version.
pub const FIRMWARE_VERSION: &str = "0.2.1-m2b1";

/// Main firmware entrypoint.
pub fn main() {
    // 1. Initialize platform
    platform::init();
    let uart = Uart::new();
    let mut usb = EspUsbIngress::new();

    // Start USB host stack witness path on target
    #[cfg(target_os = "espidf")]
    {
        if let Err(err) = usb.init_host() {
            uart.write_all(format!("ERROR: USB host init failed: {err}\n").as_bytes());
        }
    }

    // Trigger witness events for host simulation/test
    #[cfg(not(target_os = "espidf"))]
    usb.simulate_events_for_test();

    // 2. Initialize storage (In-memory for M1/M2)
    let storage = InMemoryStore::new();

    // 3. Initialize app
    let mut app = App::new(storage);
    let control = SerialControlPlane::new();

    // 4. Print startup banner
    uart.write_all(b"--- USB2BLE FIRMWARE BOOT ---\n");
    uart.write_all(format!("Name: {}\n", FIRMWARE_NAME).as_bytes());
    uart.write_all(format!("Version: {}\n", FIRMWARE_VERSION).as_bytes());
    uart.write_all(format!("Contract Version: {}\n", CONTRACT_VERSION).as_bytes());
    uart.write_all(b"Status: M2B.1 Code-path (HW Verification Pending)\n");
    uart.write_all(b"Ready for commands.\n");

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
            }
            UartReadResult::Eof => {
                // On host, stdin closed.
                #[cfg(not(target_os = "espidf"))]
                break;
            }
            UartReadResult::Error => {
                uart.write_all(b"ERROR: UART Read Error\n");
            }
        }
    }
}
