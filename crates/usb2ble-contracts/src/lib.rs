//! usb2ble-contracts
//!
//! The stable shared type/trait surface for the whole workspace.
//! All crates must treat these contracts as authoritative.

#![deny(unsafe_code)]
#![warn(missing_docs)]

/// The current version of the project contracts.
pub const CONTRACT_VERSION: u32 = 1;

/// A note on contract compatibility.
pub const CONTRACT_COMPATIBILITY_NOTE: &str = "Initial M0 baseline contracts.";

/// Shared identity types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct DeviceId(pub u32);

/// Unique identifier for a USB interface.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct InterfaceId(pub u32);

/// Address of a USB endpoint.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct EndpointAddress(pub u8);

/// Identifier for an HID report.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ReportId(pub u8);

/// Stable string identifier for a profile.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ProfileId(pub &'static str);

/// Stable string identifier for a BLE persona.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct PersonaId(pub &'static str);

/// Stable string identifier for a mapping.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct MappingId(pub &'static str);

// --- USB Topology ---

/// Path through a USB hub tree.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HubPath {
    /// Ordered list of port numbers from the root host.
    pub ports: heapless::Vec<u8, 8>,
}

/// Representation of a device's position in the USB topology.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConnectionTopology {
    /// Device is connected directly to the root host.
    Direct,
    /// Device is connected via one or more hubs.
    ViaHub {
        /// The path to the device.
        path: HubPath,
    },
}

/// A stable reference to a USB device session.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UsbDeviceRef {
    /// Session-stable device identifier.
    pub device_id: DeviceId,
    /// Topology metadata.
    pub topology: ConnectionTopology,
    /// USB Vendor ID.
    pub vendor_id: u16,
    /// USB Product ID.
    pub product_id: u16,
}

/// A stable reference to a USB interface.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UsbInterfaceRef {
    /// Source device reference.
    pub device: UsbDeviceRef,
    /// Interface identifier.
    pub interface_id: InterfaceId,
}

/// Raw HID report descriptor bytes from a specific source.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReportDescriptorBlob {
    /// The USB source interface.
    pub source: UsbInterfaceRef,
    /// Raw descriptor bytes.
    pub bytes: Vec<u8>,
}

/// A single input report received from a USB device.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InputReportPacket {
    /// The USB source interface.
    pub source: UsbInterfaceRef,
    /// HID report ID.
    pub report_id: ReportId,
    /// Raw report payload.
    pub payload: Vec<u8>,
    /// Host-relative timestamp in microseconds.
    pub timestamp_micros: u64,
}

/// Non-fatal warnings from the USB ingress layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UsbIngressWarningCode {
    /// Generic unspecified warning.
    Generic,
}

/// Fatal errors from the USB ingress layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UsbIngressErrorCode {
    /// Generic unspecified error.
    Generic,
}

/// High-level events from the USB ingress layer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UsbIngressEvent {
    /// A new USB device has been attached.
    DeviceAttached(UsbDeviceRef),
    /// A USB device has been detached.
    DeviceDetached {
        /// Reference to the detached device.
        source: UsbDeviceRef,
    },
    /// A USB HID interface was discovered on a device.
    InterfaceDiscovered {
        /// The source interface.
        source: UsbInterfaceRef,
        /// HID class code.
        class_code: u8,
        /// HID subclass code.
        subclass_code: u8,
        /// HID protocol code.
        protocol_code: u8,
    },
    /// A raw HID descriptor was successfully received.
    ReportDescriptorReceived(ReportDescriptorBlob),
    /// A raw HID input report was received.
    InputReportReceived(InputReportPacket),
    /// A non-fatal transport warning occurred.
    TransportWarning {
        /// Affected device, if known.
        source: Option<UsbDeviceRef>,
        /// Warning detail.
        code: UsbIngressWarningCode,
    },
    /// A fatal transport error occurred.
    TransportError {
        /// Affected device, if known.
        source: Option<UsbDeviceRef>,
        /// Error detail.
        code: UsbIngressErrorCode,
    },
}

/// Trait for polling USB ingress events.
pub trait UsbIngress {
    /// Poll for the next available event.
    fn poll_event(&mut self) -> Option<UsbIngressEvent>;
}

// --- HID ---

