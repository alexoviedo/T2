//! Mapping from composite normalized input into persona logical frames.

#![deny(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashSet;

use usb2ble_contracts::{
    CompositeInputFrame, DeviceSignature, Mapper, MappingDiagnosticEntry,
    MappingDiagnosticsResponse, MappingError, MappingProfile, NormalizedCompositeValue,
    NormalizedControlValue, PersonaId, PersonaInputFrame, PersonaLogicalControlValue, ProfileId,
    RuntimeTransform, SourceMappingRule,
};

/// Generic auto-mapping profile ID for the first demo path.
pub const GENERIC_AUTO_PROFILE_ID: ProfileId = ProfileId("generic_auto");

/// Curated demo profile ID for the Thrustmaster Flight Pack topology.
pub const FLIGHT_PACK_DEMO_PROFILE_ID: ProfileId = ProfileId("flight_pack_demo");

/// Generic Xbox auto-mapping profile ID.
pub const XBOX_AUTO_PROFILE_ID: ProfileId = ProfileId("xbox_auto");

/// Generic Gamepad persona ID targeted by the auto mapper.
pub const GENERIC_GAMEPAD_PERSONA_ID: PersonaId = PersonaId("generic_gamepad");

/// Xbox Flight Pack demo profile ID.
pub const XBOX_FLIGHT_PACK_DEMO_PROFILE_ID: ProfileId = ProfileId("xbox_flight_pack_demo");

/// Xbox Wireless Controller persona ID targeted by Xbox mappings.
pub const XBOX_WIRELESS_CONTROLLER_PERSONA_ID: PersonaId = PersonaId("xbox_wireless_controller");

const AXIS_TARGETS: [&str; 6] = ["x", "y", "z", "rx", "ry", "rz"];
const THRUSTMASTER_VENDOR_ID: u16 = 0x044f;
const T16000_PRODUCT_ID: u16 = 0xb10a;
const TWCS_PRODUCT_ID: u16 = 0xb687;

/// Deterministic best-effort mapper for HID-like controller inputs.
#[derive(Debug, Default, Clone, Copy)]
pub struct GenericAutoMapper;

impl Mapper for GenericAutoMapper {
    fn select_profile(
        &self,
        devices: &[DeviceSignature],
    ) -> Result<Option<ProfileId>, MappingError> {
        if has_flight_pack_signatures(devices) {
            return Ok(Some(FLIGHT_PACK_DEMO_PROFILE_ID));
        }
        Ok((!devices.is_empty()).then_some(GENERIC_AUTO_PROFILE_ID))
    }

    fn map_to_persona_frame(
        &self,
        profile: &MappingProfile,
        composite: &CompositeInputFrame,
    ) -> Result<PersonaInputFrame, MappingError> {
        if profile.target_persona != GENERIC_GAMEPAD_PERSONA_ID {
            return Err(MappingError::Generic);
        }

        Ok(map_composite_to_generic_gamepad_with_profile(
            profile, composite,
        ))
    }
}

/// Return the curated Xbox demo profile for T.16000M + TWCS.
#[must_use]
pub fn xbox_flight_pack_demo_profile() -> MappingProfile {
    MappingProfile {
        profile_id: XBOX_FLIGHT_PACK_DEMO_PROFILE_ID,
        display_name: "Thrustmaster Flight Pack Xbox Demo".to_string(),
        supported_signatures: vec![
            DeviceSignature {
                vendor_id: THRUSTMASTER_VENDOR_ID,
                product_id: T16000_PRODUCT_ID,
                interface_class: Some(3),
                capability_fingerprint: None,
            },
            DeviceSignature {
                vendor_id: THRUSTMASTER_VENDOR_ID,
                product_id: TWCS_PRODUCT_ID,
                interface_class: Some(3),
                capability_fingerprint: None,
            },
        ],
        target_persona: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
        source_mappings: vec![
            rule(T16000_PRODUCT_ID, "axis_01_30", "left_x"),
            rule(T16000_PRODUCT_ID, "axis_01_31", "left_y"),
            rule(T16000_PRODUCT_ID, "axis_01_36", "right_x"),
            rule(T16000_PRODUCT_ID, "axis_01_35", "right_y"),
            rule(TWCS_PRODUCT_ID, "axis_01_36", "left_trigger"),
            rule(TWCS_PRODUCT_ID, "axis_01_32", "right_trigger"),
            rule(T16000_PRODUCT_ID, "hat_01_39", "hat"),
            rule(T16000_PRODUCT_ID, "button_1", "a"),
            rule(T16000_PRODUCT_ID, "button_2", "b"),
            rule(T16000_PRODUCT_ID, "button_3", "x"),
            rule(T16000_PRODUCT_ID, "button_4", "y"),
            rule(T16000_PRODUCT_ID, "button_5", "lb"),
            rule(T16000_PRODUCT_ID, "button_6", "rb"),
            rule(T16000_PRODUCT_ID, "button_7", "view"),
            rule(T16000_PRODUCT_ID, "button_8", "menu"),
            rule(T16000_PRODUCT_ID, "button_9", "nexus"),
            rule(T16000_PRODUCT_ID, "button_10", "left_stick_press"),
            rule(T16000_PRODUCT_ID, "button_11", "right_stick_press"),
            rule(T16000_PRODUCT_ID, "button_12", "share"),
        ],
        merge_policy: Some(usb2ble_contracts::CompositeProfile {
            profile_id: Some(XBOX_FLIGHT_PACK_DEMO_PROFILE_ID),
        }),
    }
}

/// Return the built-in Generic Gamepad auto-mapping profile.
#[must_use]
pub fn generic_auto_profile() -> MappingProfile {
    MappingProfile {
        profile_id: GENERIC_AUTO_PROFILE_ID,
        display_name: "Generic Auto Gamepad".to_string(),
        supported_signatures: Vec::new(),
        target_persona: GENERIC_GAMEPAD_PERSONA_ID,
        source_mappings: Vec::new(),
        merge_policy: Some(usb2ble_contracts::CompositeProfile {
            profile_id: Some(GENERIC_AUTO_PROFILE_ID),
        }),
    }
}

