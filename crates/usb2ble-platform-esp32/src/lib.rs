//! usb2ble-platform-esp32
//!
//! Responsible for:
//! - ESP-IDF bindings,
//! - UART/NVS adapters.

pub mod ble_hid;
pub mod usb_host;

use std::cell::RefCell;
use std::collections::VecDeque;
use std::io;
#[cfg(not(target_os = "espidf"))]
use std::io::{Read, Write};
use std::sync::{Arc, Mutex};
use usb2ble_contracts::{UsbIngress, UsbIngressEvent};

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
        let mut chunk = [0u8; 128];
        let read_res = {
            #[cfg(target_os = "espidf")]
            unsafe {
                let n = esp_idf_sys::read(0, chunk.as_mut_ptr() as *mut _, chunk.len());
                if n < 0 {
                    Err(io::Error::last_os_error())
                } else {
                    Ok(n as usize)
                }
            }
            #[cfg(not(target_os = "espidf"))]
            io::stdin().read(&mut chunk)
        };

        match read_res {
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
        #[cfg(target_os = "espidf")]
        {
            unsafe {
                for &b in data {
                    esp_idf_sys::putchar(b as i32);
                }
            }
        }
        #[cfg(not(target_os = "espidf"))]
        {
            let mut stdout = io::stdout();
            let _ = stdout.write_all(data);
            let _ = stdout.flush();
        }
    }

    /// Flush UART.
    pub fn flush(&self) {
        #[cfg(not(target_os = "espidf"))]
        {
            let _ = io::stdout().flush();
        }
        // fsync or equivalent is usually not needed for ESP-IDF UART tx buffering,
        // it flushes automatically or blocks until written.
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
        esp_idf_sys::link_patches();

        // Ensure stdin is non-blocking so the main event loop does not halt on read
        unsafe {
            let flags = esp_idf_sys::fcntl(0, esp_idf_sys::F_GETFL as i32, 0);
            if flags >= 0 {
                esp_idf_sys::fcntl(
                    0,
                    esp_idf_sys::F_SETFL as i32,
                    flags | (esp_idf_sys::O_NONBLOCK as i32),
                );
            }
        }
    }
}

/// Emit an early target trace message.
///
/// `message` must be nul-terminated for ESP-IDF `printf`.
pub fn trace_printf(message: &'static [u8]) {
    #[cfg(target_os = "espidf")]
    unsafe {
        esp_idf_sys::printf(message.as_ptr() as *const _);
    }
    #[cfg(not(target_os = "espidf"))]
    {
        let _ = message;
    }
}

/// A minimal USB ingress implementation for M2 groundwork.
pub struct EspUsbIngress {
    rx: Arc<Mutex<VecDeque<UsbIngressEvent>>>,
    #[allow(dead_code)]
    host: usb_host::EspUsbHost,
}

impl EspUsbIngress {
    /// Create a new `EspUsbIngress` instance.
    #[must_use]
    pub fn new() -> Self {
        let queue = Arc::new(Mutex::new(VecDeque::new()));
        let host = usb_host::EspUsbHost::new(queue.clone());
        Self { rx: queue, host }
    }

    /// Initialize the USB host stack (Groundwork).
    #[cfg(target_os = "espidf")]
    pub fn init_host(&self) -> Result<(), &'static str> {
        self.host.init()
    }

    /// Trigger witness events for simulation on host.
    #[cfg(not(target_os = "espidf"))]
    pub fn simulate_events_for_test(&mut self) {
        self.host.simulate_events_for_test();
    }

    /// Service platform USB host event pumps.
    #[cfg(target_os = "espidf")]
    pub fn service_host(&self) -> Result<(), &'static str> {
        self.host.poll_target_events()
    }

    /// Host no-op to keep call-site uniform.
    #[cfg(not(target_os = "espidf"))]
    pub fn service_host(&self) {
        self.host.tick_host_noop();
    }
}

impl UsbIngress for EspUsbIngress {
    fn poll_event(&mut self) -> Option<UsbIngressEvent> {
        self.rx.lock().ok().and_then(|mut q| q.pop_front())
    }
}

impl Default for EspUsbIngress {
    fn default() -> Self {
        Self::new()
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
