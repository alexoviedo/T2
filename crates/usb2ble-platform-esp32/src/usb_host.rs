//! ESP-IDF USB Host witness implementation for M2B.1/M2B.2.
//!
//! Scope for this milestone:
//! - Real attach/detach witness on ESP32-S3.
//! - Real VID/PID identity reporting.
//! - HID interface discovery from active config descriptor.
//! - HID report descriptor capture for M2B.2.
//! - Raw HID interrupt input-report capture for M2B.2.

use std::collections::VecDeque;
#[cfg(target_os = "espidf")]
use std::collections::{HashMap, HashSet};
use usb2ble_contracts::{
    ConnectionTopology, DeviceId, InterfaceId, UsbDeviceRef, UsbIngressEvent, UsbInterfaceRef,
};
#[cfg(target_os = "espidf")]
use usb2ble_contracts::{InputReportPacket, ReportDescriptorBlob, ReportId};

use std::sync::{Arc, Mutex};

#[cfg(target_os = "espidf")]
use esp_idf_sys::*;

#[cfg(any(test, target_os = "espidf"))]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct EndpointDescriptorInfo {
    address: u8,
    attributes: u8,
    max_packet_size: u16,
    interval: u8,
}

#[cfg(any(test, target_os = "espidf"))]
impl EndpointDescriptorInfo {
    const fn is_interrupt_in(self) -> bool {
        (self.address & USB_ENDPOINT_DIR_IN) != 0
            && (self.attributes & USB_ENDPOINT_TRANSFER_TYPE_MASK)
                == USB_ENDPOINT_TRANSFER_TYPE_INTERRUPT
            && self.max_packet_size != 0
    }
}

#[cfg(any(test, target_os = "espidf"))]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct InterfaceDescriptorInfo {
    interface_number: u8,
    class_code: u8,
    subclass_code: u8,
    protocol_code: u8,
    report_descriptor_len: Option<u16>,
    interrupt_in_endpoint: Option<EndpointDescriptorInfo>,
}

#[cfg(any(test, target_os = "espidf"))]
const USB_ENDPOINT_DIR_IN: u8 = 0x80;
#[cfg(any(test, target_os = "espidf"))]
const USB_ENDPOINT_TRANSFER_TYPE_MASK: u8 = 0x03;
#[cfg(any(test, target_os = "espidf"))]
const USB_ENDPOINT_TRANSFER_TYPE_INTERRUPT: u8 = 0x03;

/// Parse interface descriptors from a raw active configuration descriptor blob.
#[cfg(any(test, target_os = "espidf"))]
fn parse_interfaces_from_config(config_blob: &[u8]) -> Vec<InterfaceDescriptorInfo> {
    const DESC_TYPE_INTERFACE: u8 = 0x04;
    const DESC_TYPE_ENDPOINT: u8 = 0x05;
    const DESC_TYPE_HID: u8 = 0x21;
    const DESC_TYPE_HID_REPORT: u8 = 0x22;

    let mut out = Vec::new();
    let mut current_interface: Option<usize> = None;
    let mut i = 0usize;

    while i + 1 < config_blob.len() {
        let len = config_blob[i] as usize;
        if len == 0 || i + len > config_blob.len() {
            break;
        }

        let desc_type = config_blob[i + 1];
        if desc_type == DESC_TYPE_INTERFACE && len >= 9 {
            let interface_number = config_blob[i + 2];
            let class_code = config_blob[i + 5];
            let subclass_code = config_blob[i + 6];
            let protocol_code = config_blob[i + 7];

            out.push(InterfaceDescriptorInfo {
                interface_number,
                class_code,
                subclass_code,
                protocol_code,
                report_descriptor_len: None,
                interrupt_in_endpoint: None,
            });
            current_interface = Some(out.len() - 1);
        } else if desc_type == DESC_TYPE_HID
            && len >= 9
            && let Some(interface_idx) = current_interface
        {
            let num_descriptors = config_blob[i + 5] as usize;
            let mut desc_offset = i + 6;
            for _ in 0..num_descriptors {
                if desc_offset + 2 >= i + len {
                    break;
                }
                let class_desc_type = config_blob[desc_offset];
                let class_desc_len = u16::from_le_bytes([
                    config_blob[desc_offset + 1],
                    config_blob[desc_offset + 2],
                ]);
                if class_desc_type == DESC_TYPE_HID_REPORT {
                    out[interface_idx].report_descriptor_len = Some(class_desc_len);
                    break;
                }
                desc_offset += 3;
            }
        } else if desc_type == DESC_TYPE_ENDPOINT
            && len >= 7
            && let Some(interface_idx) = current_interface
        {
            let raw_max_packet_size = u16::from_le_bytes([config_blob[i + 4], config_blob[i + 5]]);
            let endpoint = EndpointDescriptorInfo {
                address: config_blob[i + 2],
                attributes: config_blob[i + 3],
                max_packet_size: raw_max_packet_size & 0x07ff,
                interval: config_blob[i + 6],
            };

            if endpoint.is_interrupt_in() && out[interface_idx].interrupt_in_endpoint.is_none() {
                out[interface_idx].interrupt_in_endpoint = Some(endpoint);
            }
        }

        i += len;
    }

    out
}

