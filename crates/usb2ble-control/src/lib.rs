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
    #[allow(clippy::too_many_lines)]
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
        if s == "GET_GENERIC_GAMEPAD_REPORT" {
            return Ok(ControlCommand::GetGenericGamepadReport);
        }
        if s == "GET_GENERIC_GAMEPAD_MAPPING" {
            return Ok(ControlCommand::GetGenericGamepadMapping);
        }
        if s == "GET_XBOX_GAMEPAD_REPORT" {
            return Ok(ControlCommand::GetXboxGamepadReport);
        }
        if s == "GET_XBOX_GAMEPAD_MAPPING" {
            return Ok(ControlCommand::GetXboxGamepadMapping);
        }
        if s == "START_BLE_GENERIC_GAMEPAD" {
            return Ok(ControlCommand::StartBleGenericGamepad);
        }
        if s == "PUBLISH_GENERIC_GAMEPAD_REPORT" {
            return Ok(ControlCommand::PublishGenericGamepadReport);
        }
        if s == "SEND_BLE_SELF_TEST_REPORT" {
            return Ok(ControlCommand::SendBleSelfTestReport);
        }
        if s == "START_BLE_XBOX_CONTROLLER" {
            return Ok(ControlCommand::StartBleXboxController);
        }
        if s == "PUBLISH_XBOX_GAMEPAD_REPORT" {
            return Ok(ControlCommand::PublishXboxGamepadReport);
        }
        if s == "SEND_XBOX_SELF_TEST_REPORT" {
            return Ok(ControlCommand::SendXboxSelfTestReport);
        }
        if s == "FORGET_BLE_BONDS" {
            return Ok(ControlCommand::ForgetBleBonds);
        }
        if s == "START_BRIDGE" {
            return Ok(ControlCommand::StartBridge);
        }
        if s == "STOP_BRIDGE" {
            return Ok(ControlCommand::StopBridge);
        }
        if s == "GET_BRIDGE_STATUS" {
            return Ok(ControlCommand::GetBridgeStatus);
        }
        if s == "GET_CONFIG_STATUS" {
            return Ok(ControlCommand::GetConfigStatus);
        }
        if s == "GET_CONFIG_SCHEMA" {
            return Ok(ControlCommand::GetConfigSchema);
        }
        if let Some(rest) = s.strip_prefix("GET_PERSONA_SCHEMA ") {
            return Ok(ControlCommand::GetPersonaSchema(rest.trim().to_string()));
        }
        if s == "GET_INPUT_CATALOG" {
            return Ok(ControlCommand::GetInputCatalog);
        }
        if s == "GET_CONFIG_JSON" {
            return Ok(ControlCommand::GetConfigJson);
        }
        if let Some(rest) = s.strip_prefix("BEGIN_CONFIG_JSON ") {
            let mut parts = rest.split_whitespace();
            let total_chunks = parts
                .next()
                .ok_or(ControlError::Generic)?
                .parse::<usize>()
                .map_err(|_| ControlError::Generic)?;
            let checksum = parts
                .next()
                .filter(|value| *value != "none")
                .map(str::to_string);
            return Ok(ControlCommand::BeginConfigJson {
                total_chunks,
                checksum,
            });
        }
        if let Some(rest) = s.strip_prefix("CONFIG_JSON_CHUNK ") {
            let mut parts = rest.split_whitespace();
            let index = parts
                .next()
                .ok_or(ControlError::Generic)?
                .parse::<usize>()
                .map_err(|_| ControlError::Generic)?;
            let data = parts.next().ok_or(ControlError::Generic)?.to_string();
            return Ok(ControlCommand::ConfigJsonChunk { index, data });
        }
        if s == "COMMIT_CONFIG_JSON" {
            return Ok(ControlCommand::CommitConfigJson);
        }
        if s == "RESET_CONFIG" {
            return Ok(ControlCommand::ResetConfig);
        }
        if s == "SAVE_CONFIG" {
            return Ok(ControlCommand::SaveConfig);
        }
        if s == "LOAD_CONFIG" {
            return Ok(ControlCommand::LoadConfig);
        }
        if s == "START_CONFIGURED" {
            return Ok(ControlCommand::StartConfigured);
        }
        if let Some(rest) = s.strip_prefix("SET_BRIDGE_RATE_HZ ") {
            let rate_hz = rest
                .trim()
                .parse::<u16>()
                .map_err(|_| ControlError::InvalidBridgeRate)?;
            return Ok(ControlCommand::SetBridgeRateHz(rate_hz));
        }

        if let Some(rest) = s.strip_prefix("GET_USB_DESCRIPTOR ") {
            let key = parse_descriptor_key(rest.trim()).ok_or(ControlError::Generic)?;
            return Ok(ControlCommand::GetUsbDescriptor(key));
        }

        if let Some(rest) = s.strip_prefix("GET_LAST_USB_REPORT ") {
            let key = parse_descriptor_key(rest.trim()).ok_or(ControlError::Generic)?;
            return Ok(ControlCommand::GetLastUsbReport(key));
        }

        if let Some(rest) = s.strip_prefix("GET_HID_SUMMARY ") {
            let key = parse_descriptor_key(rest.trim()).ok_or(ControlError::Generic)?;
            return Ok(ControlCommand::GetHidSummary(key));
        }

        if let Some(rest) = s.strip_prefix("GET_NORMALIZED_INPUT ") {
            let key = parse_descriptor_key(rest.trim()).ok_or(ControlError::Generic)?;
            return Ok(ControlCommand::GetNormalizedInput(key));
        }

        Err(ControlError::Generic)
    }

    #[allow(clippy::too_many_lines)]
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
                if let Some(persona) = status.active_persona {
                    let _ = write!(out, "persona={};", persona.0);
                } else {
                    out.push_str("persona=none;");
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
            ControlResponse::HidSummary(resp) => {
                encode_hid_summary(&mut out, resp);
            }
            ControlResponse::NormalizedInput(resp) => {
                encode_normalized_input(&mut out, resp);
            }
            ControlResponse::EncodedReport(resp) => {
                out.push_str("ENCODED_REPORT:");
                let _ = write!(out, "persona={};", resp.report.persona_id.0);
                let _ = write!(out, "report_id={};", resp.report.report_id.0);
                out.push_str("bytes=");
                out.push_str(&hex::encode(&resp.report.bytes));
                out.push(';');
            }
            ControlResponse::MappingDiagnostics(resp) => {
                encode_mapping_diagnostics(&mut out, resp);
            }
            ControlResponse::BleAction(resp) => {
                out.push_str("BLE_ACTION:");
                let _ = write!(out, "action={};", resp.action);
                let _ = write!(out, "state={:?};", resp.state);
                if let Some(report) = &resp.report {
                    let _ = write!(out, "persona={};", report.persona_id.0);
                    let _ = write!(out, "report_id={};", report.report_id.0);
                    out.push_str("bytes=");
                    out.push_str(&hex::encode(&report.bytes));
                    out.push(';');
                }
            }
            ControlResponse::BridgeStatus(resp) => encode_bridge_status(&mut out, resp),
            ControlResponse::ConfigStatus(resp) => encode_config_status(&mut out, resp),
            ControlResponse::Json(resp) => {
                out.push_str(resp.prefix);
                out.push(':');
                out.push_str(&resp.json);
            }
            ControlResponse::ConfigImport(resp) => {
                out.push_str("CONFIG_IMPORT:");
                let _ = write!(out, "state={};", resp.state);
                let _ = write!(out, "total_chunks={};", resp.total_chunks);
                let _ = write!(out, "received_chunks={};", resp.received_chunks);
                let _ = write!(out, "bytes={};", resp.bytes);
            }
            ControlResponse::ConfigAction(resp) => {
                out.push_str("CONFIG_ACTION:");
                let _ = write!(out, "action={};state={};", resp.action, resp.state);
                if let Some(detail) = &resp.detail {
                    let _ = write!(out, "detail={detail};");
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

fn encode_config_status(out: &mut String, resp: &usb2ble_contracts::ConfigStatusResponse) {
    out.push_str("CONFIG_STATUS:");
    let _ = write!(out, "valid={};", resp.valid);
    let _ = write!(out, "source={};", resp.source);
    let _ = write!(out, "persona={};", resp.selected_persona);
    let _ = write!(out, "profile={};", resp.selected_profile);
    let _ = write!(out, "mappings={};", resp.mappings);
    let _ = write!(out, "import_active={};", resp.import_active);
    if let Some(last_error) = resp.last_error {
        let _ = write!(out, "last_error={last_error};");
    } else {
        out.push_str("last_error=none;");
    }
}

fn encode_bridge_status(out: &mut String, resp: &usb2ble_contracts::BridgeStatusResponse) {
    out.push_str("BRIDGE_STATUS:");
    let _ = write!(out, "enabled={};", resp.enabled);
    if let Some(persona) = resp.active_persona {
        let _ = write!(out, "persona={};", persona.0);
    } else {
        out.push_str("persona=none;");
    }
    let _ = write!(out, "rate_hz={};", resp.rate_hz);
    if let Some(last_publish_ms) = resp.last_publish_ms {
        let _ = write!(out, "last_publish_ms={last_publish_ms};");
    } else {
        out.push_str("last_publish_ms=none;");
    }
    let _ = write!(out, "published={};", resp.published);
    let _ = write!(out, "skipped_duplicate={};", resp.skipped_duplicate);
    let _ = write!(out, "skipped_rate={};", resp.skipped_rate);
    let _ = write!(out, "skipped_not_connected={};", resp.skipped_not_connected);
    let _ = write!(out, "skipped_not_ready={};", resp.skipped_not_ready);
    if let Some(last_error) = resp.last_error {
        let _ = write!(out, "last_error={last_error};");
    } else {
        out.push_str("last_error=none;");
    }
}

fn encode_mapping_diagnostics(
    out: &mut String,
    resp: &usb2ble_contracts::MappingDiagnosticsResponse,
) {
    if resp.target_persona.0 == "xbox_wireless_controller" {
        out.push_str("XBOX_GAMEPAD_MAPPING:");
    } else {
        out.push_str("GENERIC_GAMEPAD_MAPPING:");
    }
    let _ = write!(out, "profile={};", resp.profile_id.0);
    let _ = write!(out, "persona={};", resp.target_persona.0);
    let _ = write!(out, "entries={};", resp.entries.len());
    out.push_str("mappings=");
    for (i, entry) in resp.entries.iter().enumerate() {
        if i > 0 {
            out.push('|');
        }
        let _ = write!(
            out,
            "src={}:{}:{:04x}:{:04x}:{}",
            entry.source.device.device_id.0,
            entry.source.interface_id.0,
            entry.source.device.vendor_id,
            entry.source.device.product_id,
            entry.source_control_id
        );
        out.push_str(",target=");
        if let Some(target) = &entry.target_control_id {
            out.push_str(target);
        } else {
            out.push_str("none");
        }
        out.push_str(",value=");
        write_normalized_value(out, entry.source_value);
        let _ = write!(out, ",reason={}", entry.reason);
    }
    out.push(';');
}

fn encode_hid_summary(out: &mut String, resp: &usb2ble_contracts::HidSummaryResponse) {
    out.push_str("HID_SUMMARY:");
    let summary = &resp.summary;
    let _ = write!(
        out,
        "axes={};buttons={};hats={};report_ids=",
        summary.axes.len(),
        summary.buttons.len(),
        summary.hats.len()
    );
    for (i, report_id) in summary.report_ids.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        let _ = write!(out, "{}", report_id.0);
    }
    out.push(';');

    out.push_str("axis_usages=");
    for (i, axis) in summary.axes.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        let _ = write!(out, "{:02x}:{:x}", axis.usage_page, axis.usage);
    }
    out.push(';');

    out.push_str("button_usages=");
    for (i, button) in summary.buttons.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        let _ = write!(out, "{}", button.usage);
    }
    out.push(';');

    out.push_str("hat_usages=");
    for (i, hat) in summary.hats.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        let _ = write!(out, "{:02x}:{:x}", hat.usage_page, hat.usage);
    }
    out.push(';');
}