/// Return the curated Generic Gamepad demo profile for T.16000M + TWCS.
#[must_use]
pub fn flight_pack_demo_profile() -> MappingProfile {
    MappingProfile {
        profile_id: FLIGHT_PACK_DEMO_PROFILE_ID,
        display_name: "Thrustmaster Flight Pack Demo".to_string(),
        supported_signatures: vec![
            DeviceSignature {
                vendor_id: THRUSTMASTER_VENDOR_ID,
                product_id: T16000_PRODUCT_ID,
                interface_class: Some(3),
                capability_fingerprint: None,
            },
            DeviceSignature {
                vendor_id: THRUSTMASTER_VENDOR_ID,
                product_id: TWCS_PRODUCT_ID,
                interface_class: Some(3),
                capability_fingerprint: None,
            },
        ],
        target_persona: GENERIC_GAMEPAD_PERSONA_ID,
        source_mappings: vec![
            rule(T16000_PRODUCT_ID, "axis_01_30", "x"),
            rule(T16000_PRODUCT_ID, "axis_01_31", "y"),
            rule(TWCS_PRODUCT_ID, "axis_01_32", "z"),
            rule(TWCS_PRODUCT_ID, "axis_01_36", "rx"),
            rule(T16000_PRODUCT_ID, "axis_01_36", "ry"),
            rule(T16000_PRODUCT_ID, "axis_01_35", "rz"),
        ],
        merge_policy: Some(usb2ble_contracts::CompositeProfile {
            profile_id: Some(FLIGHT_PACK_DEMO_PROFILE_ID),
        }),
    }
}

/// Select the best built-in Xbox profile for current sources.
#[must_use]
pub fn select_xbox_wireless_controller_profile(composite: &CompositeInputFrame) -> MappingProfile {
    if has_flight_pack_sources(composite) {
        xbox_flight_pack_demo_profile()
    } else {
        MappingProfile {
            profile_id: XBOX_AUTO_PROFILE_ID,
            display_name: "Xbox Auto Gamepad".to_string(),
            target_persona: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            ..generic_auto_profile()
        }
    }
}

/// Map arbitrary normalized controls to an Xbox Wireless Controller frame.
#[must_use]
pub fn map_composite_to_xbox_wireless_controller(
    composite: &CompositeInputFrame,
) -> PersonaInputFrame {
    let profile = select_xbox_wireless_controller_profile(composite);
    map_composite_to_xbox_wireless_controller_with_profile(&profile, composite)
}

/// Map using an explicit Xbox Wireless Controller profile.
#[must_use]
pub fn map_composite_to_xbox_wireless_controller_with_profile(
    profile: &MappingProfile,
    composite: &CompositeInputFrame,
) -> PersonaInputFrame {
    map_composite_to_xbox_wireless_controller_with_profile_and_diagnostics(profile, composite).frame
}

/// Explain how the Xbox Wireless Controller mapper handles each source control.
#[must_use]
pub fn diagnose_xbox_wireless_controller_mapping(
    composite: &CompositeInputFrame,
) -> MappingDiagnosticsResponse {
    let profile = select_xbox_wireless_controller_profile(composite);
    map_composite_to_xbox_wireless_controller_with_profile_and_diagnostics(&profile, composite)
        .diagnostics
}

/// Explain mapping decisions for an explicit Xbox Wireless Controller profile.
#[must_use]
pub fn diagnose_xbox_wireless_controller_mapping_with_profile(
    profile: &MappingProfile,
    composite: &CompositeInputFrame,
) -> MappingDiagnosticsResponse {
    map_composite_to_xbox_wireless_controller_with_profile_and_diagnostics(profile, composite)
        .diagnostics
}

/// Select the best built-in Generic Gamepad profile for current sources.
#[must_use]
pub fn select_generic_gamepad_profile(composite: &CompositeInputFrame) -> MappingProfile {
    if has_flight_pack_sources(composite) {
        flight_pack_demo_profile()
    } else {
        generic_auto_profile()
    }
}

/// Best-effort mapping from arbitrary normalized controls to Generic Gamepad controls.
#[must_use]
pub fn map_composite_to_generic_gamepad(composite: &CompositeInputFrame) -> PersonaInputFrame {
    map_composite_to_generic_gamepad_with_diagnostics(composite).frame
}

/// Explain how the Generic Gamepad auto mapper handles each source control.
#[must_use]
pub fn diagnose_generic_gamepad_mapping(
    composite: &CompositeInputFrame,
) -> MappingDiagnosticsResponse {
    let profile = select_generic_gamepad_profile(composite);
    map_composite_to_generic_gamepad_with_profile_and_diagnostics(&profile, composite).diagnostics
}

/// Map using an explicit Generic Gamepad profile.
#[must_use]
pub fn map_composite_to_generic_gamepad_with_profile(
    profile: &MappingProfile,
    composite: &CompositeInputFrame,
) -> PersonaInputFrame {
    map_composite_to_generic_gamepad_with_profile_and_diagnostics(profile, composite).frame
}

/// Explain mapping decisions for an explicit Generic Gamepad profile.
#[must_use]
pub fn diagnose_generic_gamepad_mapping_with_profile(
    profile: &MappingProfile,
    composite: &CompositeInputFrame,
) -> MappingDiagnosticsResponse {
    map_composite_to_generic_gamepad_with_profile_and_diagnostics(profile, composite).diagnostics
}

