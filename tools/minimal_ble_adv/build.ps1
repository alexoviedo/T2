param(
    [string]$TargetDir = "C:\t2t_v553"
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

$env:CARGO_TARGET_DIR = $TargetDir
$env:ESP_IDF_VERSION = "v5.5.3"
$env:ESP_IDF_SDKCONFIG_DEFAULTS = (Resolve-Path "sdkconfig.defaults").Path
. "C:\Users\ovied\export-esp.ps1"

cargo +esp build `
    -Z build-std=std,panic_abort `
    --locked `
    --package usb2ble-fw `
    --bin minimal_ble_adv `
    --target xtensa-esp32s3-espidf
