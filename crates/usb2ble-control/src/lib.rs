//! usb2ble-control
//!
//! Responsible for:
//! - serial control-plane protocol,
//! - command/response framing,
//! - schema validation.

use std::fmt::Write;
use usb2ble_contracts::{ControlCommand, ControlError, ControlPlane, ControlResponse};

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

        match s {
            "GET_INFO" => Ok(ControlCommand::GetInfo),
            "GET_STATUS" => Ok(ControlCommand::GetStatus),
            "GET_PROFILE" => Ok(ControlCommand::GetProfile),
            _ => Err(ControlError::Generic),
        }
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
            ControlResponse::Error(err) => {
                let _ = write!(out, "ERROR:{err:?}");
            }
        }

        out.push('\n');
        Ok(out.into_bytes())
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
}
