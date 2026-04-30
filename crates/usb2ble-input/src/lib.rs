//! Input normalization from decoded HID fields into project control frames.

use usb2ble_contracts::{
    CompositeInputFrame, CompositeMerger, CompositeProfile, DecodedHidFieldValue,
    DecodedInputReport, HidDescriptorIr, InputNormalizer, MergeError, NormalizeError,
    NormalizedCompositeValue, NormalizedControlEvent, NormalizedControlValue, NormalizedInputFrame,
};

const USAGE_PAGE_GENERIC_DESKTOP: u16 = 0x01;
const USAGE_PAGE_BUTTON: u16 = 0x09;
const USAGE_HAT_SWITCH: u32 = 0x39;

/// Default input normalizer used for M4 diagnostics.
#[derive(Debug, Default, Clone, Copy)]
pub struct StandardInputNormalizer;

impl InputNormalizer for StandardInputNormalizer {
    fn normalize(
        &self,
        _ir: &HidDescriptorIr,
        decoded: &DecodedInputReport,
    ) -> Result<NormalizedInputFrame, NormalizeError> {
        Ok(normalize_decoded_report(decoded))
    }
}

/// Simple merger that flattens the latest source frames into one composite frame.
#[derive(Debug, Default, Clone, Copy)]
pub struct LatestInputMerger;

impl CompositeMerger for LatestInputMerger {
    fn merge(
        &self,
        inputs: &[NormalizedInputFrame],
        _profile: &CompositeProfile,
    ) -> Result<CompositeInputFrame, MergeError> {
        Ok(merge_latest_inputs(inputs))
    }
}

/// Flatten the latest normalized frames while retaining source identity.
#[must_use]
pub fn merge_latest_inputs(inputs: &[NormalizedInputFrame]) -> CompositeInputFrame {
    let mut sources = Vec::new();
    let mut controls = Vec::new();
    let mut timestamp_micros = 0;

    for frame in inputs {
        if !sources.contains(&frame.source) {
            sources.push(frame.source.clone());
        }
        for control in &frame.controls {
            timestamp_micros = timestamp_micros.max(control.timestamp_micros);
            controls.push(NormalizedCompositeValue {
                source: control.source.clone(),
                control_id: control.control_id.clone(),
                value: control.value,
                timestamp_micros: control.timestamp_micros,
            });
        }
    }

    CompositeInputFrame {
        sources,
        controls,
        timestamp_micros,
    }
}

/// Normalize a decoded HID report into a stable control frame.
#[must_use]
pub fn normalize_decoded_report(decoded: &DecodedInputReport) -> NormalizedInputFrame {
    let controls = decoded
        .values
        .iter()
        .enumerate()
        .map(|(index, field)| NormalizedControlEvent {
            source: decoded.source.clone(),
            control_id: control_id(field, index),
            value: normalized_value(field),
            timestamp_micros: decoded.timestamp_micros,
        })
        .collect();

    NormalizedInputFrame {
        source: decoded.source.clone(),
        controls,
    }
}

fn control_id(field: &DecodedHidFieldValue, index: usize) -> String {
    if field.usage_page == USAGE_PAGE_BUTTON {
        format!("button_{}", field.usage)
    } else if field.usage_page == USAGE_PAGE_GENERIC_DESKTOP && field.usage == USAGE_HAT_SWITCH {
        format!("hat_{:02x}_{:x}", field.usage_page, field.usage)
    } else if field.usage_page == USAGE_PAGE_GENERIC_DESKTOP && (0x30..=0x38).contains(&field.usage)
    {
        format!("axis_{:02x}_{:x}", field.usage_page, field.usage)
    } else {
        format!("usage_{:02x}_{:x}_{index}", field.usage_page, field.usage)
    }
}

fn normalized_value(field: &DecodedHidFieldValue) -> NormalizedControlValue {
    if field.usage_page == USAGE_PAGE_BUTTON {
        NormalizedControlValue::Button(field.value != 0)
    } else if field.usage_page == USAGE_PAGE_GENERIC_DESKTOP && field.usage == USAGE_HAT_SWITCH {
        NormalizedControlValue::Hat(i8::try_from(field.value).unwrap_or(i8::MAX))
    } else if field.usage_page == USAGE_PAGE_GENERIC_DESKTOP && (0x30..=0x38).contains(&field.usage)
    {
        NormalizedControlValue::Axis(normalize_axis(
            field.value,
            field.logical_min,
            field.logical_max,
        ))
    } else {
        NormalizedControlValue::Unknown(field.value)
    }
}

