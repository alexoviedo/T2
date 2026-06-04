//! BLE HID transport glue.

use usb2ble_contracts::{
    BleCompatibilityVariant, BleLinkState, BleTransport, BleTransportError, EncodedBleReport,
    PersonaDescriptor, PersonaId,
};

#[cfg(not(target_os = "espidf"))]
/// Host-side BLE transport stub for tests and local command-path validation.
#[derive(Debug)]
pub struct BleHidTransport {
    state: BleLinkState,
    active_persona: Option<PersonaId>,
    active_variant: Option<BleCompatibilityVariant>,
    published_reports: Vec<EncodedBleReport>,
}

#[cfg(not(target_os = "espidf"))]
impl BleHidTransport {
    /// Create a host-side BLE transport stub.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Reports published through the host stub.
    #[must_use]
    pub fn published_reports(&self) -> &[EncodedBleReport] {
        &self.published_reports
    }
}

#[cfg(not(target_os = "espidf"))]
impl Default for BleHidTransport {
    fn default() -> Self {
        Self {
            state: BleLinkState::Idle,
            active_persona: None,
            active_variant: None,
            published_reports: Vec::new(),
        }
    }
}

#[cfg(not(target_os = "espidf"))]
impl BleTransport for BleHidTransport {
    fn current_state(&self) -> BleLinkState {
        self.state
    }

    fn activate_persona(
        &mut self,
        descriptor: &PersonaDescriptor,
    ) -> Result<(), BleTransportError> {
        if let Some(active) = self.active_persona {
            if active == descriptor.persona_id {
                return Ok(());
            }
            return Err(BleTransportError::PersonaAlreadyActive);
        }

        self.active_persona = Some(descriptor.persona_id);
        self.active_variant = Some(descriptor.compatibility_variant);
        self.state = BleLinkState::Advertising;
        Ok(())
    }

    fn publish_report(&mut self, report: &EncodedBleReport) -> Result<(), BleTransportError> {
        if self.active_persona != Some(report.persona_id) {
            return Err(BleTransportError::PersonaMismatch);
        }
        self.published_reports.push(report.clone());
        self.state = BleLinkState::Connected;
        Ok(())
    }

    fn forget_bonds(&mut self) -> Result<(), BleTransportError> {
        Ok(())
    }

    fn start_adv_smoke_test(&mut self, _name: &str) -> Result<(), BleTransportError> {
        self.state = BleLinkState::Advertising;
        Ok(())
    }

    fn stop_adv_smoke_test(&mut self) -> Result<(), BleTransportError> {
        self.state = BleLinkState::Idle;
        Ok(())
    }

    fn adv_smoke_test_status_json(&self) -> String {
        format!(
            "{{\"supported\":true,\"active\":{},\"target\":\"host_stub\"}}",
            self.state == BleLinkState::Advertising
        )
    }

    fn advertising_events_json(&self) -> String {
        "{\"supported\":true,\"target\":\"host_stub\"}".to_string()
    }
}

#[cfg(target_os = "espidf")]
mod target {
    #![allow(unsafe_op_in_unsafe_fn)]

    use super::*;
    use core::ffi::{c_char, c_void};
    use core::ptr;
    use core::sync::atomic::{AtomicBool, AtomicI32, AtomicPtr, AtomicU8, AtomicU32, Ordering};
    use esp_idf_sys::{
        AGC_RECORRECT_EN, BLE_CTRL_CHECK_CONNECT_IND_ACCESS_ADDRESS_ENABLED,
        BLE_HW_TARGET_CODE_CHIP_ECO0, BLE_SECURITY_ENABLE, BT_BLE_ADV_DATA_LENGTH_ZERO_AUX,
        BT_BLE_CCA_MODE, BT_CTRL_50_FEATURE_SUPPORT, BT_CTRL_BLE_ADV, BT_CTRL_BLE_LLCP_DISC_FLAG,
        BT_CTRL_BLE_MASTER, BT_CTRL_BLE_SCAN, BT_CTRL_BLE_TEST, BT_CTRL_DTM_ENABLE,
        BT_CTRL_RUN_IN_FLASH_ONLY, BT_CTRL_SCAN_BACKOFF_UPPERLIMITMAX, CFG_MASK,
        CONFIG_BT_CTRL_ADV_DUP_FILT_MAX, CONFIG_BT_CTRL_BLE_MAX_ACT_EFF,
        CONFIG_BT_CTRL_BLE_STATIC_ACL_TX_BUF_NB, CONFIG_BT_CTRL_CE_LENGTH_TYPE_EFF,
        CONFIG_BT_CTRL_CHAN_ASS_EN, CONFIG_BT_CTRL_COEX_PHY_CODED_TX_RX_TLIM_EFF,
        CONFIG_BT_CTRL_DFT_TX_POWER_LEVEL_EFF, CONFIG_BT_CTRL_DUPL_SCAN_CACHE_REFRESH_PERIOD,
        CONFIG_BT_CTRL_HCI_TL_EFF, CONFIG_BT_CTRL_HW_CCA_EFF, CONFIG_BT_CTRL_HW_CCA_VAL,
        CONFIG_BT_CTRL_LE_PING_EN, CONFIG_BT_CTRL_MODE_EFF, CONFIG_BT_CTRL_PINNED_TO_CORE,
        CONFIG_BT_CTRL_RX_ANTENNA_INDEX_EFF, CONFIG_BT_CTRL_SLEEP_CLOCK_EFF,
        CONFIG_BT_CTRL_SLEEP_MODE_EFF, CONFIG_BT_CTRL_TX_ANTENNA_INDEX_EFF,
        DUPL_SCAN_CACHE_REFRESH_PERIOD, ESP_BLE_ENC_KEY_MASK, ESP_BLE_ID_KEY_MASK,
        ESP_BT_CTRL_CONFIG_MAGIC_VAL, ESP_BT_CTRL_CONFIG_VERSION, ESP_ERR_INVALID_STATE,
        ESP_ERR_NOT_FOUND, ESP_ERR_NVS_NEW_VERSION_FOUND, ESP_ERR_NVS_NO_FREE_PAGES,
        ESP_IO_CAP_NONE, ESP_LE_AUTH_BOND, ESP_OK, ESP_TASK_BT_CONTROLLER_PRIO,
        ESP_TASK_BT_CONTROLLER_STACK, MESH_DUPLICATE_SCAN_CACHE_SIZE,
        NORMAL_SCAN_DUPLICATE_CACHE_SIZE, SCAN_DUPLICATE_MODE, SCAN_DUPLICATE_TYPE_VALUE,
        SLAVE_CE_LEN_MIN_DEFAULT, esp_ble_addr_type_t_BLE_ADDR_TYPE_PUBLIC,
        esp_ble_adv_channel_t_ADV_CHNL_ALL, esp_ble_adv_data_t,
        esp_ble_adv_filter_t_ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY, esp_ble_adv_params_t,
        esp_ble_adv_type_t_ADV_TYPE_IND, esp_ble_adv_type_t_ADV_TYPE_NONCONN_IND,
        esp_ble_adv_type_t_ADV_TYPE_SCAN_IND, esp_ble_auth_req_t, esp_ble_bond_dev_t,
        esp_ble_gap_cb_param_t, esp_ble_gap_config_adv_data, esp_ble_gap_config_adv_data_raw,
        esp_ble_gap_config_scan_rsp_data_raw, esp_ble_gap_register_callback,
        esp_ble_gap_security_rsp, esp_ble_gap_set_device_name, esp_ble_gap_set_security_param,
        esp_ble_gap_start_advertising, esp_ble_gap_stop_advertising,
        esp_ble_gatts_register_callback, esp_ble_get_bond_device_list, esp_ble_get_bond_device_num,
        esp_ble_io_cap_t, esp_ble_key_mask_t, esp_ble_remove_bond_device, esp_ble_sm_param_t,
        esp_ble_sm_param_t_ESP_BLE_SM_AUTHEN_REQ_MODE, esp_ble_sm_param_t_ESP_BLE_SM_IOCAP_MODE,
        esp_ble_sm_param_t_ESP_BLE_SM_MAX_KEY_SIZE, esp_ble_sm_param_t_ESP_BLE_SM_SET_INIT_KEY,
        esp_ble_sm_param_t_ESP_BLE_SM_SET_RSP_KEY, esp_bluedroid_config_t, esp_bluedroid_enable,
        esp_bluedroid_init_with_cfg, esp_bt_controller_config_t, esp_bt_controller_enable,
        esp_bt_controller_init, esp_bt_controller_mem_release, esp_bt_hci_tl_t, esp_bt_mode_t,
        esp_bt_mode_t_ESP_BT_MODE_BLE, esp_bt_mode_t_ESP_BT_MODE_CLASSIC_BT,
        esp_bt_status_t_ESP_BT_STATUS_SUCCESS, esp_err_t, esp_event_base_t, esp_event_handler_t,
        esp_gap_ble_cb_event_t, esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_START_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_NC_REQ_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_SCAN_RSP_DATA_SET_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_SEC_REQ_EVT, esp_gatt_if_t, esp_gatts_cb_event_t,
        nvs_flash_erase, nvs_flash_init,
    };
    use usb2ble_contracts::BlePersonaIdentity;