/// Parse HID interfaces from a raw active configuration descriptor blob.
///
/// Returns `(interface_number, subclass, protocol)` tuples for HID interfaces.
#[cfg(test)]
fn parse_hid_interfaces_from_config(config_blob: &[u8]) -> Vec<(u8, u8, u8)> {
    const USB_CLASS_HID: u8 = 0x03;

    parse_interfaces_from_config(config_blob)
        .into_iter()
        .filter_map(
            |InterfaceDescriptorInfo {
                 interface_number,
                 class_code,
                 subclass_code,
                 protocol_code,
                 ..
             }| {
                (class_code == USB_CLASS_HID).then_some((
                    interface_number,
                    subclass_code,
                    protocol_code,
                ))
            },
        )
        .collect()
}

#[cfg(target_os = "espidf")]
#[derive(Debug)]
struct ControlTransferResult {
    done: bool,
    status: usb_transfer_status_t,
    actual_num_bytes: i32,
}

#[cfg(target_os = "espidf")]
#[derive(Debug)]
struct InterruptTransferResult {
    done: bool,
    status: usb_transfer_status_t,
    actual_num_bytes: i32,
}

#[cfg(target_os = "espidf")]
#[derive(Debug, Clone, Copy)]
enum ReportCaptureError {
    InterfaceClaim(i32),
    TransferAlloc(i32),
    TransferSubmit(i32),
}

#[cfg(target_os = "espidf")]
impl ReportCaptureError {
    const fn stage_code(self) -> u32 {
        match self {
            Self::InterfaceClaim(_) => 1,
            Self::TransferAlloc(_) => 2,
            Self::TransferSubmit(_) => 3,
        }
    }

    const fn esp_error(self) -> i32 {
        match self {
            Self::InterfaceClaim(err) | Self::TransferAlloc(err) | Self::TransferSubmit(err) => err,
        }
    }
}

#[cfg(target_os = "espidf")]
struct TargetDeviceSession {
    dev_ref: UsbDeviceRef,
    dev_hdl: usb_device_handle_t,
    interfaces: Vec<TargetHidInterfaceSession>,
    detach_announced: bool,
}

#[cfg(target_os = "espidf")]
struct TargetHidInterfaceSession {
    source: UsbInterfaceRef,
    endpoint: EndpointDescriptorInfo,
    transfer: *mut usb_transfer_t,
    result: Box<InterruptTransferResult>,
    in_flight: bool,
    claimed: bool,
    last_report_log_micros: u64,
}

#[cfg(target_os = "espidf")]
unsafe extern "C" fn control_transfer_cb(transfer: *mut usb_transfer_t) {
    if transfer.is_null() {
        return;
    }

    let result = unsafe { (*transfer).context as *mut ControlTransferResult };
    if result.is_null() {
        return;
    }

    unsafe {
        (*result).done = true;
        (*result).status = (*transfer).status;
        (*result).actual_num_bytes = (*transfer).actual_num_bytes;
    }
}

#[cfg(target_os = "espidf")]
unsafe extern "C" fn interrupt_transfer_cb(transfer: *mut usb_transfer_t) {
    if transfer.is_null() {
        return;
    }

    let result = unsafe { (*transfer).context as *mut InterruptTransferResult };
    if result.is_null() {
        return;
    }

    unsafe {
        (*result).done = true;
        (*result).status = (*transfer).status;
        (*result).actual_num_bytes = (*transfer).actual_num_bytes;
    }
}

/// Internal state for the USB host witness implementation.
pub struct EspUsbHost {
    event_tx: Arc<Mutex<VecDeque<UsbIngressEvent>>>,

    #[cfg(target_os = "espidf")]
    inner: Arc<Mutex<TargetUsbHostState>>,
    #[cfg(target_os = "espidf")]
    client_events: Arc<TargetClientEventState>,

    #[cfg(not(target_os = "espidf"))]
    simulated_once: bool,
}

#[cfg(target_os = "espidf")]
struct TargetClientEventState {
    event_tx: Arc<Mutex<VecDeque<UsbIngressEvent>>>,
    inner: Arc<Mutex<TargetUsbHostState>>,
}

#[cfg(target_os = "espidf")]
struct TargetUsbHostState {
    installed: bool,
    client_hdl: usb_host_client_handle_t,
    next_device_id: u32,
    by_addr: HashMap<u8, TargetDeviceSession>,
    announced_interfaces: HashSet<(DeviceId, InterfaceId)>,
}

#[cfg(target_os = "espidf")]
impl TargetUsbHostState {
    fn new() -> Self {
        Self {
            installed: false,
            client_hdl: core::ptr::null_mut(),
            next_device_id: 1,
            by_addr: HashMap::new(),
            announced_interfaces: HashSet::new(),
        }
    }

    fn alloc_device_id(&mut self) -> DeviceId {
        let id = DeviceId(self.next_device_id);
        self.next_device_id = self.next_device_id.saturating_add(1);
        id
    }
}

impl EspUsbHost {
    pub fn new(event_tx: Arc<Mutex<VecDeque<UsbIngressEvent>>>) -> Self {
        #[cfg(target_os = "espidf")]
        let inner = Arc::new(Mutex::new(TargetUsbHostState::new()));
        #[cfg(target_os = "espidf")]
        let client_events = Arc::new(TargetClientEventState {
            event_tx: event_tx.clone(),
            inner: inner.clone(),
        });

        Self {
            event_tx,
            #[cfg(target_os = "espidf")]
            inner,
            #[cfg(target_os = "espidf")]
            client_events,
            #[cfg(not(target_os = "espidf"))]
            simulated_once: false,
        }
    }

