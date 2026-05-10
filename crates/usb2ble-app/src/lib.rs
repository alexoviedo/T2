//! usb2ble-app
//!
//! Responsible for orchestration and application state.

use usb2ble_contracts::{
    AppState, BleLinkState, BondStore, BridgeRuntimeConfig, CONTRACT_VERSION,
    CUSTOM_RUNTIME_PROFILE_ID_STR, CompositeMerger, ConfigActionResponse, ConfigStatusResponse,
    ConfigStore, ControlCommand, ControlError, ControlResponse, DescriptorKey, EncodedBleReport,
    EncodedReportResponse, FLIGHT_PACK_DEMO_PROFILE_ID_STR, GENERIC_AUTO_PROFILE_ID_STR,
    GENERIC_GAMEPAD_PERSONA_ID_STR, HidDescriptorParser, HidReportDecoder, HidSummaryResponse,
    InfoResponse, InputCatalog, InputCatalogEntry, InputNormalizer, JsonResponse,
    MAX_RUNTIME_CONFIG_JSON_BYTES, Mapper, MappingDiagnosticsResponse, MappingProfile,
    NormalizedControlValue, NormalizedInputFrame, NormalizedInputResponse, PersonaEncoder,
    PersonaId, ProfileId, ProfileResponse, ProfileStore, RUNTIME_CONFIG_SCHEMA_VERSION,
    RuntimeConfig, RuntimeTransform, SourceMappingRule, StatusResponse, UsbDescriptorResponse,
    UsbIngressEvent, UsbReportResponse, UsbStatusResponse, XBOX_AUTO_PROFILE_ID_STR,
    XBOX_FLIGHT_PACK_DEMO_PROFILE_ID_STR, XBOX_WIRELESS_CONTROLLER_PERSONA_ID_STR,
};
use usb2ble_hid::{HidParser, summarize_capabilities};
use usb2ble_input::{LatestInputMerger, StandardInputNormalizer};
use usb2ble_mapping::{
    GENERIC_GAMEPAD_PERSONA_ID, GenericAutoMapper, XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
    diagnose_generic_gamepad_mapping, diagnose_generic_gamepad_mapping_with_profile,
    diagnose_xbox_wireless_controller_mapping,
    diagnose_xbox_wireless_controller_mapping_with_profile, flight_pack_demo_profile,
    generic_auto_profile, map_composite_to_xbox_wireless_controller,
    map_composite_to_xbox_wireless_controller_with_profile, select_generic_gamepad_profile,
    select_xbox_wireless_controller_profile, xbox_flight_pack_demo_profile,
};
use usb2ble_personas::{GenericGamepadEncoder, XboxWirelessControllerEncoder};

/// The main application structure.
pub struct App<S> {
    state: AppState,
    storage: S,
    runtime_config: RuntimeConfig,
    config_source: &'static str,
    last_config_error: Option<&'static str>,
}