    const STATE_IDLE: u8 = 0;
    const STATE_INITIALIZING: u8 = 1;
    const STATE_ADVERTISING: u8 = 2;
    const STATE_CONNECTED: u8 = 3;
    const STATE_ERROR: u8 = 4;

    const OWNER_NONE: u8 = 0;
    const OWNER_RAW_SMOKE: u8 = 1;
    const OWNER_HID: u8 = 2;

    const SMOKE_STATE_IDLE: u8 = 0;
    const SMOKE_STATE_STOPPING_EXISTING_ADV: u8 = 1;
    const SMOKE_STATE_CONFIGURING_ADV_DATA: u8 = 2;
    const SMOKE_STATE_CONFIGURING_SCAN_RSP: u8 = 3;
    const SMOKE_STATE_READY_TO_START: u8 = 4;
    const SMOKE_STATE_STARTING: u8 = 5;
    const SMOKE_STATE_ADVERTISING: u8 = 6;
    const SMOKE_STATE_FAILED: u8 = 7;

    const SMOKE_MODE_CONNECTABLE: u8 = 0;
    const SMOKE_MODE_SCAN_RSP: u8 = 1;
    const SMOKE_MODE_NONCONNECTABLE: u8 = 2;

    const ESP_HID_TRANSPORT_BLE: u32 = 1;
    const ESP_HIDD_START_EVENT: i32 = 0;
    const ESP_HIDD_CONNECT_EVENT: i32 = 1;
    const ESP_HIDD_DISCONNECT_EVENT: i32 = 6;
    const ESP_HIDD_STOP_EVENT: i32 = 7;
    const GAP_ADV_DATA_SET_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT;
    const GAP_ADV_DATA_RAW_SET_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT;
    const GAP_ADV_START_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_START_COMPLETE_EVT;
    const GAP_ADV_STOP_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT;
    const GAP_SCAN_RSP_DATA_SET_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_SCAN_RSP_DATA_SET_COMPLETE_EVT;
    const GAP_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT;
    const GAP_SEC_REQ_EVT: esp_gap_ble_cb_event_t = esp_gap_ble_cb_event_t_ESP_GAP_BLE_SEC_REQ_EVT;
    const GAP_NC_REQ_EVT: esp_gap_ble_cb_event_t = esp_gap_ble_cb_event_t_ESP_GAP_BLE_NC_REQ_EVT;

    static STACK_STARTED: AtomicBool = AtomicBool::new(false);
    static HID_DEV: AtomicPtr<EspHiddDev> = AtomicPtr::new(ptr::null_mut());
    static LINK_STATE: AtomicU8 = AtomicU8::new(STATE_IDLE);
    static SMOKE_ACTIVE: AtomicBool = AtomicBool::new(false);
    static BLE_OWNER: AtomicU8 = AtomicU8::new(OWNER_NONE);
    static SMOKE_STATE: AtomicU8 = AtomicU8::new(SMOKE_STATE_IDLE);
    static SMOKE_MODE: AtomicU8 = AtomicU8::new(SMOKE_MODE_CONNECTABLE);
    static SMOKE_ADV_RAW_READY: AtomicBool = AtomicBool::new(false);
    static SMOKE_SCAN_RSP_REQUIRED: AtomicBool = AtomicBool::new(false);
    static SMOKE_SCAN_RSP_RAW_READY: AtomicBool = AtomicBool::new(false);
    static GAP_ADV_CONFIG_DONE: AtomicU32 = AtomicU32::new(0);
    static GAP_ADV_RAW_CONFIG_DONE: AtomicU32 = AtomicU32::new(0);
    static GAP_SCAN_RSP_CONFIG_DONE: AtomicU32 = AtomicU32::new(0);
    static GAP_SCAN_RSP_RAW_CONFIG_DONE: AtomicU32 = AtomicU32::new(0);
    static GAP_ADV_START_COMPLETE: AtomicU32 = AtomicU32::new(0);
    static GAP_ADV_STOP_COMPLETE: AtomicU32 = AtomicU32::new(0);
    static HIDD_START_COUNT: AtomicU32 = AtomicU32::new(0);
    static HIDD_CONNECT_COUNT: AtomicU32 = AtomicU32::new(0);
    static HIDD_DISCONNECT_COUNT: AtomicU32 = AtomicU32::new(0);
    static HIDD_STOP_COUNT: AtomicU32 = AtomicU32::new(0);
    static LAST_ADV_CONFIG_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_RAW_CONFIG_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_SCAN_RSP_CONFIG_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_SCAN_RSP_RAW_CONFIG_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_START_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_STOP_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_SET_NAME_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_ADV_CONFIG_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_SCAN_RSP_CONFIG_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_ADV_START_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_ADV_STOP_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_GAP_EVENT: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_GAP_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_INT_MIN: AtomicU32 = AtomicU32::new(0);
    static LAST_ADV_INT_MAX: AtomicU32 = AtomicU32::new(0);
    static LAST_ADV_TYPE: AtomicU32 = AtomicU32::new(0);
    static LAST_ADV_OWN_ADDR_TYPE: AtomicU32 = AtomicU32::new(0);
    static LAST_ADV_CHANNEL_MAP: AtomicU32 = AtomicU32::new(0);
    static LAST_ADV_FILTER_POLICY: AtomicU32 = AtomicU32::new(0);
    static SMOKE_ADV_RAW_LEN: AtomicU32 = AtomicU32::new(0);
    static SMOKE_SCAN_RSP_RAW_LEN: AtomicU32 = AtomicU32::new(0);

    static mut SMOKE_ADV_RAW_DATA: [u8; 31] = [0; 31];
    static mut SMOKE_SCAN_RSP_RAW_DATA: [u8; 31] = [0; 31];

