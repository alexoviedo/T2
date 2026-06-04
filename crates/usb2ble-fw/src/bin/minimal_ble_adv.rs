//! Minimal ESP32-S3 BLE advertising isolation firmware.
//!
//! This diagnostic binary intentionally avoids the USB2BLE app, USB host,
//! HID, persona, and bridge paths. It initializes only NVS, BLE controller,
//! Bluedroid, one GAP callback, and one tiny raw legacy advertisement.

#[cfg(not(target_os = "espidf"))]
fn main() {
    println!("minimal_ble_adv is an ESP-IDF target-only diagnostic binary");
}

#[cfg(target_os = "espidf")]
mod target {
    #![allow(unsafe_op_in_unsafe_fn)]

    use core::ffi::c_char;
    use core::ptr;
    use core::sync::atomic::{AtomicBool, AtomicI32, AtomicU32, Ordering};
    use std::time::Duration;

    use esp_idf_sys::{
        AGC_RECORRECT_EN, BLE_HW_TARGET_CODE_CHIP_ECO0, BT_BLE_ADV_DATA_LENGTH_ZERO_AUX,
        BT_BLE_CCA_MODE, BT_CTRL_50_FEATURE_SUPPORT, BT_CTRL_SCAN_BACKOFF_UPPERLIMITMAX, CFG_MASK,
        CONFIG_BT_CTRL_ADV_DUP_FILT_MAX, CONFIG_BT_CTRL_BLE_MAX_ACT_EFF,
        CONFIG_BT_CTRL_BLE_STATIC_ACL_TX_BUF_NB, CONFIG_BT_CTRL_CE_LENGTH_TYPE_EFF,
        CONFIG_BT_CTRL_CHAN_ASS_EN, CONFIG_BT_CTRL_COEX_PHY_CODED_TX_RX_TLIM_EFF,
        CONFIG_BT_CTRL_DFT_TX_POWER_LEVEL_EFF, CONFIG_BT_CTRL_DUPL_SCAN_CACHE_REFRESH_PERIOD,
        CONFIG_BT_CTRL_HCI_TL_EFF, CONFIG_BT_CTRL_HW_CCA_EFF, CONFIG_BT_CTRL_HW_CCA_VAL,
        CONFIG_BT_CTRL_LE_PING_EN, CONFIG_BT_CTRL_MODE_EFF, CONFIG_BT_CTRL_PINNED_TO_CORE,
        CONFIG_BT_CTRL_RX_ANTENNA_INDEX_EFF, CONFIG_BT_CTRL_SLEEP_CLOCK_EFF,
        CONFIG_BT_CTRL_SLEEP_MODE_EFF, CONFIG_BT_CTRL_TX_ANTENNA_INDEX_EFF,
        DUPL_SCAN_CACHE_REFRESH_PERIOD, ESP_BT_CTRL_CONFIG_MAGIC_VAL, ESP_BT_CTRL_CONFIG_VERSION,
        ESP_ERR_INVALID_STATE, ESP_ERR_NOT_FOUND, ESP_ERR_NVS_NEW_VERSION_FOUND,
        ESP_ERR_NVS_NO_FREE_PAGES, ESP_OK, ESP_TASK_BT_CONTROLLER_PRIO,
        ESP_TASK_BT_CONTROLLER_STACK, MESH_DUPLICATE_SCAN_CACHE_SIZE,
        NORMAL_SCAN_DUPLICATE_CACHE_SIZE, SCAN_DUPLICATE_MODE, SCAN_DUPLICATE_TYPE_VALUE,
        SLAVE_CE_LEN_MIN_DEFAULT, esp_ble_addr_type_t_BLE_ADDR_TYPE_PUBLIC,
        esp_ble_adv_channel_t_ADV_CHNL_ALL, esp_ble_adv_filter_t_ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
        esp_ble_adv_params_t, esp_ble_adv_type_t_ADV_TYPE_IND, esp_ble_gap_cb_param_t,
        esp_ble_gap_config_adv_data_raw, esp_ble_gap_register_callback,
        esp_ble_gap_set_device_name, esp_ble_gap_start_advertising, esp_bluedroid_enable,
        esp_bluedroid_get_status, esp_bluedroid_init, esp_bt_controller_config_t,
        esp_bt_controller_enable, esp_bt_controller_get_status, esp_bt_controller_init,
        esp_bt_controller_mem_release, esp_bt_hci_tl_t, esp_bt_mode_t_ESP_BT_MODE_BLE,
        esp_bt_mode_t_ESP_BT_MODE_CLASSIC_BT, esp_bt_status_t_ESP_BT_STATUS_SUCCESS, esp_err_t,
        esp_gap_ble_cb_event_t, esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_START_COMPLETE_EVT,
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT, nvs_flash_erase, nvs_flash_init,
        printf,
    };

