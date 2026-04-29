//! HID report descriptor parsing and capability summaries.
//!
//! M3 keeps this crate host-testable and target-safe: the same parser runs in
//! unit tests and in firmware app state once descriptors arrive from USB.

use usb2ble_contracts::{
    DecodedHidFieldValue, DecodedInputReport, HidAxisCapability, HidButtonCapability,
    HidCapabilitySummary, HidCollection, HidDecodeError, HidDescriptorIr, HidDescriptorParser,
    HidField, HidHatCapability, HidParseError, HidReportDecoder, InputReportPacket,
    ReportDescriptorBlob, ReportId,
};

const ITEM_TYPE_MAIN: u8 = 0;
const ITEM_TYPE_GLOBAL: u8 = 1;
const ITEM_TYPE_LOCAL: u8 = 2;

const MAIN_INPUT: u8 = 8;
const MAIN_COLLECTION: u8 = 10;

const GLOBAL_USAGE_PAGE: u8 = 0;
const GLOBAL_LOGICAL_MINIMUM: u8 = 1;
const GLOBAL_LOGICAL_MAXIMUM: u8 = 2;
const GLOBAL_REPORT_SIZE: u8 = 7;
const GLOBAL_REPORT_ID: u8 = 8;
const GLOBAL_REPORT_COUNT: u8 = 9;
const GLOBAL_PUSH: u8 = 10;
const GLOBAL_POP: u8 = 11;

const LOCAL_USAGE: u8 = 0;
const LOCAL_USAGE_MINIMUM: u8 = 1;
const LOCAL_USAGE_MAXIMUM: u8 = 2;

const INPUT_CONSTANT: u32 = 0x01;
const INPUT_VARIABLE: u32 = 0x02;
const INPUT_RELATIVE: u32 = 0x04;

const USAGE_PAGE_GENERIC_DESKTOP: u16 = 0x01;
const USAGE_PAGE_BUTTON: u16 = 0x09;
const USAGE_HAT_SWITCH: u32 = 0x39;

/// HID report descriptor parser.
#[derive(Debug, Default, Clone, Copy)]
pub struct HidParser;

impl HidDescriptorParser for HidParser {
    fn parse_descriptor(
        &self,
        blob: &ReportDescriptorBlob,
    ) -> Result<HidDescriptorIr, HidParseError> {
        parse_descriptor_bytes(&blob.bytes)
    }
}

impl HidReportDecoder for HidParser {
    fn decode_report(
        &self,
        ir: &HidDescriptorIr,
        report: &InputReportPacket,
    ) -> Result<DecodedInputReport, HidDecodeError> {
        decode_input_report(ir, report)
    }
}

/// Parse raw HID report descriptor bytes into the shared IR.
///
/// The M3 parser handles HID short items, global/local state, application
/// collections, and input fields. Output and feature reports are skipped until
/// a later milestone needs them.
pub fn parse_descriptor_bytes(bytes: &[u8]) -> Result<HidDescriptorIr, HidParseError> {
    if bytes.is_empty() {
        return Err(HidParseError::EmptyDescriptor);
    }

    let mut ir = HidDescriptorIr {
        collections: Vec::new(),
        fields: Vec::new(),
        report_ids: Vec::new(),
    };
    let mut global = GlobalState::default();
    let mut global_stack = Vec::new();
    let mut local = LocalState::default();
    let mut input_offsets = Vec::new();
    let mut i = 0usize;

    while i < bytes.len() {
        let prefix = bytes[i];
        i += 1;

        if prefix == 0xfe {
            return Err(HidParseError::UnsupportedLongItem);
        }

        let payload_len = short_item_payload_len(prefix);
        if i + payload_len > bytes.len() {
            return Err(HidParseError::TruncatedItem);
        }
        let payload = &bytes[i..i + payload_len];
        i += payload_len;

        let item_type = (prefix >> 2) & 0x03;
        let tag = (prefix >> 4) & 0x0f;

        match item_type {
            ITEM_TYPE_MAIN => handle_main_item(
                tag,
                payload,
                &global,
                &mut local,
                &mut input_offsets,
                &mut ir,
            )?,
            ITEM_TYPE_GLOBAL => handle_global_item(tag, payload, &mut global, &mut global_stack)?,
            ITEM_TYPE_LOCAL => handle_local_item(tag, payload, &mut local),
            _ => {}
        }
    }

    ensure_report_id(&mut ir.report_ids, ReportId(0));
    Ok(ir)
}