    static HID_SERVICE_UUID_128: [u8; 16] = [
        0xfb, 0x34, 0x9b, 0x5f, 0x80, 0x00, 0x00, 0x80, 0x00, 0x10, 0x00, 0x00, 0x12, 0x18, 0x00,
        0x00,
    ];
    #[repr(C)]
    struct EspHiddDev {
        _private: [u8; 0],
    }

    #[repr(C)]
    struct EspHidRawReportMap {
        data: *const u8,
        len: u16,
    }

    #[repr(C)]
    struct EspHidDeviceConfig {
        vendor_id: u16,
        product_id: u16,
        version: u16,
        device_name: *const c_char,
        manufacturer_name: *const c_char,
        serial_number: *const c_char,
        report_maps: *mut EspHidRawReportMap,
        report_maps_len: u8,
    }

    unsafe extern "C" {
        fn esp_hidd_dev_init(
            config: *const EspHidDeviceConfig,
            transport: u32,
            callback: esp_event_handler_t,
            dev: *mut *mut EspHiddDev,
        ) -> esp_err_t;
        fn esp_hidd_dev_connected(dev: *mut EspHiddDev) -> bool;
        fn esp_hidd_dev_input_set(
            dev: *mut EspHiddDev,
            map_index: usize,
            report_id: usize,
            data: *mut u8,
            length: usize,
        ) -> esp_err_t;
        fn esp_hidd_gatts_event_handler(
            event: esp_gatts_cb_event_t,
            gatts_if: esp_gatt_if_t,
            param: *mut esp_idf_sys::esp_ble_gatts_cb_param_t,
        );
        fn esp_ble_confirm_reply(bd_addr: *mut u8, accept: bool) -> esp_err_t;
    }

    /// Target BLE HID transport backed by ESP-IDF Bluedroid + esp_hid.
    pub struct BleHidTransport {
        active_persona: Option<PersonaId>,
        active_variant: Option<BleCompatibilityVariant>,
        report_map: Vec<u8>,
    }

    impl BleHidTransport {
        /// Create an ESP32 BLE HID transport.
        #[must_use]
        pub fn new() -> Self {
            Self {
                active_persona: None,
                active_variant: None,
                report_map: Vec::new(),
            }
        }
    }

    impl Default for BleHidTransport {
        fn default() -> Self {
            Self::new()
        }
    }

    impl BleTransport for BleHidTransport {
        fn current_state(&self) -> BleLinkState {
            unsafe { drive_smoke_state_machine() };
            let dev = HID_DEV.load(Ordering::SeqCst);
            if !dev.is_null() && unsafe { esp_hidd_dev_connected(dev) } {
                return BleLinkState::Connected;
            }
            state_from_u8(LINK_STATE.load(Ordering::SeqCst))
        }

        fn activate_persona(
            &mut self,
            descriptor: &PersonaDescriptor,
        ) -> Result<(), BleTransportError> {
            if descriptor.report_map.is_empty() {
                set_error();
                return Err(BleTransportError::Generic);
            }

            unsafe { start_stack()? };
            if let Some(active) = self.active_persona {
                if active != descriptor.persona_id {
                    return Err(BleTransportError::PersonaAlreadyActive);
                }
                return Ok(());
            }

            self.report_map.clone_from(&descriptor.report_map);
            BLE_OWNER.store(OWNER_HID, Ordering::SeqCst);
            unsafe {
                init_hid_device(
                    &self.report_map,
                    descriptor.identity,
                    descriptor.compatibility_variant,
                )?
            };
            self.active_persona = Some(descriptor.persona_id);
            self.active_variant = Some(descriptor.compatibility_variant);
            Ok(())
        }

        fn publish_report(&mut self, report: &EncodedBleReport) -> Result<(), BleTransportError> {
            if self.active_persona != Some(report.persona_id) {
                return Err(BleTransportError::PersonaMismatch);
            }

            let dev = HID_DEV.load(Ordering::SeqCst);
            if dev.is_null() || !unsafe { esp_hidd_dev_connected(dev) } {
                return Err(BleTransportError::NotConnected);
            }

            let mut bytes = report.bytes.clone();
            esp_result(unsafe {
                esp_hidd_dev_input_set(
                    dev,
                    0,
                    usize::from(report.report_id.0),
                    bytes.as_mut_ptr(),
                    bytes.len(),
                )
            })
        }

        fn forget_bonds(&mut self) -> Result<(), BleTransportError> {
            unsafe { start_stack()? };
            let count = unsafe { esp_ble_get_bond_device_num() };
            if count <= 0 {
                return Ok(());
            }

            let mut devices = vec![esp_ble_bond_dev_t::default(); count as usize];
            let mut dev_num = count;
            esp_result(unsafe {
                esp_ble_get_bond_device_list(&mut dev_num, devices.as_mut_ptr())
            })?;
            for dev in devices.iter_mut().take(dev_num as usize) {
                esp_result(unsafe { esp_ble_remove_bond_device(dev.bd_addr.as_mut_ptr()) })?;
            }
            Ok(())
        }

        fn start_adv_smoke_test(&mut self, name: &str) -> Result<(), BleTransportError> {
            if self.active_persona.is_some() {
                return Err(BleTransportError::PersonaAlreadyActive);
            }
            unsafe {
                start_stack()?;
                reset_smoke_diagnostics();
                if advertising_may_be_active() {
                    SMOKE_STATE.store(SMOKE_STATE_STOPPING_EXISTING_ADV, Ordering::SeqCst);
                    let stop_ret = esp_ble_gap_stop_advertising();
                    LAST_ADV_STOP_RETURN.store(stop_ret, Ordering::SeqCst);
                    if stop_ret != ESP_OK && stop_ret != ESP_ERR_INVALID_STATE {
                        SMOKE_STATE.store(SMOKE_STATE_FAILED, Ordering::SeqCst);
                        BLE_OWNER.store(OWNER_NONE, Ordering::SeqCst);
                        return esp_result(stop_ret);
                    }
                }
                BLE_OWNER.store(OWNER_RAW_SMOKE, Ordering::SeqCst);
                configure_smoke_advertising(name)?;
            }
            Ok(())
        }

        fn stop_adv_smoke_test(&mut self) -> Result<(), BleTransportError> {
            let should_stop = advertising_may_be_active();
            SMOKE_ACTIVE.store(false, Ordering::SeqCst);
            if should_stop {
                let ret = unsafe { esp_ble_gap_stop_advertising() };
                LAST_ADV_STOP_RETURN.store(ret, Ordering::SeqCst);
                if ret != ESP_OK && ret != ESP_ERR_INVALID_STATE {
                    return esp_result(ret);
                }
            }
            BLE_OWNER.store(OWNER_NONE, Ordering::SeqCst);
            SMOKE_STATE.store(SMOKE_STATE_IDLE, Ordering::SeqCst);
            if LINK_STATE.load(Ordering::SeqCst) != STATE_CONNECTED {
                LINK_STATE.store(STATE_IDLE, Ordering::SeqCst);
            }
            Ok(())
        }

