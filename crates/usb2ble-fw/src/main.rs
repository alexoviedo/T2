//! usb2ble-fw
//!
//! Thin firmware entrypoint.

#[cfg(test)]
mod integration_tests;

use usb2ble_app::App;
use usb2ble_contracts::ControlPlane;
use usb2ble_control::SerialControlPlane;
use usb2ble_platform_esp32::{self as platform, Uart};
use usb2ble_storage::InMemoryStore;

/// Main firmware entrypoint.
pub fn main() {
    // 1. Initialize platform
    platform::init();
    let uart = Uart::new();

    // 2. Initialize storage (In-memory for M1)
    let storage = InMemoryStore::new();

    // 3. Initialize app
    let mut app = App::new(storage);
    let control = SerialControlPlane::new();

    // 4. Print startup banner
    uart.write_all(b"--- USB2BLE FIRMWARE BOOT ---\n");
    uart.write_all(b"Status: M1 Real\n");
    uart.write_all(b"Ready for commands.\n");

    // 5. Main loop
    let mut buf = [0u8; 128];
    loop {
        let n = uart.read_line(&mut buf);
        if n > 0 {
            if let Ok(cmd) = control.decode_command(&buf[..n]) {
                let resp = app.handle_control_command(&cmd);
                if let Ok(resp_bytes) = control.encode_response(&resp) {
                    uart.write_all(&resp_bytes);
                }
            }
        } else {
            // On host, n=0 usually means EOF (stdin closed).
            #[cfg(not(target_os = "espidf"))]
            break;
        }

        // In a real ESP-IDF environment, we might yield or sleep here.
    }
}
