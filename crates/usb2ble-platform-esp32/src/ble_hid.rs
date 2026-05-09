//! BLE HID transport glue.

use usb2ble_contracts::{
    BleLinkState, BleTransport, BleTransportError, EncodedBleReport, PersonaDescriptor, PersonaId,
};

#[cfg(not(target_os = "espidf"))]
/// Host-side BLE transport stub for tests and local command-path validation.
#[derive(Debug)]
pub struct BleHidTransport {
    state: BleLinkState,
    active_persona: Option<PersonaId>,
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
}

#[cfg(target_os = "espidf")]
mod target {
    #![allow(unsafe_op_in_unsafe_fn)]

    use super::*;
    use core::ffi::{c_char, c_void};
    use core::ptr;
    use core::sync::atomic::{AtomicBool, AtomicPtr, AtomicU8, Ordering};
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
        esp_ble_adv_type_t_ADV_TYPE_IND, esp_ble_auth_req_t, esp_ble_bond_dev_t,
        esp_ble_gap_cb_param_t, esp_ble_gap_config_adv_data, esp_ble_gap_register_callback,
        esp_ble_gap_security_rsp, esp_ble_gap_set_device_name, esp_ble_gap_set_security_param,
        esp_ble_gap_start_advertising, esp_ble_gatts_register_callback,
        esp_ble_get_bond_device_list, esp_ble_get_bond_device_num, esp_ble_io_cap_t,
        esp_ble_key_mask_t, esp_ble_remove_bond_device, esp_ble_sm_param_t,
        esp_ble_sm_param_t_ESP_BLE_SM_AUTHEN_REQ_MODE, esp_ble_sm_param_t_ESP_BLE_SM_IOCAP_MODE,
        esp_ble_sm_param_t_ESP_BLE_SM_MAX_KEY_SIZE, esp_ble_sm_param_t_ESP_BLE_SM_SET_INIT_KEY,
        esp_ble_sm_param_t_ESP_BLE_SM_SET_RSP_KEY, esp_bluedroid_config_t, esp_bluedroid_enable,
        esp_bluedroid_init_with_cfg, esp_bt_controller_config_t, esp_bt_controller_enable,
        esp_bt_controller_init, esp_bt_controller_mem_release, esp_bt_hci_tl_t, esp_bt_mode_t,
        esp_bt_mode_t_ESP_BT_MODE_BLE, esp_bt_mode_t_ESP_BT_MODE_CLASSIC_BT,
        esp_bt_status_t_ESP_BT_STATUS_SUCCESS, esp_err_t, esp_event_base_t, esp_event_handler_t,
        esp_gap_ble_cb_event_t, esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_START_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_NC_REQ_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_SEC_REQ_EVT, esp_gatt_if_t, esp_gatts_cb_event_t,
        nvs_flash_erase, nvs_flash_init,
    };
    use usb2ble_contracts::BlePersonaIdentity;

    const STATE_IDLE: u8 = 0;
    const STATE_INITIALIZING: u8 = 1;
    const STATE_ADVERTISING: u8 = 2;
    const STATE_CONNECTED: u8 = 3;
    const STATE_ERROR: u8 = 4;

    const ESP_HID_TRANSPORT_BLE: u32 = 1;
    const ESP_HIDD_START_EVENT: i32 = 0;
    const ESP_HIDD_CONNECT_EVENT: i32 = 1;
    const ESP_HIDD_DISCONNECT_EVENT: i32 = 6;
    const ESP_HIDD_STOP_EVENT: i32 = 7;
    const GAP_ADV_START_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_START_COMPLETE_EVT;
    const GAP_SEC_REQ_EVT: esp_gap_ble_cb_event_t = esp_gap_ble_cb_event_t_ESP_GAP_BLE_SEC_REQ_EVT;
    const GAP_NC_REQ_EVT: esp_gap_ble_cb_event_t = esp_gap_ble_cb_event_t_ESP_GAP_BLE_NC_REQ_EVT;

    static STACK_STARTED: AtomicBool = AtomicBool::new(false);
    static HID_DEV: AtomicPtr<EspHiddDev> = AtomicPtr::new(ptr::null_mut());
    static LINK_STATE: AtomicU8 = AtomicU8::new(STATE_IDLE);

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
        report_map: Vec<u8>,
    }

    impl BleHidTransport {
        /// Create an ESP32 BLE HID transport.
        #[must_use]
        pub fn new() -> Self {
            Self {
                active_persona: None,
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
            unsafe { init_hid_device(&self.report_map, descriptor.identity)? };
            self.active_persona = Some(descriptor.persona_id);
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
    }

    unsafe fn init_hid_device(
        report_map: &[u8],
        identity: BlePersonaIdentity,
    ) -> Result<(), BleTransportError> {
        LINK_STATE.store(STATE_INITIALIZING, Ordering::SeqCst);
        configure_security_and_advertising(identity)?;
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
        };
        esp_result(esp_bluedroid_init_with_cfg(&mut bluedroid_cfg))?;
        esp_result(esp_bluedroid_enable())?;
        esp_result(esp_ble_gap_register_callback(Some(gap_event_callback)))?;

        STACK_STARTED.store(true, Ordering::SeqCst);
        Ok(())
    }

    unsafe fn configure_security_and_advertising(
        identity: BlePersonaIdentity,
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

        esp_result(esp_ble_gap_set_device_name(
            identity.device_name.as_ptr().cast(),
        ))?;

        let mut adv_data = esp_ble_adv_data_t {
            set_scan_rsp: false,
            include_name: false,
            include_txpower: false,
            min_interval: 0,
            max_interval: 0,
            appearance: i32::from(identity.appearance),
            manufacturer_len: 0,
            p_manufacturer_data: ptr::null_mut(),
            service_data_len: 0,
            p_service_data: ptr::null_mut(),
            service_uuid_len: HID_SERVICE_UUID_128.len() as u16,
            p_service_uuid: HID_SERVICE_UUID_128.as_ptr().cast_mut(),
            flag: 0x06,
        };
        esp_result_with_context(esp_ble_gap_config_adv_data(&mut adv_data), b"config_adv\0")?;

        let mut scan_rsp_data = esp_ble_adv_data_t {
            set_scan_rsp: true,
            include_name: true,
            include_txpower: false,
            min_interval: 0,
            max_interval: 0,
            appearance: 0,
            manufacturer_len: 0,
            p_manufacturer_data: ptr::null_mut(),
            service_data_len: 0,
            p_service_data: ptr::null_mut(),
            service_uuid_len: 0,
            p_service_uuid: ptr::null_mut(),
            flag: 0,
        };
        esp_result_with_context(
            esp_ble_gap_config_adv_data(&mut scan_rsp_data),
            b"config_scan_rsp\0",
        )
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

    unsafe fn start_advertising() -> Result<(), BleTransportError> {
        let mut adv_params = esp_ble_adv_params_t {
            adv_int_min: 0x20,
            adv_int_max: 0x30,
            adv_type: esp_ble_adv_type_t_ADV_TYPE_IND,
            own_addr_type: esp_ble_addr_type_t_BLE_ADDR_TYPE_PUBLIC,
            peer_addr: [0_u8; 6],
            peer_addr_type: esp_ble_addr_type_t_BLE_ADDR_TYPE_PUBLIC,
            channel_map: esp_ble_adv_channel_t_ADV_CHNL_ALL,
            adv_filter_policy: esp_ble_adv_filter_t_ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
        };
        esp_result(esp_ble_gap_start_advertising(&mut adv_params))
    }

    unsafe extern "C" fn hidd_event_callback(
        _handler_args: *mut c_void,
        _event_base: esp_event_base_t,
        event_id: i32,
        _event_data: *mut c_void,
    ) {
        match event_id {
            ESP_HIDD_START_EVENT => {
                LINK_STATE.store(STATE_ADVERTISING, Ordering::SeqCst);
                let _ = start_advertising();
            }
            ESP_HIDD_CONNECT_EVENT => {
                LINK_STATE.store(STATE_CONNECTED, Ordering::SeqCst);
            }
            ESP_HIDD_DISCONNECT_EVENT => {
                LINK_STATE.store(STATE_ADVERTISING, Ordering::SeqCst);
                let _ = start_advertising();
            }
            ESP_HIDD_STOP_EVENT => {
                LINK_STATE.store(STATE_IDLE, Ordering::SeqCst);
            }
            _ => {}
        }
    }

    unsafe extern "C" fn gap_event_callback(
        event: esp_gap_ble_cb_event_t,
        param: *mut esp_ble_gap_cb_param_t,
    ) {
        match event {
            GAP_ADV_START_COMPLETE_EVT => {
                if param.is_null()
                    || (*param).adv_start_cmpl.status == esp_bt_status_t_ESP_BT_STATUS_SUCCESS
                {
                    if LINK_STATE.load(Ordering::SeqCst) != STATE_CONNECTED {
                        LINK_STATE.store(STATE_ADVERTISING, Ordering::SeqCst);
                    }
                } else {
                    LINK_STATE.store(STATE_ERROR, Ordering::SeqCst);
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

    #[allow(dead_code)]
    fn _assert_ble_mode(_: esp_bt_mode_t) {}
}

#[cfg(target_os = "espidf")]
pub use target::BleHidTransport;