struct GenericGamepadMappingResult {
    frame: PersonaInputFrame,
    diagnostics: MappingDiagnosticsResponse,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ProcessedControl {
    device: u32,
    interface: u32,
    control: String,
}

struct XboxWirelessControllerMappingResult {
    frame: PersonaInputFrame,
    diagnostics: MappingDiagnosticsResponse,
}

fn map_composite_to_generic_gamepad_with_diagnostics(
    composite: &CompositeInputFrame,
) -> GenericGamepadMappingResult {
    map_composite_to_generic_gamepad_with_profile_and_diagnostics(
        &generic_auto_profile(),
        composite,
    )
}

fn map_composite_to_xbox_wireless_controller_with_profile_and_diagnostics(
    profile: &MappingProfile,
    composite: &CompositeInputFrame,
) -> XboxWirelessControllerMappingResult {
    let ordered_controls = controls_in_source_priority(composite);
    let mut logical_controls = Vec::new();
    let mut diagnostics = Vec::new();
    let mut used_targets = HashSet::new();
    let mut processed_controls = Vec::new();

    if profile.source_mappings.is_empty() {
        map_xbox_auto_controls(
            &ordered_controls,
            &mut logical_controls,
            &mut diagnostics,
            &mut used_targets,
            &mut processed_controls,
        );
        mark_unprocessed_controls(
            &ordered_controls,
            &mut diagnostics,
            &processed_controls,
            "unsupported_control",
        );
    } else {
        map_profile_rules(
            profile,
            &ordered_controls,
            &mut logical_controls,
            &mut diagnostics,
            &mut used_targets,
            &mut processed_controls,
        );
        mark_unprocessed_controls(
            &ordered_controls,
            &mut diagnostics,
            &processed_controls,
            "profile_unmapped",
        );
    }

    XboxWirelessControllerMappingResult {
        frame: PersonaInputFrame {
            persona_id: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            logical_controls,
        },
        diagnostics: MappingDiagnosticsResponse {
            profile_id: profile.profile_id,
            target_persona: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            entries: diagnostics,
        },
    }
}

fn map_composite_to_generic_gamepad_with_profile_and_diagnostics(
    profile: &MappingProfile,
    composite: &CompositeInputFrame,
) -> GenericGamepadMappingResult {
    let ordered_controls = controls_in_source_priority(composite);
    let mut logical_controls = Vec::new();
    let mut diagnostics = Vec::new();
    let mut used_targets = HashSet::new();
    let mut processed_controls = Vec::new();

    if profile.profile_id.0 != "custom_runtime" {
        map_buttons_and_hat(
            &ordered_controls,
            &mut logical_controls,
            &mut diagnostics,
            &mut used_targets,
            &mut processed_controls,
        );
    }
    if profile.source_mappings.is_empty() {
        map_axes(
            &ordered_controls,
            &mut logical_controls,
            &mut diagnostics,
            &mut used_targets,
            &mut processed_controls,
        );
        mark_unprocessed_controls(
            &ordered_controls,
            &mut diagnostics,
            &processed_controls,
            "unsupported_control",
        );
    } else {
        map_profile_rules(
            profile,
            &ordered_controls,
            &mut logical_controls,
            &mut diagnostics,
            &mut used_targets,
            &mut processed_controls,
        );
        mark_unprocessed_controls(
            &ordered_controls,
            &mut diagnostics,
            &processed_controls,
            "profile_unmapped",
        );
    }

    GenericGamepadMappingResult {
        frame: PersonaInputFrame {
            persona_id: GENERIC_GAMEPAD_PERSONA_ID,
            logical_controls,
        },
        diagnostics: MappingDiagnosticsResponse {
            profile_id: profile.profile_id,
            target_persona: GENERIC_GAMEPAD_PERSONA_ID,
            entries: diagnostics,
        },
    }
}

fn map_xbox_auto_controls(
    controls: &[&NormalizedCompositeValue],
    logical_controls: &mut Vec<PersonaLogicalControlValue>,
    diagnostics: &mut Vec<MappingDiagnosticEntry>,
    used_targets: &mut HashSet<String>,
    processed_controls: &mut Vec<ProcessedControl>,
) {
    const BUTTON_TARGETS: [&str; 15] = [
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
    ];
    const AXIS_TARGETS: [&str; 4] = ["left_x", "left_y", "right_x", "right_y"];
    const TRIGGER_TARGETS: [&str; 2] = ["left_trigger", "right_trigger"];

    for control in controls {
        if let Some(button) = parse_button(&control.control_id) {
            processed_controls.push(processed_control(control));
            let Some(target) = button
                .checked_sub(1)
                .and_then(|index| BUTTON_TARGETS.get(usize::try_from(index).ok()?))
                .copied()
            else {
                diagnostics.push(mapping_diagnostic(control, None, "button_out_of_range"));
                continue;
            };
            if used_targets.insert(target.to_string()) {
                logical_controls.push(PersonaLogicalControlValue {
                    control_id: target.to_string(),
                    value: control.value,
                });
                diagnostics.push(mapping_diagnostic(control, Some(target), "button"));
            } else {
                diagnostics.push(mapping_diagnostic(control, None, "target_already_used"));
            }
            continue;
        }

        if control.control_id.starts_with("hat_") {
            processed_controls.push(processed_control(control));
            if used_targets.insert("hat".to_string()) {
                logical_controls.push(PersonaLogicalControlValue {
                    control_id: "hat".to_string(),
                    value: control.value,
                });
                diagnostics.push(mapping_diagnostic(control, Some("hat"), "first_hat"));
            } else {
                diagnostics.push(mapping_diagnostic(control, None, "target_already_used"));
            }
            continue;
        }

        if !matches!(
            control.value,
            NormalizedControlValue::Axis(_)
                | NormalizedControlValue::Trigger(_)
                | NormalizedControlValue::Unknown(_)
        ) || !control.control_id.starts_with("axis_")
        {
            continue;
        }

        processed_controls.push(processed_control(control));
        let targets = if matches!(control.value, NormalizedControlValue::Trigger(_)) {
            &TRIGGER_TARGETS[..]
        } else {
            &AXIS_TARGETS[..]
        };
        if let Some(target) = targets
            .iter()
            .copied()
            .find(|target| !used_targets.contains(*target))
        {
            used_targets.insert(target.to_string());
            logical_controls.push(PersonaLogicalControlValue {
                control_id: target.to_string(),
                value: control.value,
            });
            diagnostics.push(mapping_diagnostic(
                control,
                Some(target),
                "next_free_control",
            ));
        } else {
            diagnostics.push(mapping_diagnostic(control, None, "target_slots_full"));
        }
    }
}

fn map_buttons_and_hat(
    controls: &[&NormalizedCompositeValue],
    logical_controls: &mut Vec<PersonaLogicalControlValue>,
    diagnostics: &mut Vec<MappingDiagnosticEntry>,
    used_targets: &mut HashSet<String>,
    processed_controls: &mut Vec<ProcessedControl>,
) {
    for control in controls {
        if let Some(button) = parse_button(&control.control_id) {
            let target = format!("button_{button}");
            processed_controls.push(processed_control(control));
            if button <= 16 && used_targets.insert(target.clone()) {
                logical_controls.push(PersonaLogicalControlValue {
                    control_id: target.clone(),
                    value: control.value,
                });
                diagnostics.push(mapping_diagnostic(control, Some(&target), "button"));
            } else {
                let reason = if button > 16 {
                    "button_out_of_range"
                } else {
                    "target_already_used"
                };
                diagnostics.push(mapping_diagnostic(control, None, reason));
            }
            continue;
        }

        if control.control_id.starts_with("hat_") {
            processed_controls.push(processed_control(control));
            if used_targets.insert("hat".to_string()) {
                logical_controls.push(PersonaLogicalControlValue {
                    control_id: "hat".to_string(),
                    value: control.value,
                });
                diagnostics.push(mapping_diagnostic(control, Some("hat"), "first_hat"));
            } else {
                diagnostics.push(mapping_diagnostic(control, None, "target_already_used"));
            }
        }
    }
}

fn map_axes(
    controls: &[&NormalizedCompositeValue],
    logical_controls: &mut Vec<PersonaLogicalControlValue>,
    diagnostics: &mut Vec<MappingDiagnosticEntry>,
    used_targets: &mut HashSet<String>,
    processed_controls: &mut Vec<ProcessedControl>,
) {
    for control in controls {
        if !matches!(
            control.value,
            NormalizedControlValue::Axis(_)
                | NormalizedControlValue::Trigger(_)
                | NormalizedControlValue::Unknown(_)
        ) {
            continue;
        }
        if !control.control_id.starts_with("axis_") {
            continue;
        }

        let preferred = preferred_axis_target(&control.control_id);
        let target = preferred
            .filter(|target| !used_targets.contains(*target))
            .or_else(|| {
                AXIS_TARGETS
                    .iter()
                    .copied()
                    .find(|target| !used_targets.contains(*target))
            });

        processed_controls.push(processed_control(control));
        if let Some(target) = target {
            used_targets.insert(target.to_string());
            logical_controls.push(PersonaLogicalControlValue {
                control_id: target.to_string(),
                value: control.value,
            });
            let reason = if preferred == Some(target) {
                "preferred_axis"
            } else {
                "next_free_axis"
            };
            diagnostics.push(mapping_diagnostic(control, Some(target), reason));
        } else {
            diagnostics.push(mapping_diagnostic(control, None, "axis_slots_full"));
        }
    }
}

fn map_profile_rules(
    profile: &MappingProfile,
    controls: &[&NormalizedCompositeValue],
    logical_controls: &mut Vec<PersonaLogicalControlValue>,
    diagnostics: &mut Vec<MappingDiagnosticEntry>,
    used_targets: &mut HashSet<String>,
    processed_controls: &mut Vec<ProcessedControl>,
) {
    for rule in &profile.source_mappings {
        let Some(control) = controls
            .iter()
            .copied()
            .find(|control| profile_rule_matches(rule, control))
        else {
            continue;
        };

        processed_controls.push(processed_control(control));
        if used_targets.insert(rule.target_control_id.clone()) {
            let value = apply_rule_value(control.value, rule);
            logical_controls.push(PersonaLogicalControlValue {
                control_id: rule.target_control_id.clone(),
                value,
            });
            let reason = if rule.transform.is_some() || rule.deadzone.is_some() {
                "profile_rule_calibrated"
            } else if rule.invert {
                "profile_rule_inverted"
            } else {
                "profile_rule"
            };
            diagnostics.push(mapping_diagnostic(
                control,
                Some(&rule.target_control_id),
                reason,
            ));
        } else {
            diagnostics.push(mapping_diagnostic(control, None, "target_already_used"));
        }
    }
}

fn mark_unprocessed_controls(
    controls: &[&NormalizedCompositeValue],
    diagnostics: &mut Vec<MappingDiagnosticEntry>,
    processed_controls: &[ProcessedControl],
    reason: &str,
) {
    for control in controls {
        if !is_processed(control, processed_controls) {
            diagnostics.push(mapping_diagnostic(control, None, reason));
        }
    }
}

fn processed_control(control: &NormalizedCompositeValue) -> ProcessedControl {
    ProcessedControl {
        device: control.source.device.device_id.0,
        interface: control.source.interface_id.0,
        control: control.control_id.clone(),
    }
}

fn is_processed(control: &NormalizedCompositeValue, processed: &[ProcessedControl]) -> bool {
    let key = processed_control(control);
    processed.contains(&key)
}

fn mapping_diagnostic(
    control: &NormalizedCompositeValue,
    target: Option<&str>,
    reason: &str,
) -> MappingDiagnosticEntry {
    MappingDiagnosticEntry {
        source: control.source.clone(),
        source_control_id: control.control_id.clone(),
        source_value: control.value,
        target_control_id: target.map(str::to_string),
        reason: reason.to_string(),
    }
}

fn controls_in_source_priority(composite: &CompositeInputFrame) -> Vec<&NormalizedCompositeValue> {
    let mut source_scores = composite
        .sources
        .iter()
        .map(|source| {
            let mut unknown_count = 0_usize;
            let mut button_count = 0_usize;
            let mut axis_count = 0_usize;
            for control in composite
                .controls
                .iter()
                .filter(|control| control.source == *source)
            {
                match control.value {
                    NormalizedControlValue::Unknown(_) => unknown_count += 1,
                    NormalizedControlValue::Button(_) => button_count += 1,
                    NormalizedControlValue::Axis(_) | NormalizedControlValue::Trigger(_) => {
                        axis_count += 1;
                    }
                    NormalizedControlValue::Hat(_) => {}
                }
            }
            (
                source.clone(),
                unknown_count,
                std::cmp::Reverse(button_count),
                axis_count,
            )
        })
        .collect::<Vec<_>>();

    source_scores.sort_by_key(|(source, unknown_count, button_count, axis_count)| {
        (
            *unknown_count,
            *button_count,
            std::cmp::Reverse(*axis_count),
            source.device.device_id.0,
            source.interface_id.0,
        )
    });

    let mut ordered = Vec::new();
    for (source, ..) in source_scores {
        ordered.extend(
            composite
                .controls
                .iter()
                .filter(|control| control.source == source),
        );
    }
    ordered
}

fn parse_button(control_id: &str) -> Option<u32> {
    control_id.strip_prefix("button_")?.parse::<u32>().ok()
}

fn preferred_axis_target(control_id: &str) -> Option<&'static str> {
    match control_id {
        "axis_01_30" => Some("x"),
        "axis_01_31" => Some("y"),
        "axis_01_32" => Some("z"),
        "axis_01_33" => Some("rx"),
        "axis_01_34" => Some("ry"),
        "axis_01_35" => Some("rz"),
        _ => None,
    }
}

