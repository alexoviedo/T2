import Foundation
import IOKit.hid

final class ProbeState {
    let productNeedle: String
    let output: FileHandle?
    var matchedRegistryIds = Set<Int64>()
    var eventCount = 0

    init(productNeedle: String, outputPath: String?) {
        self.productNeedle = productNeedle.lowercased()
        if let outputPath {
            FileManager.default.createFile(atPath: outputPath, contents: nil)
            self.output = FileHandle(forWritingAtPath: outputPath)
        } else {
            self.output = nil
        }
    }

    deinit {
        try? output?.close()
    }
}

var probeState: ProbeState?

func nowIso8601() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter.string(from: Date())
}

func jsonLine(_ value: [String: Any]) {
    guard JSONSerialization.isValidJSONObject(value),
          let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
          let line = String(data: data, encoding: .utf8) else {
        return
    }
    print(line)
    if let output = probeState?.output {
        output.write((line + "\n").data(using: .utf8)!)
    }
    fflush(stdout)
}

func deviceProperty(_ device: IOHIDDevice, _ key: CFString) -> Any? {
    IOHIDDeviceGetProperty(device, key)
}

func stringProperty(_ device: IOHIDDevice, _ key: CFString) -> String {
    if let value = deviceProperty(device, key) as? String {
        return value
    }
    return ""
}

func intProperty(_ device: IOHIDDevice, _ key: CFString) -> Int64? {
    if let value = deviceProperty(device, key) as? NSNumber {
        return value.int64Value
    }
    return nil
}

func registryId(_ device: IOHIDDevice) -> Int64? {
    var id: UInt64 = 0
    let result = IORegistryEntryGetRegistryEntryID(IOHIDDeviceGetService(device), &id)
    return result == KERN_SUCCESS ? Int64(id) : nil
}

func deviceMatches(_ device: IOHIDDevice) -> Bool {
    guard let state = probeState else { return false }
    if state.productNeedle.isEmpty {
        return true
    }
    let product = stringProperty(device, kIOHIDProductKey as CFString).lowercased()
    return product.contains(state.productNeedle)
}

func deviceMetadata(_ device: IOHIDDevice) -> [String: Any] {
    var metadata: [String: Any] = [
        "type": "device",
        "at": nowIso8601(),
        "product": stringProperty(device, kIOHIDProductKey as CFString),
        "manufacturer": stringProperty(device, kIOHIDManufacturerKey as CFString),
        "transport": stringProperty(device, kIOHIDTransportKey as CFString),
    ]
    if let vendorId = intProperty(device, kIOHIDVendorIDKey as CFString) {
        metadata["vendor_id"] = vendorId
    }
    if let productId = intProperty(device, kIOHIDProductIDKey as CFString) {
        metadata["product_id"] = productId
    }
    if let usagePage = intProperty(device, kIOHIDPrimaryUsagePageKey as CFString) {
        metadata["usage_page"] = usagePage
    }
    if let usage = intProperty(device, kIOHIDPrimaryUsageKey as CFString) {
        metadata["usage"] = usage
    }
    if let id = registryId(device) {
        metadata["registry_id"] = id
    }
    return metadata
}

let inputValueCallback: IOHIDValueCallback = { _, _, _, value in
    let element = IOHIDValueGetElement(value)
    let device = IOHIDElementGetDevice(element)
    guard deviceMatches(device) else { return }

    probeState?.eventCount += 1
    let logicalMin = IOHIDElementGetLogicalMin(element)
    let logicalMax = IOHIDElementGetLogicalMax(element)
    let integerValue = IOHIDValueGetIntegerValue(value)
    var normalized: Double? = nil
    if logicalMax != logicalMin {
        normalized = (Double(integerValue) - Double(logicalMin)) / (Double(logicalMax) - Double(logicalMin))
    }

    var event: [String: Any] = [
        "type": "input_value",
        "at": nowIso8601(),
        "product": stringProperty(device, kIOHIDProductKey as CFString),
        "usage_page": IOHIDElementGetUsagePage(element),
        "usage": IOHIDElementGetUsage(element),
        "logical_min": logicalMin,
        "logical_max": logicalMax,
        "integer_value": integerValue,
        "hid_timestamp": IOHIDValueGetTimeStamp(value),
    ]
    if let normalized {
        event["normalized_0_1"] = normalized
    }
    if let id = registryId(device) {
        event["registry_id"] = id
    }
    jsonLine(event)
}

func argumentValue(_ name: String, default defaultValue: String) -> String {
    let args = CommandLine.arguments
    guard let index = args.firstIndex(of: name), index + 1 < args.count else {
        return defaultValue
    }
    return args[index + 1]
}

let duration = Double(argumentValue("--duration", default: "10")) ?? 10.0
let product = argumentValue("--product-contains", default: "USB2BLE Gamepad")
let outputPathArg = argumentValue("--out", default: "")
let outputPath = outputPathArg.isEmpty ? nil : outputPathArg
probeState = ProbeState(productNeedle: product, outputPath: outputPath)

let manager = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
IOHIDManagerSetDeviceMatching(manager, nil)
IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetCurrent(), CFRunLoopMode.defaultMode.rawValue)
let openResult = IOHIDManagerOpen(manager, IOOptionBits(kIOHIDOptionsTypeNone))
jsonLine([
    "type": "probe_start",
    "at": nowIso8601(),
    "product_contains": product,
    "duration_seconds": duration,
    "open_result": openResult,
])

if let devices = IOHIDManagerCopyDevices(manager) as? Set<IOHIDDevice> {
    for device in devices where deviceMatches(device) {
        if let id = registryId(device) {
            probeState?.matchedRegistryIds.insert(id)
        }
        jsonLine(deviceMetadata(device))
    }
}

IOHIDManagerRegisterInputValueCallback(manager, inputValueCallback, nil)

let deadline = Date(timeIntervalSinceNow: duration)
while Date() < deadline {
    RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
}

jsonLine([
    "type": "probe_end",
    "at": nowIso8601(),
    "event_count": probeState?.eventCount ?? 0,
    "matched_device_count": probeState?.matchedRegistryIds.count ?? 0,
])

IOHIDManagerClose(manager, IOOptionBits(kIOHIDOptionsTypeNone))
