//! Mapping from composite normalized input into persona logical frames.

#![deny(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashSet;

use usb2ble_contracts::{
    CompositeInputFrame, DeviceSignature, Mapper, MappingDiagnosticEntry,
    MappingDiagnosticsResponse, MappingError, MappingProfile, NormalizedCompositeValue,
    NormalizedControlValue, PersonaId, PersonaInputFrame, PersonaLogicalControlValue, ProfileId,
};

/// Generic auto-mapping profile ID for the first demo path.
pub const GENERIC_AUTO_PROFILE_ID: ProfileId = ProfileId("generic_auto");

/// Generic Gamepad persona ID targeted by the auto mapper.
pub const GENERIC_GAMEPAD_PERSONA_ID: PersonaId = PersonaId("generic_gamepad");

const AXIS_TARGETS: [&str; 6] = ["x", "y", "z", "rx", "ry", "rz"];

/// Deterministic best-effort mapper for HID-like controller inputs.
#[derive(Debug, Default, Clone, Copy)]
pub struct GenericAutoMapper;

impl Mapper for GenericAutoMapper {
    fn select_profile(
        &self,
        devices: &[DeviceSignature],
    ) -> Result<Option<ProfileId>, MappingError> {
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

        Ok(map_composite_to_generic_gamepad(composite))
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
    map_composite_to_generic_gamepad_with_diagnostics(composite).diagnostics
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

fn map_composite_to_generic_gamepad_with_diagnostics(
    composite: &CompositeInputFrame,
) -> GenericGamepadMappingResult {
    let ordered_controls = controls_in_source_priority(composite);
    let mut logical_controls = Vec::new();
    let mut diagnostics = Vec::new();
    let mut used_targets = HashSet::new();
    let mut processed_controls = Vec::new();

    map_buttons_and_hat(
        &ordered_controls,
        &mut logical_controls,
        &mut diagnostics,
        &mut used_targets,
        &mut processed_controls,
    );
    map_axes(
        &ordered_controls,
        &mut logical_controls,
        &mut diagnostics,
        &mut used_targets,
        &mut processed_controls,
    );
    mark_unsupported_controls(&ordered_controls, &mut diagnostics, &processed_controls);

    GenericGamepadMappingResult {
        frame: PersonaInputFrame {
            persona_id: GENERIC_GAMEPAD_PERSONA_ID,
            logical_controls,
        },
        diagnostics: MappingDiagnosticsResponse {
            profile_id: GENERIC_AUTO_PROFILE_ID,
            target_persona: GENERIC_GAMEPAD_PERSONA_ID,
            entries: diagnostics,
        },
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

fn mark_unsupported_controls(
    controls: &[&NormalizedCompositeValue],
    diagnostics: &mut Vec<MappingDiagnosticEntry>,
    processed_controls: &[ProcessedControl],
) {
    for control in controls {
        if !is_processed(control, processed_controls) {
            diagnostics.push(mapping_diagnostic(control, None, "unsupported_control"));
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

        let diagnostics = diagnose_generic_gamepad_mapping(&composite);

        assert_eq!(diagnostics.profile_id, GENERIC_AUTO_PROFILE_ID);
        assert_eq!(diagnostics.target_persona, GENERIC_GAMEPAD_PERSONA_ID);
        assert_eq!(diagnostics.entries.len(), 5);
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "axis_01_30"
                && entry.source.device.product_id == 0xb10a
                && entry.target_control_id.as_deref() == Some("x")
                && entry.reason == "preferred_axis"
        }));
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "axis_01_30"
                && entry.source.device.product_id == 0xb687
                && entry.target_control_id.as_deref() == Some("z")
                && entry.reason == "next_free_axis"
        }));
        assert!(diagnostics.entries.iter().any(|entry| {
            entry.source_control_id == "usage_ff00_21_23"
                && entry.target_control_id.is_none()
                && entry.reason == "unsupported_control"
        }));
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
        UsbInterfaceRef {
            device: UsbDeviceRef {
                device_id: DeviceId(device_id),
                topology: ConnectionTopology::Direct,
                vendor_id,
                product_id,
            },
            interface_id: InterfaceId(0),
        }
    }
}