/// Build a compact capability summary from parsed HID IR.
#[must_use]
pub fn summarize_capabilities(ir: &HidDescriptorIr) -> HidCapabilitySummary {
    let mut axes = Vec::new();
    let mut buttons = Vec::new();
    let mut hats = Vec::new();

    for field in &ir.fields {
        if field.usage_page == USAGE_PAGE_BUTTON {
            buttons.push(HidButtonCapability {
                report_id: field.report_id,
                usage: field.usage,
                bit_offset: field.bit_offset,
            });
        } else if field.usage_page == USAGE_PAGE_GENERIC_DESKTOP && field.usage == USAGE_HAT_SWITCH
        {
            hats.push(HidHatCapability {
                report_id: field.report_id,
                usage_page: field.usage_page,
                usage: field.usage,
                bit_offset: field.bit_offset,
                bit_size: field.bit_size,
                logical_min: field.logical_min,
                logical_max: field.logical_max,
            });
        } else if is_generic_desktop_axis(field.usage_page, field.usage) {
            axes.push(HidAxisCapability {
                report_id: field.report_id,
                usage_page: field.usage_page,
                usage: field.usage,
                bit_offset: field.bit_offset,
                bit_size: field.bit_size,
                logical_min: field.logical_min,
                logical_max: field.logical_max,
            });
        }
    }

    HidCapabilitySummary {
        axes,
        buttons,
        hats,
        report_ids: ir.report_ids.clone(),
    }
}

/// Decode a raw HID input report using parsed descriptor IR.
pub fn decode_input_report(
    ir: &HidDescriptorIr,
    report: &InputReportPacket,
) -> Result<DecodedInputReport, HidDecodeError> {
    let report_id = effective_report_id(ir, report);
    let fields = ir
        .fields
        .iter()
        .filter(|field| field.report_id == report_id)
        .collect::<Vec<_>>();
    if fields.is_empty() && !ir.fields.is_empty() {
        return Err(HidDecodeError::ReportIdMismatch);
    }

    let mut values = Vec::new();
    for field in fields {
        let unsigned = extract_bits(&report.payload, field.bit_offset, field.bit_size)?;
        let value = if field.logical_min < 0 {
            sign_extend(unsigned, field.bit_size)
        } else {
            i32::try_from(unsigned).map_err(|_| HidDecodeError::Generic)?
        };
        values.push(DecodedHidFieldValue {
            report_id: field.report_id,
            usage_page: field.usage_page,
            usage: field.usage,
            value,
            logical_min: field.logical_min,
            logical_max: field.logical_max,
        });
    }

    Ok(DecodedInputReport {
        source: report.source.clone(),
        timestamp_micros: report.timestamp_micros,
        values,
    })
}

fn effective_report_id(ir: &HidDescriptorIr, report: &InputReportPacket) -> ReportId {
    if report.report_id.0 != 0 || !ir.report_ids.iter().any(|id| id.0 != 0) {
        return report.report_id;
    }

    report
        .payload
        .first()
        .copied()
        .map_or(report.report_id, ReportId)
}

#[derive(Debug, Clone, Copy)]
struct GlobalState {
    usage_page: u16,
    logical_min: i32,
    logical_max: i32,
    report_size: Option<u16>,
    report_count: Option<u16>,
    report_id: ReportId,
}

impl Default for GlobalState {
    fn default() -> Self {
        Self {
            usage_page: 0,
            logical_min: 0,
            logical_max: 0,
            report_size: None,
            report_count: None,
            report_id: ReportId(0),
        }
    }
}

#[derive(Debug, Default)]
struct LocalState {
    usages: Vec<u32>,
    usage_minimum: Option<u32>,
    usage_maximum: Option<u32>,
}

impl LocalState {
    fn clear(&mut self) {
        self.usages.clear();
        self.usage_minimum = None;
        self.usage_maximum = None;
    }
}

const fn short_item_payload_len(prefix: u8) -> usize {
    match prefix & 0x03 {
        0 => 0,
        1 => 1,
        2 => 2,
        _ => 4,
    }
}

fn handle_main_item(
    tag: u8,
    payload: &[u8],
    global: &GlobalState,
    local: &mut LocalState,
    input_offsets: &mut Vec<(ReportId, u32)>,
    ir: &mut HidDescriptorIr,
) -> Result<(), HidParseError> {
    match tag {
        MAIN_INPUT => {
            emit_input_fields(payload, global, local, input_offsets, ir)?;
            local.clear();
        }
        MAIN_COLLECTION => {
            ir.collections.push(HidCollection {});
            local.clear();
        }
        _ => local.clear(),
    }
    Ok(())
}