        fn adv_smoke_test_status_json(&self) -> String {
            format!(
                "{{\"supported\":true,\"active\":{},\"name\":\"USB2BLE_ADV_TEST\",\"connectable\":{},\"state\":\"{:?}\",\"smoke_state\":\"{}\",\"smoke_mode\":\"{}\",\"owner\":\"{}\",\"adv_payload_len\":{},\"scan_rsp_payload_len\":{},\"last_set_name_return\":{},\"last_adv_config_return\":{},\"last_adv_raw_config_status\":{},\"last_adv_start_return\":{},\"last_adv_start_status\":{},\"last_adv_stop_return\":{},\"last_adv_stop_status\":{}}}",
                SMOKE_ACTIVE.load(Ordering::SeqCst),
                SMOKE_MODE.load(Ordering::SeqCst) == SMOKE_MODE_CONNECTABLE,
                self.current_state(),
                smoke_state_name(SMOKE_STATE.load(Ordering::SeqCst)),
                smoke_mode_name(SMOKE_MODE.load(Ordering::SeqCst)),
                owner_name(BLE_OWNER.load(Ordering::SeqCst)),
                SMOKE_ADV_RAW_LEN.load(Ordering::SeqCst),
                SMOKE_SCAN_RSP_RAW_LEN.load(Ordering::SeqCst),
                option_i32(LAST_SET_NAME_RETURN.load(Ordering::SeqCst)),
                option_i32(LAST_ADV_CONFIG_RETURN.load(Ordering::SeqCst)),
                option_status(LAST_ADV_RAW_CONFIG_STATUS.load(Ordering::SeqCst)),
                option_i32(LAST_ADV_START_RETURN.load(Ordering::SeqCst)),
                option_status(LAST_ADV_START_STATUS.load(Ordering::SeqCst)),
                option_i32(LAST_ADV_STOP_RETURN.load(Ordering::SeqCst)),
                option_status(LAST_ADV_STOP_STATUS.load(Ordering::SeqCst))
            )
        }

        fn advertising_events_json(&self) -> String {
            format!(
                "{{\"supported\":true,\"owner\":\"{}\",\"smoke_state\":\"{}\",\"smoke_mode\":\"{}\",\"adv_config_done\":{},\"adv_raw_config_done\":{},\"scan_rsp_config_done\":{},\"scan_rsp_raw_config_done\":{},\"adv_start_complete\":{},\"adv_stop_complete\":{},\"hidd_start\":{},\"hidd_connect\":{},\"hidd_disconnect\":{},\"hidd_stop\":{},\"last_gap_event\":{},\"last_gap_status\":{},\"last_set_name_return\":{},\"last_adv_config_return\":{},\"last_scan_rsp_config_return\":{},\"last_adv_start_return\":{},\"last_adv_stop_return\":{},\"last_adv_config_status\":{},\"last_adv_raw_config_status\":{},\"last_scan_rsp_config_status\":{},\"last_scan_rsp_raw_config_status\":{},\"last_adv_start_status\":{},\"last_adv_stop_status\":{},\"adv_params\":{{\"interval_min\":{},\"interval_max\":{},\"adv_type\":{},\"own_addr_type\":{},\"channel_map\":{},\"filter_policy\":{}}},\"smoke_active\":{},\"state\":\"{:?}\"}}",
                owner_name(BLE_OWNER.load(Ordering::SeqCst)),
                smoke_state_name(SMOKE_STATE.load(Ordering::SeqCst)),
                smoke_mode_name(SMOKE_MODE.load(Ordering::SeqCst)),
                GAP_ADV_CONFIG_DONE.load(Ordering::SeqCst),
                GAP_ADV_RAW_CONFIG_DONE.load(Ordering::SeqCst),
                GAP_SCAN_RSP_CONFIG_DONE.load(Ordering::SeqCst),
                GAP_SCAN_RSP_RAW_CONFIG_DONE.load(Ordering::SeqCst),
                GAP_ADV_START_COMPLETE.load(Ordering::SeqCst),
                GAP_ADV_STOP_COMPLETE.load(Ordering::SeqCst),
                HIDD_START_COUNT.load(Ordering::SeqCst),
                HIDD_CONNECT_COUNT.load(Ordering::SeqCst),
                HIDD_DISCONNECT_COUNT.load(Ordering::SeqCst),
                HIDD_STOP_COUNT.load(Ordering::SeqCst),
                option_status(LAST_GAP_EVENT.load(Ordering::SeqCst)),
                option_status(LAST_GAP_STATUS.load(Ordering::SeqCst)),
                option_i32(LAST_SET_NAME_RETURN.load(Ordering::SeqCst)),
                option_i32(LAST_ADV_CONFIG_RETURN.load(Ordering::SeqCst)),
                option_i32(LAST_SCAN_RSP_CONFIG_RETURN.load(Ordering::SeqCst)),
                option_i32(LAST_ADV_START_RETURN.load(Ordering::SeqCst)),
                option_i32(LAST_ADV_STOP_RETURN.load(Ordering::SeqCst)),
                option_status(LAST_ADV_CONFIG_STATUS.load(Ordering::SeqCst)),
                option_status(LAST_ADV_RAW_CONFIG_STATUS.load(Ordering::SeqCst)),
                option_status(LAST_SCAN_RSP_CONFIG_STATUS.load(Ordering::SeqCst)),
                option_status(LAST_SCAN_RSP_RAW_CONFIG_STATUS.load(Ordering::SeqCst)),
                option_status(LAST_ADV_START_STATUS.load(Ordering::SeqCst)),
                option_status(LAST_ADV_STOP_STATUS.load(Ordering::SeqCst)),
                LAST_ADV_INT_MIN.load(Ordering::SeqCst),
                LAST_ADV_INT_MAX.load(Ordering::SeqCst),
                LAST_ADV_TYPE.load(Ordering::SeqCst),
                LAST_ADV_OWN_ADDR_TYPE.load(Ordering::SeqCst),
                LAST_ADV_CHANNEL_MAP.load(Ordering::SeqCst),
                LAST_ADV_FILTER_POLICY.load(Ordering::SeqCst),
                SMOKE_ACTIVE.load(Ordering::SeqCst),
                self.current_state()
            )
        }
    }

    unsafe fn init_hid_device(
        report_map: &[u8],
        identity: BlePersonaIdentity,
        variant: BleCompatibilityVariant,
    ) -> Result<(), BleTransportError> {
        LINK_STATE.store(STATE_INITIALIZING, Ordering::SeqCst);
        configure_security_and_advertising(identity, variant)?;
        esp_result_with_context(
            esp_ble_gatts_register_callback(Some(esp_hidd_gatts_event_handler)),
            b"gatts_register_callback\0",
        )?;

        let len = u16::try_from(report_map.len()).map_err(|_| BleTransportError::Generic)?;
        let mut report_maps = [EspHidRawReportMap {
            data: report_map.as_ptr(),
            len,
        }];
        // The identity byte slices come from persona-owned static NUL-terminated
        // constants. ESP-IDF may retain these pointers after init, so never pass
        // temporary String/CString storage here.
        let config = EspHidDeviceConfig {
            vendor_id: identity.vendor_id,
            product_id: identity.product_id,
            version: identity.version,
            device_name: identity.device_name.as_ptr().cast(),
            manufacturer_name: identity.manufacturer_name.as_ptr().cast(),
            serial_number: identity.serial_number.as_ptr().cast(),
            report_maps: report_maps.as_mut_ptr(),
            report_maps_len: 1,
        };
        let mut dev: *mut EspHiddDev = ptr::null_mut();
        esp_result_with_context(
            esp_hidd_dev_init(
                &config,
                ESP_HID_TRANSPORT_BLE,
                Some(hidd_event_callback),
                &mut dev,
            ),
            b"hidd_dev_init\0",
        )?;
        HID_DEV.store(dev, Ordering::SeqCst);
        Ok(())
    }

