//! usb2ble-platform-esp32
//!
//! Responsible for:
//! - ESP-IDF bindings (stubs for M1),
//! - UART/NVS adapters.

use std::io::{self, Read, Write};

/// A minimal UART abstraction for M1.
pub struct Uart {
}

impl Uart {
    /// Initialize the UART.
    #[must_use]
    pub fn new() -> Self {
        Self {}
    }

    /// Read a line from UART (simulated via stdin for M1 host testability).
    pub fn read_line(&self, buf: &mut [u8]) -> usize {
        let mut stdin = io::stdin();
        match stdin.read(buf) {
            Ok(n) => n,
            Err(_) => 0,
        }
    }

    /// Write bytes to UART (simulated via stdout for M1 host testability).
    pub fn write_all(&self, data: &[u8]) {
        let mut stdout = io::stdout();
        let _ = stdout.write_all(data);
        let _ = stdout.flush();
    }

    /// Flush UART.
    pub fn flush(&self) {
        let _ = io::stdout().flush();
    }
}

impl Default for Uart {
    fn default() -> Self {
        Self::new()
    }
}

/// Initialize the platform.
pub fn init() {
    // Stub for ESP-IDF system init
}