    /// Initialize USB Host library + client registration for target witness mode.
    #[cfg(target_os = "espidf")]
    pub fn init(&self) -> Result<(), &'static str> {
        let mut state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
        if state.installed {
            return Ok(());
        }

        let mut lib_cfg: usb_host_config_t = Default::default();
        lib_cfg.skip_phy_setup = false;
        lib_cfg.intr_flags = 0;
        lib_cfg.enum_filter_cb = None;

        let install_err = unsafe { usb_host_install(&lib_cfg) };
        if install_err != ESP_OK as i32 {
            return Err("usb_host_install failed");
        }

        unsafe extern "C" fn client_event_cb(
            event_msg: *const esp_idf_sys::usb_host_client_event_msg_t,
            arg: *mut core::ffi::c_void,
        ) {
            if event_msg.is_null() || arg.is_null() {
                return;
            }

            let state = unsafe { &*(arg as *const TargetClientEventState) };
            let event = unsafe { (*event_msg).event };
            if event != usb_host_client_event_t_USB_HOST_CLIENT_EVENT_DEV_GONE {
                return;
            }

            let dev_hdl = unsafe { (*event_msg).__bindgen_anon_1.dev_gone.dev_hdl };
            let detached = {
                let Ok(mut host_state) = state.inner.lock() else {
                    return;
                };

                let Some(addr) = host_state.by_addr.iter().find_map(|(addr, session)| {
                    (session.dev_hdl == dev_hdl && !session.detach_announced).then_some(*addr)
                }) else {
                    return;
                };

                let Some(session) = host_state.by_addr.get_mut(&addr) else {
                    return;
                };

                session.detach_announced = true;
                let dev_ref = session.dev_ref.clone();
                host_state
                    .announced_interfaces
                    .retain(|(dev_id, _)| *dev_id != dev_ref.device_id);
                dev_ref
            };

            if let Ok(mut q) = state.event_tx.lock() {
                q.push_back(UsbIngressEvent::DeviceDetached { source: detached });
            }
        }

        let mut client_cfg: usb_host_client_config_t = Default::default();
        client_cfg.is_synchronous = false;
        client_cfg.max_num_event_msg = 8;
        client_cfg.__bindgen_anon_1.async_ =
            esp_idf_sys::usb_host_client_config_t__bindgen_ty_1__bindgen_ty_1 {
                client_event_callback: Some(client_event_cb),
                callback_arg: Arc::as_ptr(&self.client_events) as *mut core::ffi::c_void,
            };

        let mut client_hdl: usb_host_client_handle_t = core::ptr::null_mut();
        let client_err = unsafe { usb_host_client_register(&client_cfg, &mut client_hdl) };
        if client_err != ESP_OK as i32 {
            unsafe {
                let _ = usb_host_uninstall();
            }
            return Err("usb_host_client_register failed");
        }

