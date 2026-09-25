@echo off
rem SYAWIT_SAIBER_TOOLS launcher — menjalankan aplikasi desktop Flutter.
rem Backend FastAPI otomatis di-spawn oleh aplikasi (lihat frontend/lib/services/backend.dart).
setlocal
cd /d "%~dp0"

where flutter >nul 2>nul
if errorlevel 1 (
    echo [!] Flutter tidak ditemukan di PATH. Install dari https://docs.flutter.dev/get-started/install/windows
    pause
    exit /b 1
)

echo [i] Menjalankan SYAWIT_SAIBER_TOOLS (flutter run -d windows)...
flutter run -d windows
endlocal