    const GAP_ADV_DATA_RAW_SET_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT;
    const GAP_ADV_START_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_START_COMPLETE_EVT;
    const GAP_ADV_STOP_COMPLETE_EVT: esp_gap_ble_cb_event_t =
        esp_gap_ble_cb_event_t_ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT;

    static ADV_CONFIG_READY: AtomicBool = AtomicBool::new(false);
    static ADV_START_REQUESTED: AtomicBool = AtomicBool::new(false);
    static ADV_STARTED: AtomicBool = AtomicBool::new(false);
    static ADV_FAILED: AtomicBool = AtomicBool::new(false);
    static ADV_CONFIG_DONE: AtomicU32 = AtomicU32::new(0);
    static ADV_START_COMPLETE: AtomicU32 = AtomicU32::new(0);
    static ADV_STOP_COMPLETE: AtomicU32 = AtomicU32::new(0);
    static LAST_GAP_EVENT: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_CONFIG_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_START_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_ADV_STOP_STATUS: AtomicU32 = AtomicU32::new(u32::MAX);
    static LAST_SET_NAME_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_CONFIG_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);
    static LAST_START_RETURN: AtomicI32 = AtomicI32::new(i32::MAX);

    static mut ADV_DATA: [u8; 14] = [
        0x02, 0x01, 0x06, // flags
        0x0a, 0x09, // complete local name, 9 bytes
        b'B', b'L', b'E', b'_', b'S', b'M', b'O', b'K', b'E',
    ];

    pub fn main() -> ! {
        esp_idf_sys::link_patches();
        log_line(b"\n--- MINIMAL BLE ADV BOOT ---\n\0");
        unsafe {
            if let Err(code) = init_ble_stack() {
                log_i32(b"MIN_ADV:init_failed=%ld\n\0", code);
                loop {
                    std::thread::sleep(Duration::from_secs(1));
                }
            }
            configure_raw_advertising();
        }

        loop {
            unsafe {
                if ADV_CONFIG_READY.load(Ordering::SeqCst)
                    && !ADV_START_REQUESTED.load(Ordering::SeqCst)
                {
                    ADV_START_REQUESTED.store(true, Ordering::SeqCst);
                    let ret = start_advertising();
                    LAST_START_RETURN.store(ret, Ordering::SeqCst);
                    log_i32(b"MIN_ADV:start_return=%ld\n\0", ret);
                    if ret != ESP_OK {
                        ADV_FAILED.store(true, Ordering::SeqCst);
                    }
                }
            }
            log_status();
            std::thread::sleep(Duration::from_secs(1));
        }
    }

    unsafe fn init_ble_stack() -> Result<(), esp_err_t> {
        let mut ret = nvs_flash_init();
        if ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND {
            check(nvs_flash_erase())?;
            ret = nvs_flash_init();
        }
        check(ret)?;

        let mem_ret = esp_bt_controller_mem_release(esp_bt_mode_t_ESP_BT_MODE_CLASSIC_BT);
        if mem_ret != ESP_OK && mem_ret != ESP_ERR_INVALID_STATE && mem_ret != ESP_ERR_NOT_FOUND {
            return Err(mem_ret);
        }
        log_i32(b"MIN_ADV:classic_mem_release=%ld\n\0", mem_ret);

        let mut bt_cfg = bt_controller_default_config();
        check(esp_bt_controller_init(&mut bt_cfg))?;
        log_u32(
            b"MIN_ADV:controller_status_after_init=%lu\n\0",
            esp_bt_controller_get_status(),
        );
        check(esp_bt_controller_enable(esp_bt_mode_t_ESP_BT_MODE_BLE))?;
        log_u32(
            b"MIN_ADV:controller_status_after_enable=%lu\n\0",
            esp_bt_controller_get_status(),
        );

        check(esp_bluedroid_init())?;
        log_u32(
            b"MIN_ADV:bluedroid_status_after_init=%lu\n\0",
            esp_bluedroid_get_status(),
        );
        check(esp_bluedroid_enable())?;
        log_u32(
            b"MIN_ADV:bluedroid_status_after_enable=%lu\n\0",
            esp_bluedroid_get_status(),
        );
        check(esp_ble_gap_register_callback(Some(gap_event_callback)))?;
        Ok(())
    }

    unsafe fn configure_raw_advertising() {
        let set_name_ret = esp_ble_gap_set_device_name(b"BLE_SMOKE\0".as_ptr().cast());
        LAST_SET_NAME_RETURN.store(set_name_ret, Ordering::SeqCst);
        log_i32(b"MIN_ADV:set_name_return=%ld\n\0", set_name_ret);

        let raw = core::ptr::addr_of_mut!(ADV_DATA).cast::<u8>();
        let ret = esp_ble_gap_config_adv_data_raw(raw, 14);
        LAST_CONFIG_RETURN.store(ret, Ordering::SeqCst);
        log_i32(b"MIN_ADV:config_raw_return=%ld\n\0", ret);
        if ret != ESP_OK {
            ADV_FAILED.store(true, Ordering::SeqCst);
        }
    }

    unsafe fn start_advertising() -> esp_err_t {
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
        log_line(b"MIN_ADV:start_request=connectable_undirected_public\n\0");
        esp_ble_gap_start_advertising(&mut adv_params)
    }

    unsafe extern "C" fn gap_event_callback(
        event: esp_gap_ble_cb_event_t,
        param: *mut esp_ble_gap_cb_param_t,
    ) {
        LAST_GAP_EVENT.store(event as u32, Ordering::SeqCst);
        match event {
            GAP_ADV_DATA_RAW_SET_COMPLETE_EVT => {
                ADV_CONFIG_DONE.fetch_add(1, Ordering::SeqCst);
                let status = if param.is_null() {
                    u32::MAX
                } else {
                    (*param).adv_data_raw_cmpl.status as u32
                };
                LAST_ADV_CONFIG_STATUS.store(status, Ordering::SeqCst);
                log_u32(b"MIN_ADV:adv_raw_config_complete_status=%lu\n\0", status);
                if status == esp_bt_status_t_ESP_BT_STATUS_SUCCESS as u32 {
                    ADV_CONFIG_READY.store(true, Ordering::SeqCst);
                } else {
                    ADV_FAILED.store(true, Ordering::SeqCst);
                }
            }
            GAP_ADV_START_COMPLETE_EVT => {
                ADV_START_COMPLETE.fetch_add(1, Ordering::SeqCst);
                let status = if param.is_null() {
                    u32::MAX
                } else {
                    (*param).adv_start_cmpl.status as u32
                };
                LAST_ADV_START_STATUS.store(status, Ordering::SeqCst);
                log_u32(b"MIN_ADV:adv_start_complete_status=%lu\n\0", status);
                if status == esp_bt_status_t_ESP_BT_STATUS_SUCCESS as u32 {
                    ADV_STARTED.store(true, Ordering::SeqCst);
                } else {
                    ADV_FAILED.store(true, Ordering::SeqCst);
                }
            }
            GAP_ADV_STOP_COMPLETE_EVT => {
                ADV_STOP_COMPLETE.fetch_add(1, Ordering::SeqCst);
                if !param.is_null() {
                    LAST_ADV_STOP_STATUS
                        .store((*param).adv_stop_cmpl.status as u32, Ordering::SeqCst);
                }
            }
            _ => {}
        }
    }

    fn log_status() {
        unsafe {
            printf(
                b"MIN_ADV:status config_ready=%d start_requested=%d started=%d failed=%d config_done=%lu start_done=%lu last_event=%lu set_name_ret=%ld config_ret=%ld start_ret=%ld config_status=%lu start_status=%lu controller=%lu bluedroid=%lu\n\0"
                    .as_ptr()
                    .cast(),
                i32::from(ADV_CONFIG_READY.load(Ordering::SeqCst)),
                i32::from(ADV_START_REQUESTED.load(Ordering::SeqCst)),
                i32::from(ADV_STARTED.load(Ordering::SeqCst)),
                i32::from(ADV_FAILED.load(Ordering::SeqCst)),
                ADV_CONFIG_DONE.load(Ordering::SeqCst),
                ADV_START_COMPLETE.load(Ordering::SeqCst),
                LAST_GAP_EVENT.load(Ordering::SeqCst),
                LAST_SET_NAME_RETURN.load(Ordering::SeqCst),
                LAST_CONFIG_RETURN.load(Ordering::SeqCst),
                LAST_START_RETURN.load(Ordering::SeqCst),
                LAST_ADV_CONFIG_STATUS.load(Ordering::SeqCst),
                LAST_ADV_START_STATUS.load(Ordering::SeqCst),
                esp_bt_controller_get_status(),
                esp_bluedroid_get_status(),
            );
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
            ..Default::default()
        }
    }

    fn check(code: esp_err_t) -> Result<(), esp_err_t> {
        if code == ESP_OK { Ok(()) } else { Err(code) }
    }

    fn log_line(message: &'static [u8]) {
        unsafe {
            printf(message.as_ptr().cast::<c_char>());
        }
    }

    fn log_i32(format: &'static [u8], value: i32) {
        unsafe {
            printf(format.as_ptr().cast::<c_char>(), value);
        }
    }

    fn log_u32(format: &'static [u8], value: u32) {
        unsafe {
            printf(format.as_ptr().cast::<c_char>(), value);
        }
    }
}

#[cfg(target_os = "espidf")]
fn main() -> ! {
    target::main()
}