impl<S> App<S>
where
    S: ProfileStore + BondStore + ConfigStore,
{
    /// Create a new application instance.
    pub fn new(storage: S) -> Self {
        let active_profile = storage.load_active_profile().ok().flatten();
        let (runtime_config, config_source, last_config_error) = match storage.load_config() {
            Ok(Some(config)) => match validate_runtime_config(&config) {
                Ok(()) => (config, "loaded", None),
                Err(_) => (RuntimeConfig::default(), "default", Some("stored_invalid")),
            },
            Ok(None) => (RuntimeConfig::default(), "default", None),
            Err(_) => (RuntimeConfig::default(), "default", Some("storage_failure")),
        };

        Self {
            state: AppState {
                physical_devices: Vec::new(),
                hid_interfaces: Vec::new(),
                descriptors: Vec::new(),
                raw_descriptors: Vec::new(),
                last_reports: Vec::new(),
                last_report_packets: Vec::new(),
                active_profile,
                active_persona: None,
                ble_state: BleLinkState::Idle,
            },
            storage,
            runtime_config,
            config_source,
            last_config_error,
        }
    }

    /// Process a control plane command.
    #[allow(clippy::too_many_lines)]
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
                    active_persona: self.state.active_persona,
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
            ControlCommand::GetHidSummary(key) => {
                if let Some((_, ir)) = self.state.descriptors.iter().find(|(k, _)| k == key) {
                    ControlResponse::HidSummary(HidSummaryResponse {
                        summary: summarize_capabilities(ir),
                    })
                } else {
                    ControlResponse::Error(ControlError::NotFound)
                }
            }
            ControlCommand::GetNormalizedInput(key) => {
                self.normalized_frame_for_key(key).map_or_else(
                    || ControlResponse::Error(ControlError::NotFound),
                    |frame| ControlResponse::NormalizedInput(NormalizedInputResponse { frame }),
                )
            }
            ControlCommand::GetGenericGamepadReport => self.generic_gamepad_report_response(),
            ControlCommand::GetGenericGamepadMapping => self.generic_gamepad_mapping_response(),
            ControlCommand::GetXboxGamepadReport => self.xbox_gamepad_report_response(),
            ControlCommand::GetXboxGamepadMapping => self.xbox_gamepad_mapping_response(),
            ControlCommand::GetConfigStatus => {
                ControlResponse::ConfigStatus(self.config_status(false))
            }
            ControlCommand::GetConfigSchema => Self::config_schema_response(),
            ControlCommand::GetPersonaSchema(persona) => Self::persona_schema_response(persona),
            ControlCommand::GetInputCatalog => self.input_catalog_response(),
            ControlCommand::GetConfigJson => self.config_json_response(),
            ControlCommand::ResetConfig => {
                self.reset_runtime_config();
                ControlResponse::ConfigAction(ConfigActionResponse {
                    action: "reset",
                    state: "ok",
                    detail: None,
                })
            }
            ControlCommand::SaveConfig => match self.save_runtime_config() {
                Ok(()) => ControlResponse::ConfigAction(ConfigActionResponse {
                    action: "save",
                    state: "ok",
                    detail: None,
                }),
                Err(err) => ControlResponse::Error(err),
            },
            ControlCommand::LoadConfig => match self.load_runtime_config() {
                Ok(()) => ControlResponse::ConfigAction(ConfigActionResponse {
                    action: "load",
                    state: "ok",
                    detail: None,
                }),
                Err(err) => ControlResponse::Error(err),
            },
            ControlCommand::StartBleGenericGamepad
            | ControlCommand::PublishGenericGamepadReport
            | ControlCommand::SendBleSelfTestReport
            | ControlCommand::StartBleXboxController
            | ControlCommand::PublishXboxGamepadReport
            | ControlCommand::SendXboxSelfTestReport
            | ControlCommand::ForgetBleBonds
            | ControlCommand::StartBridge
            | ControlCommand::StopBridge
            | ControlCommand::GetBridgeStatus
            | ControlCommand::SetBridgeRateHz(_)
            | ControlCommand::BeginConfigJson { .. }
            | ControlCommand::ConfigJsonChunk { .. }
            | ControlCommand::CommitConfigJson
            | ControlCommand::StartConfigured => ControlResponse::Error(ControlError::Generic),
        }
    }

    fn normalized_frame_for_key(&self, key: &DescriptorKey) -> Option<NormalizedInputFrame> {
        let (_, ir) = self.state.descriptors.iter().find(|(k, _)| k == key)?;
        let (_, packet) = self
            .state
            .last_report_packets
            .iter()
            .find(|(k, _)| k == key)?;
        let decoded = HidParser.decode_report(ir, packet).ok()?;
        StandardInputNormalizer.normalize(ir, &decoded).ok()
    }

    fn latest_normalized_frames(&self) -> Vec<NormalizedInputFrame> {
        self.state
            .last_report_packets
            .iter()
            .filter_map(|(key, _)| self.normalized_frame_for_key(key))
            .collect()
    }

    fn latest_composite(&self) -> Result<usb2ble_contracts::CompositeInputFrame, ControlError> {
        let frames = self.latest_normalized_frames();
        if frames.is_empty() {
            return Err(ControlError::NotFound);
        }

        LatestInputMerger
            .merge(&frames, &usb2ble_contracts::CompositeProfile::default())
            .map_err(|_| ControlError::Generic)
    }

    /// Current runtime configuration.
    #[must_use]
    pub const fn runtime_config(&self) -> &RuntimeConfig {
        &self.runtime_config
    }

    /// Build a config status response.
    #[must_use]
    pub fn config_status(&self, import_active: bool) -> ConfigStatusResponse {
        ConfigStatusResponse {
            valid: validate_runtime_config(&self.runtime_config).is_ok(),
            source: self.config_source,
            selected_persona: self.runtime_config.selected_persona.clone(),
            selected_profile: self.runtime_config.selected_profile.clone(),
            mappings: self.runtime_config.mappings.len(),
            import_active,
            last_error: self.last_config_error,
        }
    }

    /// Replace the in-memory runtime configuration after JSON import.
    pub fn set_runtime_config(&mut self, config: RuntimeConfig) -> Result<(), ControlError> {
        validate_runtime_config(&config)?;
        self.runtime_config = config;
        self.config_source = "runtime";
        self.last_config_error = None;
        Ok(())
    }

    /// Save the current runtime configuration through the configured store.
    pub fn save_runtime_config(&mut self) -> Result<(), ControlError> {
        validate_runtime_config(&self.runtime_config)?;
        self.storage
            .save_config(&self.runtime_config)
            .map_err(|_| ControlError::StorageFailure)?;
        self.config_source = "saved";
        self.last_config_error = None;
        Ok(())
    }

    /// Load persisted runtime configuration through the configured store.
    pub fn load_runtime_config(&mut self) -> Result<(), ControlError> {
        match self
            .storage
            .load_config()
            .map_err(|_| ControlError::StorageFailure)?
        {
            Some(config) => {
                validate_runtime_config(&config)?;
                self.runtime_config = config;
                self.config_source = "loaded";
                self.last_config_error = None;
            }
            None => self.reset_runtime_config(),
        }
        Ok(())
    }

    /// Reset in-memory runtime configuration to built-in defaults.
    pub fn reset_runtime_config(&mut self) {
        self.runtime_config = RuntimeConfig::default();
        self.config_source = "default";
        self.last_config_error = None;
    }

    fn config_json_response(&self) -> ControlResponse {
        serde_json::to_string(&self.runtime_config).map_or_else(
            |_| ControlResponse::Error(ControlError::Generic),
            |json| {
                ControlResponse::Json(JsonResponse {
                    prefix: "CONFIG_JSON",
                    json,
                })
            },
        )
    }

    fn config_schema_response() -> ControlResponse {
        let schema = serde_json::json!({
            "schema_version": RUNTIME_CONFIG_SCHEMA_VERSION,
            "max_json_bytes": MAX_RUNTIME_CONFIG_JSON_BYTES,
            "personas": [
                GENERIC_GAMEPAD_PERSONA_ID_STR,
                XBOX_WIRELESS_CONTROLLER_PERSONA_ID_STR
            ],
            "profiles": [
                GENERIC_AUTO_PROFILE_ID_STR,
                FLIGHT_PACK_DEMO_PROFILE_ID_STR,
                XBOX_AUTO_PROFILE_ID_STR,
                XBOX_FLIGHT_PACK_DEMO_PROFILE_ID_STR,
                CUSTOM_RUNTIME_PROFILE_ID_STR
            ],
            "bridge": {
                "auto_start_persona": "bool",
                "auto_start_bridge": "bool",
                "rate_hz": { "min": 1, "max": 200, "default": 50 }
            },
            "mapping_rule": {
                "source_vendor_id": "u16|required",
                "source_product_id": "u16|required",
                "source_interface_id": "u32|optional",
                "source_control_id": "string|required",
                "target_control_id": "string|required",
                "invert": "bool",
                "deadzone": "i32|optional",
                "transform": ["axis_to_trigger"]
            },
            "presets": ["flight-pack-generic", "flight-pack-xbox"],
        });
        ControlResponse::Json(JsonResponse {
            prefix: "CONFIG_SCHEMA_JSON",
            json: schema.to_string(),
        })
    }

    fn persona_schema_response(persona: &str) -> ControlResponse {
        let descriptor = match persona_id_from_alias(persona) {
            Ok(GENERIC_GAMEPAD_PERSONA_ID) => {
                GenericGamepadEncoder.descriptor(GENERIC_GAMEPAD_PERSONA_ID)
            }
            Ok(XBOX_WIRELESS_CONTROLLER_PERSONA_ID) => {
                XboxWirelessControllerEncoder.descriptor(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
            }
            Ok(_) | Err(_) => return ControlResponse::Error(ControlError::UnknownPersona),
        };
        match descriptor {
            Ok(descriptor) => {
                let json = serde_json::json!({
                    "persona": descriptor.persona_id.0,
                    "controls": descriptor.input_schema.controls,
                });
                ControlResponse::Json(JsonResponse {
                    prefix: "PERSONA_SCHEMA_JSON",
                    json: json.to_string(),
                })
            }
            Err(_) => ControlResponse::Error(ControlError::UnknownPersona),
        }
    }

    fn input_catalog_response(&self) -> ControlResponse {
        let catalog = self.input_catalog();
        serde_json::to_string(&catalog).map_or_else(
            |_| ControlResponse::Error(ControlError::Generic),
            |json| {
                ControlResponse::Json(JsonResponse {
                    prefix: "INPUT_CATALOG_JSON",
                    json,
                })
            },
        )
    }

    fn input_catalog(&self) -> InputCatalog {
        let Ok(composite) = self.latest_composite() else {
            return InputCatalog {
                entries: Vec::new(),
            };
        };
        let diagnostics = self
            .diagnostics_for_configured_persona(&composite)
            .unwrap_or_else(|_| MappingDiagnosticsResponse {
                profile_id: ProfileId("none"),
                target_persona: GENERIC_GAMEPAD_PERSONA_ID,
                entries: Vec::new(),
            });

        let entries = composite
            .controls
            .iter()
            .map(|control| {
                let same_source = |entry: &&usb2ble_contracts::MappingDiagnosticEntry| {
                    (&entry.source, entry.source_control_id.as_str())
                        == (&control.source, control.control_id.as_str())
                };
                let mapped_target = diagnostics
                    .entries
                    .iter()
                    .find(same_source)
                    .and_then(|entry| entry.target_control_id.clone());
                InputCatalogEntry {
                    device_id: control.source.device.device_id.0,
                    interface_id: control.source.interface_id.0,
                    vendor_id: control.source.device.vendor_id,
                    product_id: control.source.device.product_id,
                    source_control_id: control.control_id.clone(),
                    value: normalized_value_string(control.value),
                    kind: normalized_kind(control.value).to_string(),
                    mapped_target,
                    source_display_hint: source_display_hint(
                        control.source.device.vendor_id,
                        control.source.device.product_id,
                    )
                    .map(str::to_string),
                }
            })
            .collect();

        InputCatalog { entries }
    }

    fn generic_gamepad_report_response(&self) -> ControlResponse {
        self.generic_gamepad_report()
            .map_or_else(ControlResponse::Error, |report| {
                ControlResponse::EncodedReport(EncodedReportResponse { report })
            })
    }

    fn generic_gamepad_mapping_response(&self) -> ControlResponse {
        let composite = match self.latest_composite() {
            Ok(composite) => composite,
            Err(err) => return ControlResponse::Error(err),
        };

        ControlResponse::MappingDiagnostics(
            self.profile_for_persona(GENERIC_GAMEPAD_PERSONA_ID, &composite)
                .map_or_else(
                    |_| diagnose_generic_gamepad_mapping(&composite),
                    |profile| diagnose_generic_gamepad_mapping_with_profile(&profile, &composite),
                ),
        )
    }

    fn xbox_gamepad_report_response(&self) -> ControlResponse {
        self.xbox_gamepad_report()
            .map_or_else(ControlResponse::Error, |report| {
                ControlResponse::EncodedReport(EncodedReportResponse { report })
            })
    }

    fn xbox_gamepad_mapping_response(&self) -> ControlResponse {
        let composite = match self.latest_composite() {
            Ok(composite) => composite,
            Err(err) => return ControlResponse::Error(err),
        };

        ControlResponse::MappingDiagnostics(
            self.profile_for_persona(XBOX_WIRELESS_CONTROLLER_PERSONA_ID, &composite)
                .map_or_else(
                    |_| diagnose_xbox_wireless_controller_mapping(&composite),
                    |profile| {
                        diagnose_xbox_wireless_controller_mapping_with_profile(&profile, &composite)
                    },
                ),
        )
    }

    /// Build a Generic Gamepad report from all latest normalized inputs.
    pub fn generic_gamepad_report(&self) -> Result<EncodedBleReport, ControlError> {
        let composite = self.latest_composite()?;
        let profile = self
            .profile_for_persona(GENERIC_GAMEPAD_PERSONA_ID, &composite)
            .unwrap_or_else(|_| select_generic_gamepad_profile(&composite));
        let persona_frame = GenericAutoMapper
            .map_to_persona_frame(&profile, &composite)
            .map_err(|_| ControlError::Generic)?;
        GenericGamepadEncoder
            .encode(&persona_frame)
            .map_err(|_| ControlError::Generic)
    }

    /// Build an Xbox Wireless Controller report from all latest normalized inputs.
    pub fn xbox_gamepad_report(&self) -> Result<EncodedBleReport, ControlError> {
        let composite = self.latest_composite()?;
        let persona_frame = self
            .profile_for_persona(XBOX_WIRELESS_CONTROLLER_PERSONA_ID, &composite)
            .map_or_else(
                |_| map_composite_to_xbox_wireless_controller(&composite),
                |profile| {
                    map_composite_to_xbox_wireless_controller_with_profile(&profile, &composite)
                },
            );
        XboxWirelessControllerEncoder
            .encode(&persona_frame)
            .map_err(|_| ControlError::Generic)
    }

    fn diagnostics_for_configured_persona(
        &self,
        composite: &usb2ble_contracts::CompositeInputFrame,
    ) -> Result<MappingDiagnosticsResponse, ControlError> {
        let persona = persona_id_from_alias(&self.runtime_config.selected_persona)?;
        if persona == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
            Ok(self.profile_for_persona(persona, composite).map_or_else(
                |_| diagnose_xbox_wireless_controller_mapping(composite),
                |profile| {
                    diagnose_xbox_wireless_controller_mapping_with_profile(&profile, composite)
                },
            ))
        } else {
            Ok(self.profile_for_persona(persona, composite).map_or_else(
                |_| diagnose_generic_gamepad_mapping(composite),
                |profile| diagnose_generic_gamepad_mapping_with_profile(&profile, composite),
            ))
        }
    }

    fn profile_for_persona(
        &self,
        persona: PersonaId,
        composite: &usb2ble_contracts::CompositeInputFrame,
    ) -> Result<MappingProfile, ControlError> {
        validate_runtime_config(&self.runtime_config)?;
        let selected_persona = persona_id_from_alias(&self.runtime_config.selected_persona)?;
        if selected_persona != persona {
            return Err(ControlError::PersonaMismatch);
        }
        if self.runtime_config.uses_custom_mappings() {
            return Ok(MappingProfile {
                profile_id: ProfileId(CUSTOM_RUNTIME_PROFILE_ID_STR),
                display_name: self.runtime_config.display_name.clone(),
                supported_signatures: Vec::new(),
                target_persona: persona,
                source_mappings: self.runtime_config.mappings.clone(),
                merge_policy: Some(usb2ble_contracts::CompositeProfile {
                    profile_id: Some(ProfileId(CUSTOM_RUNTIME_PROFILE_ID_STR)),
                }),
            });
        }

        match self.runtime_config.selected_profile.as_str() {
            GENERIC_AUTO_PROFILE_ID_STR if persona == GENERIC_GAMEPAD_PERSONA_ID => {
                Ok(generic_auto_profile())
            }
            FLIGHT_PACK_DEMO_PROFILE_ID_STR if persona == GENERIC_GAMEPAD_PERSONA_ID => {
                Ok(flight_pack_demo_profile())
            }
            XBOX_AUTO_PROFILE_ID_STR if persona == XBOX_WIRELESS_CONTROLLER_PERSONA_ID => {
                Ok(select_xbox_wireless_controller_profile(composite))
            }
            XBOX_FLIGHT_PACK_DEMO_PROFILE_ID_STR
                if persona == XBOX_WIRELESS_CONTROLLER_PERSONA_ID =>
            {
                Ok(xbox_flight_pack_demo_profile())
            }
            _ => Err(ControlError::PersonaMismatch),
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
                    .last_report_packets
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
                if let Ok(ir) = HidParser.parse_descriptor(&blob) {
                    if let Some(entry) = self.state.descriptors.iter_mut().find(|(k, _)| k == &key)
                    {
                        entry.1 = ir;
                    } else {
                        self.state.descriptors.push((key, ir));
                    }
                }
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
                    entry.1.clone_from(&packet.payload);
                } else {
                    self.state.last_reports.push((key, packet.payload.clone()));
                }
                if let Some(entry) = self
                    .state
                    .last_report_packets
                    .iter_mut()
                    .find(|(k, _)| k == &key)
                {
                    entry.1 = packet;
                } else {
                    self.state.last_report_packets.push((key, packet));
                }
            }
            _ => {}
        }
    }

    /// Set the BLE state (e.g. from platform glue).
    pub const fn set_ble_state(&mut self, state: BleLinkState) {
        self.state.ble_state = state;
    }

    /// Set the active BLE persona (e.g. from platform glue).
    pub const fn set_active_persona(&mut self, persona: Option<PersonaId>) {
        self.state.active_persona = persona;
    }

    /// Get current app state (read-only).
    #[must_use]
    pub const fn state(&self) -> &AppState {
        &self.state
    }
}

