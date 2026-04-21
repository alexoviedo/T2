//! usb2ble-contracts
//!
//! The stable shared type/trait surface for the whole workspace.

use heapless;

pub type ContractVersion = u32;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct DeviceId(pub u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct InterfaceId(pub u32);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct EndpointAddress(pub u8);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ReportId(pub u8);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ProfileId(pub &'static str);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct PersonaId(pub &'static str);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct MappingId(pub &'static str);

// --- USB Topology ---

pub struct HubPath {
    pub ports: heapless::Vec<u8, 8>,
}

pub enum ConnectionTopology {
    Direct,
    ViaHub { path: HubPath },
}

pub struct UsbDeviceRef {
    pub device_id: DeviceId,
    pub topology: ConnectionTopology,
    pub vendor_id: u16,
    pub product_id: u16,
    pub interface_id: Option<InterfaceId>,
}

pub struct ReportDescriptorBlob {
    pub source: UsbDeviceRef,
    pub bytes: Vec<u8>,
}

pub struct InputReportPacket {
    pub source: UsbDeviceRef,
    pub report_id: ReportId,
    pub payload: Vec<u8>,
    pub timestamp_micros: u64,
}

#[derive(Debug)]
pub enum UsbIngressWarningCode {
    // Placeholder
    Generic,
}

#[derive(Debug)]
pub enum UsbIngressErrorCode {
    // Placeholder
    Generic,
}

pub enum UsbIngressEvent {
    DeviceAttached(UsbDeviceRef),
    DeviceDetached {
        source: UsbDeviceRef,
    },
    InterfaceDiscovered {
        source: UsbDeviceRef,
        class_code: u8,
        subclass_code: u8,
        protocol_code: u8,
    },
    ReportDescriptorReceived(ReportDescriptorBlob),
    InputReportReceived(InputReportPacket),
    TransportWarning {
        source: Option<UsbDeviceRef>,
        code: UsbIngressWarningCode,
    },
    TransportError {
        source: Option<UsbDeviceRef>,
        code: UsbIngressErrorCode,
    },
}

pub trait UsbIngress {
    fn poll_event(&mut self) -> Option<UsbIngressEvent>;
}

// --- HID ---

pub struct HidDescriptorIr {
    pub collections: Vec<HidCollection>,
    pub fields: Vec<HidField>,
    pub report_ids: Vec<ReportId>,
}

pub struct HidCollection {
    // Placeholder
}

pub struct HidField {
    pub report_id: ReportId,
    pub usage_page: u16,
    pub usage: u32,
    pub bit_offset: u32,
    pub bit_size: u16,
    pub logical_min: i32,
    pub logical_max: i32,
    pub is_array: bool,
    pub is_variable: bool,
    pub is_relative: bool,
}

#[derive(Debug)]
pub enum HidParseError {
    // Placeholder
}

pub trait HidDescriptorParser {
    fn parse_descriptor(
        &self,
        blob: &ReportDescriptorBlob,
    ) -> Result<HidDescriptorIr, HidParseError>;
}

pub struct HidCapabilitySummary {
    pub axes: Vec<HidAxisCapability>,
    pub buttons: Vec<HidButtonCapability>,
    pub hats: Vec<HidHatCapability>,
    pub report_ids: Vec<ReportId>,
}

pub struct HidAxisCapability {}
pub struct HidButtonCapability {}
pub struct HidHatCapability {}

pub struct DecodedInputReport {
    // Placeholder
}

#[derive(Debug)]
pub enum HidDecodeError {
    // Placeholder
}

pub trait HidReportDecoder {
    fn decode_report(
        &self,
        ir: &HidDescriptorIr,
        report: &InputReportPacket,
    ) -> Result<DecodedInputReport, HidDecodeError>;
}

// --- Input Normalization ---

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NormalizedControlValue {
    Axis(i32),
    Button(bool),
    Hat(i8),
    Trigger(i32),
    Unknown(i32),
}

pub struct NormalizedControlEvent {
    pub source: UsbDeviceRef,
    pub control_id: String,
    pub value: NormalizedControlValue,
    pub timestamp_micros: u64,
}

pub struct NormalizedInputFrame {
    pub source: UsbDeviceRef,
    pub controls: Vec<NormalizedControlEvent>,
}

pub struct NormalizedCompositeValue {
    // Placeholder
}

pub struct CompositeInputFrame {
    pub sources: Vec<UsbDeviceRef>,
    pub controls: Vec<NormalizedCompositeValue>,
    pub timestamp_micros: u64,
}

#[derive(Debug)]
pub enum NormalizeError {
    // Placeholder
}

pub trait InputNormalizer {
    fn normalize(
        &self,
        ir: &HidDescriptorIr,
        decoded: &DecodedInputReport,
    ) -> Result<NormalizedInputFrame, NormalizeError>;
}

pub struct CompositeProfile {
    // Placeholder
}

#[derive(Debug)]
pub enum MergeError {
    // Placeholder
}

pub trait CompositeMerger {
    fn merge(
        &self,
        inputs: &[NormalizedInputFrame],
        profile: &CompositeProfile,
    ) -> Result<CompositeInputFrame, MergeError>;
}

// --- Mapping ---

pub struct DeviceSignature {
    pub vendor_id: u16,
    pub product_id: u16,
    pub interface_class: Option<u8>,
    pub capability_fingerprint: Option<String>,
}

pub struct SourceMappingRule {
    // Placeholder
}

pub struct MappingProfile {
    pub profile_id: ProfileId,
    pub display_name: String,
    pub supported_signatures: Vec<DeviceSignature>,
    pub target_persona: PersonaId,
    pub source_mappings: Vec<SourceMappingRule>,
    pub merge_policy: Option<CompositeProfile>,
}

#[derive(Debug)]
pub enum MappingError {
    // Placeholder
}

pub trait Mapper {
    fn select_profile(&self, devices: &[DeviceSignature]) -> Result<Option<ProfileId>, MappingError>;

    fn map_to_persona_frame(
        &self,
        profile: &MappingProfile,
        composite: &CompositeInputFrame,
    ) -> Result<PersonaInputFrame, MappingError>;
}

// --- Personas ---

pub enum BleTransportFamily {
    Generic,
    Xbox,
}

pub struct PersonaInputSchema {
    // Placeholder
}

pub struct PersonaDescriptor {
    pub persona_id: PersonaId,
    pub display_name: String,
    pub transport_family: BleTransportFamily,
    pub report_map: Vec<u8>,
    pub input_schema: PersonaInputSchema,
}

pub struct PersonaLogicalControlValue {
    // Placeholder
}

pub struct PersonaInputFrame {
    pub persona_id: PersonaId,
    pub logical_controls: Vec<PersonaLogicalControlValue>,
}

pub struct EncodedBleReport {
    pub persona_id: PersonaId,
    pub report_id: ReportId,
    pub bytes: Vec<u8>,
}

#[derive(Debug)]
pub enum PersonaError {
    // Placeholder
}

pub trait PersonaEncoder {
    fn descriptor(&self, persona_id: PersonaId) -> Result<PersonaDescriptor, PersonaError>;
    fn encode(&self, input: &PersonaInputFrame) -> Result<EncodedBleReport, PersonaError>;
}

// --- BLE Transport ---

pub enum BleLinkState {
    Idle,
    Initializing,
    Advertising,
    Connected,
    Error,
}

#[derive(Debug)]
pub enum BleTransportError {
    // Placeholder
}

pub trait BleTransport {
    fn current_state(&self) -> BleLinkState;

    fn activate_persona(&mut self, descriptor: &PersonaDescriptor) -> Result<(), BleTransportError>;

    fn publish_report(&mut self, report: &EncodedBleReport) -> Result<(), BleTransportError>;

    fn forget_bonds(&mut self) -> Result<(), BleTransportError>;
}

// --- Storage ---

#[derive(Debug)]
pub enum StoreError {
    // Placeholder
}

pub struct RuntimeConfig {
    // Placeholder
}

pub trait ProfileStore {
    fn load_active_profile(&self) -> Result<Option<ProfileId>, StoreError>;
    fn save_active_profile(&mut self, profile: ProfileId) -> Result<(), StoreError>;
}

pub trait ConfigStore {
    fn load_config(&self) -> Result<Option<RuntimeConfig>, StoreError>;
    fn save_config(&mut self, config: &RuntimeConfig) -> Result<(), StoreError>;
}

pub trait BondStore {
    fn bonds_present(&self) -> Result<bool, StoreError>;
    fn clear_bonds(&mut self) -> Result<(), StoreError>;
}

// --- Control Plane ---

pub struct ControlCommand {
    // Placeholder
}

pub struct ControlResponse {
    // Placeholder
}

#[derive(Debug)]
pub enum ControlError {
    // Placeholder
}

pub trait ControlPlane {
    fn decode_command(&self, bytes: &[u8]) -> Result<ControlCommand, ControlError>;
    fn encode_response(&self, response: &ControlResponse) -> Result<Vec<u8>, ControlError>;
}

// --- App Orchestration ---

pub struct AppState {
    pub known_devices: Vec<UsbDeviceRef>,
    pub descriptors: Vec<(DeviceId, HidDescriptorIr)>,
    pub active_profile: Option<ProfileId>,
    pub active_persona: Option<PersonaId>,
    pub ble_state: BleLinkState,
}

// --- Diagnostics ---

pub struct BootInfo {}
pub struct UsbDiagnosticEvent {}
pub struct HidDiagnosticEvent {}
pub struct MappingDiagnosticEvent {}
pub struct BleDiagnosticEvent {}
pub struct StoreDiagnosticEvent {}
pub struct ControlDiagnosticEvent {}

pub enum DiagnosticEvent {
    Boot(BootInfo),
    Usb(UsbDiagnosticEvent),
    Hid(HidDiagnosticEvent),
    Mapping(MappingDiagnosticEvent),
    Ble(BleDiagnosticEvent),
    Store(StoreDiagnosticEvent),
    Control(ControlDiagnosticEvent),
}