        state.client_hdl = client_hdl;
        state.installed = true;
        Ok(())
    }

    /// Pump USB host events and emit app-facing ingress events.
    #[cfg(target_os = "espidf")]
    pub fn poll_target_events(&self) -> Result<(), &'static str> {
        let mut flags: u32 = 0;
        let lib_err = unsafe { usb_host_lib_handle_events(0, &mut flags) };
        if lib_err != ESP_OK as i32 {
            return Err("usb_host_lib_handle_events failed");
        }

        let client_hdl = {
            let state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            if !state.installed || state.client_hdl.is_null() {
                return Ok(());
            }
            state.client_hdl
        };

        let client_err = unsafe { usb_host_client_handle_events(client_hdl, 0) };
        if client_err != ESP_OK as i32 {
            return Err("usb_host_client_handle_events failed");
        }

        self.poll_completed_interrupt_transfers()?;
        self.scan_for_new_devices()?;

        Ok(())
    }

    #[cfg(target_os = "espidf")]
    fn scan_for_new_devices(&self) -> Result<(), &'static str> {
        let mut addr_list = [0u8; 16];
        let mut num_devices: i32 = 0;

        let fill_err = unsafe {
            usb_host_device_addr_list_fill(
                addr_list.len() as i32,
                addr_list.as_mut_ptr(),
                &mut num_devices,
            )
        };
        if fill_err != ESP_OK as i32 {
            return Err("usb_host_device_addr_list_fill failed");
        }

        let mut present = HashSet::new();
        for addr in addr_list.into_iter().take(num_devices as usize) {
            if addr == 0 {
                continue;
            }
            let _ = present.insert(addr);
            self.register_device_if_needed(addr)?;
        }

        let detached_addrs = {
            let state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            state
                .by_addr
                .iter()
                .filter_map(|(addr, session)| {
                    (!present.contains(addr) && !session.detach_announced).then_some(*addr)
                })
                .collect::<Vec<_>>()
        };

        let detached = if detached_addrs.is_empty() {
            Vec::new()
        } else {
            let mut state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            let mut detached = Vec::new();
            for addr in detached_addrs {
                let Some(dev_ref) = state.by_addr.get_mut(&addr).map(|session| {
                    session.detach_announced = true;
                    session.dev_ref.clone()
                }) else {
                    continue;
                };
                state
                    .announced_interfaces
                    .retain(|(dev_id, _)| *dev_id != dev_ref.device_id);
                detached.push(dev_ref);
            }
            detached
        };

        for source in detached {
            if let Ok(mut q) = self.event_tx.lock() {
                q.push_back(UsbIngressEvent::DeviceDetached { source });
            }
        }

        self.cleanup_detached_sessions()?;

        Ok(())
    }

    #[cfg(target_os = "espidf")]
    fn register_device_if_needed(&self, dev_addr: u8) -> Result<(), &'static str> {
        {
            let state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            if state.by_addr.contains_key(&dev_addr) {
                return Ok(());
            }
        }

        let client_hdl = {
            let state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            state.client_hdl
        };

        let mut dev_hdl: usb_device_handle_t = core::ptr::null_mut();
        let open_err = unsafe { usb_host_device_open(client_hdl, dev_addr, &mut dev_hdl) };
        if open_err != ESP_OK as i32 || dev_hdl.is_null() {
            return Err("usb_host_device_open failed");
        }

        // Ownership model:
        // - TargetDeviceSession owns the device handle until detach cleanup.
        // - active config descriptor is cached by ESP-IDF and must not be freed here.
        let register_result = (|| -> Result<(), &'static str> {
            let mut desc_ptr: *const usb_device_desc_t = core::ptr::null();
            let desc_err = unsafe { usb_host_get_device_descriptor(dev_hdl, &mut desc_ptr) };
            if desc_err != ESP_OK as i32 || desc_ptr.is_null() {
                return Err("usb_host_get_device_descriptor failed");
            }

            let dev_ref = {
                let mut state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
                let dev_ref = UsbDeviceRef {
                    device_id: state.alloc_device_id(),
                    topology: ConnectionTopology::Direct,
                    vendor_id: unsafe { (*desc_ptr).__bindgen_anon_1.idVendor },
                    product_id: unsafe { (*desc_ptr).__bindgen_anon_1.idProduct },
                };
                state.by_addr.insert(
                    dev_addr,
                    TargetDeviceSession {
                        dev_ref: dev_ref.clone(),
                        dev_hdl,
                        interfaces: Vec::new(),
                        detach_announced: false,
                    },
                );
                dev_ref
            };

            if let Ok(mut q) = self.event_tx.lock() {
                q.push_back(UsbIngressEvent::DeviceAttached(dev_ref.clone()));
            }

            let ep0_mps = unsafe { (*desc_ptr).__bindgen_anon_1.bMaxPacketSize0 };
            self.emit_hid_interfaces_from_active_config(
                dev_addr, dev_ref, dev_hdl, client_hdl, ep0_mps,
            )?;
            Ok(())
        })();

        if register_result.is_err() {
            let removed_session = self
                .inner
                .lock()
                .ok()
                .and_then(|mut state| state.by_addr.remove(&dev_addr));
            if let Some(mut session) = removed_session {
                let _ = cleanup_device_session(client_hdl, &mut session);
            } else {
                let _ = unsafe { usb_host_device_close(client_hdl, dev_hdl) };
            }
        }

        register_result
    }

    #[cfg(target_os = "espidf")]
    fn emit_hid_interfaces_from_active_config(
        &self,
        dev_addr: u8,
        dev_ref: UsbDeviceRef,
        dev_hdl: usb_device_handle_t,
        client_hdl: usb_host_client_handle_t,
        ep0_mps: u8,
    ) -> Result<(), &'static str> {
        let mut cfg_ptr: *const usb_config_desc_t = core::ptr::null();
        let cfg_err = unsafe { usb_host_get_active_config_descriptor(dev_hdl, &mut cfg_ptr) };
        if cfg_err != ESP_OK as i32 || cfg_ptr.is_null() {
            // For M2B.1 witness, attach identity is the primary signal.
            // Missing config descriptor is non-fatal for this milestone.
            return Ok(());
        }

        let cfg_len = unsafe { (*cfg_ptr).__bindgen_anon_1.wTotalLength as usize };
        let cfg_blob = unsafe {
            let ptr = (*cfg_ptr).val.as_ptr();
            core::slice::from_raw_parts(ptr, cfg_len)
        };

        let interfaces = parse_interfaces_from_config(cfg_blob);
        for iface in &interfaces {
            unsafe {
                printf(
                    b"[USB_IFACE] Device: ID=%lu, IFACE=%u, CLASS=%02x, SUBCLASS=%02x, PROTOCOL=%02x\n\0"
                        .as_ptr() as *const _,
                    dev_ref.device_id.0 as u32,
                    iface.interface_number as u32,
                    iface.class_code as u32,
                    iface.subclass_code as u32,
                    iface.protocol_code as u32,
                );
            }
        }

        for iface in interfaces.into_iter().filter(|iface| iface.class_code == 3) {
            let iface_id = InterfaceId(iface.interface_number as u32);
            let should_emit = {
                let mut state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
                state
                    .announced_interfaces
                    .insert((dev_ref.device_id, iface_id))
            };

            if should_emit {
                let source = UsbInterfaceRef {
                    device: dev_ref.clone(),
                    interface_id: iface_id,
                };
                if let Ok(mut q) = self.event_tx.lock() {
                    q.push_back(UsbIngressEvent::InterfaceDiscovered {
                        source: source.clone(),
                        class_code: 3,
                        subclass_code: iface.subclass_code,
                        protocol_code: iface.protocol_code,
                    });
                }
                if let Some(report_descriptor_len) = iface.report_descriptor_len {
                    match self.read_hid_report_descriptor(
                        client_hdl,
                        dev_hdl,
                        ep0_mps,
                        iface.interface_number,
                        report_descriptor_len,
                    ) {
                        Ok(bytes) => {
                            unsafe {
                                printf(
                                    b"[USB_DESCRIPTOR] Device: ID=%lu, IFACE=%u, BYTES=%u\n\0"
                                        .as_ptr() as *const _,
                                    dev_ref.device_id.0 as u32,
                                    iface.interface_number as u32,
                                    bytes.len() as u32,
                                );
                            }
                            if let Ok(mut q) = self.event_tx.lock() {
                                q.push_back(UsbIngressEvent::ReportDescriptorReceived(
                                    ReportDescriptorBlob {
                                        source: source.clone(),
                                        bytes,
                                    },
                                ));
                            }
                        }
                        Err(_) => unsafe {
                            printf(
                                b"[USB_DESCRIPTOR_WARN] Device: ID=%lu, IFACE=%u, STATUS=unavailable\n\0"
                                    .as_ptr() as *const _,
                                dev_ref.device_id.0 as u32,
                                iface.interface_number as u32,
                            );
                        },
                    }
                }

                if let Some(endpoint) = iface.interrupt_in_endpoint {
                    match self.start_interrupt_report_capture(
                        client_hdl,
                        dev_hdl,
                        source.clone(),
                        iface.interface_number,
                        endpoint,
                    ) {
                        Ok(session) => {
                            let mut state =
                                self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
                            if let Some(device_session) = state.by_addr.get_mut(&dev_addr) {
                                device_session.interfaces.push(session);
                            }
                        }
                        Err(err) => unsafe {
                            printf(
                                b"[USB_REPORT_WARN] Device: ID=%lu, IFACE=%u, STATUS=unavailable, STAGE=%u, ERR=%d, EP=%02x, MPS=%u, INTERVAL=%u\n\0"
                                    .as_ptr() as *const _,
                                dev_ref.device_id.0 as u32,
                                iface.interface_number as u32,
                                err.stage_code(),
                                err.esp_error(),
                                endpoint.address as u32,
                                endpoint.max_packet_size as u32,
                                endpoint.interval as u32,
                            );
                        },
                    }
                } else {
                    unsafe {
                        printf(
                            b"[USB_REPORT_WARN] Device: ID=%lu, IFACE=%u, STATUS=no_interrupt_in\n\0"
                                .as_ptr() as *const _,
                            dev_ref.device_id.0 as u32,
                            iface.interface_number as u32,
                        );
                    }
                }
            }
        }

        Ok(())
    }

    #[cfg(target_os = "espidf")]
    fn start_interrupt_report_capture(
        &self,
        client_hdl: usb_host_client_handle_t,
        dev_hdl: usb_device_handle_t,
        source: UsbInterfaceRef,
        interface_number: u8,
        endpoint: EndpointDescriptorInfo,
    ) -> Result<TargetHidInterfaceSession, ReportCaptureError> {
        let claim_err =
            unsafe { usb_host_interface_claim(client_hdl, dev_hdl, interface_number, 0) };
        if claim_err != ESP_OK as i32 {
            return Err(ReportCaptureError::InterfaceClaim(claim_err));
        }

        let mut transfer: *mut usb_transfer_t = core::ptr::null_mut();
        let alloc_len = endpoint.max_packet_size as usize;
        let alloc_err = unsafe { usb_host_transfer_alloc(alloc_len, 0, &mut transfer) };
        if alloc_err != ESP_OK as i32 || transfer.is_null() {
            let _ = unsafe { usb_host_interface_release(client_hdl, dev_hdl, interface_number) };
            return Err(ReportCaptureError::TransferAlloc(alloc_err));
        }

        let mut result = Box::new(InterruptTransferResult {
            done: false,
            status: usb_transfer_status_t_USB_TRANSFER_STATUS_ERROR,
            actual_num_bytes: 0,
        });

        unsafe {
            (*transfer).device_handle = dev_hdl;
            (*transfer).bEndpointAddress = endpoint.address;
            (*transfer).num_bytes = endpoint.max_packet_size as i32;
            (*transfer).callback = Some(interrupt_transfer_cb);
            (*transfer).context = (&mut *result as *mut InterruptTransferResult).cast();
        }

        let submit_err = unsafe { usb_host_transfer_submit(transfer) };
        if submit_err != ESP_OK as i32 {
            let _ = unsafe { usb_host_transfer_free(transfer) };
            let _ = unsafe { usb_host_interface_release(client_hdl, dev_hdl, interface_number) };
            return Err(ReportCaptureError::TransferSubmit(submit_err));
        }

        Ok(TargetHidInterfaceSession {
            source,
            endpoint,
            transfer,
            result,
            in_flight: true,
            claimed: true,
            last_report_log_micros: 0,
        })
    }

    #[cfg(target_os = "espidf")]
    fn poll_completed_interrupt_transfers(&self) -> Result<(), &'static str> {
        let mut reports = Vec::new();
        let mut detached = Vec::new();

        {
            let mut state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            let mut detached_dev_ids = Vec::new();
            for device_session in state.by_addr.values_mut() {
                if device_session.detach_announced {
                    continue;
                }

                for interface_session in &mut device_session.interfaces {
                    if !interface_session.in_flight || !interface_session.result.done {
                        continue;
                    }

                    interface_session.in_flight = false;
                    let status = interface_session.result.status;
                    let actual_num_bytes =
                        interface_session.result.actual_num_bytes.max(0) as usize;

                    if status == usb_transfer_status_t_USB_TRANSFER_STATUS_COMPLETED {
                        if actual_num_bytes > 0 {
                            let copy_len = actual_num_bytes
                                .min(unsafe { (*interface_session.transfer).data_buffer_size });
                            let bytes = unsafe {
                                core::slice::from_raw_parts(
                                    (*interface_session.transfer).data_buffer,
                                    copy_len,
                                )
                                .to_vec()
                            };

                            let timestamp_micros = unsafe { esp_timer_get_time().max(0) as u64 };
                            if interface_session.last_report_log_micros == 0
                                || timestamp_micros
                                    .saturating_sub(interface_session.last_report_log_micros)
                                    >= 1_000_000
                            {
                                unsafe {
                                    printf(
                                        b"[USB_REPORT] Device: ID=%lu, IFACE=%u, BYTES=%u\n\0"
                                            .as_ptr()
                                            as *const _,
                                        interface_session.source.device.device_id.0 as u32,
                                        interface_session.source.interface_id.0 as u32,
                                        bytes.len() as u32,
                                    );
                                }
                                interface_session.last_report_log_micros = timestamp_micros;
                            }
                            reports.push(InputReportPacket {
                                source: interface_session.source.clone(),
                                report_id: ReportId(0),
                                payload: bytes,
                                timestamp_micros,
                            });
                        }

                        if resubmit_interrupt_transfer(interface_session) {
                            interface_session.in_flight = true;
                        }
                    } else if status == usb_transfer_status_t_USB_TRANSFER_STATUS_NO_DEVICE
                        || status == usb_transfer_status_t_USB_TRANSFER_STATUS_CANCELED
                    {
                        if !device_session.detach_announced {
                            device_session.detach_announced = true;
                            detached_dev_ids.push(device_session.dev_ref.device_id);
                            detached.push(device_session.dev_ref.clone());
                        }
                    } else {
                        unsafe {
                            printf(
                                b"[USB_REPORT_WARN] Device: ID=%lu, IFACE=%u, STATUS=%u\n\0"
                                    .as_ptr() as *const _,
                                interface_session.source.device.device_id.0 as u32,
                                interface_session.source.interface_id.0 as u32,
                                status as u32,
                            );
                        }
                        if recover_interrupt_transfer(device_session.dev_hdl, interface_session) {
                            interface_session.in_flight = true;
                        }
                    }
                }
            }

            for dev_id in detached_dev_ids {
                state
                    .announced_interfaces
                    .retain(|(announced_dev_id, _)| *announced_dev_id != dev_id);
            }
        }

        if !reports.is_empty()
            && let Ok(mut q) = self.event_tx.lock()
        {
            for report in reports {
                q.push_back(UsbIngressEvent::InputReportReceived(report));
            }
        }
        if !detached.is_empty()
            && let Ok(mut q) = self.event_tx.lock()
        {
            for source in detached {
                q.push_back(UsbIngressEvent::DeviceDetached { source });
            }
        }

        Ok(())
    }

    #[cfg(target_os = "espidf")]
    fn cleanup_detached_sessions(&self) -> Result<(), &'static str> {
        let client_hdl = {
            let state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            state.client_hdl
        };

        let detached_addrs = {
            let state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
            state
                .by_addr
                .iter()
                .filter_map(|(addr, session)| session.detach_announced.then_some(*addr))
                .collect::<Vec<_>>()
        };

        if detached_addrs.is_empty() {
            return Ok(());
        }

        let mut state = self.inner.lock().map_err(|_| "usb host mutex poisoned")?;
        for addr in detached_addrs {
            let is_clean = {
                let Some(session) = state.by_addr.get_mut(&addr) else {
                    continue;
                };
                cleanup_device_session(client_hdl, session)
            };

            if is_clean {
                let _ = state.by_addr.remove(&addr);
            }
        }

        Ok(())
    }

    #[cfg(target_os = "espidf")]
    fn read_hid_report_descriptor(
        &self,
        client_hdl: usb_host_client_handle_t,
        dev_hdl: usb_device_handle_t,
        ep0_mps: u8,
        interface_number: u8,
        report_descriptor_len: u16,
    ) -> Result<Vec<u8>, &'static str> {
        const HID_REPORT_DESCRIPTOR_TYPE: u16 = 0x22;
        const MAX_REPORT_DESCRIPTOR_LEN: usize = 1024;

        let report_len = report_descriptor_len as usize;
        if report_len == 0 || report_len > MAX_REPORT_DESCRIPTOR_LEN {
            return Err("unsupported HID report descriptor length");
        }

        let setup_len = core::mem::size_of::<usb_setup_packet_t>();
        let rounded_report_len = round_up_to_mps(report_len, ep0_mps as usize);
        let transfer_len = setup_len + rounded_report_len;

        let mut transfer: *mut usb_transfer_t = core::ptr::null_mut();
        let alloc_err = unsafe { usb_host_transfer_alloc(transfer_len, 0, &mut transfer) };
        if alloc_err != ESP_OK as i32 || transfer.is_null() {
            return Err("usb_host_transfer_alloc failed");
        }

        let mut result = ControlTransferResult {
            done: false,
            status: usb_transfer_status_t_USB_TRANSFER_STATUS_ERROR,
            actual_num_bytes: 0,
        };

        let read_result = (|| -> Result<Vec<u8>, &'static str> {
            unsafe {
                (*transfer).device_handle = dev_hdl;
                (*transfer).bEndpointAddress = 0;
                (*transfer).num_bytes = transfer_len as i32;
                (*transfer).callback = Some(control_transfer_cb);
                (*transfer).context = (&mut result as *mut ControlTransferResult).cast();

                let setup = (*transfer).data_buffer as *mut usb_setup_packet_t;
                (*setup).__bindgen_anon_1.bmRequestType = (USB_BM_REQUEST_TYPE_DIR_IN
                    | USB_BM_REQUEST_TYPE_TYPE_STANDARD
                    | USB_BM_REQUEST_TYPE_RECIP_INTERFACE)
                    as u8;
                (*setup).__bindgen_anon_1.bRequest = USB_B_REQUEST_GET_DESCRIPTOR as u8;
                (*setup).__bindgen_anon_1.wValue = HID_REPORT_DESCRIPTOR_TYPE << 8;
                (*setup).__bindgen_anon_1.wIndex = interface_number as u16;
                (*setup).__bindgen_anon_1.wLength = report_descriptor_len;
            }

            let submit_err = unsafe { usb_host_transfer_submit_control(client_hdl, transfer) };
            if submit_err != ESP_OK as i32 {
                return Err("usb_host_transfer_submit_control failed");
            }

            while !result.done {
                let mut flags: u32 = 0;
                let _ = unsafe { usb_host_lib_handle_events(0, &mut flags) };
                let _ = unsafe { usb_host_client_handle_events(client_hdl, 1) };
            }

            if result.status != usb_transfer_status_t_USB_TRANSFER_STATUS_COMPLETED {
                return Err("control transfer did not complete");
            }

            let actual_data_len = result
                .actual_num_bytes
                .saturating_sub(setup_len as i32)
                .max(0) as usize;
            let copy_len = actual_data_len.min(report_len);
            let bytes = unsafe {
                let ptr = (*transfer).data_buffer.add(setup_len);
                core::slice::from_raw_parts(ptr, copy_len).to_vec()
            };

            if bytes.is_empty() {
                return Err("empty report descriptor");
            }

            Ok(bytes)
        })();

        let free_err = unsafe { usb_host_transfer_free(transfer) };
        if free_err != ESP_OK as i32 {
            return Err("usb_host_transfer_free failed");
        }

        read_result
    }

    /// Simulation helper for host-side verification of app-logic groundwork.
    /// Never called in the real target path.
    #[cfg(not(target_os = "espidf"))]
    pub fn simulate_events_for_test(&mut self) {
        if self.simulated_once {
            return;
        }
        self.simulated_once = true;

        let dev_ref = UsbDeviceRef {
            device_id: DeviceId(1),
            topology: ConnectionTopology::Direct,
            vendor_id: 0x045e,
            product_id: 0x028e,
        };
        if let Ok(mut q) = self.event_tx.lock() {
            q.push_back(UsbIngressEvent::DeviceAttached(dev_ref.clone()));
        }

        let iface_ref = UsbInterfaceRef {
            device: dev_ref.clone(),
            interface_id: InterfaceId(0),
        };
        if let Ok(mut q) = self.event_tx.lock() {
            q.push_back(UsbIngressEvent::InterfaceDiscovered {
                source: iface_ref,
                class_code: 3,
                subclass_code: 0,
                protocol_code: 0,
            });
        }
    }

    #[cfg(not(target_os = "espidf"))]
    pub fn tick_host_noop(&self) {}
}

