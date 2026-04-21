# Contract Definitions

This document defines the implementation boundaries for the new repo.

All crates and all coding agents must treat these contracts as authoritative.

---

## 1. General contract rules

### C-001 Contract source of truth
`usb2ble-contracts` is the only crate allowed to define shared DTOs, IDs, traits, and cross-crate error enums.

### C-002 Contract change policy
Any change to a public contract must update:
- `CONTRACTS.md`
- the contract crate
- tests or snapshots affected by the change
- milestone acceptance notes if behavior changed

### C-003 Host-testability
All crates except `usb2ble-platform-esp32` and `usb2ble-fw` must compile and test on host.

### C-004 Unsafe isolation
All embedded `unsafe` code must remain in `usb2ble-platform-esp32` unless this document is amended.

### C-005 Versioning
The contract crate must expose a stable `CONTRACT_VERSION` and semver-like compatibility note for the control plane and major shared schemas.

---

## 2. Core shared identity types

These types belong in `usb2ble-contracts`.

```rust
pub type ContractVersion = u32;

pub struct DeviceId(pub u32);
pub struct InterfaceId(pub u32);
pub struct EndpointAddress(pub u8);
pub struct ReportId(pub u8);
pub struct ProfileId(pub &'static str);
pub struct PersonaId(pub &'static str);
pub struct MappingId(pub &'static str);
```

### Required invariants
- IDs must be small, copyable, and stable for the duration of a session.
- `ProfileId` and `PersonaId` are stable string IDs, not display labels.

---

## 3. USB topology and ingress contracts

### 3.1 Topology model

```rust
pub struct HubPath {
    pub ports: heapless::Vec<u8, 8>,
}

pub enum ConnectionTopology {
    Direct,
    ViaHub { path: HubPath },
}
```

#### Invariants
- The topology model must exist even before full hub support ships.
- Any USB source event must be attributable to either direct attach or a hub path.

### 3.2 USB device reference

```rust
pub struct UsbDeviceRef {
    pub device_id: DeviceId,
    pub topology: ConnectionTopology,
    pub vendor_id: u16,
    pub product_id: u16,
    pub interface_id: Option<InterfaceId>,
}
```

#### Invariants
- `device_id` is session-stable.
- `interface_id` may be absent at attach time but must be available by interface discovery when relevant.

### 3.3 Descriptor and report packets

```rust
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
```

#### Invariants
- Raw bytes are preserved exactly.
- Report ID must be explicit, not inferred downstream from a hidden convention.

### 3.4 USB ingress event enum

```rust
pub enum UsbIngressEvent {
    DeviceAttached(UsbDeviceRef),
    DeviceDetached { source: UsbDeviceRef },
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
```

### 3.5 USB ingress trait

```rust
pub trait UsbIngress {
    fn poll_event(&mut self) -> Option<UsbIngressEvent>;
}
```

#### Rules
- `usb2ble-app` depends on this trait only.
- No downstream crate may depend on ESP-IDF callback signatures.

---

## 4. HID descriptor and decode contracts

### 4.1 HID descriptor IR contract

The HID parser must output a general-purpose IR, not a tiny milestone-specific subset.

Minimum shape:

```rust
pub struct HidDescriptorIr {
    pub collections: Vec<HidCollection>,
    pub fields: Vec<HidField>,
    pub report_ids: Vec<ReportId>,
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
```

#### Invariants
- IR must be independent of ESP-IDF.
- IR must preserve enough information for decode, normalization, and diagnostics.
- IR must not hardcode one report shape, one report count, or one device type.

### 4.2 HID parser trait

```rust
pub trait HidDescriptorParser {
    fn parse_descriptor(
        &self,
        blob: &ReportDescriptorBlob,
    ) -> Result<HidDescriptorIr, HidParseError>;
}
```

### 4.3 HID capability summary

```rust
pub struct HidCapabilitySummary {
    pub axes: Vec<HidAxisCapability>,
    pub buttons: Vec<HidButtonCapability>,
    pub hats: Vec<HidHatCapability>,
    pub report_ids: Vec<ReportId>,
}
```

### 4.4 HID decoder trait

```rust
pub trait HidReportDecoder {
    fn decode_report(
        &self,
        ir: &HidDescriptorIr,
        report: &InputReportPacket,
    ) -> Result<DecodedInputReport, HidDecodeError>;
}
```

#### Rule
The decoder may not mutate application state.

---

## 5. Normalized input contracts

### 5.1 Normalized control model

The normalized model must be broad enough for:
- single-device curated support,
- later multi-device composition,
- later generic-to-persona remapping.