/// Intermediate representation of an HID descriptor.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HidDescriptorIr {
    /// Logical collections defined in the descriptor.
    pub collections: Vec<HidCollection>,
    /// Individual HID fields (inputs, outputs, features).
    pub fields: Vec<HidField>,
    /// All report IDs referenced in the descriptor.
    pub report_ids: Vec<ReportId>,
}

/// A logical grouping of HID fields.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HidCollection {
    // Placeholder for M3
}

/// Metadata for a single field within an HID report.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HidField {
    /// Report ID this field belongs to.
    pub report_id: ReportId,
    /// HID usage page.
    pub usage_page: u16,
    /// HID usage ID.
    pub usage: u32,
    /// Offset in bits within the report payload.
    pub bit_offset: u32,
    /// Size in bits.
    pub bit_size: u16,
    /// Logical minimum value.
    pub logical_min: i32,
    /// Logical maximum value.
    pub logical_max: i32,
    /// True if the field is an array.
    pub is_array: bool,
    /// True if the field is a variable.
    pub is_variable: bool,
    /// True if values are relative.
    pub is_relative: bool,
}

/// Errors occurring during HID descriptor parsing.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HidParseError {
    /// Generic parsing failure.
    Generic,
}

/// Trait for parsing raw HID descriptors into IR.
pub trait HidDescriptorParser {
    /// Parse a raw blob into a structured IR.
    fn parse_descriptor(
        &self,
        blob: &ReportDescriptorBlob,
    ) -> Result<HidDescriptorIr, HidParseError>;
}

/// High-level summary of a device's HID capabilities.
pub struct HidCapabilitySummary {
    /// Available axes.
    pub axes: Vec<HidAxisCapability>,
    /// Available buttons.
    pub buttons: Vec<HidButtonCapability>,
    /// Available hat switches.
    pub hats: Vec<HidHatCapability>,
    /// List of all report IDs.
    pub report_ids: Vec<ReportId>,
}

/// Metadata for an axis capability.
pub struct HidAxisCapability {}
/// Metadata for a button capability.
pub struct HidButtonCapability {}
/// Metadata for a hat switch capability.
pub struct HidHatCapability {}

/// A decoded HID input report.
pub struct DecodedInputReport {
    // Placeholder for M4
}

/// Errors occurring during HID report decoding.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HidDecodeError {
    /// Generic decoding failure.
    Generic,
}

/// Trait for decoding raw HID reports using a parsed IR.
pub trait HidReportDecoder {
    /// Decode a raw packet into a structured report.
    fn decode_report(
        &self,
        ir: &HidDescriptorIr,
        report: &InputReportPacket,
    ) -> Result<DecodedInputReport, HidDecodeError>;
}

// --- Input Normalization ---

/// A normalized value for a controller input.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NormalizedControlValue {
    /// A signed 32-bit axis value.
    Axis(i32),
    /// A boolean button state.
    Button(bool),
    /// A hat switch position.
    Hat(i8),
    /// A trigger value.
    Trigger(i32),
    /// An unknown or unmapped control value.
    Unknown(i32),
}

/// A normalized event from a specific source control.
pub struct NormalizedControlEvent {
    /// The USB source interface.
    pub source: UsbInterfaceRef,
    /// Stable identifier for the control.
    pub control_id: String,
    /// Normalized value.
    pub value: NormalizedControlValue,
    /// Event timestamp in microseconds.
    pub timestamp_micros: u64,
}

/// A full frame of normalized input from a single source.
pub struct NormalizedInputFrame {
    /// The USB source interface.
    pub source: UsbInterfaceRef,
    /// List of control updates in this frame.
    pub controls: Vec<NormalizedControlEvent>,
}

/// A normalized value within a composite frame.
pub struct NormalizedCompositeValue {
    // Placeholder for M9
}

/// A composed frame representing state from multiple sources.
pub struct CompositeInputFrame {
    /// All contributing USB sources.
    pub sources: Vec<UsbInterfaceRef>,
    /// Composed control states.
    pub controls: Vec<NormalizedCompositeValue>,
    /// Aggregated timestamp.
    pub timestamp_micros: u64,
}

/// Errors occurring during input normalization.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NormalizeError {
    /// Generic normalization failure.
    Generic,
}

/// Trait for normalizing decoded HID reports.
pub trait InputNormalizer {
    /// Normalize a decoded report into a standard frame.
    fn normalize(
        &self,
        ir: &HidDescriptorIr,
        decoded: &DecodedInputReport,
    ) -> Result<NormalizedInputFrame, NormalizeError>;
}

