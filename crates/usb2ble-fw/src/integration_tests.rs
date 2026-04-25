//! integration_tests
//!
//! Milestone 1 integration tests.

#[cfg(test)]
mod tests {
    use usb2ble_app::App;
    use usb2ble_contracts::{CONTRACT_VERSION, ControlCommand, ControlPlane, ControlResponse};
    use usb2ble_control::SerialControlPlane;
    use usb2ble_platform_esp32::{Uart, UartReadResult};
    use usb2ble_storage::InMemoryStore;

    #[test]
    fn test_sequential_commands() {
        let storage = InMemoryStore::new();
        let mut app = App::new(storage);
        let control = SerialControlPlane::new();

        // Simulate GET_INFO
        let cmd = ControlCommand::GetInfo;
        let resp = app.handle_control_command(&cmd);
        if let ControlResponse::Info(info) = &resp {
            assert_eq!(info.contract_version, CONTRACT_VERSION);
        } else {
            panic!("Expected Info response");
        }

        // Simulate GET_STATUS
        let cmd = ControlCommand::GetStatus;
        let resp = app.handle_control_command(&cmd);
        if let ControlResponse::Status(status) = &resp {
            assert_eq!(status.active_profile, None);
        } else {
            panic!("Expected Status response");
        }

        // Round-trip through control plane bytes
        let bytes = control.encode_response(&resp).unwrap();
        assert!(bytes.starts_with(b"STATUS:"));
        assert!(bytes.ends_with(b"\n"));
    }

    #[test]
    fn test_fragmented_input() {
        let uart = Uart::new();
        let mut buf = [0u8; 128];

        // First fragment
        uart.push_to_buffer(b"GET_");
        assert_eq!(uart.read_line(&mut buf), UartReadResult::Pending);

        // Second fragment completes the command
        uart.push_to_buffer(b"INFO\n");
        if let UartReadResult::Frame(n) = uart.read_line(&mut buf) {
            assert_eq!(&buf[..n], b"GET_INFO\n");
        } else {
            panic!("Expected Frame result");
        }
    }
}
