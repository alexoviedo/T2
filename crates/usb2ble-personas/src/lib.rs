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

/// Stable persona ID for Xbox Wireless Controller BLE HID emulation.
pub const XBOX_WIRELESS_CONTROLLER_PERSONA_ID: PersonaId = PersonaId("xbox_wireless_controller");

/// HID report ID used by the Xbox Wireless Controller input report.
pub const XBOX_INPUT_REPORT_ID: ReportId = ReportId(1);

/// HID report ID used by the Xbox Wireless Controller rumble output report.
pub const XBOX_RUMBLE_REPORT_ID: ReportId = ReportId(3);

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

const XBOX_WIRELESS_CONTROLLER_REPORT_MAP: &[u8] = &[
    0x05, 0x01, 0x09, 0x05, 0xa1, 0x01, 0x85, 0x01, 0x09, 0x01, 0xa1, 0x00, 0x09, 0x30, 0x09, 0x31,
    0x15, 0x00, 0x27, 0xff, 0xff, 0x00, 0x00, 0x95, 0x02, 0x75, 0x10, 0x81, 0x02, 0xc0, 0x09, 0x01,
    0xa1, 0x00, 0x09, 0x32, 0x09, 0x35, 0x15, 0x00, 0x27, 0xff, 0xff, 0x00, 0x00, 0x95, 0x02, 0x75,
    0x10, 0x81, 0x02, 0xc0, 0x05, 0x02, 0x09, 0xc5, 0x15, 0x00, 0x26, 0xff, 0x03, 0x95, 0x01, 0x75,
    0x0a, 0x81, 0x02, 0x15, 0x00, 0x25, 0x00, 0x75, 0x06, 0x95, 0x01, 0x81, 0x03, 0x05, 0x02, 0x09,
    0xc4, 0x15, 0x00, 0x26, 0xff, 0x03, 0x95, 0x01, 0x75, 0x0a, 0x81, 0x02, 0x15, 0x00, 0x25, 0x00,
    0x75, 0x06, 0x95, 0x01, 0x81, 0x03, 0x05, 0x01, 0x09, 0x39, 0x15, 0x01, 0x25, 0x08, 0x35, 0x00,
    0x46, 0x3b, 0x01, 0x66, 0x14, 0x00, 0x75, 0x04, 0x95, 0x01, 0x81, 0x42, 0x75, 0x04, 0x95, 0x01,
    0x15, 0x00, 0x25, 0x00, 0x35, 0x00, 0x45, 0x00, 0x65, 0x00, 0x81, 0x03, 0x05, 0x09, 0x19, 0x01,
    0x29, 0x0f, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x0f, 0x81, 0x02, 0x15, 0x00, 0x25, 0x00,
    0x75, 0x01, 0x95, 0x01, 0x81, 0x03, 0x05, 0x0c, 0x0a, 0xb2, 0x00, 0x15, 0x00, 0x25, 0x01, 0x95,
    0x01, 0x75, 0x01, 0x81, 0x02, 0x15, 0x00, 0x25, 0x00, 0x75, 0x07, 0x95, 0x01, 0x81, 0x03, 0x05,
    0x0f, 0x09, 0x21, 0x85, 0x03, 0xa1, 0x02, 0x09, 0x97, 0x15, 0x00, 0x25, 0x01, 0x75, 0x04, 0x95,
    0x01, 0x91, 0x02, 0x15, 0x00, 0x25, 0x00, 0x75, 0x04, 0x95, 0x01, 0x91, 0x03, 0x09, 0x70, 0x15,
    0x00, 0x25, 0x64, 0x75, 0x08, 0x95, 0x04, 0x91, 0x02, 0x09, 0x50, 0x66, 0x01, 0x10, 0x55, 0x0e,
    0x15, 0x00, 0x26, 0xff, 0x00, 0x75, 0x08, 0x95, 0x01, 0x91, 0x02, 0x09, 0xa7, 0x15, 0x00, 0x26,
    0xff, 0x00, 0x75, 0x08, 0x95, 0x01, 0x91, 0x02, 0x65, 0x00, 0x55, 0x00, 0x09, 0x7c, 0x15, 0x00,
    0x26, 0xff, 0x00, 0x75, 0x08, 0x95, 0x01, 0x91, 0x02, 0xc0, 0xc0,
];