fn handle_global_item(
    tag: u8,
    payload: &[u8],
    global: &mut GlobalState,
    global_stack: &mut Vec<GlobalState>,
) -> Result<(), HidParseError> {
    match tag {
        GLOBAL_USAGE_PAGE => {
            global.usage_page =
                u16::try_from(unsigned_payload(payload)).map_err(|_| HidParseError::Generic)?;
        }
        GLOBAL_LOGICAL_MINIMUM => global.logical_min = signed_payload(payload),
        GLOBAL_LOGICAL_MAXIMUM => global.logical_max = signed_payload(payload),
        GLOBAL_REPORT_SIZE => {
            global.report_size =
                Some(u16::try_from(unsigned_payload(payload)).map_err(|_| HidParseError::Generic)?);
        }
        GLOBAL_REPORT_ID => {
            global.report_id = ReportId(
                u8::try_from(unsigned_payload(payload)).map_err(|_| HidParseError::Generic)?,
            );
        }
        GLOBAL_REPORT_COUNT => {
            global.report_count =
                Some(u16::try_from(unsigned_payload(payload)).map_err(|_| HidParseError::Generic)?);
        }
        GLOBAL_PUSH => global_stack.push(*global),
        GLOBAL_POP => {
            if let Some(restored) = global_stack.pop() {
                *global = restored;
            }
        }
        _ => {}
    }
    Ok(())
}

fn handle_local_item(tag: u8, payload: &[u8], local: &mut LocalState) {
    match tag {
        LOCAL_USAGE => local.usages.push(unsigned_payload(payload)),
        LOCAL_USAGE_MINIMUM => local.usage_minimum = Some(unsigned_payload(payload)),
        LOCAL_USAGE_MAXIMUM => local.usage_maximum = Some(unsigned_payload(payload)),
        _ => {}
    }
}

fn emit_input_fields(
    payload: &[u8],
    global: &GlobalState,
    local: &LocalState,
    input_offsets: &mut Vec<(ReportId, u32)>,
    ir: &mut HidDescriptorIr,
) -> Result<(), HidParseError> {
    let flags = unsigned_payload(payload);
    let report_size = global.report_size.ok_or(HidParseError::MissingReportSize)?;
    let report_count = global
        .report_count
        .ok_or(HidParseError::MissingReportCount)?;
    let offset = input_offset_mut(input_offsets, global.report_id);
    let total_bits = u32::from(report_size) * u32::from(report_count);

    ensure_report_id(&mut ir.report_ids, global.report_id);
    if flags & INPUT_CONSTANT != 0 {
        *offset = offset.saturating_add(total_bits);
        return Ok(());
    }

    let is_variable = flags & INPUT_VARIABLE != 0;
    let is_relative = flags & INPUT_RELATIVE != 0;
    for idx in 0..usize::from(report_count) {
        let idx_u32 = u32::try_from(idx).map_err(|_| HidParseError::Generic)?;
        let bit_offset = offset.saturating_add(idx_u32 * u32::from(report_size));
        ir.fields.push(HidField {
            report_id: global.report_id,
            usage_page: global.usage_page,
            usage: usage_for_index(local, idx),
            bit_offset,
            bit_size: report_size,
            logical_min: global.logical_min,
            logical_max: global.logical_max,
            is_array: !is_variable,
            is_variable,
            is_relative,
        });
    }

    *offset = offset.saturating_add(total_bits);
    Ok(())
}

fn input_offset_mut(offsets: &mut Vec<(ReportId, u32)>, report_id: ReportId) -> &mut u32 {
    if let Some(pos) = offsets.iter().position(|(id, _)| *id == report_id) {
        return &mut offsets[pos].1;
    }

    let initial_offset = if report_id.0 == 0 { 0 } else { 8 };
    offsets.push((report_id, initial_offset));
    let pos = offsets.len() - 1;
    &mut offsets[pos].1
}

fn usage_for_index(local: &LocalState, index: usize) -> u32 {
    if let Some(usage) = local.usages.get(index).copied() {
        return usage;
    }

    if let Some(usage) = local.usages.last().copied() {
        return usage;
    }

    if let Some(minimum) = local.usage_minimum {
        let offset = u32::try_from(index).unwrap_or(u32::MAX);
        let usage = minimum.saturating_add(offset);
        if let Some(maximum) = local.usage_maximum {
            return usage.min(maximum);
        }
        return usage;
    }

    0
}

fn ensure_report_id(report_ids: &mut Vec<ReportId>, report_id: ReportId) {
    if !report_ids.contains(&report_id) {
        report_ids.push(report_id);
    }
}