    unsafe fn start_stack() -> Result<(), BleTransportError> {
        if STACK_STARTED.load(Ordering::SeqCst) {
            return Ok(());
        }

        LINK_STATE.store(STATE_INITIALIZING, Ordering::SeqCst);

        let mut ret = nvs_flash_init();
        if ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND {
            esp_result(nvs_flash_erase())?;
            ret = nvs_flash_init();
        }
        esp_result(ret)?;

        let mem_ret = esp_bt_controller_mem_release(esp_bt_mode_t_ESP_BT_MODE_CLASSIC_BT);
        if mem_ret != ESP_OK && mem_ret != ESP_ERR_INVALID_STATE && mem_ret != ESP_ERR_NOT_FOUND {
            return esp_result(mem_ret);
        }

        let mut bt_cfg = bt_controller_default_config();
        esp_result(esp_bt_controller_init(&mut bt_cfg))?;
        esp_result(esp_bt_controller_enable(esp_bt_mode_t_ESP_BT_MODE_BLE))?;

        let mut bluedroid_cfg = esp_bluedroid_config_t {
            ssp_en: true,
            sc_en: false,
            ..Default::default()
        };
        esp_result(esp_bluedroid_init_with_cfg(&mut bluedroid_cfg))?;
        esp_result(esp_bluedroid_enable())?;
        esp_result(esp_ble_gap_register_callback(Some(gap_event_callback)))?;

        STACK_STARTED.store(true, Ordering::SeqCst);
        Ok(())
    }

    unsafe fn configure_security_and_advertising(
        identity: BlePersonaIdentity,
        variant: BleCompatibilityVariant,
    ) -> Result<(), BleTransportError> {
        let mut auth_req: esp_ble_auth_req_t = ESP_LE_AUTH_BOND as esp_ble_auth_req_t;
        set_security_param(
            esp_ble_sm_param_t_ESP_BLE_SM_AUTHEN_REQ_MODE,
            &mut auth_req,
            1,
        )?;

        let mut iocap: esp_ble_io_cap_t = ESP_IO_CAP_NONE as esp_ble_io_cap_t;
        set_security_param(esp_ble_sm_param_t_ESP_BLE_SM_IOCAP_MODE, &mut iocap, 1)?;

        let mut init_key: esp_ble_key_mask_t =
            (ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK) as esp_ble_key_mask_t;
        set_security_param(esp_ble_sm_param_t_ESP_BLE_SM_SET_INIT_KEY, &mut init_key, 1)?;

        let mut rsp_key: esp_ble_key_mask_t =
            (ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK) as esp_ble_key_mask_t;
        set_security_param(esp_ble_sm_param_t_ESP_BLE_SM_SET_RSP_KEY, &mut rsp_key, 1)?;

        let mut key_size = 16_u8;
        set_security_param(esp_ble_sm_param_t_ESP_BLE_SM_MAX_KEY_SIZE, &mut key_size, 1)?;

        let set_name_ret = esp_ble_gap_set_device_name(identity.device_name.as_ptr().cast());
        LAST_SET_NAME_RETURN.store(set_name_ret, Ordering::SeqCst);
        esp_result(set_name_ret)?;

        let strict_hogp = variant == BleCompatibilityVariant::GenericHogpStrict;
        let (adv_service_uuid, adv_service_uuid_len, scan_service_uuid, scan_service_uuid_len) =
            if strict_hogp {
                (
                    ptr::null_mut(),
                    0,
                    HID_SERVICE_UUID_128.as_ptr().cast_mut(),
                    HID_SERVICE_UUID_128.len() as u16,
                )
            } else {
                (
                    HID_SERVICE_UUID_128.as_ptr().cast_mut(),
                    HID_SERVICE_UUID_128.len() as u16,
                    ptr::null_mut(),
                    0,
                )
            };

        let mut adv_data = esp_ble_adv_data_t {
            set_scan_rsp: false,
            include_name: strict_hogp,
            include_txpower: false,
            min_interval: 0,
            max_interval: 0,
            appearance: i32::from(identity.appearance),
            manufacturer_len: 0,
            p_manufacturer_data: ptr::null_mut(),
            service_data_len: 0,
            p_service_data: ptr::null_mut(),
            service_uuid_len: adv_service_uuid_len,
            p_service_uuid: adv_service_uuid,
            flag: 0x06,
        };
        let adv_ret = esp_ble_gap_config_adv_data(&mut adv_data);
        LAST_ADV_CONFIG_RETURN.store(adv_ret, Ordering::SeqCst);
        esp_result_with_context(adv_ret, b"config_adv\0")?;

        let mut scan_rsp_data = esp_ble_adv_data_t {
            set_scan_rsp: true,
            include_name: !strict_hogp,
            include_txpower: false,
            min_interval: 0,
            max_interval: 0,
            appearance: 0,
            manufacturer_len: 0,
            p_manufacturer_data: ptr::null_mut(),
            service_data_len: 0,
            p_service_data: ptr::null_mut(),
            service_uuid_len: scan_service_uuid_len,
            p_service_uuid: scan_service_uuid,
            flag: 0,
        };
        let scan_ret = esp_ble_gap_config_adv_data(&mut scan_rsp_data);
        LAST_SCAN_RSP_CONFIG_RETURN.store(scan_ret, Ordering::SeqCst);
        esp_result_with_context(scan_ret, b"config_scan_rsp\0")
    }

    unsafe fn set_security_param<T>(
        param: esp_ble_sm_param_t,
        value: &mut T,
        len: u8,
    ) -> Result<(), BleTransportError> {
        esp_result(esp_ble_gap_set_security_param(
            param,
            ptr::from_mut(value).cast::<c_void>(),
            len,
        ))
    }