#[cfg(target_os = "espidf")]
fn resubmit_interrupt_transfer(interface_session: &mut TargetHidInterfaceSession) -> bool {
    interface_session.result.done = false;
    interface_session.result.status = usb_transfer_status_t_USB_TRANSFER_STATUS_ERROR;
    interface_session.result.actual_num_bytes = 0;

    unsafe {
        (*interface_session.transfer).actual_num_bytes = 0;
        (*interface_session.transfer).num_bytes = interface_session.endpoint.max_packet_size as i32;
    }

    let submit_err = unsafe { usb_host_transfer_submit(interface_session.transfer) };
    submit_err == ESP_OK as i32
}

#[cfg(target_os = "espidf")]
fn recover_interrupt_transfer(
    dev_hdl: usb_device_handle_t,
    interface_session: &mut TargetHidInterfaceSession,
) -> bool {
    let _ = unsafe { usb_host_endpoint_flush(dev_hdl, interface_session.endpoint.address) };
    let _ = unsafe { usb_host_endpoint_clear(dev_hdl, interface_session.endpoint.address) };
    resubmit_interrupt_transfer(interface_session)
}

#[cfg(target_os = "espidf")]
fn cleanup_device_session(
    client_hdl: usb_host_client_handle_t,
    session: &mut TargetDeviceSession,
) -> bool {
    let mut all_interfaces_clean = true;

    for interface_session in &mut session.interfaces {
        if interface_session.in_flight {
            if !interface_session.result.done {
                let _ = unsafe {
                    usb_host_endpoint_halt(session.dev_hdl, interface_session.endpoint.address)
                };
                let _ = unsafe {
                    usb_host_endpoint_flush(session.dev_hdl, interface_session.endpoint.address)
                };
                for _ in 0..4 {
                    if interface_session.result.done {
                        break;
                    }
                    let _ = unsafe { usb_host_client_handle_events(client_hdl, 0) };
                }
            }

            if interface_session.result.done {
                interface_session.in_flight = false;
            }
        }

        if interface_session.in_flight {
            all_interfaces_clean = false;
            continue;
        }

        if !interface_session.transfer.is_null() {
            let free_err = unsafe { usb_host_transfer_free(interface_session.transfer) };
            if free_err == ESP_OK as i32 {
                interface_session.transfer = core::ptr::null_mut();
            } else {
                all_interfaces_clean = false;
            }
        }

        if interface_session.claimed {
            let release_err = unsafe {
                usb_host_interface_release(
                    client_hdl,
                    session.dev_hdl,
                    interface_session.source.interface_id.0 as u8,
                )
            };
            if release_err == ESP_OK as i32 {
                interface_session.claimed = false;
            } else {
                all_interfaces_clean = false;
            }
        }
    }

    if !all_interfaces_clean {
        return false;
    }

    let close_err = unsafe { usb_host_device_close(client_hdl, session.dev_hdl) };
    close_err == ESP_OK as i32
}