/// Validate a runtime configuration before applying or persisting it.
pub fn validate_runtime_config(config: &RuntimeConfig) -> Result<(), ControlError> {
    if config.schema_version != RUNTIME_CONFIG_SCHEMA_VERSION {
        return Err(ControlError::InvalidConfigVersion);
    }
    let persona = persona_id_from_alias(&config.selected_persona)?;
    validate_bridge_config(&config.bridge)?;
    validate_profile_for_persona(&config.selected_profile, persona)?;

    if !config.uses_custom_mappings() {
        return Ok(());
    }

    let mut targets = std::collections::HashSet::new();
    for rule in &config.mappings {
        if rule.source_vendor_id.is_none() || rule.source_product_id.is_none() {
            return Err(ControlError::InvalidTransform);
        }
        if !is_valid_target_control(persona, &rule.target_control_id) {
            return Err(ControlError::UnknownTargetControl);
        }
        if !targets.insert(rule.target_control_id.clone()) {
            return Err(ControlError::DuplicateTargetMapping);
        }
        validate_rule_transform(rule)?;
    }
    Ok(())
}

fn is_valid_target_control(persona: PersonaId, control_id: &str) -> bool {
    if persona == GENERIC_GAMEPAD_PERSONA_ID {
        return control_id == "hat"
            || ["x", "y", "z", "rx", "ry", "rz"].contains(&control_id)
            || parse_numbered_control(control_id, "button_")
                .is_some_and(|button| (1..=16).contains(&button));
    }
    if persona == XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
        return control_id == "hat"
            || [
                "left_x",
                "left_y",
                "right_x",
                "right_y",
                "left_trigger",
                "right_trigger",
                "a",
                "b",
                "x",
                "y",
                "lb",
                "rb",
                "view",
                "menu",
                "nexus",
                "left_stick_press",
                "right_stick_press",
                "paddle_1",
                "paddle_2",
                "paddle_3",
                "paddle_4",
                "share",
            ]
            .contains(&control_id);
    }
    false
}