    unsafe fn configure_smoke_advertising(name: &str) -> Result<(), BleTransportError> {
        SMOKE_STATE.store(SMOKE_STATE_CONFIGURING_ADV_DATA, Ordering::SeqCst);
        let mode = smoke_mode_from_name(name);
        SMOKE_MODE.store(mode, Ordering::SeqCst);
        SMOKE_SCAN_RSP_REQUIRED.store(mode == SMOKE_MODE_SCAN_RSP, Ordering::SeqCst);
        let mut device_name = name
            .as_bytes()
            .iter()
            .copied()
            .filter(|byte| *byte != 0 && (*byte).is_ascii_graphic())
            .take(16)
            .collect::<Vec<u8>>();
        if device_name.is_empty() {
            device_name.extend_from_slice(b"USB2BLE_ADV_TEST");
        }
        device_name.push(0);
        let set_name_ret = esp_ble_gap_set_device_name(device_name.as_ptr().cast());
        LAST_SET_NAME_RETURN.store(set_name_ret, Ordering::SeqCst);
        esp_result_with_context(set_name_ret, b"smoke_set_name\0")?;

        let name_len = device_name.len().saturating_sub(1).min(16);
        let raw = core::ptr::addr_of_mut!(SMOKE_ADV_RAW_DATA).cast::<u8>();
        *raw.add(0) = 0x02;
        *raw.add(1) = 0x01;
        *raw.add(2) = 0x06;
        let raw_len = if mode == SMOKE_MODE_SCAN_RSP {
            3
        } else {
            *raw.add(3) = (name_len + 1) as u8;
            *raw.add(4) = 0x09;
            for (index, byte) in device_name.iter().take(name_len).enumerate() {
                *raw.add(5 + index) = *byte;
            }
            5 + name_len
        };
        if mode == SMOKE_MODE_SCAN_RSP {
            let scan_rsp = core::ptr::addr_of_mut!(SMOKE_SCAN_RSP_RAW_DATA).cast::<u8>();
            *scan_rsp.add(0) = (name_len + 1) as u8;
            *scan_rsp.add(1) = 0x09;
            for (index, byte) in device_name.iter().take(name_len).enumerate() {
                *scan_rsp.add(2 + index) = *byte;
            }
            SMOKE_SCAN_RSP_RAW_LEN.store((2 + name_len) as u32, Ordering::SeqCst);
        } else {
            SMOKE_SCAN_RSP_RAW_LEN.store(0, Ordering::SeqCst);
        }
        SMOKE_ADV_RAW_LEN.store(raw_len as u32, Ordering::SeqCst);
        let adv_ret = esp_ble_gap_config_adv_data_raw(raw, raw_len as u32);
        LAST_ADV_CONFIG_RETURN.store(adv_ret, Ordering::SeqCst);
        esp_result_with_context(adv_ret, b"smoke_config_adv_raw\0")?;
        if mode == SMOKE_MODE_SCAN_RSP {
            SMOKE_STATE.store(SMOKE_STATE_CONFIGURING_SCAN_RSP, Ordering::SeqCst);
            let scan_rsp = core::ptr::addr_of_mut!(SMOKE_SCAN_RSP_RAW_DATA).cast::<u8>();
            let scan_ret = esp_ble_gap_config_scan_rsp_data_raw(
                scan_rsp,
                SMOKE_SCAN_RSP_RAW_LEN.load(Ordering::SeqCst),
            );
            LAST_SCAN_RSP_CONFIG_RETURN.store(scan_ret, Ordering::SeqCst);
            esp_result_with_context(scan_ret, b"smoke_config_scan_rsp_raw\0")?;
        }
        Ok(())
    }

    unsafe fn start_advertising() -> Result<(), BleTransportError> {
        let ret = request_start_advertising();
        esp_result(ret)
    }

    unsafe fn request_start_advertising() -> esp_err_t {
        let mut adv_params = esp_ble_adv_params_t {
            adv_int_min: 0x20,
            adv_int_max: 0x30,
            adv_type: smoke_adv_type(),
            own_addr_type: esp_ble_addr_type_t_BLE_ADDR_TYPE_PUBLIC,
            peer_addr: [0_u8; 6],
            peer_addr_type: esp_ble_addr_type_t_BLE_ADDR_TYPE_PUBLIC,
            channel_map: esp_ble_adv_channel_t_ADV_CHNL_ALL,
            adv_filter_policy: esp_ble_adv_filter_t_ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
        };
        LAST_ADV_INT_MIN.store(u32::from(adv_params.adv_int_min), Ordering::SeqCst);
        LAST_ADV_INT_MAX.store(u32::from(adv_params.adv_int_max), Ordering::SeqCst);
        LAST_ADV_TYPE.store(adv_params.adv_type as u32, Ordering::SeqCst);
        LAST_ADV_OWN_ADDR_TYPE.store(adv_params.own_addr_type as u32, Ordering::SeqCst);
        LAST_ADV_CHANNEL_MAP.store(adv_params.channel_map as u32, Ordering::SeqCst);
        LAST_ADV_FILTER_POLICY.store(adv_params.adv_filter_policy as u32, Ordering::SeqCst);
        let ret = esp_ble_gap_start_advertising(&mut adv_params);
        LAST_ADV_START_RETURN.store(ret, Ordering::SeqCst);
        ret
    }

    unsafe fn start_smoke_after_config() {
        if BLE_OWNER.load(Ordering::SeqCst) != OWNER_RAW_SMOKE {
            return;
        }
        if !SMOKE_ADV_RAW_READY.load(Ordering::SeqCst) {
            return;
        }
        if SMOKE_SCAN_RSP_REQUIRED.load(Ordering::SeqCst)
            && !SMOKE_SCAN_RSP_RAW_READY.load(Ordering::SeqCst)
        {
            return;
        }
        let state = SMOKE_STATE.load(Ordering::SeqCst);
        if state != SMOKE_STATE_CONFIGURING_ADV_DATA && state != SMOKE_STATE_CONFIGURING_SCAN_RSP {
            return;
        }
        SMOKE_STATE.store(SMOKE_STATE_READY_TO_START, Ordering::SeqCst);
    }

    unsafe fn drive_smoke_state_machine() {
        if BLE_OWNER.load(Ordering::SeqCst) != OWNER_RAW_SMOKE
            || SMOKE_STATE.load(Ordering::SeqCst) != SMOKE_STATE_READY_TO_START
        {
            return;
        }
        let ret = request_start_advertising();
        if ret == ESP_OK {
            SMOKE_STATE.store(SMOKE_STATE_STARTING, Ordering::SeqCst);
        } else {
            SMOKE_ACTIVE.store(false, Ordering::SeqCst);
            SMOKE_STATE.store(SMOKE_STATE_FAILED, Ordering::SeqCst);
            LINK_STATE.store(STATE_ERROR, Ordering::SeqCst);
        }
    }

    fn reset_smoke_diagnostics() {
        SMOKE_ACTIVE.store(false, Ordering::SeqCst);
        SMOKE_STATE.store(SMOKE_STATE_IDLE, Ordering::SeqCst);
        SMOKE_ADV_RAW_READY.store(false, Ordering::SeqCst);
        SMOKE_SCAN_RSP_REQUIRED.store(false, Ordering::SeqCst);
        SMOKE_SCAN_RSP_RAW_READY.store(false, Ordering::SeqCst);
        LAST_ADV_RAW_CONFIG_STATUS.store(u32::MAX, Ordering::SeqCst);
        LAST_SCAN_RSP_RAW_CONFIG_STATUS.store(u32::MAX, Ordering::SeqCst);
        LAST_ADV_START_STATUS.store(u32::MAX, Ordering::SeqCst);
        LAST_ADV_STOP_STATUS.store(u32::MAX, Ordering::SeqCst);
        LAST_SET_NAME_RETURN.store(i32::MAX, Ordering::SeqCst);
        LAST_ADV_CONFIG_RETURN.store(i32::MAX, Ordering::SeqCst);
        LAST_SCAN_RSP_CONFIG_RETURN.store(i32::MAX, Ordering::SeqCst);
        LAST_ADV_START_RETURN.store(i32::MAX, Ordering::SeqCst);
        LAST_ADV_STOP_RETURN.store(i32::MAX, Ordering::SeqCst);
        LAST_GAP_EVENT.store(u32::MAX, Ordering::SeqCst);
        LAST_GAP_STATUS.store(u32::MAX, Ordering::SeqCst);
        SMOKE_ADV_RAW_LEN.store(0, Ordering::SeqCst);
        SMOKE_SCAN_RSP_RAW_LEN.store(0, Ordering::SeqCst);
    }

    fn advertising_may_be_active() -> bool {
        BLE_OWNER.load(Ordering::SeqCst) != OWNER_NONE
            || SMOKE_ACTIVE.load(Ordering::SeqCst)
            || LINK_STATE.load(Ordering::SeqCst) == STATE_ADVERTISING
    }