```rust
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
```

### 5.2 Normalized frame

```rust
pub struct NormalizedInputFrame {
    pub source: UsbDeviceRef,
    pub controls: Vec<NormalizedControlEvent>,
}
```

### 5.3 Composite frame

```rust
pub struct CompositeInputFrame {
    pub sources: Vec<UsbDeviceRef>,
    pub controls: Vec<NormalizedCompositeValue>,
    pub timestamp_micros: u64,
}
```

### 5.4 Normalizer trait

```rust
pub trait InputNormalizer {
    fn normalize(
        &self,
        ir: &HidDescriptorIr,
        decoded: &DecodedInputReport,
    ) -> Result<NormalizedInputFrame, NormalizeError>;
}
```

### 5.5 Merger trait

```rust
pub trait CompositeMerger {
    fn merge(
        &self,
        inputs: &[NormalizedInputFrame],
        profile: &CompositeProfile,
    ) -> Result<CompositeInputFrame, MergeError>;
}
```

#### Rules
- Normalized input contracts must retain source identity.
- Composite state must be defined in contracts before full hub merge ships.
- Detach handling must be implementable without rewriting the normalized model.

---

## 6. Mapping and profile contracts

### 6.1 Device signature contract

```rust
pub struct DeviceSignature {
    pub vendor_id: u16,
    pub product_id: u16,
    pub interface_class: Option<u8>,
    pub capability_fingerprint: Option<String>,
}
```

### 6.2 Profile definition contract

```rust
pub struct MappingProfile {
    pub profile_id: ProfileId,
    pub display_name: String,
    pub supported_signatures: Vec<DeviceSignature>,
    pub target_persona: PersonaId,
    pub source_mappings: Vec<SourceMappingRule>,
    pub merge_policy: Option<CompositeProfile>,
}
```

### 6.3 Mapper trait

```rust
pub trait Mapper {
    fn select_profile(
        &self,
        devices: &[DeviceSignature],
    ) -> Result<Option<ProfileId>, MappingError>;

    fn map_to_persona_frame(
        &self,
        profile: &MappingProfile,
        composite: &CompositeInputFrame,
    ) -> Result<PersonaInputFrame, MappingError>;
}
```

#### Rules
- Profile selection logic is pure and testable.
- Mapping profiles should be data-driven as far as practical.
- Quirks must be explicit and isolated.

---

## 7. Persona contracts

### 7.1 Persona metadata

```rust
pub struct PersonaDescriptor {
    pub persona_id: PersonaId,
    pub display_name: String,
    pub transport_family: BleTransportFamily,
    pub report_map: Vec<u8>,
    pub input_schema: PersonaInputSchema,
}
```

### 7.2 Persona input frame

```rust
pub struct PersonaInputFrame {
    pub persona_id: PersonaId,
    pub logical_controls: Vec<PersonaLogicalControlValue>,
}
```

### 7.3 Encoded persona report

```rust
pub struct EncodedBleReport {
    pub persona_id: PersonaId,
    pub report_id: ReportId,
    pub bytes: Vec<u8>,
}
```

### 7.4 Persona encoder trait

```rust
pub trait PersonaEncoder {
    fn descriptor(&self, persona_id: PersonaId) -> Result<PersonaDescriptor, PersonaError>;
    fn encode(
        &self,
        input: &PersonaInputFrame,
    ) -> Result<EncodedBleReport, PersonaError>;
}
```

#### Rules
- Persona definitions are independent of USB sources.
- Generic Gamepad and Xbox must both fit this contract family.
- Persona encoders must have exact-wire tests.

---

## 8. BLE transport contracts

### 8.1 BLE transport state

```rust
pub enum BleLinkState {
    Idle,
    Initializing,
    Advertising,
    Connected,
    Error,
}
```

### 8.2 BLE transport trait

```rust
pub trait BleTransport {
    fn current_state(&self) -> BleLinkState;

    fn activate_persona(
        &mut self,
        descriptor: &PersonaDescriptor,
    ) -> Result<(), BleTransportError>;

    fn publish_report(
        &mut self,
        report: &EncodedBleReport,
    ) -> Result<(), BleTransportError>;

    fn forget_bonds(&mut self) -> Result<(), BleTransportError>;
}
```

#### Rules
- BLE transport does not know USB details.
- BLE transport accepts encoded persona reports only.
- Persona activation and report publication are separate operations.

---

## 9. Persistence contracts

### 9.1 Profile/config store trait

