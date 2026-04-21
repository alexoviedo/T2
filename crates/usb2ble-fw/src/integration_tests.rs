//! integration_tests
//!
//! Milestone 1 integration tests.

#[cfg(test)]
mod tests {
    use usb2ble_app::App;
    use usb2ble_contracts::{CONTRACT_VERSION, ControlCommand, ControlPlane, ControlResponse};
    use usb2ble_control::SerialControlPlane;
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
}