    fn smoke_mode_from_name(name: &str) -> u8 {
        let upper = name.to_ascii_uppercase();
        if upper.contains("NONCONN") || upper.contains("NON_CONN") {
            SMOKE_MODE_NONCONNECTABLE
        } else if upper.contains("SCANRSP") || upper.contains("SCAN_RSP") {
            SMOKE_MODE_SCAN_RSP
        } else {
            SMOKE_MODE_CONNECTABLE
        }
    }

    fn smoke_adv_type() -> esp_idf_sys::esp_ble_adv_type_t {
        match SMOKE_MODE.load(Ordering::SeqCst) {
            SMOKE_MODE_SCAN_RSP => esp_ble_adv_type_t_ADV_TYPE_SCAN_IND,
            SMOKE_MODE_NONCONNECTABLE => esp_ble_adv_type_t_ADV_TYPE_NONCONN_IND,
            _ => esp_ble_adv_type_t_ADV_TYPE_IND,
        }
    }

    unsafe extern "C" fn hidd_event_callback(
        _handler_args: *mut c_void,
        _event_base: esp_event_base_t,
        event_id: i32,
        _event_data: *mut c_void,
    ) {
        match event_id {
            ESP_HIDD_START_EVENT => {
                HIDD_START_COUNT.fetch_add(1, Ordering::SeqCst);
                LINK_STATE.store(STATE_ADVERTISING, Ordering::SeqCst);
                let _ = start_advertising();
            }
            ESP_HIDD_CONNECT_EVENT => {
                HIDD_CONNECT_COUNT.fetch_add(1, Ordering::SeqCst);
                LINK_STATE.store(STATE_CONNECTED, Ordering::SeqCst);
            }
            ESP_HIDD_DISCONNECT_EVENT => {
                HIDD_DISCONNECT_COUNT.fetch_add(1, Ordering::SeqCst);
                LINK_STATE.store(STATE_ADVERTISING, Ordering::SeqCst);
                let _ = start_advertising();
            }
            ESP_HIDD_STOP_EVENT => {
                HIDD_STOP_COUNT.fetch_add(1, Ordering::SeqCst);
                LINK_STATE.store(STATE_IDLE, Ordering::SeqCst);
            }
            _ => {}
        }
    }

    unsafe extern "C" fn gap_event_callback(
        event: esp_gap_ble_cb_event_t,
        param: *mut esp_ble_gap_cb_param_t,
    ) {
        LAST_GAP_EVENT.store(event as u32, Ordering::SeqCst);
        match event {
            GAP_ADV_DATA_SET_COMPLETE_EVT => {
                GAP_ADV_CONFIG_DONE.fetch_add(1, Ordering::SeqCst);
                if !param.is_null() {
                    let status = (*param).adv_data_cmpl.status as u32;
                    LAST_ADV_CONFIG_STATUS.store(status, Ordering::SeqCst);
                    LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                }
            }
            GAP_ADV_DATA_RAW_SET_COMPLETE_EVT => {
                GAP_ADV_RAW_CONFIG_DONE.fetch_add(1, Ordering::SeqCst);
                if !param.is_null() {
                    let status = (*param).adv_data_raw_cmpl.status as u32;
                    LAST_ADV_RAW_CONFIG_STATUS.store(status, Ordering::SeqCst);
                    LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                    if status == esp_bt_status_t_ESP_BT_STATUS_SUCCESS as u32 {
                        SMOKE_ADV_RAW_READY.store(true, Ordering::SeqCst);
                        start_smoke_after_config();
                    } else if BLE_OWNER.load(Ordering::SeqCst) == OWNER_RAW_SMOKE {
                        SMOKE_ACTIVE.store(false, Ordering::SeqCst);
                        SMOKE_STATE.store(SMOKE_STATE_FAILED, Ordering::SeqCst);
                        LINK_STATE.store(STATE_ERROR, Ordering::SeqCst);
                    }
                }
            }
            GAP_SCAN_RSP_DATA_SET_COMPLETE_EVT => {
                GAP_SCAN_RSP_CONFIG_DONE.fetch_add(1, Ordering::SeqCst);
                if !param.is_null() {
                    let status = (*param).scan_rsp_data_cmpl.status as u32;
                    LAST_SCAN_RSP_CONFIG_STATUS.store(status, Ordering::SeqCst);
                    LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                }
            }
            GAP_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT => {
                GAP_SCAN_RSP_RAW_CONFIG_DONE.fetch_add(1, Ordering::SeqCst);
                if !param.is_null() {
                    let status = (*param).scan_rsp_data_raw_cmpl.status as u32;
                    LAST_SCAN_RSP_RAW_CONFIG_STATUS.store(status, Ordering::SeqCst);
                    LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                    if status == esp_bt_status_t_ESP_BT_STATUS_SUCCESS as u32 {
                        SMOKE_SCAN_RSP_RAW_READY.store(true, Ordering::SeqCst);
                        start_smoke_after_config();
                    } else if BLE_OWNER.load(Ordering::SeqCst) == OWNER_RAW_SMOKE {
                        SMOKE_ACTIVE.store(false, Ordering::SeqCst);
                        SMOKE_STATE.store(SMOKE_STATE_FAILED, Ordering::SeqCst);
                        LINK_STATE.store(STATE_ERROR, Ordering::SeqCst);
                    }
                }
            }
            GAP_ADV_START_COMPLETE_EVT => {
                GAP_ADV_START_COMPLETE.fetch_add(1, Ordering::SeqCst);
                if param.is_null()
                    || (*param).adv_start_cmpl.status == esp_bt_status_t_ESP_BT_STATUS_SUCCESS
                {
                    if !param.is_null() {
                        let status = (*param).adv_start_cmpl.status as u32;
                        LAST_ADV_START_STATUS.store(status, Ordering::SeqCst);
                        LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                    }
                    if BLE_OWNER.load(Ordering::SeqCst) == OWNER_RAW_SMOKE {
                        SMOKE_ACTIVE.store(true, Ordering::SeqCst);
                        SMOKE_STATE.store(SMOKE_STATE_ADVERTISING, Ordering::SeqCst);
                    }
                    if LINK_STATE.load(Ordering::SeqCst) != STATE_CONNECTED {
                        LINK_STATE.store(STATE_ADVERTISING, Ordering::SeqCst);
                    }
                } else {
                    let status = (*param).adv_start_cmpl.status as u32;
                    LAST_ADV_START_STATUS.store(status, Ordering::SeqCst);
                    LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                    SMOKE_ACTIVE.store(false, Ordering::SeqCst);
                    if BLE_OWNER.load(Ordering::SeqCst) == OWNER_RAW_SMOKE {
                        SMOKE_STATE.store(SMOKE_STATE_FAILED, Ordering::SeqCst);
                    }
                    LINK_STATE.store(STATE_ERROR, Ordering::SeqCst);
                }
            }
            GAP_ADV_STOP_COMPLETE_EVT => {
                GAP_ADV_STOP_COMPLETE.fetch_add(1, Ordering::SeqCst);
                if !param.is_null() {
                    let status = (*param).adv_stop_cmpl.status as u32;
                    LAST_ADV_STOP_STATUS.store(status, Ordering::SeqCst);
                    LAST_GAP_STATUS.store(status, Ordering::SeqCst);
                }
            }
            GAP_SEC_REQ_EVT => {
                if !param.is_null() {
                    let mut req = (*param).ble_security.ble_req;
                    let _ = esp_ble_gap_security_rsp(req.bd_addr.as_mut_ptr(), true);
                }
            }
            GAP_NC_REQ_EVT => {
                if !param.is_null() {
                    let mut key = (*param).ble_security.key_notif;
                    let _ = esp_ble_confirm_reply(key.bd_addr.as_mut_ptr(), true);
                }
            }
            _ => {}
        }
    }