fn encode_normalized_input(out: &mut String, resp: &usb2ble_contracts::NormalizedInputResponse) {
    out.push_str("NORMALIZED_INPUT:");
    let _ = write!(out, "controls={};", resp.frame.controls.len());
    for control in &resp.frame.controls {
        let _ = write!(out, "{}=", control.control_id);
        write_normalized_value(out, control.value);
        out.push(';');
    }
}

fn write_normalized_value(out: &mut String, value: usb2ble_contracts::NormalizedControlValue) {
    match value {
        usb2ble_contracts::NormalizedControlValue::Axis(value) => {
            let _ = write!(out, "axis:{value}");
        }
        usb2ble_contracts::NormalizedControlValue::Button(value) => {
            let _ = write!(out, "button:{}", u8::from(value));
        }
        usb2ble_contracts::NormalizedControlValue::Hat(value) => {
            let _ = write!(out, "hat:{value}");
        }
        usb2ble_contracts::NormalizedControlValue::Trigger(value) => {
            let _ = write!(out, "trigger:{value}");
        }
        usb2ble_contracts::NormalizedControlValue::Unknown(value) => {
            let _ = write!(out, "unknown:{value}");
        }
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
    use usb2ble_contracts::{
        BleLinkState, BridgeStatusResponse, InfoResponse, PersonaId, ProfileId, StatusResponse,
    };

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
            active_persona: Some(PersonaId("generic_gamepad")),
            bonds_present: true,
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "STATUS:ble=Advertising;profile=test-profile;persona=generic_gamepad;bonds=true;\n"
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
        assert_eq!(
            cp.decode_command(b"GET_HID_SUMMARY 2:1").unwrap(),
            ControlCommand::GetHidSummary(DescriptorKey {
                device_id: DeviceId(2),
                interface_id: Some(InterfaceId(1))
            })
        );
        assert_eq!(
            cp.decode_command(b"GET_NORMALIZED_INPUT 2:1").unwrap(),
            ControlCommand::GetNormalizedInput(DescriptorKey {
                device_id: DeviceId(2),
                interface_id: Some(InterfaceId(1))
            })
        );
        assert_eq!(
            cp.decode_command(b"GET_GENERIC_GAMEPAD_REPORT").unwrap(),
            ControlCommand::GetGenericGamepadReport
        );
        assert_eq!(
            cp.decode_command(b"GET_GENERIC_GAMEPAD_MAPPING").unwrap(),
            ControlCommand::GetGenericGamepadMapping
        );
        assert_eq!(
            cp.decode_command(b"GET_XBOX_GAMEPAD_REPORT").unwrap(),
            ControlCommand::GetXboxGamepadReport
        );
        assert_eq!(
            cp.decode_command(b"GET_XBOX_GAMEPAD_MAPPING").unwrap(),
            ControlCommand::GetXboxGamepadMapping
        );
        assert_eq!(
            cp.decode_command(b"START_BLE_GENERIC_GAMEPAD").unwrap(),
            ControlCommand::StartBleGenericGamepad
        );
        assert_eq!(
            cp.decode_command(b"PUBLISH_GENERIC_GAMEPAD_REPORT")
                .unwrap(),
            ControlCommand::PublishGenericGamepadReport
        );
        assert_eq!(
            cp.decode_command(b"SEND_BLE_SELF_TEST_REPORT").unwrap(),
            ControlCommand::SendBleSelfTestReport
        );
        assert_eq!(
            cp.decode_command(b"START_BLE_XBOX_CONTROLLER").unwrap(),
            ControlCommand::StartBleXboxController
        );
        assert_eq!(
            cp.decode_command(b"PUBLISH_XBOX_GAMEPAD_REPORT").unwrap(),
            ControlCommand::PublishXboxGamepadReport
        );
        assert_eq!(
            cp.decode_command(b"SEND_XBOX_SELF_TEST_REPORT").unwrap(),
            ControlCommand::SendXboxSelfTestReport
        );
        assert_eq!(
            cp.decode_command(b"FORGET_BLE_BONDS").unwrap(),
            ControlCommand::ForgetBleBonds
        );
    }

    #[test]
    fn test_decode_bridge_commands() {
        let cp = SerialControlPlane::new();

        assert_eq!(
            cp.decode_command(b"START_BRIDGE").unwrap(),
            ControlCommand::StartBridge
        );
        assert_eq!(
            cp.decode_command(b"STOP_BRIDGE").unwrap(),
            ControlCommand::StopBridge
        );
        assert_eq!(
            cp.decode_command(b"GET_BRIDGE_STATUS").unwrap(),
            ControlCommand::GetBridgeStatus
        );
        assert_eq!(
            cp.decode_command(b"SET_BRIDGE_RATE_HZ 25").unwrap(),
            ControlCommand::SetBridgeRateHz(25)
        );
        assert_eq!(
            cp.decode_command(b"SET_BRIDGE_RATE_HZ nope").unwrap_err(),
            ControlError::InvalidBridgeRate
        );
    }

    #[test]
    fn test_decode_config_commands() {
        let cp = SerialControlPlane::new();

        assert_eq!(
            cp.decode_command(b"GET_CONFIG_STATUS").unwrap(),
            ControlCommand::GetConfigStatus
        );
        assert_eq!(
            cp.decode_command(b"GET_CONFIG_SCHEMA").unwrap(),
            ControlCommand::GetConfigSchema
        );
        assert_eq!(
            cp.decode_command(b"GET_PERSONA_SCHEMA xbox").unwrap(),
            ControlCommand::GetPersonaSchema("xbox".to_string())
        );
        assert_eq!(
            cp.decode_command(b"GET_INPUT_CATALOG").unwrap(),
            ControlCommand::GetInputCatalog
        );
        assert_eq!(
            cp.decode_command(b"GET_CONFIG_JSON").unwrap(),
            ControlCommand::GetConfigJson
        );
        assert_eq!(
            cp.decode_command(b"BEGIN_CONFIG_JSON 2 none").unwrap(),
            ControlCommand::BeginConfigJson {
                total_chunks: 2,
                checksum: None,
            }
        );
        assert_eq!(
            cp.decode_command(b"CONFIG_JSON_CHUNK 1 e30").unwrap(),
            ControlCommand::ConfigJsonChunk {
                index: 1,
                data: "e30".to_string(),
            }
        );
        assert_eq!(
            cp.decode_command(b"COMMIT_CONFIG_JSON").unwrap(),
            ControlCommand::CommitConfigJson
        );
        assert_eq!(
            cp.decode_command(b"RESET_CONFIG").unwrap(),
            ControlCommand::ResetConfig
        );
        assert_eq!(
            cp.decode_command(b"SAVE_CONFIG").unwrap(),
            ControlCommand::SaveConfig
        );
        assert_eq!(
            cp.decode_command(b"LOAD_CONFIG").unwrap(),
            ControlCommand::LoadConfig
        );
        assert_eq!(
            cp.decode_command(b"START_CONFIGURED").unwrap(),
            ControlCommand::StartConfigured
        );
    }

    #[test]
    #[allow(clippy::too_many_lines)]
    fn test_encode_m2_responses() {
        use usb2ble_contracts::{
            ConnectionTopology, EncodedBleReport, EncodedReportResponse, HidAxisCapability,
            HidCapabilitySummary, HidSummaryResponse, NormalizedControlEvent,
            NormalizedControlValue, NormalizedInputFrame, NormalizedInputResponse, PersonaId,
            ReportId, UsbDescriptorResponse, UsbDeviceRef, UsbInterfaceRef, UsbReportResponse,
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

        // HidSummary
        let resp = ControlResponse::HidSummary(HidSummaryResponse {
            summary: HidCapabilitySummary {
                axes: vec![HidAxisCapability {
                    report_id: ReportId(0),
                    usage_page: 0x01,
                    usage: 0x30,
                    bit_offset: 24,
                    bit_size: 14,
                    logical_min: 0,
                    logical_max: 16_383,
                }],
                buttons: Vec::new(),
                hats: Vec::new(),
                report_ids: vec![ReportId(0)],
            },
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "HID_SUMMARY:axes=1;buttons=0;hats=0;report_ids=0;axis_usages=01:30;button_usages=;hat_usages=;\n"
        );

        // NormalizedInput
        let source = UsbInterfaceRef {
            device: UsbDeviceRef {
                device_id: DeviceId(1),
                topology: ConnectionTopology::Direct,
                vendor_id: 0x1234,
                product_id: 0x5678,
            },
            interface_id: InterfaceId(0),
        };
        let resp = ControlResponse::NormalizedInput(NormalizedInputResponse {
            frame: NormalizedInputFrame {
                source: source.clone(),
                controls: vec![NormalizedControlEvent {
                    source,
                    control_id: "button_1".to_string(),
                    value: NormalizedControlValue::Button(true),
                    timestamp_micros: 7,
                }],
            },
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "NORMALIZED_INPUT:controls=1;button_1=button:1;\n"
        );

        let resp = ControlResponse::EncodedReport(EncodedReportResponse {
            report: EncodedBleReport {
                persona_id: PersonaId("generic_gamepad"),
                report_id: ReportId(1),
                bytes: vec![0x01, 0x00, 0x08],
            },
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=010008;\n"
        );

        let resp = ControlResponse::BleAction(usb2ble_contracts::BleActionResponse {
            action: "self_test",
            state: BleLinkState::Connected,
            report: Some(EncodedBleReport {
                persona_id: PersonaId("generic_gamepad"),
                report_id: ReportId(1),
                bytes: vec![0x01, 0x00, 0x08],
            }),
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "BLE_ACTION:action=self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=010008;\n"
        );

        let resp = ControlResponse::BridgeStatus(BridgeStatusResponse {
            enabled: true,
            active_persona: Some(PersonaId("xbox_wireless_controller")),
            rate_hz: 50,
            last_publish_ms: Some(12345),
            published: 42,
            skipped_duplicate: 100,
            skipped_rate: 25,
            skipped_not_connected: 3,
            skipped_not_ready: 2,
            last_error: None,
        });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=12345;published=42;skipped_duplicate=100;skipped_rate=25;skipped_not_connected=3;skipped_not_ready=2;last_error=none;\n"
        );

        let resp =
            ControlResponse::MappingDiagnostics(usb2ble_contracts::MappingDiagnosticsResponse {
                profile_id: ProfileId("generic_auto"),
                target_persona: PersonaId("generic_gamepad"),
                entries: vec![usb2ble_contracts::MappingDiagnosticEntry {
                    source: UsbInterfaceRef {
                        device: UsbDeviceRef {
                            device_id: DeviceId(1),
                            topology: ConnectionTopology::Direct,
                            vendor_id: 0x044f,
                            product_id: 0xb10a,
                        },
                        interface_id: InterfaceId(0),
                    },
                    source_control_id: "axis_01_30".to_string(),
                    source_value: NormalizedControlValue::Axis(123),
                    target_control_id: Some("x".to_string()),
                    reason: "preferred_axis".to_string(),
                }],
            });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "GENERIC_GAMEPAD_MAPPING:profile=generic_auto;persona=generic_gamepad;entries=1;mappings=src=1:0:044f:b10a:axis_01_30,target=x,value=axis:123,reason=preferred_axis;\n"
        );

        let resp =
            ControlResponse::MappingDiagnostics(usb2ble_contracts::MappingDiagnosticsResponse {
                profile_id: ProfileId("xbox_flight_pack_demo"),
                target_persona: PersonaId("xbox_wireless_controller"),
                entries: Vec::new(),
            });
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "XBOX_GAMEPAD_MAPPING:profile=xbox_flight_pack_demo;persona=xbox_wireless_controller;entries=0;mappings=;\n"
        );

        let resp = ControlResponse::Error(ControlError::PersonaAlreadyActive);
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "ERROR:PersonaAlreadyActive\n"
        );

        let resp = ControlResponse::Error(ControlError::PersonaMismatch);
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "ERROR:PersonaMismatch\n"
        );

        let resp = ControlResponse::Error(ControlError::BleNotConnected);
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "ERROR:BleNotConnected\n"
        );

        let resp = ControlResponse::Error(ControlError::BridgeNoActivePersona);
        let bytes = cp.encode_response(&resp).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "ERROR:BridgeNoActivePersona\n"
        );
    }

    #[test]
    fn test_encode_config_responses() {
        let cp = SerialControlPlane::new();
        let status = ControlResponse::ConfigStatus(usb2ble_contracts::ConfigStatusResponse {
            valid: true,
            source: "runtime",
            selected_persona: "xbox_wireless_controller".to_string(),
            selected_profile: "custom_runtime".to_string(),
            mappings: 4,
            import_active: false,
            last_error: None,
        });
        let bytes = cp.encode_response(&status).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=4;import_active=false;last_error=none;\n"
        );

        let json = ControlResponse::Json(usb2ble_contracts::JsonResponse {
            prefix: "CONFIG_JSON",
            json: "{}".to_string(),
        });
        let bytes = cp.encode_response(&json).unwrap();
        assert_eq!(std::str::from_utf8(&bytes).unwrap(), "CONFIG_JSON:{}\n");

        let import = ControlResponse::ConfigImport(usb2ble_contracts::ConfigImportResponse {
            state: "chunk",
            total_chunks: 2,
            received_chunks: 1,
            bytes: 16,
        });
        let bytes = cp.encode_response(&import).unwrap();
        assert_eq!(
            std::str::from_utf8(&bytes).unwrap(),
            "CONFIG_IMPORT:state=chunk;total_chunks=2;received_chunks=1;bytes=16;\n"
        );
    }
}