fn normalize_axis(value: i32, logical_min: i32, logical_max: i32) -> i32 {
    if logical_max <= logical_min {
        return value;
    }

    let clamped = value.clamp(logical_min, logical_max);
    let numerator = i64::from(clamped - logical_min) * 65_535;
    let denominator = i64::from(logical_max - logical_min);
    let scaled = (numerator / denominator) - 32_768;
    i32::try_from(scaled).unwrap_or_else(|_| {
        if scaled.is_negative() {
            i32::MIN
        } else {
            i32::MAX
        }
    })
}

#[cfg(test)]
mod tests {
    use super::{
        LatestInputMerger, StandardInputNormalizer, merge_latest_inputs, normalize_decoded_report,
    };
    use usb2ble_contracts::{
        CompositeMerger, ConnectionTopology, DecodedHidFieldValue, DecodedInputReport, DeviceId,
        HidDescriptorIr, InputNormalizer, InterfaceId, NormalizedControlEvent,
        NormalizedControlValue, NormalizedInputFrame, ReportId, UsbDeviceRef, UsbInterfaceRef,
    };

    #[test]
    fn normalizes_buttons_hat_and_axes() {
        let decoded = DecodedInputReport {
            source: test_source(),
            timestamp_micros: 123,
            values: vec![
                field(0x09, 1, 1, 0, 1),
                field(0x01, 0x39, 15, 0, 7),
                field(0x01, 0x30, 8_191, 0, 16_383),
            ],
        };

        let frame = normalize_decoded_report(&decoded);
        assert_eq!(frame.controls.len(), 3);
        assert_eq!(
            frame.controls[0].value,
            usb2ble_contracts::NormalizedControlValue::Button(true)
        );
        assert_eq!(
            frame.controls[1].value,
            usb2ble_contracts::NormalizedControlValue::Hat(15)
        );
        assert_eq!(frame.controls[2].control_id, "axis_01_30");
    }

    #[test]
    fn trait_normalizer_matches_helper() {
        let decoded = DecodedInputReport {
            source: test_source(),
            timestamp_micros: 123,
            values: vec![field(0x09, 1, 0, 0, 1)],
        };
        let ir = HidDescriptorIr {
            collections: Vec::new(),
            fields: Vec::new(),
            report_ids: vec![ReportId(0)],
        };

        let normalizer = StandardInputNormalizer;
        assert_eq!(
            normalizer.normalize(&ir, &decoded).expect("normalizes"),
            normalize_decoded_report(&decoded)
        );
    }

    #[test]
    fn unknown_controls_include_position_to_keep_ids_unique() {
        let decoded = DecodedInputReport {
            source: test_source(),
            timestamp_micros: 123,
            values: vec![
                field(0xff00, 0x21, 1, 0, 255),
                field(0xff00, 0x21, 2, 0, 255),
            ],
        };

        let frame = normalize_decoded_report(&decoded);
        assert_eq!(frame.controls[0].control_id, "usage_ff00_21_0");
        assert_eq!(frame.controls[1].control_id, "usage_ff00_21_1");
    }

    #[test]
    fn latest_merger_flattens_frames_and_keeps_sources() {
        let source = test_source();
        let frame = NormalizedInputFrame {
            source: source.clone(),
            controls: vec![NormalizedControlEvent {
                source,
                control_id: "axis_01_30".to_string(),
                value: NormalizedControlValue::Axis(12),
                timestamp_micros: 456,
            }],
        };

        let composite = merge_latest_inputs(std::slice::from_ref(&frame));
        assert_eq!(composite.sources.len(), 1);
        assert_eq!(composite.controls.len(), 1);
        assert_eq!(composite.timestamp_micros, 456);
        assert_eq!(composite.controls[0].control_id, "axis_01_30");

        let via_trait = LatestInputMerger
            .merge(&[frame], &usb2ble_contracts::CompositeProfile::default())
            .unwrap();
        assert_eq!(via_trait.controls.len(), 1);
    }

    fn field(
        usage_page: u16,
        usage: u32,
        value: i32,
        logical_min: i32,
        logical_max: i32,
    ) -> DecodedHidFieldValue {
        DecodedHidFieldValue {
            report_id: ReportId(0),
            usage_page,
            usage,
            value,
            logical_min,
            logical_max,
        }
    }

    fn test_source() -> UsbInterfaceRef {
        UsbInterfaceRef {
            device: UsbDeviceRef {
                device_id: DeviceId(2),
                topology: ConnectionTopology::Direct,
                vendor_id: 0x044f,
                product_id: 0xb10a,
            },
            interface_id: InterfaceId(0),
        }
    }
}