fn parse_numbered_control(control_id: &str, prefix: &str) -> Option<u16> {
    control_id.strip_prefix(prefix)?.parse().ok()
}

fn validate_bridge_config(config: &BridgeRuntimeConfig) -> Result<(), ControlError> {
    if (1..=200).contains(&config.rate_hz) {
        Ok(())
    } else {
        Err(ControlError::InvalidBridgeRate)
    }
}

fn validate_profile_for_persona(profile: &str, persona: PersonaId) -> Result<(), ControlError> {
    match (profile, persona) {
        (CUSTOM_RUNTIME_PROFILE_ID_STR, _)
        | (
            GENERIC_AUTO_PROFILE_ID_STR | FLIGHT_PACK_DEMO_PROFILE_ID_STR,
            GENERIC_GAMEPAD_PERSONA_ID,
        )
        | (
            XBOX_AUTO_PROFILE_ID_STR | XBOX_FLIGHT_PACK_DEMO_PROFILE_ID_STR,
            XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
        ) => Ok(()),
        (
            GENERIC_AUTO_PROFILE_ID_STR
            | FLIGHT_PACK_DEMO_PROFILE_ID_STR
            | XBOX_AUTO_PROFILE_ID_STR
            | XBOX_FLIGHT_PACK_DEMO_PROFILE_ID_STR,
            _,
        ) => Err(ControlError::PersonaMismatch),
        _ => Err(ControlError::UnknownProfile),
    }
}