fn rule(product_id: u16, source_control_id: &str, target_control_id: &str) -> SourceMappingRule {
    SourceMappingRule {
        source_vendor_id: Some(THRUSTMASTER_VENDOR_ID),
        source_product_id: Some(product_id),
        source_interface_id: None,
        source_control_id: source_control_id.to_string(),
        target_control_id: target_control_id.to_string(),
        invert: false,
        deadzone: None,
        transform: None,
    }
}

fn profile_rule_matches(rule: &SourceMappingRule, control: &NormalizedCompositeValue) -> bool {
    rule.source_vendor_id
        .is_none_or(|vendor_id| vendor_id == control.source.device.vendor_id)
        && rule
            .source_product_id
            .is_none_or(|product_id| product_id == control.source.device.product_id)
        && rule
            .source_interface_id
            .is_none_or(|interface_id| interface_id == control.source.interface_id.0)
        && rule.source_control_id == control.control_id
}

fn apply_rule_value(
    value: NormalizedControlValue,
    rule: &SourceMappingRule,
) -> NormalizedControlValue {
    let mut value = maybe_invert(value, rule.invert);
    if let Some(deadzone) = rule.deadzone {
        value = apply_deadzone(value, deadzone);
    }
    if let Some(transform) = &rule.transform {
        value = apply_transform(value, transform);
    }
    value
}

