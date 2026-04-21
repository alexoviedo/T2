//! usb2ble-platform-esp32
//!
//! Responsible for:
//! - ESP-IDF bindings (stubs for M1),
//! - UART/NVS adapters.

use std::cell::RefCell;
use std::io::{self, Read, Write};

/// A minimal UART abstraction for M1.
pub struct Uart {
    #[cfg(not(target_os = "espidf"))]
    buffer: RefCell<Vec<u8>>,
}

impl Uart {
    /// Initialize the UART.
    #[must_use]
    pub fn new() -> Self {
        Self {
            #[cfg(not(target_os = "espidf"))]
            buffer: RefCell::new(Vec::new()),
        }
    }

    /// Read a line from UART.
    ///
    /// In host mode, this buffers input from stdin and returns a complete
    /// newline-delimited frame when available.
    pub fn read_line(&self, buf: &mut [u8]) -> usize {
        #[cfg(not(target_os = "espidf"))]
        {
            let mut internal_buf = self.buffer.borrow_mut();

            // Check if we already have a newline in the buffer
            if let Some(pos) = internal_buf.iter().position(|&b| b == b'\n') {
                let line_len = pos + 1;
                let copy_len = line_len.min(buf.len());
                buf[..copy_len].copy_from_slice(&internal_buf[..copy_len]);
                internal_buf.drain(..line_len);
                return copy_len;
            }

            // Not enough data, try to read from stdin
            // In a test environment, stdin might be closed or empty.
            let mut chunk = [0u8; 128];
            match io::stdin().read(&mut chunk) {
                Ok(0) => 0, // EOF
                Ok(n) => {
                    internal_buf.extend_from_slice(&chunk[..n]);
                    // Check again after reading
                    if let Some(pos) = internal_buf.iter().position(|&b| b == b'\n') {
                        let line_len = pos + 1;
                        let copy_len = line_len.min(buf.len());
                        buf[..copy_len].copy_from_slice(&internal_buf[..copy_len]);
                        internal_buf.drain(..line_len);
                        return copy_len;
                    }
                    0
                }
                Err(_) => 0,
            }
        }
        #[cfg(target_os = "espidf")]
        {
            // Stub for real ESP32-S3 UART read.
            0
        }
    }

    /// Write bytes to UART (simulated via stdout for M1 host testability).
    pub fn write_all(&self, data: &[u8]) {
        #[cfg(not(target_os = "espidf"))]
        {
            let mut stdout = io::stdout();
            let _ = stdout.write_all(data);
            let _ = stdout.flush();
        }
        #[cfg(target_os = "espidf")]
        {
            // Stub for real ESP32-S3 UART write.
        }
    }

    /// Flush UART.
    pub fn flush(&self) {
        #[cfg(not(target_os = "espidf"))]
        {
            let _ = io::stdout().flush();
        }
    }

    /// Push data into the internal buffer (for testing only).
    #[cfg(all(test, not(target_os = "espidf")))]
    pub fn push_to_buffer(&self, data: &[u8]) {
        self.buffer.borrow_mut().extend_from_slice(data);
    }
}

impl Default for Uart {
    fn default() -> Self {
        Self::new()
    }
}

/// Initialize the platform.
pub fn init() {
    #[cfg(target_os = "espidf")]
    {
        // Real ESP-IDF initialization logic would go here.
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_uart_framing_draining() {
        let uart = Uart::new();
        let mut buf = [0u8; 64];

        uart.push_to_buffer(b"HELLO\nWORLD\n");

        let n = uart.read_line(&mut buf);
        assert_eq!(n, 6);
        assert_eq!(&buf[..n], b"HELLO\n");

        let n = uart.read_line(&mut buf);
        assert_eq!(n, 6);
        assert_eq!(&buf[..n], b"WORLD\n");
    }

    #[test]
    fn test_uart_framing_partial() {
        let uart = Uart::new();
        let mut buf = [0u8; 64];

        uart.push_to_buffer(b"PART");
        let n = uart.read_line(&mut buf);
        // Should return 0 because there's no newline (and it can't read from stdin in test)
        assert_eq!(n, 0);

        uart.push_to_buffer(b"IAL\n");
        let n = uart.read_line(&mut buf);
        assert_eq!(n, 8);
        assert_eq!(&buf[..n], b"PARTIAL\n");
    }

    #[test]
    fn test_uart_framing_multi_command_chunk() {
        let uart = Uart::new();
        let mut buf = [0u8; 64];

        uart.push_to_buffer(b"CMD1\nCMD2\nCMD3");

        let n = uart.read_line(&mut buf);
        assert_eq!(n, 5);
        assert_eq!(&buf[..n], b"CMD1\n");

        let n = uart.read_line(&mut buf);
        assert_eq!(n, 5);
        assert_eq!(&buf[..n], b"CMD2\n");

        let n = uart.read_line(&mut buf);
        assert_eq!(n, 0); // CMD3 is partial
    }
}
