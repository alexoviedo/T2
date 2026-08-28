//! Minimal Bluedroid HID publication latency differential.
//!
//! This target intentionally excludes the USB host, input aggregation, bridge,
//! runtime configuration, persona switching, and control plane. It activates the
//! existing Generic Gamepad descriptor through the current ESP-IDF v5.5.3
//! Bluedroid transport, waits for a host connection, and attempts 500 deliberately
//! changed reports on a 50 Hz internal clock without catch-up bursts.

#[cfg(not(target_os = "espidf"))]
fn main() {
    println!("minimal_ble_hid_latency is an ESP-IDF target-only diagnostic binary");
}

#[cfg(target_os = "espidf")]
fn main() {
    use std::ffi::CString;
    use std::time::{Duration, Instant};

    use usb2ble_contracts::{
        BleLinkState, BleTransport, EncodedBleReport, PersonaEncoder,
    };
    use usb2ble_personas::{
        GENERIC_GAMEPAD_PERSONA_ID, GENERIC_GAMEPAD_REPORT_ID, GenericGamepadEncoder,
    };
    use usb2ble_platform_esp32::ble_hid::BleHidTransport;

    const EXPECTED_REPORTS: u64 = 500;
    const INTERVAL: Duration = Duration::from_millis(20);
    const CONNECTION_TIMEOUT: Duration = Duration::from_secs(90);
    const CAPTURE_ARM_DELAY: Duration = Duration::from_secs(8);

    fn log(line: &str) {
        let Ok(message) = CString::new(line) else {
            return;
        };
        unsafe {
            esp_idf_sys::printf(b"%s\n\0".as_ptr().cast(), message.as_ptr());
        }
    }

    fn report(change_index: u64) -> EncodedBleReport {
        let x = if change_index % 2 == 0 {
            i16::MIN
        } else {
            i16::MAX
        };
        let mut bytes = Vec::with_capacity(15);
        bytes.extend_from_slice(&0_u16.to_le_bytes());
        bytes.push(8);
        bytes.extend_from_slice(&x.to_le_bytes());
        for _ in 1..6 {
            bytes.extend_from_slice(&0_i16.to_le_bytes());
        }
        EncodedBleReport {
            persona_id: GENERIC_GAMEPAD_PERSONA_ID,
            report_id: GENERIC_GAMEPAD_REPORT_ID,
            bytes,
        }
    }

    esp_idf_sys::link_patches();
    log("MIN_HID:boot sdk=esp-idf-v5.5.3 stack=bluedroid expected=500 rate_hz=50");

    let descriptor = match GenericGamepadEncoder.descriptor(GENERIC_GAMEPAD_PERSONA_ID) {
        Ok(descriptor) => descriptor,
        Err(error) => {
            log(&format!("MIN_HID:fatal descriptor_error={error:?}"));
            loop {
                std::thread::sleep(Duration::from_secs(1));
            }
        }
    };
    let mut transport = BleHidTransport::new();
    if let Err(error) = transport.activate_persona(&descriptor) {
        log(&format!("MIN_HID:fatal activation_error={error:?}"));
        loop {
            std::thread::sleep(Duration::from_secs(1));
        }
    }
    log("MIN_HID:advertising");

    let connection_started = Instant::now();
    while transport.current_state() != BleLinkState::Connected {
        if connection_started.elapsed() >= CONNECTION_TIMEOUT {
            log(&format!(
                "MIN_HID:fatal connection_timeout info={}",
                transport.connection_info_json()
            ));
            loop {
                std::thread::sleep(Duration::from_secs(1));
            }
        }
        std::thread::sleep(Duration::from_millis(20));
    }

    log(&format!(
        "MIN_HID:connected capture_arm_delay_ms={} info={}",
        CAPTURE_ARM_DELAY.as_millis(),
        transport.connection_info_json()
    ));
    std::thread::sleep(CAPTURE_ARM_DELAY);
    log("MIN_HID:sequence_start expected=500 interval_micros=20000");

    let sequence_started = Instant::now();
    let mut attempted = 0_u64;
    let mut published = 0_u64;
    let mut missed = 0_u64;
    let mut errors = 0_u64;
    let mut publish_total_micros = 0_u64;
    let mut publish_max_micros = 0_u64;
    let mut publish_over_50ms = 0_u64;
    let mut publish_over_100ms = 0_u64;

    for slot in 0..EXPECTED_REPORTS {
        let deadline = sequence_started + INTERVAL * slot as u32;
        let now = Instant::now();
        if now >= deadline + INTERVAL {
            missed += 1;
            continue;
        }
        if now < deadline {
            std::thread::sleep(deadline - now);
        }

        let next_report = report(attempted);
        attempted += 1;
        let publish_started = Instant::now();
        let result = transport.publish_report(&next_report);
        let publish_micros = publish_started
            .elapsed()
            .as_micros()
            .min(u128::from(u64::MAX)) as u64;
        publish_total_micros = publish_total_micros.saturating_add(publish_micros);
        publish_max_micros = publish_max_micros.max(publish_micros);
        if publish_micros > 50_000 {
            publish_over_50ms += 1;
        }
        if publish_micros > 100_000 {
            publish_over_100ms += 1;
        }
        match result {
            Ok(()) => published += 1,
            Err(_) => errors += 1,
        }
    }

    let elapsed_micros = sequence_started
        .elapsed()
        .as_micros()
        .min(u128::from(u64::MAX)) as u64;
    log(&format!(
        "MIN_HID:sequence_complete expected={} attempted={} published={} missed={} errors={} elapsed_micros={} publish_total_micros={} publish_max_micros={} publish_over_50ms={} publish_over_100ms={} info={}",
        EXPECTED_REPORTS,
        attempted,
        published,
        missed,
        errors,
        elapsed_micros,
        publish_total_micros,
        publish_max_micros,
        publish_over_50ms,
        publish_over_100ms,
        transport.connection_info_json()
    ));

    loop {
        std::thread::sleep(Duration::from_secs(1));
    }
}
