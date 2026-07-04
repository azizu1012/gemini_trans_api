param(
    [switch]$Cli
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $ProjectRoot ".venv"
$Activate = Join-Path $VenvPath "Scripts\Activate.ps1"

if (Test-Path $Activate) {
    Write-Host "⏳ Kích hoạt môi trường ảo..." -ForegroundColor Cyan
    & $Activate
} else {
    Write-Host "❌ Không tìm thấy .venv tại: $VenvPath" -ForegroundColor Red
    Read-Host "Nhấn Enter để thoát..."
    exit
}

if ($Cli) {
    Write-Host "🚀 Khởi chạy CLI mode..." -ForegroundColor Green
    python main.py --cli
} else {
    Write-Host "🚀 Khởi chạy Textual TUI..." -ForegroundColor Green
    python -m refactor_oop_gemini_trans_api.tui.app
}
