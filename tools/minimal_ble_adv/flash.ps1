param(
    [string]$Port,
    [string]$TargetDir = "C:\t2t_v553"
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repo

if (-not $Port) {
    $Port = [System.IO.Ports.SerialPort]::GetPortNames() | Select-Object -First 1
}

if (-not $Port) {
    throw "No serial COM port found."
}

$image = Join-Path $TargetDir "xtensa-esp32s3-espidf\debug\minimal_ble_adv"
if (-not (Test-Path $image)) {
    throw "Minimal BLE advertiser image not found at $image. Run build.ps1 first."
}

espflash flash --port $Port $image