#[cfg(target_os = "espidf")]
fn round_up_to_mps(value: usize, mps: usize) -> usize {
    if mps == 0 {
        value
    } else {
        value.div_ceil(mps) * mps
    }
}

#[cfg(test)]
mod tests {
    use super::{
        EndpointDescriptorInfo, InterfaceDescriptorInfo, parse_hid_interfaces_from_config,
        parse_interfaces_from_config,
    };

    #[test]
    fn parses_hid_interface_descriptors_only() {
        let blob = [
            9, 2, 34, 0, 2, 1, 0, 0x80, 50, // config desc
            9, 4, 0, 0, 1, 3, 1, 2, 0, // HID iface (boot keyboard)
            9, 4, 1, 0, 1, 8, 6, 80, 0, // mass storage iface
        ];

        let hid = parse_hid_interfaces_from_config(&blob);
        assert_eq!(hid, vec![(0, 1, 2)]);
    }

    #[test]
    fn parses_all_interface_descriptors_for_target_witness() {
        let blob = [
            9, 2, 34, 0, 2, 1, 0, 0x80, 50, // config desc
            9, 4, 0, 0, 1, 3, 1, 2, 0, // HID iface (boot keyboard)
            9, 4, 1, 0, 1, 255, 93, 1, 0, // vendor-specific iface
        ];

        let interfaces = parse_interfaces_from_config(&blob);
        assert_eq!(
            interfaces,
            vec![
                InterfaceDescriptorInfo {
                    interface_number: 0,
                    class_code: 3,
                    subclass_code: 1,
                    protocol_code: 2,
                    report_descriptor_len: None,
                    interrupt_in_endpoint: None,
                },
                InterfaceDescriptorInfo {
                    interface_number: 1,
                    class_code: 255,
                    subclass_code: 93,
                    protocol_code: 1,
                    report_descriptor_len: None,
                    interrupt_in_endpoint: None,
                }
            ]
        );
    }