const fn apply_deadzone(value: NormalizedControlValue, deadzone: i32) -> NormalizedControlValue {
    let deadzone = deadzone.abs();
    match value {
        NormalizedControlValue::Axis(raw) if raw.abs() <= deadzone => {
            NormalizedControlValue::Axis(0)
        }
        NormalizedControlValue::Trigger(raw) if raw.abs() <= deadzone => {
            NormalizedControlValue::Trigger(0)
        }
        NormalizedControlValue::Unknown(raw) if raw.abs() <= deadzone => {
            NormalizedControlValue::Unknown(0)
        }
        unchanged => unchanged,
    }
}

fn apply_transform(
    value: NormalizedControlValue,
    transform: &RuntimeTransform,
) -> NormalizedControlValue {
    match transform {
        RuntimeTransform::AxisToTrigger {
            source_min,
            source_max,
            invert,
        } => {
            let raw = scalar_value(value);
            let span = i64::from(*source_max) - i64::from(*source_min);
            if span == 0 {
                return NormalizedControlValue::Trigger(0);
            }
            let clamped = raw.clamp(
                (*source_min).min(*source_max),
                (*source_min).max(*source_max),
            );
            let mut scaled = ((i64::from(clamped) - i64::from(*source_min)) * 1_023) / span;
            if scaled.is_negative() {
                scaled = 0;
            }
            if *invert {
                scaled = 1_023 - scaled;
            }
            NormalizedControlValue::Trigger(i32::try_from(scaled.clamp(0, 1_023)).unwrap_or(0))
        }
    }
}

fn scalar_value(value: NormalizedControlValue) -> i32 {
    match value {
        NormalizedControlValue::Axis(value)
        | NormalizedControlValue::Trigger(value)
        | NormalizedControlValue::Unknown(value) => value,
        NormalizedControlValue::Button(value) => {
            if value {
                i32::from(i16::MAX)
            } else {
                0
            }
        }
        NormalizedControlValue::Hat(value) => i32::from(value),
    }
}

const fn maybe_invert(value: NormalizedControlValue, invert: bool) -> NormalizedControlValue {
    if !invert {
        return value;
    }

    match value {
        NormalizedControlValue::Axis(value) => NormalizedControlValue::Axis(-value),
        NormalizedControlValue::Trigger(value) => NormalizedControlValue::Trigger(-value),
        NormalizedControlValue::Unknown(value) => NormalizedControlValue::Unknown(-value),
        unchanged => unchanged,
    }
}

