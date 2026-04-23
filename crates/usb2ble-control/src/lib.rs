//! usb2ble-control
//!
//! Responsible for:
//! - serial control-plane protocol,
//! - command/response framing,
//! - schema validation.

use std::fmt::Write;
use usb2ble_contracts::{
    ControlCommand, ControlError, ControlPlane, ControlResponse, DescriptorKey, DeviceId,
    InterfaceId,
};

/// Implementation of the newline-framed serial control plane.
#[derive(Default)]
pub struct SerialControlPlane;

impl SerialControlPlane {
    /// Create a new `SerialControlPlane` instance.
    #[must_use]
    pub const fn new() -> Self {
        Self
    }
}

impl ControlPlane for SerialControlPlane {
    fn decode_command(&self, bytes: &[u8]) -> Result<ControlCommand, ControlError> {
        let s = std::str::from_utf8(bytes).map_err(|_| ControlError::Generic)?;
        let s = s.trim();

        if s == "GET_INFO" {
            return Ok(ControlCommand::GetInfo);
        }
        if s == "GET_STATUS" {
            return Ok(ControlCommand::GetStatus);
        }
        if s == "GET_PROFILE" {
            return Ok(ControlCommand::GetProfile);
        }
        if s == "GET_USB_STATUS" {
            return Ok(ControlCommand::GetUsbStatus);
        }
        if s == "LIST_USB_DEVICES" {
            return Ok(ControlCommand::ListUsbDevices);
        }

        if let Some(rest) = s.strip_prefix("GET_USB_DESCRIPTOR ") {
            let key = parse_descriptor_key(rest.trim()).ok_or(ControlError::Generic)?;
            return Ok(ControlCommand::GetUsbDescriptor(key));
        }

        if let Some(rest) = s.strip_prefix("GET_LAST_USB_REPORT ") {
            let key = parse_descriptor_key(rest.trim()).ok_or(ControlError::Generic)?;
            return Ok(ControlCommand::GetLastUsbReport(key));
        }

        Err(ControlError::Generic)
    }

    fn encode_response(&self, response: &ControlResponse) -> Result<Vec<u8>, ControlError> {
        let mut out = String::new();

        match response {
            ControlResponse::Info(info) => {
                out.push_str("INFO:");
                let _ = write!(out, "version={};", info.contract_version);
                let _ = write!(out, "name={};", info.firmware_name);
                if let Some(persona) = info.active_persona {
                    let _ = write!(out, "persona={};", persona.0);
                } else {
                    out.push_str("persona=none;");
                }
            }
            ControlResponse::Status(status) => {
                out.push_str("STATUS:");
                let _ = write!(out, "ble={:?};", status.ble_state);
                if let Some(profile) = status.active_profile {
                    let _ = write!(out, "profile={};", profile.0);
                } else {
                    out.push_str("profile=none;");
                }
                let _ = write!(out, "bonds={};", status.bonds_present);
            }
            ControlResponse::Profile(profile) => {
                out.push_str("PROFILE:");
                if let Some(p) = profile.active_profile {
                    out.push_str(p.0);
                } else {
                    out.push_str("none");
                }
            }
            ControlResponse::UsbStatus(status) => {
                out.push_str("USB_STATUS:");
                let _ = write!(
                    out,
                    "devices={};interfaces={};",
                    status.physical_devices, status.total_interfaces
                );
            }
            ControlResponse::UsbDevices(devices) => {
                out.push_str("USB_DEVICES:");
                for (i, dev) in devices.iter().enumerate() {
                    let _ = write!(
                        out,
                        "id={},vid={:04x},pid={:04x}",
                        dev.device_id.0, dev.vendor_id, dev.product_id
                    );
                    if i < devices.len() - 1 {
                        out.push('|');
                    }
                }
            }
            ControlResponse::UsbDescriptor(resp) => {
                out.push_str("USB_DESCRIPTOR:");
                out.push_str(&hex::encode(&resp.bytes));
            }
            ControlResponse::UsbReport(resp) => {
                out.push_str("USB_REPORT:");
                out.push_str(&hex::encode(&resp.bytes));
            }
            ControlResponse::Error(err) => {
                let _ = write!(out, "ERROR:{err:?}");
            }
        }

        out.push('\n');
        Ok(out.into_bytes())
    }
}

