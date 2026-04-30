//! Persona definitions and encoders.

#![deny(unsafe_code)]
#![warn(missing_docs)]

use usb2ble_contracts::{
    BleTransportFamily, EncodedBleReport, NormalizedControlValue, PersonaControlDescriptor,
    PersonaControlKind, PersonaDescriptor, PersonaEncoder, PersonaError, PersonaId,
    PersonaInputFrame, PersonaInputSchema, ReportId,
};

/// Stable persona ID for the first Generic Gamepad demo persona.
pub const GENERIC_GAMEPAD_PERSONA_ID: PersonaId = PersonaId("generic_gamepad");

/// HID report ID used by the Generic Gamepad input report.
pub const GENERIC_GAMEPAD_REPORT_ID: ReportId = ReportId(1);

const GENERIC_GAMEPAD_REPORT_MAP: &[u8] = &[
    0x05, 0x01, // Usage Page (Generic Desktop)
    0x09, 0x05, // Usage (Game Pad)
    0xa1, 0x01, // Collection (Application)
    0x85, 0x01, //   Report ID (1)
    0x05, 0x09, //   Usage Page (Button)
    0x19, 0x01, //   Usage Minimum (Button 1)
    0x29, 0x10, //   Usage Maximum (Button 16)
    0x15, 0x00, //   Logical Minimum (0)
    0x25, 0x01, //   Logical Maximum (1)
    0x75, 0x01, //   Report Size (1)
    0x95, 0x10, //   Report Count (16)
    0x81, 0x02, //   Input (Data,Var,Abs)
    0x05, 0x01, //   Usage Page (Generic Desktop)
    0x09, 0x39, //   Usage (Hat switch)
    0x15, 0x00, //   Logical Minimum (0)
    0x25, 0x07, //   Logical Maximum (7)
    0x35, 0x00, //   Physical Minimum (0)
    0x46, 0x3b, 0x01, //   Physical Maximum (315)
    0x65, 0x14, //   Unit (Eng Rot:Angular Pos)
    0x75, 0x04, //   Report Size (4)
    0x95, 0x01, //   Report Count (1)
    0x81, 0x42, //   Input (Data,Var,Abs,Null)
    0x65, 0x00, //   Unit (None)
    0x75, 0x04, //   Report Size (4)
    0x95, 0x01, //   Report Count (1)
    0x81, 0x03, //   Input (Const,Var,Abs)
    0x09, 0x30, //   Usage (X)
    0x09, 0x31, //   Usage (Y)
    0x09, 0x32, //   Usage (Z)
    0x09, 0x33, //   Usage (Rx)
    0x09, 0x34, //   Usage (Ry)
    0x09, 0x35, //   Usage (Rz)
    0x16, 0x00, 0x80, //   Logical Minimum (-32768)
    0x26, 0xff, 0x7f, //   Logical Maximum (32767)
    0x75, 0x10, //   Report Size (16)
    0x95, 0x06, //   Report Count (6)
    0x81, 0x02, //   Input (Data,Var,Abs)
    0xc0, // End Collection
];

const AXIS_IDS: [&str; 6] = ["x", "y", "z", "rx", "ry", "rz"];

/// Encoder for the fixed Generic Gamepad demo persona.
#[derive(Debug, Default, Clone, Copy)]
pub struct GenericGamepadEncoder;

impl PersonaEncoder for GenericGamepadEncoder {
    fn descriptor(&self, persona_id: PersonaId) -> Result<PersonaDescriptor, PersonaError> {
        if persona_id != GENERIC_GAMEPAD_PERSONA_ID {
            return Err(PersonaError::Generic);
        }

        Ok(PersonaDescriptor {
            persona_id,
            display_name: "USB2BLE Generic Gamepad".to_string(),
            transport_family: BleTransportFamily::Generic,
            report_map: GENERIC_GAMEPAD_REPORT_MAP.to_vec(),
            input_schema: generic_gamepad_schema(),
        })
    }

    fn encode(&self, input: &PersonaInputFrame) -> Result<EncodedBleReport, PersonaError> {
        if input.persona_id != GENERIC_GAMEPAD_PERSONA_ID {
            return Err(PersonaError::Generic);
        }

        let mut buttons = 0_u16;
        let mut hat = 8_u8;
        let mut axes = [0_i16; 6];

        for logical in &input.logical_controls {
            if let Some(index) = parse_button_index(&logical.control_id) {
                if matches!(logical.value, NormalizedControlValue::Button(true)) {
                    buttons |= 1_u16 << index;
                }
                continue;
            }

            if logical.control_id == "hat" {
                if let NormalizedControlValue::Hat(value) = logical.value {
                    hat = normalize_hat(value);
                }
                continue;
            }

            if let Some(index) = AXIS_IDS
                .iter()
                .position(|control_id| *control_id == logical.control_id)
            {
                axes[index] = normalize_axis(logical.value);
            }
        }

        let mut bytes = Vec::with_capacity(15);
        bytes.extend_from_slice(&buttons.to_le_bytes());
        bytes.push(hat);
        for axis in axes {
            bytes.extend_from_slice(&axis.to_le_bytes());
        }

        Ok(EncodedBleReport {
            persona_id: GENERIC_GAMEPAD_PERSONA_ID,
            report_id: GENERIC_GAMEPAD_REPORT_ID,
            bytes,
        })
    }
}