const AXIS_IDS: [&str; 6] = ["x", "y", "z", "rx", "ry", "rz"];
const XBOX_STICK_IDS: [&str; 4] = ["left_x", "left_y", "right_x", "right_y"];
const XBOX_TRIGGER_IDS: [&str; 2] = ["left_trigger", "right_trigger"];
const XBOX_BUTTON_IDS: [&str; 15] = [
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

/// Encoder for the Xbox Wireless Controller BLE HID persona.
#[derive(Debug, Default, Clone, Copy)]
pub struct XboxWirelessControllerEncoder;

impl PersonaEncoder for XboxWirelessControllerEncoder {
    fn descriptor(&self, persona_id: PersonaId) -> Result<PersonaDescriptor, PersonaError> {
        if persona_id != XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
            return Err(PersonaError::Generic);
        }

        Ok(PersonaDescriptor {
            persona_id,
            display_name: "Xbox Wireless Controller".to_string(),
            transport_family: BleTransportFamily::Xbox,
            report_map: XBOX_WIRELESS_CONTROLLER_REPORT_MAP.to_vec(),
            input_schema: xbox_wireless_controller_schema(),
        })
    }

    fn encode(&self, input: &PersonaInputFrame) -> Result<EncodedBleReport, PersonaError> {
        if input.persona_id != XBOX_WIRELESS_CONTROLLER_PERSONA_ID {
            return Err(PersonaError::Generic);
        }

        let mut sticks = [scale_axis_to_xbox(NormalizedControlValue::Axis(0)); 4];
        let mut triggers = [0_u16; 2];
        let mut hat = 0_u8;
        let mut buttons = 0_u16;
        let mut record = false;

        for logical in &input.logical_controls {
            if let Some(index) = XBOX_STICK_IDS
                .iter()
                .position(|control_id| *control_id == logical.control_id)
            {
                sticks[index] = scale_axis_to_xbox(logical.value);
                continue;
            }

            if let Some(index) = XBOX_TRIGGER_IDS
                .iter()
                .position(|control_id| *control_id == logical.control_id)
            {
                triggers[index] = scale_trigger_to_xbox(logical.value);
                continue;
            }

            if let Some(index) = XBOX_BUTTON_IDS
                .iter()
                .position(|control_id| *control_id == logical.control_id)
            {
                if matches!(logical.value, NormalizedControlValue::Button(true)) {
                    buttons |= 1_u16 << index;
                }
                continue;
            }

            if logical.control_id == "hat" {
                if let NormalizedControlValue::Hat(value) = logical.value {
                    hat = normalize_xbox_hat(value);
                }
                continue;
            }

            if matches!(logical.control_id.as_str(), "share" | "capture") {
                record = matches!(logical.value, NormalizedControlValue::Button(true));
            }
        }

        let mut bytes = Vec::with_capacity(16);
        for axis in sticks {
            bytes.extend_from_slice(&axis.to_le_bytes());
        }
        for trigger in triggers {
            bytes.extend_from_slice(&(trigger & 0x03ff).to_le_bytes());
        }
        bytes.push(hat & 0x0f);
        bytes.extend_from_slice(&(buttons & 0x7fff).to_le_bytes());
        bytes.push(u8::from(record));

        Ok(EncodedBleReport {
            persona_id: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
            report_id: XBOX_INPUT_REPORT_ID,
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

fn xbox_wireless_controller_schema() -> PersonaInputSchema {
    let mut controls = Vec::new();
    for axis in XBOX_STICK_IDS {
        controls.push(PersonaControlDescriptor {
            control_id: axis.to_string(),
            kind: PersonaControlKind::Axis,
            logical_min: 0,
            logical_max: 65_534,
        });
    }
    for trigger in XBOX_TRIGGER_IDS {
        controls.push(PersonaControlDescriptor {
            control_id: trigger.to_string(),
            kind: PersonaControlKind::Trigger,
            logical_min: 0,
            logical_max: 1_023,
        });
    }
    controls.push(PersonaControlDescriptor {
        control_id: "hat".to_string(),
        kind: PersonaControlKind::Hat,
        logical_min: 0,
        logical_max: 8,
    });
    for button in XBOX_BUTTON_IDS {
        controls.push(PersonaControlDescriptor {
            control_id: button.to_string(),
            kind: PersonaControlKind::Button,
            logical_min: 0,
            logical_max: 1,
        });
    }
    controls.push(PersonaControlDescriptor {
        control_id: "share".to_string(),
        kind: PersonaControlKind::Button,
        logical_min: 0,
        logical_max: 1,
    });
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

fn normalize_xbox_hat(value: i8) -> u8 {
    u8::try_from(value)
        .ok()
        .filter(|value| *value <= 8)
        .map_or(0, |value| if value == 8 { 0 } else { value + 1 })
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

fn scale_axis_to_xbox(value: NormalizedControlValue) -> u16 {
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
    let clamped = i64::from(raw.clamp(i32::from(i16::MIN), i32::from(i16::MAX)));
    let shifted = clamped + 32_768;
    u16::try_from((shifted * 65_534) / 65_535).unwrap_or(0)
}

fn scale_trigger_to_xbox(value: NormalizedControlValue) -> u16 {
    match value {
        NormalizedControlValue::Trigger(value) | NormalizedControlValue::Unknown(value) => {
            u16::try_from(value.clamp(0, 1_023)).unwrap_or(0)
        }
        NormalizedControlValue::Axis(_) => {
            let scaled = u32::from(scale_axis_to_xbox(value));
            u16::try_from((scaled * 1_023) / 65_534).unwrap_or(0)
        }
        NormalizedControlValue::Button(value) => {
            if value {
                1_023
            } else {
                0
            }
        }
        NormalizedControlValue::Hat(value) => u16::try_from(value.clamp(0, 8)).unwrap_or(0),
    }
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

    #[test]
    fn xbox_descriptor_exposes_report_map_and_schema() {
        let descriptor = XboxWirelessControllerEncoder
            .descriptor(XBOX_WIRELESS_CONTROLLER_PERSONA_ID)
            .unwrap();

        assert_eq!(descriptor.persona_id, XBOX_WIRELESS_CONTROLLER_PERSONA_ID);
        assert_eq!(descriptor.transport_family, BleTransportFamily::Xbox);
        assert_eq!(descriptor.report_map.len(), 283);
        assert!(
            descriptor
                .report_map
                .windows(2)
                .any(|bytes| bytes == [0x85, 0x03])
        );
        assert_eq!(descriptor.input_schema.controls.len(), 23);
    }

    #[test]
    fn xbox_encodes_neutral_report() {
        let report = XboxWirelessControllerEncoder
            .encode(&PersonaInputFrame {
                persona_id: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
                logical_controls: Vec::new(),
            })
            .unwrap();

        assert_eq!(report.report_id, XBOX_INPUT_REPORT_ID);
        assert_eq!(report.bytes.len(), 16);
        assert_eq!(&report.bytes[0..2], &32_767_u16.to_le_bytes());
        assert_eq!(&report.bytes[2..4], &32_767_u16.to_le_bytes());
        assert_eq!(&report.bytes[4..6], &32_767_u16.to_le_bytes());
        assert_eq!(&report.bytes[6..8], &32_767_u16.to_le_bytes());
        assert_eq!(&report.bytes[8..10], &0_u16.to_le_bytes());
        assert_eq!(&report.bytes[10..12], &0_u16.to_le_bytes());
        assert_eq!(report.bytes[12], 0);
        assert_eq!(&report.bytes[13..15], &0_u16.to_le_bytes());
        assert_eq!(report.bytes[15], 0);
    }

    #[test]
    fn xbox_encodes_axes_triggers_buttons_hat_and_share() {
        let report = XboxWirelessControllerEncoder
            .encode(&PersonaInputFrame {
                persona_id: XBOX_WIRELESS_CONTROLLER_PERSONA_ID,
                logical_controls: vec![
                    PersonaLogicalControlValue {
                        control_id: "left_x".to_string(),
                        value: NormalizedControlValue::Axis(i32::from(i16::MIN)),
                    },
                    PersonaLogicalControlValue {
                        control_id: "left_y".to_string(),
                        value: NormalizedControlValue::Axis(i32::from(i16::MAX)),
                    },
                    PersonaLogicalControlValue {
                        control_id: "right_x".to_string(),
                        value: NormalizedControlValue::Axis(0),
                    },
                    PersonaLogicalControlValue {
                        control_id: "right_trigger".to_string(),
                        value: NormalizedControlValue::Trigger(1_023),
                    },
                    PersonaLogicalControlValue {
                        control_id: "hat".to_string(),
                        value: NormalizedControlValue::Hat(0),
                    },
                    PersonaLogicalControlValue {
                        control_id: "a".to_string(),
                        value: NormalizedControlValue::Button(true),
                    },
                    PersonaLogicalControlValue {
                        control_id: "right_stick_press".to_string(),
                        value: NormalizedControlValue::Button(true),
                    },
                    PersonaLogicalControlValue {
                        control_id: "share".to_string(),
                        value: NormalizedControlValue::Button(true),
                    },
                ],
            })
            .unwrap();

        assert_eq!(&report.bytes[0..2], &0_u16.to_le_bytes());
        assert_eq!(&report.bytes[2..4], &65_534_u16.to_le_bytes());
        assert_eq!(&report.bytes[4..6], &32_767_u16.to_le_bytes());
        assert_eq!(&report.bytes[10..12], &1_023_u16.to_le_bytes());
        assert_eq!(report.bytes[12], 1);
        assert_eq!(&report.bytes[13..15], &(0b100_0000_0001_u16).to_le_bytes());
        assert_eq!(report.bytes[15], 1);
    }
}
