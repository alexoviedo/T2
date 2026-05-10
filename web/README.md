# USB2BLE Web Configurator

This is a Vite + TypeScript frontend for configuring the USB2BLE board over Web Serial, and providing a firmware flashing interface using ESP Web Tools.

## Development

```bash
cd web
npm install
npm run dev
```

> **Note:** Web Serial requires a Chromium-based browser (Chrome or Edge) on desktop and MUST be served over HTTPS or localhost.

## Build

```bash
npm run build
```

The output will be placed in `dist/`.

## Flashing

The firmware flashing tab uses [ESP Web Tools](https://esphome.github.io/esp-web-tools/). The GitHub Actions pipeline is configured to automatically inject the compiled `usb2ble-fw-esp32s3-merged.bin` and a `manifest.json` into the `dist/firmware/` directory during deployment.

### Features
- **Config Editor**: View and modify the mapping schema, select persona, configure bridge settings, and modify generic settings.
- **Mapping Table**: A tabular interface for simple modification of the input bindings.
- **Presets**: Load bundled presets (e.g., Flight Pack Xbox, Flight Pack Generic).
- **Firmware Update**: Simple 1-click updates using ESP Web Tools in Chrome.

## Constraints
- Does NOT currently support BLE GATT configuration.
- Needs the firmware chunk protocol payload schema implemented in the `tools/configure_board.py` tool.