    #[test]
    fn parses_hid_report_descriptor_lengths() {
        let blob = [
            9, 2, 34, 0, 1, 1, 0, 0x80, 50, // config desc
            9, 4, 3, 0, 1, 3, 0, 0, 0, // HID iface
            9, 0x21, 0x11, 0x01, 0, 1, 0x22, 0x3f, 0, // HID desc
        ];

        let interfaces = parse_interfaces_from_config(&blob);
        assert_eq!(
            interfaces,
            vec![InterfaceDescriptorInfo {
                interface_number: 3,
                class_code: 3,
                subclass_code: 0,
                protocol_code: 0,
                report_descriptor_len: Some(63),
                interrupt_in_endpoint: None,
            }]
        );
    }

    #[test]
    fn parses_hid_interrupt_in_endpoint() {
        let blob = [
            9, 2, 34, 0, 1, 1, 0, 0x80, 50, // config desc
            9, 4, 2, 0, 1, 3, 0, 0, 0, // HID iface
            9, 0x21, 0x11, 0x01, 0, 1, 0x22, 0x20, 0, // HID desc
            7, 5, 0x81, 0x03, 0x10, 0, 10, // interrupt IN endpoint
        ];

        let interfaces = parse_interfaces_from_config(&blob);
        assert_eq!(
            interfaces,
            vec![InterfaceDescriptorInfo {
                interface_number: 2,
                class_code: 3,
                subclass_code: 0,
                protocol_code: 0,
                report_descriptor_len: Some(32),
                interrupt_in_endpoint: Some(EndpointDescriptorInfo {
                    address: 0x81,
                    attributes: 0x03,
                    max_packet_size: 16,
                    interval: 10,
                }),
            }]
        );
    }

    #[test]
    fn stops_on_invalid_descriptor_lengths() {
        let blob = [9, 2, 10, 0, 1, 1, 0, 0x80, 50, 0, 4, 0];
        let hid = parse_hid_interfaces_from_config(&blob);
        assert!(hid.is_empty());
    }
}