/// Policy for merging multiple inputs.
pub struct CompositeProfile {
    // Placeholder for M9
}

/// Errors occurring during input merging.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MergeError {
    /// Generic merge failure.
    Generic,
}

/// Trait for merging multiple normalized frames into one composite frame.
pub trait CompositeMerger {
    /// Merge several frames into one logical composite state.
    fn merge(
        &self,
        inputs: &[NormalizedInputFrame],
        profile: &CompositeProfile,
    ) -> Result<CompositeInputFrame, MergeError>;
}

// --- Mapping ---

/// A signature used to identify a USB device for mapping.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeviceSignature {
    /// USB Vendor ID.
    pub vendor_id: u16,
    /// USB Product ID.
    pub product_id: u16,
    /// Optional interface class.
    pub interface_class: Option<u8>,
    /// Optional unique fingerprint based on capabilities.
    pub capability_fingerprint: Option<String>,
}

/// A rule defining how a source input maps to a target.
pub struct SourceMappingRule {
    // Placeholder for M6
}

/// A full profile defining mapping and target persona.
pub struct MappingProfile {
    /// Unique profile identifier.
    pub profile_id: ProfileId,
    /// Human-readable name.
    pub display_name: String,
    /// List of devices this profile supports.
    pub supported_signatures: Vec<DeviceSignature>,
    /// The target BLE persona.
    pub target_persona: PersonaId,
    /// Rules for mapping source controls.
    pub source_mappings: Vec<SourceMappingRule>,
    /// Optional policy for multi-device merging.
    pub merge_policy: Option<CompositeProfile>,
}

/// Errors occurring during mapping operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MappingError {
    /// Generic mapping failure.
    Generic,
}

/// Trait for profile selection and remapping to persona frames.
pub trait Mapper {
    /// Select the best profile for a given set of devices.
    fn select_profile(
        &self,
        devices: &[DeviceSignature],
    ) -> Result<Option<ProfileId>, MappingError>;

    /// Map a composite frame into a persona-specific input frame.
    fn map_to_persona_frame(
        &self,
        profile: &MappingProfile,
        composite: &CompositeInputFrame,
    ) -> Result<PersonaInputFrame, MappingError>;
}

// --- Personas ---

/// Major families of BLE transports.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BleTransportFamily {
    /// Generic HID Gamepad.
    Generic,
    /// Emulated Xbox Wireless Controller.
    Xbox,
}

/// Schema for a persona's expected logical input.
pub struct PersonaInputSchema {
    // Placeholder for M5
}

/// Full definition of a BLE output persona.
pub struct PersonaDescriptor {
    /// Unique persona identifier.
    pub persona_id: PersonaId,
    /// Human-readable name.
    pub display_name: String,
    /// Transport family.
    pub transport_family: BleTransportFamily,
    /// Raw HID report map for BLE.
    pub report_map: Vec<u8>,
    /// Expected input schema.
    pub input_schema: PersonaInputSchema,
}

/// A logical control value for a persona.
pub struct PersonaLogicalControlValue {
    // Placeholder for M5
}

/// A frame of input ready for persona encoding.
pub struct PersonaInputFrame {
    /// The target persona.
    pub persona_id: PersonaId,
    /// Logical control values.
    pub logical_controls: Vec<PersonaLogicalControlValue>,
}

/// An encoded report ready for BLE transmission.
pub struct EncodedBleReport {
    /// The persona that generated this report.
    pub persona_id: PersonaId,
    /// BLE/HID report ID.
    pub report_id: ReportId,
    /// Encoded wire bytes.
    pub bytes: Vec<u8>,
}

/// Errors occurring during persona operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PersonaError {
    /// Generic persona failure.
    Generic,
}

/// Trait for encoding persona frames into wire reports.
pub trait PersonaEncoder {
    /// Get the full descriptor for a persona.
    fn descriptor(&self, persona_id: PersonaId) -> Result<PersonaDescriptor, PersonaError>;
    /// Encode a logical frame into a wire-ready report.
    fn encode(&self, input: &PersonaInputFrame) -> Result<EncodedBleReport, PersonaError>;
}

// --- BLE Transport ---

/// State of the BLE link.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BleLinkState {
    /// BLE is off or idle.
    Idle,
    /// BLE stack is initializing.
    Initializing,
    /// Device is advertising.
    Advertising,
    /// Device is connected to a host.
    Connected,
    /// A fatal BLE error occurred.
    Error,
}