fn generic_gamepad_schema() -> PersonaInputSchema {
    let mut controls = Vec::new();
    for button in 1..=16 {
        controls.push(PersonaControlDescriptor {
            control_id: format!("button_{button}"),
            kind: PersonaControlKind::Button,
            logical_min: 0,
            logical_max: 1,
        });
    }
    controls.push(PersonaControlDescriptor {
        control_id: "hat".to_string(),
        kind: PersonaControlKind::Hat,
        logical_min: 0,
        logical_max: 8,
    });
    for axis in AXIS_IDS {
        controls.push(PersonaControlDescriptor {
            control_id: axis.to_string(),
            kind: PersonaControlKind::Axis,
            logical_min: i32::from(i16::MIN),
            logical_max: i32::from(i16::MAX),
        });
    }
    PersonaInputSchema { controls }
}

fn parse_button_index(control_id: &str) -> Option<u16> {
    let value = control_id.strip_prefix("button_")?.parse::<u16>().ok()?;
    (1..=16).contains(&value).then_some(value - 1)
}

fn normalize_hat(value: i8) -> u8 {
    u8::try_from(value)
        .ok()
        .filter(|value| *value <= 8)
        .unwrap_or(8)
}

fn normalize_axis(value: NormalizedControlValue) -> i16 {
    let raw = match value {
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
    };

    let clamped = raw.clamp(i32::from(i16::MIN), i32::from(i16::MAX));
    i16::try_from(clamped).unwrap_or_else(|_| {
        if clamped.is_negative() {
            i16::MIN
        } else {
            i16::MAX
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use usb2ble_contracts::PersonaLogicalControlValue;

    #[test]
    fn descriptor_exposes_generic_gamepad_report_map_and_schema() {
        let descriptor = GenericGamepadEncoder
            .descriptor(GENERIC_GAMEPAD_PERSONA_ID)
            .unwrap();

        assert_eq!(descriptor.persona_id, GENERIC_GAMEPAD_PERSONA_ID);
        assert_eq!(descriptor.transport_family, BleTransportFamily::Generic);
        assert!(!descriptor.report_map.is_empty());
        assert_eq!(descriptor.input_schema.controls.len(), 23);
    }

    #[test]
    fn encodes_neutral_report() {
        let report = GenericGamepadEncoder
            .encode(&PersonaInputFrame {
                persona_id: GENERIC_GAMEPAD_PERSONA_ID,
                logical_controls: Vec::new(),
            })
            .unwrap();

        assert_eq!(report.report_id, GENERIC_GAMEPAD_REPORT_ID);
        assert_eq!(report.bytes.len(), 15);
        assert_eq!(&report.bytes[0..3], &[0x00, 0x00, 0x08]);
        assert!(report.bytes[3..].iter().all(|byte| *byte == 0));
    }

    #[test]
    fn encodes_buttons_hat_and_axes() {
        let report = GenericGamepadEncoder
            .encode(&PersonaInputFrame {
                persona_id: GENERIC_GAMEPAD_PERSONA_ID,
                logical_controls: vec![
                    PersonaLogicalControlValue {
                        control_id: "button_1".to_string(),
                        value: NormalizedControlValue::Button(true),
                    },
                    PersonaLogicalControlValue {
                        control_id: "button_16".to_string(),
                        value: NormalizedControlValue::Button(true),
                    },
                    PersonaLogicalControlValue {
                        control_id: "hat".to_string(),
                        value: NormalizedControlValue::Hat(3),
                    },
                    PersonaLogicalControlValue {
                        control_id: "x".to_string(),
                        value: NormalizedControlValue::Axis(i32::from(i16::MIN)),
                    },
                    PersonaLogicalControlValue {
                        control_id: "rz".to_string(),
                        value: NormalizedControlValue::Axis(i32::from(i16::MAX)),
                    },
                ],
            })
            .unwrap();

        assert_eq!(&report.bytes[0..2], &0x8001_u16.to_le_bytes());
        assert_eq!(report.bytes[2], 3);
        assert_eq!(&report.bytes[3..5], &i16::MIN.to_le_bytes());
        assert_eq!(&report.bytes[13..15], &i16::MAX.to_le_bytes());
    }
}
