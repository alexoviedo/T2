//! usb2ble-platform-esp32
//!
//! Responsible for:
//! - ESP-IDF bindings,
//! - UART/NVS adapters.

use std::cell::RefCell;
use std::io::{self, Read, Write};
use usb2ble_contracts::UsbIngress;

/// Result of a UART read operation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UartReadResult {
    /// A complete newline-delimited frame was read.
    Frame(usize),
    /// No complete frame is available yet.
    Pending,
    /// The end of the input stream was reached.
    Eof,
    /// A read error occurred.
    Error,
}

/// A minimal UART abstraction for M1.
pub struct Uart {
    buffer: RefCell<Vec<u8>>,
}

impl Uart {
    /// Initialize the UART.
    #[must_use]
    pub fn new() -> Self {
        Self {
            buffer: RefCell::new(Vec::new()),
        }
    }

    /// Read a line from UART.
    ///
    /// Buffers input from the underlying stream (stdin on host/espidf)
    /// and returns a complete newline-delimited frame when available.
    pub fn read_line(&self, buf: &mut [u8]) -> UartReadResult {
        let mut internal_buf = self.buffer.borrow_mut();

        // Check if we already have a newline in the buffer
        if let Some(pos) = internal_buf.iter().position(|&b| b == b'\n') {
            let line_len = pos + 1;
            let copy_len = line_len.min(buf.len());
            buf[..copy_len].copy_from_slice(&internal_buf[..copy_len]);
            internal_buf.drain(..line_len);
            return UartReadResult::Frame(copy_len);
        }

        // Not enough data, try to read from the underlying stream
        // On host tests, stdin might return 0 (EOF) immediately.
        let mut chunk = [0u8; 128];
        match io::stdin().read(&mut chunk) {
            Ok(0) => {
                // If we are in a test and we manually pushed data,
                // we should return Pending if there's no newline.
                if internal_buf.is_empty() {
                    UartReadResult::Eof
                } else {
                    UartReadResult::Pending
                }
            }
            Ok(n) => {
                internal_buf.extend_from_slice(&chunk[..n]);
                // Check again after reading
                if let Some(pos) = internal_buf.iter().position(|&b| b == b'\n') {
                    let line_len = pos + 1;
                    let copy_len = line_len.min(buf.len());
                    buf[..copy_len].copy_from_slice(&internal_buf[..copy_len]);
                    internal_buf.drain(..line_len);
                    return UartReadResult::Frame(copy_len);
                }
                UartReadResult::Pending
            }
            Err(_) => UartReadResult::Error,
        }
    }

    /// Write bytes to UART.
    pub fn write_all(&self, data: &[u8]) {
        let mut stdout = io::stdout();
        let _ = stdout.write_all(data);
        let _ = stdout.flush();
    }

    /// Flush UART.
    pub fn flush(&self) {
        let _ = io::stdout().flush();
    }

    /// Push data into the internal buffer.
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
        // Required for ESP-IDF linkage
        esp_idf_svc::sys::link_patches();
    }
}

/// A minimal USB ingress implementation for M2.
#[derive(Default)]
pub struct EspUsbIngress {
    events: RefCell<Vec<usb2ble_contracts::UsbIngressEvent>>,
}

impl EspUsbIngress {
    /// Create a new `EspUsbIngress` instance.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Initialize the USB host stack.
    pub fn init_host(&self) {
        #[cfg(target_os = "espidf")]
        {
            // SAFETY: ESP-IDF USB Host initialization involves FFI calls.
            // This is a representative structural implementation for M2.
            unsafe {
                // 1. Install USB Host driver
                // esp_idf_sys::usb_host_install(...);

                // 2. Create a background task to handle USB events
                // This task would call esp_host_lib_handle_events() in a loop

                // 3. Register HID class driver
                // hid_host_install(...);

                // 4. Set up callbacks that push to self.events
                // Device attach -> UsbIngressEvent::DeviceAttached
                // HID Descriptor -> UsbIngressEvent::ReportDescriptorReceived
                // HID Report -> UsbIngressEvent::InputReportReceived
            }
        }
    }

    /// Push a synthetic event (useful for testing or platform-sim).
    pub fn push_event(&self, event: usb2ble_contracts::UsbIngressEvent) {
        self.events.borrow_mut().push(event);
    }
}

impl UsbIngress for EspUsbIngress {
    fn poll_event(&mut self) -> Option<usb2ble_contracts::UsbIngressEvent> {
        let mut events = self.events.borrow_mut();
        if events.is_empty() {
            None
        } else {
            Some(events.remove(0))
        }
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

        let res = uart.read_line(&mut buf);
        assert_eq!(res, UartReadResult::Frame(6));
        assert_eq!(&buf[..6], b"HELLO\n");

        let res = uart.read_line(&mut buf);
        assert_eq!(res, UartReadResult::Frame(6));
        assert_eq!(&buf[..6], b"WORLD\n");
    }

    #[test]
    fn test_uart_framing_partial() {
        let uart = Uart::new();
        let mut buf = [0u8; 64];

        uart.push_to_buffer(b"PART");
        let res = uart.read_line(&mut buf);
        assert_eq!(res, UartReadResult::Pending);
    }

    #[test]
    fn test_uart_framing_multi_command_chunk() {
        let uart = Uart::new();
        let mut buf = [0u8; 64];

        uart.push_to_buffer(b"CMD1\nCMD2\nCMD3");

        let res = uart.read_line(&mut buf);
        assert_eq!(res, UartReadResult::Frame(5));
        assert_eq!(&buf[..5], b"CMD1\n");

        let res = uart.read_line(&mut buf);
        assert_eq!(res, UartReadResult::Frame(5));
        assert_eq!(&buf[..5], b"CMD2\n");
    }
}