    fn bt_controller_default_config() -> esp_bt_controller_config_t {
        esp_bt_controller_config_t {
            magic: ESP_BT_CTRL_CONFIG_MAGIC_VAL,
            version: ESP_BT_CTRL_CONFIG_VERSION,
            controller_task_stack_size: ESP_TASK_BT_CONTROLLER_STACK as u16,
            controller_task_prio: ESP_TASK_BT_CONTROLLER_PRIO as u8,
            controller_task_run_cpu: CONFIG_BT_CTRL_PINNED_TO_CORE as u8,
            bluetooth_mode: CONFIG_BT_CTRL_MODE_EFF as u8,
            ble_max_act: CONFIG_BT_CTRL_BLE_MAX_ACT_EFF as u8,
            sleep_mode: CONFIG_BT_CTRL_SLEEP_MODE_EFF as u8,
            sleep_clock: CONFIG_BT_CTRL_SLEEP_CLOCK_EFF as u8,
            ble_st_acl_tx_buf_nb: CONFIG_BT_CTRL_BLE_STATIC_ACL_TX_BUF_NB as u8,
            ble_hw_cca_check: CONFIG_BT_CTRL_HW_CCA_EFF as u8,
            ble_adv_dup_filt_max: CONFIG_BT_CTRL_ADV_DUP_FILT_MAX as u16,
            coex_param_en: false,
            ce_len_type: CONFIG_BT_CTRL_CE_LENGTH_TYPE_EFF as u8,
            coex_use_hooks: false,
            hci_tl_type: CONFIG_BT_CTRL_HCI_TL_EFF as u8,
            hci_tl_funcs: ptr::null_mut::<esp_bt_hci_tl_t>(),
            txant_dft: CONFIG_BT_CTRL_TX_ANTENNA_INDEX_EFF as u8,
            rxant_dft: CONFIG_BT_CTRL_RX_ANTENNA_INDEX_EFF as u8,
            txpwr_dft: CONFIG_BT_CTRL_DFT_TX_POWER_LEVEL_EFF as u8,
            cfg_mask: CFG_MASK,
            scan_duplicate_mode: SCAN_DUPLICATE_MODE as u8,
            scan_duplicate_type: SCAN_DUPLICATE_TYPE_VALUE as u8,
            normal_adv_size: NORMAL_SCAN_DUPLICATE_CACHE_SIZE as u16,
            mesh_adv_size: MESH_DUPLICATE_SCAN_CACHE_SIZE as u16,
            coex_phy_coded_tx_rx_time_limit: CONFIG_BT_CTRL_COEX_PHY_CODED_TX_RX_TLIM_EFF as u8,
            hw_target_code: BLE_HW_TARGET_CODE_CHIP_ECO0,
            slave_ce_len_min: SLAVE_CE_LEN_MIN_DEFAULT as u8,
            hw_recorrect_en: AGC_RECORRECT_EN as u8,
            cca_thresh: CONFIG_BT_CTRL_HW_CCA_VAL as u8,
            scan_backoff_upperlimitmax: BT_CTRL_SCAN_BACKOFF_UPPERLIMITMAX as u16,
            dup_list_refresh_period: DUPL_SCAN_CACHE_REFRESH_PERIOD
                .max(CONFIG_BT_CTRL_DUPL_SCAN_CACHE_REFRESH_PERIOD)
                as u16,
            ble_50_feat_supp: BT_CTRL_50_FEATURE_SUPPORT != 0,
            ble_cca_mode: BT_BLE_CCA_MODE as u8,
            ble_data_lenth_zero_aux: BT_BLE_ADV_DATA_LENGTH_ZERO_AUX as u8,
            ble_chan_ass_en: CONFIG_BT_CTRL_CHAN_ASS_EN as u8,
            ble_ping_en: CONFIG_BT_CTRL_LE_PING_EN as u8,
            ble_llcp_disc_flag: BT_CTRL_BLE_LLCP_DISC_FLAG as u8,
            run_in_flash: BT_CTRL_RUN_IN_FLASH_ONLY != 0,
            dtm_en: BT_CTRL_DTM_ENABLE != 0,
            enc_en: BLE_SECURITY_ENABLE != 0,
            qa_test: BT_CTRL_BLE_TEST != 0,
            connect_en: BT_CTRL_BLE_MASTER != 0,
            scan_en: BT_CTRL_BLE_SCAN != 0,
            ble_aa_check: BLE_CTRL_CHECK_CONNECT_IND_ACCESS_ADDRESS_ENABLED != 0,
            adv_en: BT_CTRL_BLE_ADV != 0,
            ..Default::default()
        }
    }

    fn esp_result(code: esp_err_t) -> Result<(), BleTransportError> {
        if code == ESP_OK {
            Ok(())
        } else {
            set_error();
            Err(BleTransportError::Generic)
        }
    }

    unsafe fn esp_result_with_context(
        code: esp_err_t,
        context: &'static [u8],
    ) -> Result<(), BleTransportError> {
        if code == ESP_OK {
            Ok(())
        } else {
            esp_idf_sys::printf(
                b"[BLE_HID] %s failed: %ld\n\0".as_ptr().cast(),
                context.as_ptr().cast::<c_char>(),
                code,
            );
            set_error();
            Err(BleTransportError::Generic)
        }
    }

    fn set_error() {
        LINK_STATE.store(STATE_ERROR, Ordering::SeqCst);
    }

    fn state_from_u8(value: u8) -> BleLinkState {
        match value {
            STATE_INITIALIZING => BleLinkState::Initializing,
            STATE_ADVERTISING => BleLinkState::Advertising,
            STATE_CONNECTED => BleLinkState::Connected,
            STATE_ERROR => BleLinkState::Error,
            _ => BleLinkState::Idle,
        }
    }

    fn option_status(value: u32) -> String {
        if value == u32::MAX {
            "null".to_string()
        } else {
            value.to_string()
        }
    }

    fn option_i32(value: i32) -> String {
        if value == i32::MAX {
            "null".to_string()
        } else {
            value.to_string()
        }
    }

    fn owner_name(value: u8) -> &'static str {
        match value {
            OWNER_RAW_SMOKE => "raw_smoke",
            OWNER_HID => "hid",
            _ => "none",
        }
    }

    fn smoke_state_name(value: u8) -> &'static str {
        match value {
            SMOKE_STATE_STOPPING_EXISTING_ADV => "stopping_existing_adv",
            SMOKE_STATE_CONFIGURING_ADV_DATA => "configuring_adv_data",
            SMOKE_STATE_CONFIGURING_SCAN_RSP => "configuring_scan_rsp",
            SMOKE_STATE_READY_TO_START => "ready_to_start",
            SMOKE_STATE_STARTING => "starting",
            SMOKE_STATE_ADVERTISING => "advertising",
            SMOKE_STATE_FAILED => "failed",
            _ => "idle",
        }
    }

    fn smoke_mode_name(value: u8) -> &'static str {
        match value {
            SMOKE_MODE_SCAN_RSP => "scan_response_name",
            SMOKE_MODE_NONCONNECTABLE => "nonconnectable",
            _ => "connectable",
        }
    }

    #[allow(dead_code)]
    fn _assert_ble_mode(_: esp_bt_mode_t) {}
}

#[cfg(target_os = "espidf")]
pub use target::BleHidTransport;