fn unsigned_payload(payload: &[u8]) -> u32 {
    match payload {
        [a] => u32::from(*a),
        [a, b] => u32::from(u16::from_le_bytes([*a, *b])),
        [a, b, c, d] => u32::from_le_bytes([*a, *b, *c, *d]),
        _ => 0,
    }
}

fn signed_payload(payload: &[u8]) -> i32 {
    match payload {
        [a] => i32::from(i8::from_le_bytes([*a])),
        [a, b] => i32::from(i16::from_le_bytes([*a, *b])),
        [a, b, c, d] => i32::from_le_bytes([*a, *b, *c, *d]),
        _ => 0,
    }
}

fn is_generic_desktop_axis(usage_page: u16, usage: u32) -> bool {
    usage_page == USAGE_PAGE_GENERIC_DESKTOP && (0x30..=0x38).contains(&usage)
}

fn extract_bits(payload: &[u8], bit_offset: u32, bit_size: u16) -> Result<u32, HidDecodeError> {
    if bit_size == 0 || bit_size > 32 {
        return Err(HidDecodeError::Generic);
    }

    let end_bit = bit_offset.saturating_add(u32::from(bit_size));
    let payload_bits =
        u32::try_from(payload.len().saturating_mul(8)).map_err(|_| HidDecodeError::Generic)?;
    if end_bit > payload_bits {
        return Err(HidDecodeError::TruncatedReport);
    }

    let mut value = 0u32;
    for bit_idx in 0..u32::from(bit_size) {
        let source_bit = bit_offset + bit_idx;
        let byte = payload[(source_bit / 8) as usize];
        let bit = (byte >> (source_bit % 8)) & 1;
        value |= u32::from(bit) << bit_idx;
    }

    Ok(value)
}

fn sign_extend(value: u32, bit_size: u16) -> i32 {
    let sign_bit = 1u32 << (u32::from(bit_size) - 1);
    if value & sign_bit == 0 {
        return i32::try_from(value).unwrap_or(i32::MAX);
    }

    let signed = i64::from(value) - (1_i64 << u32::from(bit_size));
    i32::try_from(signed).unwrap_or(i32::MIN)
}

#[cfg(test)]
mod tests {
    use super::{HidParser, decode_input_report, parse_descriptor_bytes, summarize_capabilities};
    use usb2ble_contracts::{
        ConnectionTopology, DeviceId, HidDescriptorParser, InputReportPacket, InterfaceId,
        ReportDescriptorBlob, ReportId, UsbDeviceRef, UsbInterfaceRef,
    };

    const T16000_DESCRIPTOR_HEX: &str =
        include_str!("../fixtures/thrustmaster_t16000_fcs_044f_b10a_report_descriptor.hex");
    const T16000_REPORT_HEX: &str = "00000f711f2a1f7600070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00";

    #[test]
    fn parses_t16000_descriptor_fixture_into_expected_ir() {
        let bytes = decode_hex(T16000_DESCRIPTOR_HEX);
        let ir = parse_descriptor_bytes(&bytes).expect("fixture should parse");

        assert_eq!(ir.collections.len(), 1);
        assert_eq!(ir.report_ids, vec![ReportId(0)]);
        assert_eq!(ir.fields.len(), 21);

        let first_button = &ir.fields[0];
        assert_eq!(first_button.usage_page, 0x09);
        assert_eq!(first_button.usage, 1);
        assert_eq!(first_button.bit_offset, 0);
        assert_eq!(first_button.bit_size, 1);

        let hat = &ir.fields[16];
        assert_eq!(hat.usage_page, 0x01);
        assert_eq!(hat.usage, 0x39);
        assert_eq!(hat.bit_offset, 16);
        assert_eq!(hat.bit_size, 4);

        let axes = [
            &ir.fields[17],
            &ir.fields[18],
            &ir.fields[19],
            &ir.fields[20],
        ];
        assert_eq!(axes.map(|field| field.usage), [0x30, 0x31, 0x35, 0x36]);
        assert_eq!(axes.map(|field| field.bit_offset), [24, 40, 56, 64]);
    }

    #[test]
    fn summarizes_t16000_capabilities() {
        let bytes = decode_hex(T16000_DESCRIPTOR_HEX);
        let ir = parse_descriptor_bytes(&bytes).expect("fixture should parse");
        let summary = summarize_capabilities(&ir);

        assert_eq!(summary.report_ids, vec![ReportId(0)]);
        assert_eq!(summary.buttons.len(), 16);
        assert_eq!(summary.hats.len(), 1);
        assert_eq!(summary.axes.len(), 4);
        assert_eq!(
            summary
                .axes
                .iter()
                .map(|axis| axis.usage)
                .collect::<Vec<_>>(),
            vec![0x30, 0x31, 0x35, 0x36]
        );
    }

