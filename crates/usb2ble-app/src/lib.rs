//! usb2ble-app
//!
//! Responsible for orchestration and application state.

use usb2ble_contracts::{
    AppState, BleLinkState, BondStore, CONTRACT_VERSION, ControlCommand, ControlError,
    ControlResponse, DescriptorKey, InfoResponse, ProfileResponse, ProfileStore, StatusResponse,
    UsbDescriptorResponse, UsbIngressEvent, UsbReportResponse, UsbStatusResponse,
};

/// The main application structure.
pub struct App<S> {
    state: AppState,
    storage: S,
}

impl<S> App<S>
where
    S: ProfileStore + BondStore,
{
    /// Create a new application instance.
    pub fn new(storage: S) -> Self {
        let active_profile = storage.load_active_profile().ok().flatten();

        Self {
            state: AppState {
                physical_devices: Vec::new(),
                hid_interfaces: Vec::new(),
                descriptors: Vec::new(),
                raw_descriptors: Vec::new(),
                last_reports: Vec::new(),
                active_profile,
                active_persona: None,
                ble_state: BleLinkState::Idle,
            },
            storage,
        }
    }

    /// Process a control plane command.
    pub fn handle_control_command(&mut self, cmd: &ControlCommand) -> ControlResponse {
        match cmd {
            ControlCommand::GetInfo => ControlResponse::Info(InfoResponse {
                contract_version: CONTRACT_VERSION,
                firmware_name: "usb2ble",
                active_persona: self.state.active_persona,
            }),
            ControlCommand::GetStatus => {
                let bonds_present = self.storage.bonds_present().unwrap_or(false);
                ControlResponse::Status(StatusResponse {
                    ble_state: self.state.ble_state,
                    active_profile: self.state.active_profile,
                    bonds_present,
                })
            }
            ControlCommand::GetProfile => ControlResponse::Profile(ProfileResponse {
                active_profile: self.state.active_profile,
            }),
            ControlCommand::GetUsbStatus => ControlResponse::UsbStatus(UsbStatusResponse {
                physical_devices: self.state.physical_devices.len(),
                total_interfaces: self.state.hid_interfaces.len(),
            }),
            ControlCommand::ListUsbDevices => {
                ControlResponse::UsbDevices(self.state.physical_devices.clone())
            }
            ControlCommand::GetUsbDescriptor(key) => {
                if let Some((_, bytes)) = self.state.raw_descriptors.iter().find(|(k, _)| k == key)
                {
                    ControlResponse::UsbDescriptor(UsbDescriptorResponse {
                        bytes: bytes.clone(),
                    })
                } else {
                    ControlResponse::Error(ControlError::NotFound)
                }
            }
            ControlCommand::GetLastUsbReport(key) => {
                if let Some((_, bytes)) = self.state.last_reports.iter().find(|(k, _)| k == key) {
                    ControlResponse::UsbReport(UsbReportResponse {
                        bytes: bytes.clone(),
                    })
                } else {
                    ControlResponse::Error(ControlError::NotFound)
                }
            }
        }
    }

    /// Handle a USB ingress event.
    pub fn handle_usb_event(&mut self, event: UsbIngressEvent) {
        match event {
            UsbIngressEvent::DeviceAttached(dev) if !self.state.physical_devices.contains(&dev) => {
                self.state.physical_devices.push(dev);
            }
            UsbIngressEvent::DeviceDetached { source } => {
                self.state
                    .physical_devices
                    .retain(|d| d.device_id != source.device_id);
                self.state
                    .hid_interfaces
                    .retain(|i| i.device.device_id != source.device_id);
                self.state
                    .raw_descriptors
                    .retain(|(k, _)| k.device_id != source.device_id);
                self.state
                    .last_reports
                    .retain(|(k, _)| k.device_id != source.device_id);
                self.state
                    .descriptors
                    .retain(|(k, _)| k.device_id != source.device_id);
            }
            UsbIngressEvent::InterfaceDiscovered { source, .. }
                if !self.state.hid_interfaces.contains(&source) =>
            {
                self.state.hid_interfaces.push(source);
            }
            UsbIngressEvent::ReportDescriptorReceived(blob) => {
                let key = DescriptorKey {
                    device_id: blob.source.device.device_id,
                    interface_id: Some(blob.source.interface_id),
                };
                if let Some(entry) = self
                    .state
                    .raw_descriptors
                    .iter_mut()
                    .find(|(k, _)| k == &key)
                {
                    entry.1 = blob.bytes;
                } else {
                    self.state.raw_descriptors.push((key, blob.bytes));
                }
            }
            UsbIngressEvent::InputReportReceived(packet) => {
                let key = DescriptorKey {
                    device_id: packet.source.device.device_id,
                    interface_id: Some(packet.source.interface_id),
                };
                if let Some(entry) = self.state.last_reports.iter_mut().find(|(k, _)| k == &key) {
                    entry.1 = packet.payload;
                } else {
                    self.state.last_reports.push((key, packet.payload));
                }
            }
            _ => {}
        }
    }

    /// Set the BLE state (e.g. from platform glue).
    pub const fn set_ble_state(&mut self, state: BleLinkState) {
        self.state.ble_state = state;
    }

    /// Get current app state (read-only).
    #[must_use]
    pub const fn state(&self) -> &AppState {
        &self.state
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::ProfileId;
    use usb2ble_storage::InMemoryStore;

    #[test]
    fn test_handle_get_info() {
        let storage = InMemoryStore::new();
        let mut app = App::new(storage);
        let resp = app.handle_control_command(&ControlCommand::GetInfo);

        if let ControlResponse::Info(info) = resp {
            assert_eq!(info.contract_version, CONTRACT_VERSION);
            assert_eq!(info.firmware_name, "usb2ble");
        } else {
            panic!("Expected Info response");
        }
    }

    #[test]
    fn test_handle_get_status() {
        let mut storage = InMemoryStore::new();
        let profile = ProfileId("test-profile");
        storage.save_active_profile(profile).unwrap();

        let mut app = App::new(storage);
        app.set_ble_state(BleLinkState::Connected);

        let resp = app.handle_control_command(&ControlCommand::GetStatus);

        if let ControlResponse::Status(status) = resp {
            assert_eq!(status.ble_state, BleLinkState::Connected);
            assert_eq!(status.active_profile, Some(profile));
            assert!(!status.bonds_present);
        } else {
            panic!("Expected Status response");
        }
    }

    #[test]
    fn test_handle_usb_events_and_commands() {
        use usb2ble_contracts::{
            ConnectionTopology, DeviceId, InputReportPacket, InterfaceId, ReportDescriptorBlob,
            UsbDeviceRef, UsbInterfaceRef,
        };

        let storage = InMemoryStore::new();
        let mut app = App::new(storage);

        let dev = UsbDeviceRef {
            device_id: DeviceId(1),
            topology: ConnectionTopology::Direct,
            vendor_id: 0x1234,
            product_id: 0x5678,
        };
        let iface = UsbInterfaceRef {
            device: dev.clone(),
            interface_id: InterfaceId(0),
        };

        // 1. Attach
        app.handle_usb_event(UsbIngressEvent::DeviceAttached(dev.clone()));
        assert_eq!(app.state().physical_devices.len(), 1);

        // 2. Discover interface
        app.handle_usb_event(UsbIngressEvent::InterfaceDiscovered {
            source: iface.clone(),
            class_code: 3,
            subclass_code: 0,
            protocol_code: 0,
        });
        assert_eq!(app.state().hid_interfaces.len(), 1);

        // 3. Descriptor
        app.handle_usb_event(UsbIngressEvent::ReportDescriptorReceived(
            ReportDescriptorBlob {
                source: iface.clone(),
                bytes: vec![0x01, 0x02, 0x03],
            },
        ));

        // 4. Report
        app.handle_usb_event(UsbIngressEvent::InputReportReceived(InputReportPacket {
            source: iface.clone(),
            report_id: usb2ble_contracts::ReportId(0),
            payload: vec![0xAA, 0xBB],
            timestamp_micros: 100,
        }));

        // 5. Verify via control commands
        let resp = app.handle_control_command(&ControlCommand::GetUsbStatus);
        if let ControlResponse::UsbStatus(s) = resp {
            assert_eq!(s.physical_devices, 1);
            assert_eq!(s.total_interfaces, 1);
        } else {
            panic!("Expected UsbStatus");
        }

        let key = DescriptorKey {
            device_id: DeviceId(1),
            interface_id: Some(InterfaceId(0)),
        };

        let resp = app.handle_control_command(&ControlCommand::GetUsbDescriptor(key));
        if let ControlResponse::UsbDescriptor(d) = resp {
            assert_eq!(d.bytes, vec![0x01, 0x02, 0x03]);
        } else {
            panic!("Expected UsbDescriptor");
        }

        let resp = app.handle_control_command(&ControlCommand::GetLastUsbReport(key));
        if let ControlResponse::UsbReport(r) = resp {
            assert_eq!(r.bytes, vec![0xAA, 0xBB]);
        } else {
            panic!("Expected UsbReport");
        }

        // Test missing key
        let missing_key = DescriptorKey {
            device_id: DeviceId(2),
            interface_id: Some(InterfaceId(0)),
        };
        let resp = app.handle_control_command(&ControlCommand::GetUsbDescriptor(missing_key));
        if let ControlResponse::Error(ControlError::NotFound) = resp {
        } else {
            panic!("Expected NotFound error");
        }

        // 6. Detach
        app.handle_usb_event(UsbIngressEvent::DeviceDetached { source: dev });
        assert_eq!(app.state().physical_devices.len(), 0);
        assert_eq!(app.state().hid_interfaces.len(), 0);
        assert_eq!(app.state().raw_descriptors.len(), 0);
        assert_eq!(app.state().last_reports.len(), 0);
    }

    #[test]
    fn test_usb_status_and_list_follow_attach_detach() {
        use usb2ble_contracts::{ConnectionTopology, DeviceId, UsbDeviceRef};

        let storage = InMemoryStore::new();
        let mut app = App::new(storage);

        let before = app.handle_control_command(&ControlCommand::GetUsbStatus);
        if let ControlResponse::UsbStatus(status) = before {
            assert_eq!(status.physical_devices, 0);
            assert_eq!(status.total_interfaces, 0);
        } else {
            panic!("Expected UsbStatus response");
        }

        let dev = UsbDeviceRef {
            device_id: DeviceId(42),
            topology: ConnectionTopology::Direct,
            vendor_id: 0x046d,
            product_id: 0xc534,
        };
        app.handle_usb_event(UsbIngressEvent::DeviceAttached(dev.clone()));

        let listed = app.handle_control_command(&ControlCommand::ListUsbDevices);
        if let ControlResponse::UsbDevices(devices) = listed {
            assert_eq!(devices.len(), 1);
            assert_eq!(devices[0].vendor_id, 0x046d);
            assert_eq!(devices[0].product_id, 0xc534);
        } else {
            panic!("Expected UsbDevices response");
        }

        app.handle_usb_event(UsbIngressEvent::DeviceDetached { source: dev });

        let after = app.handle_control_command(&ControlCommand::GetUsbStatus);
        if let ControlResponse::UsbStatus(status) = after {
            assert_eq!(status.physical_devices, 0);
        } else {
            panic!("Expected UsbStatus response");
        }
    }
}
