#!/bin/bash
set -euxo pipefail

echo "Packaging USB2BLE ESP32-S3 flash image..."

TARGET="${TARGET:-xtensa-esp32s3-espidf}"
CHIP="${CHIP:-esp32s3}"
PROFILE="${PROFILE:-debug}"
FLASH_SIZE="${FLASH_SIZE:-16mb}"
FLASH_MODE="${FLASH_MODE:-dio}"
FLASH_FREQ="${FLASH_FREQ:-40mhz}"
OUT_DIR="${OUT_DIR:-target/firmware}"
BINARY="${BINARY:-target/$TARGET/$PROFILE/usb2ble-fw}"
IMAGE="${IMAGE:-$OUT_DIR/usb2ble-fw-$CHIP-merged.bin}"
MANIFEST="${MANIFEST:-$OUT_DIR/usb2ble-fw-$CHIP-manifest.txt}"

if ! command -v espflash &> /dev/null; then
    echo "Error: espflash not found."
    echo "Install with: cargo install espflash --locked"
    exit 1
fi

if [[ ! -f "$BINARY" ]]; then
    echo "Error: firmware ELF not found at $BINARY"
    echo "Run scripts/check_target_build.sh first."
    exit 1
fi

mkdir -p "$OUT_DIR"

espflash save-image \
    --chip "$CHIP" \
    --merge \
    --skip-padding \
    --flash-size "$FLASH_SIZE" \
    --flash-mode "$FLASH_MODE" \
    --flash-freq "$FLASH_FREQ" \
    "$BINARY" \
    "$IMAGE"

if command -v sha256sum &> /dev/null; then
    IMAGE_SHA256="$(sha256sum "$IMAGE" | awk '{print $1}')"
else
    IMAGE_SHA256="$(shasum -a 256 "$IMAGE" | awk '{print $1}')"
fi

{
    printf 'name=usb2ble-fw\n'
    printf 'target=%s\n' "$TARGET"
    printf 'chip=%s\n' "$CHIP"
    printf 'profile=%s\n' "$PROFILE"
    printf 'flash_size=%s\n' "$FLASH_SIZE"
    printf 'flash_mode=%s\n' "$FLASH_MODE"
    printf 'flash_freq=%s\n' "$FLASH_FREQ"
    printf 'elf=%s\n' "$BINARY"
    printf 'image=%s\n' "$IMAGE"
    printf 'image_sha256=%s\n' "$IMAGE_SHA256"
    printf 'espflash=%s\n' "$(espflash --version)"
    printf 'rustc=%s\n' "$(rustc --version)"
    printf 'cargo=%s\n' "$(cargo --version)"
    printf 'git_rev=%s\n' "$(git rev-parse --short HEAD 2>/dev/null || printf unknown)"
    printf 'git_dirty=%s\n' "$(git diff --quiet --ignore-submodules HEAD -- 2>/dev/null && printf false || printf true)"
    printf 'flash_command=espflash write-bin --chip %s --port <PORT> 0x0 %s\n' "$CHIP" "$IMAGE"
    printf 'elf_flash_command=espflash flash --port <PORT> %s\n' "$BINARY"
} > "$MANIFEST"

ls -lh "$IMAGE" "$MANIFEST"
echo "Firmware package complete."