/// Errors occurring during BLE transport operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BleTransportError {
    /// Generic transport failure.
    Generic,
}

/// Trait for abstracting the underlying BLE stack.
pub trait BleTransport {
    /// Get the current link state.
    fn current_state(&self) -> BleLinkState;

    /// Activate a specific persona on the BLE stack.
    fn activate_persona(&mut self, descriptor: &PersonaDescriptor)
    -> Result<(), BleTransportError>;

    /// Publish an encoded report to the connected host.
    fn publish_report(&mut self, report: &EncodedBleReport) -> Result<(), BleTransportError>;

    /// Clear all stored bonding information.
    fn forget_bonds(&mut self) -> Result<(), BleTransportError>;
}

// --- Storage ---

/// Errors occurring during storage operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StoreError {
    /// Generic storage failure.
    Generic,
}

/// Runtime configuration of the project.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuntimeConfig {
    // Placeholder for M7
}

/// Trait for persisting the active profile.
pub trait ProfileStore {
    /// Load the last saved active profile ID.
    fn load_active_profile(&self) -> Result<Option<ProfileId>, StoreError>;
    /// Save the current active profile ID.
    fn save_active_profile(&mut self, profile: ProfileId) -> Result<(), StoreError>;
}

/// Trait for persisting runtime configuration.
pub trait ConfigStore {
    /// Load the current runtime configuration.
    fn load_config(&self) -> Result<Option<RuntimeConfig>, StoreError>;
    /// Save a new runtime configuration.
    fn save_config(&mut self, config: &RuntimeConfig) -> Result<(), StoreError>;
}

/// Trait for persisting BLE bonding information.
pub trait BondStore {
    /// Returns true if any bonds are currently stored.
    fn bonds_present(&self) -> Result<bool, StoreError>;
    /// Clear all stored bonding information.
    fn clear_bonds(&mut self) -> Result<(), StoreError>;
}

// --- Control Plane ---

/// Response payload for `GET_INFO`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InfoResponse {
    /// The current contract version.
    pub contract_version: u32,
    /// Human-readable firmware name.
    pub firmware_name: &'static str,
    /// Active persona info.
    pub active_persona: Option<PersonaId>,
}

/// Response payload for `GET_STATUS`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StatusResponse {
    /// Current BLE link state.
    pub ble_state: BleLinkState,
    /// Active profile ID.
    pub active_profile: Option<ProfileId>,
    /// Whether any bonds are present.
    pub bonds_present: bool,
}

/// Response payload for `GET_PROFILE`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProfileResponse {
    /// The currently active profile.
    pub active_profile: Option<ProfileId>,
}

/// Response payload for `GET_USB_STATUS`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UsbStatusResponse {
    /// Number of physical devices.
    pub physical_devices: usize,
    /// Total number of HID interfaces discovered.
    pub total_interfaces: usize,
}

/// Response payload for `GET_USB_DESCRIPTOR`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UsbDescriptorResponse {
    /// Raw descriptor bytes.
    pub bytes: Vec<u8>,
}

/// Response payload for `GET_LAST_USB_REPORT`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UsbReportResponse {
    /// Raw report bytes.
    pub bytes: Vec<u8>,
}

/// A command received over the serial control plane.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ControlCommand {
    /// Request firmware and persona information.
    GetInfo,
    /// Request current system status.
    GetStatus,
    /// Request the active profile.
    GetProfile,
    /// Request USB status.
    GetUsbStatus,
    /// List all USB devices.
    ListUsbDevices,
    /// Request the raw HID descriptor for a device/interface.
    GetUsbDescriptor(DescriptorKey),
    /// Request the last raw input report for a device/interface.
    GetLastUsbReport(DescriptorKey),
}

/// A response to be sent over the serial control plane.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ControlResponse {
    /// Response to `GET_INFO`.
    Info(InfoResponse),
    /// Response to `GET_STATUS`.
    Status(StatusResponse),
    /// Response to `GET_PROFILE`.
    Profile(ProfileResponse),
    /// Response to `GET_USB_STATUS`.
    UsbStatus(UsbStatusResponse),
    /// Response to `LIST_USB_DEVICES`.
    UsbDevices(Vec<UsbDeviceRef>),
    /// Response to `GET_USB_DESCRIPTOR`.
    UsbDescriptor(UsbDescriptorResponse),
    /// Response to `GET_LAST_USB_REPORT`.
    UsbReport(UsbReportResponse),
    /// An error response.
    Error(ControlError),
}