    #[test]
    fn parser_trait_matches_byte_parser() {
        let bytes = decode_hex(T16000_DESCRIPTOR_HEX);
        let blob = ReportDescriptorBlob {
            source: UsbInterfaceRef {
                device: UsbDeviceRef {
                    device_id: DeviceId(2),
                    topology: ConnectionTopology::Direct,
                    vendor_id: 0x044f,
                    product_id: 0xb10a,
                },
                interface_id: InterfaceId(0),
            },
            bytes: bytes.clone(),
        };

        let parser = HidParser;
        assert_eq!(
            parser.parse_descriptor(&blob).expect("trait parser"),
            parse_descriptor_bytes(&bytes).expect("byte parser")
        );
    }

    #[test]
    fn decodes_t16000_report_fixture() {
        let descriptor = decode_hex(T16000_DESCRIPTOR_HEX);
        let ir = parse_descriptor_bytes(&descriptor).expect("fixture should parse");
        let report = InputReportPacket {
            source: test_source(),
            report_id: ReportId(0),
            payload: decode_hex(T16000_REPORT_HEX),
            timestamp_micros: 123,
        };

        let decoded = decode_input_report(&ir, &report).expect("report should decode");
        assert_eq!(decoded.values.len(), 21);
        assert_eq!(decoded.values[0].usage_page, 0x09);
        assert_eq!(decoded.values[0].usage, 1);
        assert_eq!(decoded.values[0].value, 0);
        assert_eq!(decoded.values[16].usage, 0x39);
        assert_eq!(decoded.values[16].value, 15);
        assert_eq!(
            decoded.values[17..=20]
                .iter()
                .map(|value| (value.usage, value.value))
                .collect::<Vec<_>>(),
            vec![(0x30, 8049), (0x31, 7978), (0x35, 118), (0x36, 0)]
        );
    }

    #[test]
    fn rejects_truncated_short_item() {
        let err = parse_descriptor_bytes(&[0x26, 0xff]).expect_err("truncated item");
        assert_eq!(err, usb2ble_contracts::HidParseError::TruncatedItem);
    }

    #[test]
    fn rejects_truncated_report() {
        let descriptor = decode_hex(T16000_DESCRIPTOR_HEX);
        let ir = parse_descriptor_bytes(&descriptor).expect("fixture should parse");
        let report = InputReportPacket {
            source: test_source(),
            report_id: ReportId(0),
            payload: vec![0],
            timestamp_micros: 0,
        };

        let err = decode_input_report(&ir, &report).expect_err("report too short");
        assert_eq!(err, usb2ble_contracts::HidDecodeError::TruncatedReport);
    }

    #[test]
    fn infers_report_id_from_payload_when_platform_does_not_set_it() {
        let ir = parse_descriptor_bytes(&[
            0x05, 0x01, // Usage Page (Generic Desktop)
            0x09, 0x30, // Usage (X)
            0x15, 0x00, // Logical Minimum (0)
            0x26, 0xff, 0x00, // Logical Maximum (255)
            0x75, 0x08, // Report Size (8)
            0x95, 0x01, // Report Count (1)
            0x85, 0x01, // Report ID (1)
            0x81, 0x02, // Input (Data, Variable, Absolute)
        ])
        .expect("descriptor should parse");
        let report = InputReportPacket {
            source: test_source(),
            report_id: ReportId(0),
            payload: vec![1, 42],
            timestamp_micros: 0,
        };

        let decoded = decode_input_report(&ir, &report).expect("report id should be inferred");
        assert_eq!(decoded.values.len(), 1);
        assert_eq!(decoded.values[0].report_id, ReportId(1));
        assert_eq!(decoded.values[0].usage, 0x30);
        assert_eq!(decoded.values[0].value, 42);
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

    fn decode_hex(input: &str) -> Vec<u8> {
        let compact = input
            .chars()
            .filter(|c| !c.is_whitespace())
            .collect::<String>();
        assert_eq!(compact.len() % 2, 0);

        compact
            .as_bytes()
            .chunks_exact(2)
            .map(|chunk| {
                let text = std::str::from_utf8(chunk).expect("fixture is utf8");
                u8::from_str_radix(text, 16).expect("fixture is hex")
            })
            .collect()
    }
}