fn validate_rule_transform(rule: &SourceMappingRule) -> Result<(), ControlError> {
    if rule.deadzone.is_some_and(i32::is_negative) {
        return Err(ControlError::InvalidTransform);
    }
    if let Some(RuntimeTransform::AxisToTrigger {
        source_min,
        source_max,
        ..
    }) = rule.transform
        && source_min == source_max
    {
        return Err(ControlError::InvalidTransform);
    }
    Ok(())
}

fn persona_id_from_alias(persona: &str) -> Result<PersonaId, ControlError> {
    match persona {
        "generic" | GENERIC_GAMEPAD_PERSONA_ID_STR => Ok(GENERIC_GAMEPAD_PERSONA_ID),
        "xbox" | XBOX_WIRELESS_CONTROLLER_PERSONA_ID_STR => Ok(XBOX_WIRELESS_CONTROLLER_PERSONA_ID),
        _ => Err(ControlError::UnknownPersona),
    }
}

const fn normalized_kind(value: NormalizedControlValue) -> &'static str {
    match value {
        NormalizedControlValue::Axis(_) => "axis",
        NormalizedControlValue::Button(_) => "button",
        NormalizedControlValue::Hat(_) => "hat",
        NormalizedControlValue::Trigger(_) => "trigger",
        NormalizedControlValue::Unknown(_) => "unknown",
    }
}