```rust
pub trait ProfileStore {
    fn load_active_profile(&self) -> Result<Option<ProfileId>, StoreError>;
    fn save_active_profile(&mut self, profile: ProfileId) -> Result<(), StoreError>;
}

pub trait ConfigStore {
    fn load_config(&self) -> Result<Option<RuntimeConfig>, StoreError>;
    fn save_config(&mut self, config: &RuntimeConfig) -> Result<(), StoreError>;
}
```

### 9.2 Bond store trait

```rust
pub trait BondStore {
    fn bonds_present(&self) -> Result<bool, StoreError>;
    fn clear_bonds(&mut self) -> Result<(), StoreError>;
}
```

#### Rules
- App crate depends on traits only.
- Memory-backed test implementations must exist.

---

## 10. Control-plane contracts

### 10.1 Command set

The control plane must include at least:

- `GET_INFO`
- `GET_STATUS`
- `GET_PROFILE`
- `SET_PROFILE`
- `LIST_DEVICES`
- `GET_DESCRIPTOR_SUMMARY`
- `GET_PERSONAS`
- `GET_ACTIVE_PERSONA`
- `INJECT_TEST_INPUT`
- `FORGET_BONDS`
- `REBOOT`
- `STREAM_DIAGNOSTICS on|off`

### 10.2 Control protocol trait

```rust
pub trait ControlPlane {
    fn decode_command(&self, bytes: &[u8]) -> Result<ControlCommand, ControlError>;
    fn encode_response(&self, response: &ControlResponse) -> Result<Vec<u8>, ControlError>;
}
```

#### Rules
- Framing and schema are owned by `usb2ble-control`.
- App crate handles semantics, not wire parsing.

---

## 11. Application orchestration contracts

### 11.1 App responsibilities
`usb2ble-app` is the only crate allowed to coordinate:
- USB ingress,
- parser,
- normalizer,
- merger,
- mapper,
- persona encoder,
- BLE transport,
- storage,
- control plane.

### 11.2 App state contract

At minimum, app state must track:

```rust
pub struct AppState {
    pub known_devices: Vec<UsbDeviceRef>,
    pub descriptors: Vec<(DescriptorKey, HidDescriptorIr)>,
    pub active_profile: Option<ProfileId>,
    pub active_persona: Option<PersonaId>,
    pub ble_state: BleLinkState,
}

pub struct DescriptorKey {
    pub device_id: DeviceId,
    pub interface_id: Option<InterfaceId>,
}
```

#### Rules
- App state must allow more than one device to exist simultaneously.
- Single-device demo logic may be a policy choice, not a state-model limitation.

---

## 12. Diagnostics contracts

### 12.1 Event log schema
Every major subsystem event must be expressible as a typed diagnostic event:

```rust
pub enum DiagnosticEvent {
    Boot(BootInfo),
    Usb(UsbDiagnosticEvent),
    Hid(HidDiagnosticEvent),
    Mapping(MappingDiagnosticEvent),
    Ble(BleDiagnosticEvent),
    Store(StoreDiagnosticEvent),
    Control(ControlDiagnosticEvent),
}
```

#### Required properties
- suitable for serial logging,
- suitable for future structured export,
- stable enough for milestone evidence.

---

## 13. Forbidden shortcuts

The following are prohibited unless this document is updated:

1. Hardcoding the entire app around one active device in the shared contracts.
2. Hardcoding the output layer around one persona in the shared contracts.
3. Inferring report IDs via hidden assumptions after the USB boundary.
4. Performing mapping logic in the BLE transport crate.
5. Performing ESP-IDF calls in `usb2ble-app`.
6. Defining duplicate DTOs in multiple crates.
7. Claiming hub/multi-device readiness without topology-aware contracts and tests.

---

## 14. Required tests per contract family

### USB ingress
- attach/detach tests
- descriptor delivery tests
- report delivery tests
- source identity tests

### HID
- descriptor parse snapshots
- decode fixtures
- parity tests against hardware-captured blobs

### Input
- normalization tests
- detach/reset tests
- merge-policy tests

### Mapping
- signature selection tests
- profile loading tests
- mapping output tests

### Personas
- descriptor tests
- exact-wire encoding tests
- invalid-input rejection tests

### BLE transport
- host stubs
- publish lifecycle tests
- persona activation tests

### App
- milestone-oriented orchestration tests
- control/USB/BLE coordination tests
- graceful error propagation tests

---

## 15. Agent implementation rule

If an agent cannot complete a task without changing a contract, it must:

1. stop implementation,
2. propose the contract diff explicitly,
3. explain the downstream impact,
4. and wait for orchestration approval before widening scope.
