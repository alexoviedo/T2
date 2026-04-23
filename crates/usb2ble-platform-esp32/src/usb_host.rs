//! ESP-IDF USB Host groundwork for M2.
//!
//! This module provides the structural plumbing for USB Host and HID Class drivers.
//! Real hardware event production is deferred to M2B.

#[cfg(target_os = "espidf")]
use esp_idf_sys::*;
use std::sync::mpsc;
use usb2ble_contracts::{
    ConnectionTopology, DeviceId, InputReportPacket, InterfaceId, ReportDescriptorBlob,
    UsbDeviceRef, UsbIngressEvent, UsbInterfaceRef,
};

/// Internal state for the USB host groundwork.
pub struct EspUsbHost {
    event_tx: mpsc::Sender<UsbIngressEvent>,
}

impl EspUsbHost {
    pub fn new(event_tx: mpsc::Sender<UsbIngressEvent>) -> Self {
        Self { event_tx }
    }

    /// Initialize the USB host stack (Groundwork).
    ///
    /// NOTE: This currently only performs basic driver installation.
    /// Real HID device discovery and report capture are NOT yet implemented.
    #[cfg(target_os = "espidf")]
    pub fn init(&self) {
        unsafe {
            // Install USB Host driver
            let config = usb_host_config_t {
                intr_flags: ESP_INTR_FLAG_LEVEL1 as i32,
                ..Default::default()
            };
            // NOTE: M2B - Return code handling and full host lifecycle management
            // are deferred until real HID device support is added.
            let _ = usb_host_install(&config);

            // TODO: M2B - Implement real HID client registration and event handling.
        }
    }

    /// Simulation helper for host-side verification of app-logic groundwork.
    /// Never called in the real target path.
    #[cfg(not(target_os = "espidf"))]
    pub fn simulate_events_for_test(&self) {
        // Physical device attachment
        let dev_ref = UsbDeviceRef {
            device_id: DeviceId(1),
            topology: ConnectionTopology::Direct,
            vendor_id: 0x045e,
            product_id: 0x028e,
        };
        let _ = self.event_tx.send(UsbIngressEvent::DeviceAttached(dev_ref.clone()));

        // HID Interface discovery
        let iface_ref = UsbInterfaceRef {
            device: dev_ref.clone(),
            interface_id: InterfaceId(0),
        };
        let _ = self.event_tx.send(UsbIngressEvent::InterfaceDiscovered {
            source: iface_ref.clone(),
            class_code: 3, // HID
            subclass_code: 0,
            protocol_code: 0,
        });

        // HID Report Descriptor capture
        let descriptor = vec![0x05, 0x01, 0x09, 0x05]; // Minimal dummy for groundwork test
        let _ = self.event_tx.send(UsbIngressEvent::ReportDescriptorReceived(
            ReportDescriptorBlob {
                source: iface_ref.clone(),
                bytes: descriptor,
            },
        ));

        // Raw input report capture
        let report = vec![0x00, 0x01, 0x02];
        let _ = self.event_tx.send(UsbIngressEvent::InputReportReceived(InputReportPacket {
            source: iface_ref,
            report_id: usb2ble_contracts::ReportId(0),
            payload: report,
            timestamp_micros: 1000,
        }));
    }
}