fn has_flight_pack_signatures(devices: &[DeviceSignature]) -> bool {
    let has_stick = devices.iter().any(|device| {
        device.vendor_id == THRUSTMASTER_VENDOR_ID && device.product_id == T16000_PRODUCT_ID
    });
    let has_twcs = devices.iter().any(|device| {
        device.vendor_id == THRUSTMASTER_VENDOR_ID && device.product_id == TWCS_PRODUCT_ID
    });
    has_stick && has_twcs
}

fn has_flight_pack_sources(composite: &CompositeInputFrame) -> bool {
    let has_stick = composite.sources.iter().any(|source| {
        source.device.vendor_id == THRUSTMASTER_VENDOR_ID
            && source.device.product_id == T16000_PRODUCT_ID
    });
    let has_twcs = composite.sources.iter().any(|source| {
        source.device.vendor_id == THRUSTMASTER_VENDOR_ID
            && source.device.product_id == TWCS_PRODUCT_ID
    });
    has_stick && has_twcs
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::{
        CompositeInputFrame, ConnectionTopology, DeviceId, InterfaceId, NormalizedCompositeValue,
        UsbDeviceRef, UsbInterfaceRef,
    };

    #[test]
    fn selects_generic_profile_when_devices_exist() {
        let mapper = GenericAutoMapper;
        assert_eq!(mapper.select_profile(&[]).unwrap(), None);
        assert_eq!(
            mapper
                .select_profile(&[DeviceSignature {
                    vendor_id: 0x044f,
                    product_id: 0xb10a,
                    interface_class: Some(3),
                    capability_fingerprint: None,
                }])
                .unwrap(),
            Some(GENERIC_AUTO_PROFILE_ID)
        );
    }

    #[test]
    fn selects_flight_pack_demo_profile_for_known_thrustmaster_pair() {
        let mapper = GenericAutoMapper;
        assert_eq!(
            mapper
                .select_profile(&[
                    DeviceSignature {
                        vendor_id: 0x044f,
                        product_id: 0xb10a,
                        interface_class: Some(3),
                        capability_fingerprint: None,
                    },
                    DeviceSignature {
                        vendor_id: 0x044f,
                        product_id: 0xb687,
                        interface_class: Some(3),
                        capability_fingerprint: None,
                    },
                ])
                .unwrap(),
            Some(FLIGHT_PACK_DEMO_PROFILE_ID)
        );
    }

    #[test]
    fn prioritizes_stick_like_source_for_primary_axes() {
        let throttle = source(2, 0x044f, 0xb687);
        let stick = source(3, 0x044f, 0xb10a);
        let composite = CompositeInputFrame {
            sources: vec![throttle.clone(), stick.clone()],
            controls: vec![
                value(
                    throttle.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(10),
                ),
                value(
                    throttle,
                    "usage_ff00_21_23",
                    NormalizedControlValue::Unknown(42),
                ),
                value(
                    stick.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(100),
                ),
                value(
                    stick.clone(),
                    "axis_01_31",
                    NormalizedControlValue::Axis(200),
                ),
                value(stick, "button_1", NormalizedControlValue::Button(true)),
            ],
            timestamp_micros: 7,
        };

        let frame = map_composite_to_generic_gamepad(&composite);

        assert_eq!(
            control(&frame, "x"),
            Some(NormalizedControlValue::Axis(100))
        );
        assert_eq!(
            control(&frame, "y"),
            Some(NormalizedControlValue::Axis(200))
        );
        assert_eq!(
            control(&frame, "button_1"),
            Some(NormalizedControlValue::Button(true))
        );
        assert_eq!(control(&frame, "z"), Some(NormalizedControlValue::Axis(10)));
    }

    #[test]
    fn maps_throttle_and_pedal_axes_into_remaining_slots() {
        let source = source(2, 0x044f, 0xb687);
        let composite = CompositeInputFrame {
            sources: vec![source.clone()],
            controls: vec![
                value(
                    source.clone(),
                    "axis_01_36",
                    NormalizedControlValue::Axis(-1000),
                ),
                value(
                    source.clone(),
                    "axis_01_37",
                    NormalizedControlValue::Axis(2000),
                ),
                value(source, "hat_01_39", NormalizedControlValue::Hat(8)),
            ],
            timestamp_micros: 9,
        };

        let frame = map_composite_to_generic_gamepad(&composite);

        assert_eq!(
            control(&frame, "x"),
            Some(NormalizedControlValue::Axis(-1000))
        );
        assert_eq!(
            control(&frame, "y"),
            Some(NormalizedControlValue::Axis(2000))
        );
        assert_eq!(control(&frame, "hat"), Some(NormalizedControlValue::Hat(8)));
    }

    #[test]
    fn diagnoses_mapped_and_unmapped_controls() {
        let throttle = source(2, 0xabcd, 0x0001);
        let stick = source(3, 0xabcd, 0x0002);
        let composite = CompositeInputFrame {
            sources: vec![throttle.clone(), stick.clone()],
            controls: vec![
                value(
                    throttle.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(10),
                ),
                value(
                    throttle,
                    "usage_ff00_21_23",
                    NormalizedControlValue::Unknown(42),
                ),
                value(
                    stick.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(100),
                ),
                value(
                    stick.clone(),
                    "axis_01_31",
                    NormalizedControlValue::Axis(200),
                ),
                value(stick, "button_1", NormalizedControlValue::Button(true)),
            ],
            timestamp_micros: 7,
        };

        let diagnostics = diagnose_generic_gamepad_mapping(&composite);

        assert_eq!(diagnostics.profile_id, GENERIC_AUTO_PROFILE_ID);
        assert_eq!(diagnostics.target_persona, GENERIC_GAMEPAD_PERSONA_ID);
        assert_eq!(diagnostics.entries.len(), 5);
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "axis_01_30"
                && entry.source.device.product_id == 0x0002
                && entry.target_control_id.as_deref() == Some("x")
                && entry.reason == "preferred_axis"
        }));
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "axis_01_30"
                && entry.source.device.product_id == 0x0001
                && entry.target_control_id.as_deref() == Some("z")
                && entry.reason == "next_free_axis"
        }));
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "usage_ff00_21_23"
                && entry.target_control_id.is_none()
                && entry.reason == "unsupported_control"
        }));
    }

    #[test]
    fn flight_pack_demo_profile_maps_curated_axes_before_auto_fallback() {
        let twcs = source(2, 0x044f, 0xb687);
        let stick = source(3, 0x044f, 0xb10a);
        let composite = CompositeInputFrame {
            sources: vec![twcs.clone(), stick.clone()],
            controls: vec![
                value(
                    twcs.clone(),
                    "axis_01_32",
                    NormalizedControlValue::Axis(-30_000),
                ),
                value(
                    twcs.clone(),
                    "axis_01_36",
                    NormalizedControlValue::Axis(3_000),
                ),
                value(twcs, "axis_01_30", NormalizedControlValue::Axis(11_111)),
                value(
                    stick.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(100),
                ),
                value(
                    stick.clone(),
                    "axis_01_31",
                    NormalizedControlValue::Axis(200),
                ),
                value(
                    stick.clone(),
                    "axis_01_35",
                    NormalizedControlValue::Axis(300),
                ),
                value(
                    stick.clone(),
                    "axis_01_36",
                    NormalizedControlValue::Axis(400),
                ),
                value(stick, "button_1", NormalizedControlValue::Button(true)),
            ],
            timestamp_micros: 11,
        };

        let profile = select_generic_gamepad_profile(&composite);
        let frame = GenericAutoMapper
            .map_to_persona_frame(&profile, &composite)
            .unwrap();
        let diagnostics = diagnose_generic_gamepad_mapping(&composite);

        assert_eq!(profile.profile_id, FLIGHT_PACK_DEMO_PROFILE_ID);
        assert_eq!(diagnostics.profile_id, FLIGHT_PACK_DEMO_PROFILE_ID);
        assert_eq!(
            control(&frame, "button_1"),
            Some(NormalizedControlValue::Button(true))
        );
        assert_eq!(
            control(&frame, "x"),
            Some(NormalizedControlValue::Axis(100))
        );
        assert_eq!(
            control(&frame, "y"),
            Some(NormalizedControlValue::Axis(200))
        );
        assert_eq!(
            control(&frame, "z"),
            Some(NormalizedControlValue::Axis(-30_000))
        );
        assert_eq!(
            control(&frame, "rx"),
            Some(NormalizedControlValue::Axis(3_000))
        );
        assert_eq!(
            control(&frame, "ry"),
            Some(NormalizedControlValue::Axis(400))
        );
        assert_eq!(
            control(&frame, "rz"),
            Some(NormalizedControlValue::Axis(300))
        );
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "axis_01_30"
                && entry.source.device.product_id == 0xb687
                && entry.target_control_id.is_none()
                && entry.reason == "profile_unmapped"
        }));
    }

    #[test]
    fn xbox_auto_profile_maps_controls_to_named_xbox_targets() {
        let source = source(1, 0xabcd, 0x0001);
        let composite = CompositeInputFrame {
            sources: vec![source.clone()],
            controls: vec![
                value(
                    source.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(-123),
                ),
                value(source.clone(), "hat_01_39", NormalizedControlValue::Hat(8)),
                value(source, "button_1", NormalizedControlValue::Button(true)),
            ],
            timestamp_micros: 13,
        };

        let profile = select_xbox_wireless_controller_profile(&composite);
        let frame = map_composite_to_xbox_wireless_controller(&composite);
        let diagnostics = diagnose_xbox_wireless_controller_mapping(&composite);

        assert_eq!(profile.profile_id, XBOX_AUTO_PROFILE_ID);
        assert_eq!(profile.target_persona, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(frame.persona_id, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(
            control(&frame, "left_x"),
            Some(NormalizedControlValue::Axis(-123))
        );
        assert_eq!(control(&frame, "hat"), Some(NormalizedControlValue::Hat(8)));
        assert_eq!(
            control(&frame, "a"),
            Some(NormalizedControlValue::Button(true))
        );
        assert_eq!(diagnostics.profile_id, XBOX_AUTO_PROFILE_ID);
        assert_eq!(
            diagnostics.target_persona,
            XBOX_WIRELESS_CONTROLLER_PERSONA_ID
        );
    }

    #[test]
    fn xbox_flight_pack_demo_profile_maps_curated_controls() {
        let twcs = source(2, 0x044f, 0xb687);
        let stick = source(3, 0x044f, 0xb10a);
        let composite = CompositeInputFrame {
            sources: vec![twcs.clone(), stick.clone()],
            controls: vec![
                value(
                    twcs.clone(),
                    "axis_01_32",
                    NormalizedControlValue::Axis(12_000),
                ),
                value(twcs, "axis_01_36", NormalizedControlValue::Axis(-12_000)),
                value(
                    stick.clone(),
                    "axis_01_30",
                    NormalizedControlValue::Axis(100),
                ),
                value(
                    stick.clone(),
                    "axis_01_31",
                    NormalizedControlValue::Axis(200),
                ),
                value(
                    stick.clone(),
                    "axis_01_35",
                    NormalizedControlValue::Axis(300),
                ),
                value(
                    stick.clone(),
                    "axis_01_36",
                    NormalizedControlValue::Axis(400),
                ),
                value(stick.clone(), "hat_01_39", NormalizedControlValue::Hat(0)),
                value(stick, "button_1", NormalizedControlValue::Button(true)),
            ],
            timestamp_micros: 17,
        };

        let profile = select_xbox_wireless_controller_profile(&composite);
        let frame = map_composite_to_xbox_wireless_controller(&composite);
        let diagnostics = diagnose_xbox_wireless_controller_mapping(&composite);

        assert_eq!(profile.profile_id, XBOX_FLIGHT_PACK_DEMO_PROFILE_ID);
        assert_eq!(profile.target_persona, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(
            control(&frame, "left_x"),
            Some(NormalizedControlValue::Axis(100))
        );
        assert_eq!(
            control(&frame, "left_y"),
            Some(NormalizedControlValue::Axis(200))
        );
        assert_eq!(
            control(&frame, "right_x"),
            Some(NormalizedControlValue::Axis(400))
        );
        assert_eq!(
            control(&frame, "right_y"),
            Some(NormalizedControlValue::Axis(300))
        );
        assert_eq!(
            control(&frame, "left_trigger"),
            Some(NormalizedControlValue::Axis(-12_000))
        );
        assert_eq!(
            control(&frame, "right_trigger"),
            Some(NormalizedControlValue::Axis(12_000))
        );
        assert_eq!(control(&frame, "hat"), Some(NormalizedControlValue::Hat(0)));
        assert_eq!(
            control(&frame, "a"),
            Some(NormalizedControlValue::Button(true))
        );
        assert_eq!(diagnostics.profile_id, XBOX_FLIGHT_PACK_DEMO_PROFILE_ID);
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "axis_01_30"
                && entry.source.device.product_id == 0xb10a
                && entry.target_control_id.as_deref() == Some("left_x")
                && entry.reason == "profile_rule"
        }));
    }

    #[test]
    fn profile_rule_supports_interface_deadzone_and_axis_to_trigger() {
        let iface0 = source_with_interface(1, 0x1234, 0x5678, 0);
        let iface1 = source_with_interface(1, 0x1234, 0x5678, 1);
        let composite = CompositeInputFrame {
            sources: vec![iface0.clone(), iface1.clone()],
            controls: vec![
                value(iface0, "axis_01_30", NormalizedControlValue::Axis(24)),
                value(
                    iface1,
                    "axis_01_30",
                    NormalizedControlValue::Axis(i32::from(i16::MAX)),
                ),
            ],
            timestamp_micros: 21,
        };
        let profile = MappingProfile {
            profile_id: ProfileId("custom_runtime"),
            display_name: "Custom".to_string(),
            supported_signatures: Vec::new(),
            target_persona: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            source_mappings: vec![SourceMappingRule {
                source_vendor_id: Some(0x1234),
                source_product_id: Some(0x5678),
                source_interface_id: Some(1),
                source_control_id: "axis_01_30".to_string(),
                target_control_id: "right_trigger".to_string(),
                invert: false,
                deadzone: Some(32),
                transform: Some(RuntimeTransform::AxisToTrigger {
                    source_min: i32::from(i16::MIN),
                    source_max: i32::from(i16::MAX),
                    invert: false,
                }),
            }],
            merge_policy: None,
        };

        let frame = map_composite_to_xbox_wireless_controller_with_profile(&profile, &composite);
        let diagnostics =
            diagnose_xbox_wireless_controller_mapping_with_profile(&profile, &composite);

        assert_eq!(
            control(&frame, "right_trigger"),
            Some(NormalizedControlValue::Trigger(1_023))
        );
        assert_eq!(diagnostics.entries[0].reason, "profile_rule_calibrated");
    }

    #[test]
    fn profile_rule_deadzone_zeroes_centered_values() {
        let source = source(1, 0x1234, 0x5678);
        let composite = CompositeInputFrame {
            sources: vec![source.clone()],
            controls: vec![value(
                source,
                "axis_01_30",
                NormalizedControlValue::Axis(12),
            )],
            timestamp_micros: 23,
        };
        let profile = MappingProfile {
            profile_id: ProfileId("custom_runtime"),
            display_name: "Custom".to_string(),
            supported_signatures: Vec::new(),
            target_persona: GENERIC_GAMEPAD_PERSONA_ID,
            source_mappings: vec![SourceMappingRule {
                source_vendor_id: Some(0x1234),
                source_product_id: Some(0x5678),
                source_interface_id: None,
                source_control_id: "axis_01_30".to_string(),
                target_control_id: "x".to_string(),
                invert: false,
                deadzone: Some(32),
                transform: None,
            }],
            merge_policy: None,
        };

        let frame = map_composite_to_generic_gamepad_with_profile(&profile, &composite);
        assert_eq!(control(&frame, "x"), Some(NormalizedControlValue::Axis(0)));
    }

    fn control(frame: &PersonaInputFrame, control_id: &str) -> Option<NormalizedControlValue> {
        frame
            .logical_controls
            .iter()
            .find(|control| control.control_id == control_id)
            .map(|control| control.value)
    }

    fn value(
        source: UsbInterfaceRef,
        control_id: &str,
        value: NormalizedControlValue,
    ) -> NormalizedCompositeValue {
        NormalizedCompositeValue {
            source,
            control_id: control_id.to_string(),
            value,
            timestamp_micros: 1,
        }
    }

    fn source(device_id: u32, vendor_id: u16, product_id: u16) -> UsbInterfaceRef {
        source_with_interface(device_id, vendor_id, product_id, 0)
    }

    fn source_with_interface(
        device_id: u32,
        vendor_id: u16,
        product_id: u16,
        interface_id: u32,
    ) -> UsbInterfaceRef {
        UsbInterfaceRef {
            device: UsbDeviceRef {
                device_id: DeviceId(device_id),
                topology: ConnectionTopology::Direct,
                vendor_id,
                product_id,
            },
            interface_id: InterfaceId(interface_id),
        }
    }
}