fn normalized_value_string(value: NormalizedControlValue) -> String {
    match value {
        NormalizedControlValue::Axis(value) => format!("axis:{value}"),
        NormalizedControlValue::Button(value) => format!("button:{}", u8::from(value)),
        NormalizedControlValue::Hat(value) => format!("hat:{value}"),
        NormalizedControlValue::Trigger(value) => format!("trigger:{value}"),
        NormalizedControlValue::Unknown(value) => format!("unknown:{value}"),
    }
}

const fn source_display_hint(vendor_id: u16, product_id: u16) -> Option<&'static str> {
    match (vendor_id, product_id) {
        (0x044f, 0xb10a) => Some("Thrustmaster T.16000M"),
        (0x044f, 0xb687) => Some("Thrustmaster TWCS/RJ12"),
        (0x2109, 0x2813) => Some("VIA Labs USB hub"),
        _ => None,
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
    #[allow(clippy::cognitive_complexity, clippy::too_many_lines)]
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
        let report_descriptor = vec![
            0x05, 0x09, // Usage Page (Button)
            0x19, 0x01, // Usage Minimum (1)
            0x29, 0x01, // Usage Maximum (1)
            0x15, 0x00, // Logical Minimum (0)
            0x25, 0x01, // Logical Maximum (1)
            0x75, 0x01, // Report Size (1)
            0x95, 0x01, // Report Count (1)
            0x81, 0x02, // Input (Data, Variable, Absolute)
        ];

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
                bytes: report_descriptor.clone(),
            },
        ));

        // 4. Report
        app.handle_usb_event(UsbIngressEvent::InputReportReceived(InputReportPacket {
            source: iface,
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
            assert_eq!(d.bytes, report_descriptor);
        } else {
            panic!("Expected UsbDescriptor");
        }

        let resp = app.handle_control_command(&ControlCommand::GetHidSummary(key));
        if let ControlResponse::HidSummary(summary) = resp {
            assert_eq!(summary.summary.buttons.len(), 1);
            assert_eq!(summary.summary.axes.len(), 0);
            assert_eq!(summary.summary.hats.len(), 0);
        } else {
            panic!("Expected HidSummary");
        }

        let resp = app.handle_control_command(&ControlCommand::GetLastUsbReport(key));
        if let ControlResponse::UsbReport(r) = resp {
            assert_eq!(r.bytes, vec![0xAA, 0xBB]);
        } else {
            panic!("Expected UsbReport");
        }

        let resp = app.handle_control_command(&ControlCommand::GetNormalizedInput(key));
        if let ControlResponse::NormalizedInput(normalized) = resp {
            assert_eq!(normalized.frame.controls.len(), 1);
            assert_eq!(normalized.frame.controls[0].control_id, "button_1");
            assert_eq!(
                normalized.frame.controls[0].value,
                usb2ble_contracts::NormalizedControlValue::Button(false)
            );
        } else {
            panic!("Expected NormalizedInput");
        }

        let resp = app.handle_control_command(&ControlCommand::GetGenericGamepadReport);
        if let ControlResponse::EncodedReport(report) = resp {
            assert_eq!(report.report.persona_id.0, "generic_gamepad");
            assert_eq!(report.report.report_id.0, 1);
            assert_eq!(report.report.bytes.len(), 15);
        } else {
            panic!("Expected EncodedReport");
        }

        let resp = app.handle_control_command(&ControlCommand::GetGenericGamepadMapping);
        if let ControlResponse::MappingDiagnostics(diagnostics) = resp {
            assert_eq!(diagnostics.profile_id.0, "generic_auto");
            assert_eq!(diagnostics.target_persona.0, "generic_gamepad");
            assert_eq!(diagnostics.entries.len(), 1);
            assert_eq!(diagnostics.entries[0].source_control_id, "button_1");
            assert_eq!(
                diagnostics.entries[0].target_control_id.as_deref(),
                Some("button_1")
            );
            assert_eq!(diagnostics.entries[0].reason, "button");
        } else {
            panic!("Expected MappingDiagnostics");
        }

        let resp = app.handle_control_command(&ControlCommand::GetXboxGamepadReport);
        if let ControlResponse::EncodedReport(report) = resp {
            assert_eq!(report.report.persona_id.0, "xbox_wireless_controller");
            assert_eq!(report.report.report_id.0, 1);
            assert_eq!(report.report.bytes.len(), 16);
        } else {
            panic!("Expected EncodedReport");
        }

        let resp = app.handle_control_command(&ControlCommand::GetXboxGamepadMapping);
        if let ControlResponse::MappingDiagnostics(diagnostics) = resp {
            assert_eq!(diagnostics.profile_id.0, "xbox_auto");
            assert_eq!(diagnostics.target_persona.0, "xbox_wireless_controller");
            assert_eq!(diagnostics.entries.len(), 1);
            assert_eq!(diagnostics.entries[0].source_control_id, "button_1");
            assert_eq!(
                diagnostics.entries[0].target_control_id.as_deref(),
                Some("a")
            );
            assert_eq!(diagnostics.entries[0].reason, "button");
        } else {
            panic!("Expected MappingDiagnostics");
        }

        // Test missing key
        let missing_key = DescriptorKey {
            device_id: DeviceId(2),
            interface_id: Some(InterfaceId(0)),
        };
        let resp = app.handle_control_command(&ControlCommand::GetUsbDescriptor(missing_key));
        assert_eq!(resp, ControlResponse::Error(ControlError::NotFound));

        // 6. Detach
        app.handle_usb_event(UsbIngressEvent::DeviceDetached { source: dev });
        assert_eq!(app.state().physical_devices.len(), 0);
        assert_eq!(app.state().hid_interfaces.len(), 0);
        assert_eq!(app.state().raw_descriptors.len(), 0);
        assert_eq!(app.state().last_reports.len(), 0);
        assert_eq!(app.state().last_report_packets.len(), 0);
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

    #[test]
    fn runtime_config_validation_rejects_bad_configs() {
        let config = RuntimeConfig {
            schema_version: 999,
            ..RuntimeConfig::default()
        };
        assert_eq!(
            validate_runtime_config(&config),
            Err(ControlError::InvalidConfigVersion)
        );

        let config = RuntimeConfig {
            selected_persona: "mystery".to_string(),
            ..RuntimeConfig::default()
        };
        assert_eq!(
            validate_runtime_config(&config),
            Err(ControlError::UnknownPersona)
        );

        let mut config = RuntimeConfig::flight_pack_generic_preset();
        config.mappings[0].target_control_id = "nope".to_string();
        assert_eq!(
            validate_runtime_config(&config),
            Err(ControlError::UnknownTargetControl)
        );

        let mut config = RuntimeConfig::flight_pack_generic_preset();
        config.mappings[1].target_control_id = config.mappings[0].target_control_id.clone();
        assert_eq!(
            validate_runtime_config(&config),
            Err(ControlError::DuplicateTargetMapping)
        );

        let mut config = RuntimeConfig::flight_pack_xbox_preset();
        config.mappings[3].transform = Some(RuntimeTransform::AxisToTrigger {
            source_min: 1,
            source_max: 1,
            invert: false,
        });
        assert_eq!(
            validate_runtime_config(&config),
            Err(ControlError::InvalidTransform)
        );
    }

    #[test]
    fn config_mapping_drives_generic_report_and_catalog() {
        let mut app = App::new(InMemoryStore::new());
        inject_button_true(&mut app);

        let config = RuntimeConfig {
            selected_profile: CUSTOM_RUNTIME_PROFILE_ID_STR.to_string(),
            mappings: vec![SourceMappingRule {
                source_vendor_id: Some(0x1234),
                source_product_id: Some(0x5678),
                source_interface_id: Some(0),
                source_control_id: "button_1".to_string(),
                target_control_id: "button_2".to_string(),
                invert: false,
                deadzone: None,
                transform: None,
            }],
            ..RuntimeConfig::default()
        };
        app.set_runtime_config(config).unwrap();

        let report = app.generic_gamepad_report().unwrap();
        assert_eq!(report.persona_id, GENERIC_GAMEPAD_PERSONA_ID);
        assert_eq!(report.bytes[0], 0b0000_0010);

        let mapping = app.handle_control_command(&ControlCommand::GetGenericGamepadMapping);
        if let ControlResponse::MappingDiagnostics(diagnostics) = mapping {
            assert_eq!(
                diagnostics.entries[0].target_control_id.as_deref(),
                Some("button_2")
            );
        } else {
            panic!("Expected mapping diagnostics");
        }

        let catalog = app.handle_control_command(&ControlCommand::GetInputCatalog);
        if let ControlResponse::Json(json) = catalog {
            let parsed: InputCatalog = serde_json::from_str(&json.json).unwrap();
            assert_eq!(parsed.entries.len(), 1);
            assert_eq!(parsed.entries[0].mapped_target.as_deref(), Some("button_2"));
        } else {
            panic!("Expected input catalog JSON");
        }
    }

    #[test]
    fn config_mapping_drives_xbox_report() {
        let mut app = App::new(InMemoryStore::new());
        inject_button_true(&mut app);

        let config = RuntimeConfig {
            selected_persona: XBOX_WIRELESS_CONTROLLER_PERSONA_ID_STR.to_string(),
            selected_profile: CUSTOM_RUNTIME_PROFILE_ID_STR.to_string(),
            mappings: vec![SourceMappingRule {
                source_vendor_id: Some(0x1234),
                source_product_id: Some(0x5678),
                source_interface_id: Some(0),
                source_control_id: "button_1".to_string(),
                target_control_id: "b".to_string(),
                invert: false,
                deadzone: None,
                transform: None,
            }],
            ..RuntimeConfig::default()
        };
        app.set_runtime_config(config).unwrap();

        let report = app.xbox_gamepad_report().unwrap();
        assert_eq!(report.persona_id, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(report.bytes.len(), 16);

        let mapping = app.handle_control_command(&ControlCommand::GetXboxGamepadMapping);
        if let ControlResponse::MappingDiagnostics(diagnostics) = mapping {
            assert_eq!(
                diagnostics.entries[0].target_control_id.as_deref(),
                Some("b")
            );
        } else {
            panic!("Expected mapping diagnostics");
        }
    }

    #[test]
    fn config_save_load_round_trips_in_memory_store() {
        let store = InMemoryStore::new();
        let mut app = App::new(store.clone());
        let config = RuntimeConfig::flight_pack_xbox_preset();
        app.set_runtime_config(config.clone()).unwrap();
        app.save_runtime_config().unwrap();

        let app = App::new(store);
        assert_eq!(app.runtime_config(), &config);
        assert_eq!(app.config_status(false).source, "loaded");
    }

    #[test]
    fn persona_schema_commands_expose_expected_controls() {
        let mut app = App::new(InMemoryStore::new());
        let generic =
            app.handle_control_command(&ControlCommand::GetPersonaSchema("generic".to_string()));
        if let ControlResponse::Json(json) = generic {
            assert!(json.json.contains("\"control_id\":\"x\""));
        } else {
            panic!("Expected Generic persona schema JSON");
        }

        let xbox =
            app.handle_control_command(&ControlCommand::GetPersonaSchema("xbox".to_string()));
        if let ControlResponse::Json(json) = xbox {
            assert!(json.json.contains("\"control_id\":\"left_trigger\""));
        } else {
            panic!("Expected Xbox persona schema JSON");
        }
    }

    fn inject_button_true(app: &mut App<InMemoryStore>) {
        use usb2ble_contracts::{
            ConnectionTopology, DeviceId, InputReportPacket, InterfaceId, ReportDescriptorBlob,
            UsbDeviceRef, UsbInterfaceRef,
        };

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
        let report_descriptor = vec![
            0x05, 0x09, 0x19, 0x01, 0x29, 0x01, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x01,
            0x81, 0x02,
        ];

        app.handle_usb_event(UsbIngressEvent::DeviceAttached(dev));
        app.handle_usb_event(UsbIngressEvent::InterfaceDiscovered {
            source: iface.clone(),
            class_code: 3,
            subclass_code: 0,
            protocol_code: 0,
        });
        app.handle_usb_event(UsbIngressEvent::ReportDescriptorReceived(
            ReportDescriptorBlob {
                source: iface.clone(),
                bytes: report_descriptor,
            },
        ));
        app.handle_usb_event(UsbIngressEvent::InputReportReceived(InputReportPacket {
            source: iface,
            report_id: usb2ble_contracts::ReportId(0),
            payload: vec![0x01],
            timestamp_micros: 100,
        }));
    }
}