fn parse_descriptor_key(s: &str) -> Option<DescriptorKey> {
    if let Some((dev_str, iface_str)) = s.split_once(':') {
        let device_id = dev_str.parse::<u32>().ok()?;
        let interface_id = iface_str.parse::<u32>().ok()?;
        Some(DescriptorKey {
            device_id: DeviceId(device_id),
            interface_id: Some(InterfaceId(interface_id)),
        })
    } else {
        let device_id = s.parse::<u32>().ok()?;
        Some(DescriptorKey {
            device_id: DeviceId(device_id),
            interface_id: None,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::{BleLinkState, InfoResponse, PersonaId, ProfileId, StatusResponse};

    #[test]
    fn test_decode() {
        let cp = SerialControlPlane::new();
        assert_eq!(
            cp.decode_command(b"GET_INFO\n").unwrap(),
            ControlCommand::GetInfo
        );
        assert_eq!(
            cp.decode_command(b"GET_STATUS").unwrap(),
            ControlCommand::GetStatus
        );
        assert_eq!(
            cp.decode_command(b"  GET_PROFILE  ").unwrap(),
            ControlCommand::GetProfile
        );
        assert!(cp.decode_command(b"UNKNOWN").is_err());
    }

    #[test]
    fn test_encode_info() {
        let cp = SerialControlPlane::new();
        let resp = ControlResponse::Info(InfoResponse {
            contract_version: 1,
            firmware_name: "test-fw",
            active_persona: Some(PersonaId("test-persona")),
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "INFO:version=1;name=test-fw;persona=test-persona;\n"
        );
    }

    #[test]
    fn test_encode_status() {
        let cp = SerialControlPlane::new();
        let resp = ControlResponse::Status(StatusResponse {
            ble_state: BleLinkState::Advertising,
            active_profile: Some(ProfileId("test-profile")),
            bonds_present: true,
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "STATUS:ble=Advertising;profile=test-profile;bonds=true;\n"
        );
    }

    #[test]
    fn test_decode_m2_commands() {
        let cp = SerialControlPlane::new();

        assert_eq!(
            cp.decode_command(b"GET_USB_STATUS").unwrap(),
            ControlCommand::GetUsbStatus
        );
        assert_eq!(
            cp.decode_command(b"LIST_USB_DEVICES").unwrap(),
            ControlCommand::ListUsbDevices
        );
        assert_eq!(
            cp.decode_command(b"GET_USB_DESCRIPTOR 1").unwrap(),
            ControlCommand::GetUsbDescriptor(DescriptorKey {
                device_id: DeviceId(1),
                interface_id: None
            })
        );
        assert_eq!(
            cp.decode_command(b"GET_USB_DESCRIPTOR 1:0").unwrap(),
            ControlCommand::GetUsbDescriptor(DescriptorKey {
                device_id: DeviceId(1),
                interface_id: Some(InterfaceId(0))
            })
        );
        assert_eq!(
            cp.decode_command(b"GET_LAST_USB_REPORT 2:1").unwrap(),
            ControlCommand::GetLastUsbReport(DescriptorKey {
                device_id: DeviceId(2),
                interface_id: Some(InterfaceId(1))
            })
        );
    }

    #[test]
    fn test_encode_m2_responses() {
        use usb2ble_contracts::{
            ConnectionTopology, UsbDescriptorResponse, UsbDeviceRef, UsbReportResponse,
            UsbStatusResponse,
        };

        let cp = SerialControlPlane::new();

        // UsbStatus
        let resp = ControlResponse::UsbStatus(UsbStatusResponse {
            physical_devices: 2,
            total_interfaces: 3,
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "USB_STATUS:devices=2;interfaces=3;\n"
        );

        // UsbDevices
        let dev1 = UsbDeviceRef {
            device_id: DeviceId(1),
            topology: ConnectionTopology::Direct,
            vendor_id: 0x1234,
            product_id: 0x5678,
        };
        let resp = ControlResponse::UsbDevices(vec![dev1]);
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "USB_DEVICES:id=1,vid=1234,pid=5678\n"
        );

        // UsbDescriptor
        let resp = ControlResponse::UsbDescriptor(UsbDescriptorResponse {
            bytes: vec![0xDE, 0xAD, 0xBE, 0xEF],
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "USB_DESCRIPTOR:deadbeef\n"
        );

        // UsbReport
        let resp = ControlResponse::UsbReport(UsbReportResponse {
            bytes: vec![0x01, 0x02],
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(std::str::from_utf8(&bytes).unwrap(), "USB_REPORT:0102\n");
    }
}