/// Errors occurring during control plane operations.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ControlError {
    /// Generic control plane failure.
    Generic,
    /// Requested resource was not found.
    NotFound,
}

/// Trait for serial control plane framing and schema.
pub trait ControlPlane {
    /// Decode a raw byte stream into a command.
    fn decode_command(&self, bytes: &[u8]) -> Result<ControlCommand, ControlError>;
    /// Encode a response into a wire-ready byte stream.
    fn encode_response(&self, response: &ControlResponse) -> Result<Vec<u8>, ControlError>;
}

// --- App Orchestration ---

/// Unique identifier for a descriptor entry in app state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct DescriptorKey {
    /// Source device ID.
    pub device_id: DeviceId,
    /// Source interface ID.
    pub interface_id: Option<InterfaceId>,
}

/// Current state of the application.
pub struct AppState {
    /// Currently attached physical USB devices.
    pub physical_devices: Vec<UsbDeviceRef>,
    /// Discovered HID interfaces.
    pub hid_interfaces: Vec<UsbInterfaceRef>,
    /// Active HID descriptors keyed by device/interface.
    pub descriptors: Vec<(DescriptorKey, HidDescriptorIr)>,
    /// Raw HID descriptors keyed by device/interface.
    pub raw_descriptors: Vec<(DescriptorKey, Vec<u8>)>,
    /// Last raw input reports keyed by device/interface.
    pub last_reports: Vec<(DescriptorKey, Vec<u8>)>,
    /// Currently active mapping profile.
    pub active_profile: Option<ProfileId>,
    /// Currently active BLE persona.
    pub active_persona: Option<PersonaId>,
    /// Current BLE link state.
    pub ble_state: BleLinkState,
}

// --- Diagnostics ---

/// Diagnostic information about the boot process.
pub struct BootInfo {}
/// Diagnostic information about USB events.
pub struct UsbDiagnosticEvent {}
/// Diagnostic information about HID events.
pub struct HidDiagnosticEvent {}
/// Diagnostic information about mapping events.
pub struct MappingDiagnosticEvent {}
/// Diagnostic information about BLE events.
pub struct BleDiagnosticEvent {}
/// Diagnostic information about storage events.
pub struct StoreDiagnosticEvent {}
/// Diagnostic information about control plane events.
pub struct ControlDiagnosticEvent {}

/// Unified diagnostic event enum.
pub enum DiagnosticEvent {
    /// System boot event.
    Boot(BootInfo),
    /// USB subsystem event.
    Usb(UsbDiagnosticEvent),
    /// HID subsystem event.
    Hid(HidDiagnosticEvent),
    /// Mapping subsystem event.
    Mapping(MappingDiagnosticEvent),
    /// BLE subsystem event.
    Ble(BleDiagnosticEvent),
    /// Storage subsystem event.
    Store(StoreDiagnosticEvent),
    /// Control plane event.
    Control(ControlDiagnosticEvent),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[allow(clippy::assertions_on_constants)]
    fn test_contract_version() {
        assert!(CONTRACT_VERSION > 0);
    }

    #[test]
    #[allow(clippy::match_wildcard_for_single_variants)]
    fn test_topology_direct() {
        let topo = ConnectionTopology::Direct;
        match topo {
            ConnectionTopology::Direct => (),
            _ => panic!("Expected Direct topology"),
        }
    }

    #[test]
    #[allow(clippy::match_wildcard_for_single_variants)]
    fn test_topology_hub() {
        let mut ports = heapless::Vec::new();
        ports.push(1).unwrap();
        ports.push(2).unwrap();
        let path = HubPath { ports };
        let topo = ConnectionTopology::ViaHub { path: path.clone() };
        match topo {
            ConnectionTopology::ViaHub { path: p } => assert_eq!(p.ports, path.ports),
            _ => panic!("Expected ViaHub topology"),
        }
    }

    #[test]
    fn test_descriptor_key() {
        let key = DescriptorKey {
            device_id: DeviceId(1),
            interface_id: Some(InterfaceId(0)),
        };
        assert_eq!(key.device_id, DeviceId(1));
        assert_eq!(key.interface_id, Some(InterfaceId(0)));
    }
}
