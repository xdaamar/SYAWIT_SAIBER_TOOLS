# CTFSuite — manual nmap installer (run as Administrator)
# Use this only if the in-app Smart Setup (winget path) failed.
#
# Usage (PowerShell as Admin):
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   .\scripts\setup_admin_nmap.ps1

$ErrorActionPreference = 'Stop'
Write-Host '=== CTFSuite: nmap installer ==='

# 1) Try winget first
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host '[i] winget ditemukan — install Insecure.Nmap...'
    winget install --id Insecure.Nmap --accept-source-agreements `
        --accept-package-agreements --silent
    if ($LASTEXITCODE -eq 0) {
        Write-Host '[+] nmap terinstall via winget'
        exit 0
    }
    Write-Host "[!] winget rc=$LASTEXITCODE — fallback unduh installer..."
}

# 2) Fallback: official installer, silent
$url = 'https://nmap.org/dist/nmap-7.95-setup.exe'
$dest = Join-Path $env:TEMP 'nmap-setup.exe'
Write-Host "[i] mengunduh $url ..."
Invoke-WebRequest -Uri $url -OutFile $dest

Write-Host '[i] menjalankan installer silent (/S)...'
$proc = Start-Process -FilePath $dest -ArgumentList '/S' -Wait -PassThru
Write-Host "[i] installer rc=$($proc.ExitCode)"

# 3) Add to PATH for current session & machine
$nmapDir = 'C:\Program Files (x86)\Nmap'
if (Test-Path (Join-Path $nmapDir 'nmap.exe')) {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if ($machinePath -notlike "*$nmapDir*") {
        [Environment]::SetEnvironmentVariable('Path', "$machinePath;$nmapDir", 'Machine')
        Write-Host "[+] $nmapDir ditambahkan ke PATH sistem"
    }
    $env:Path += ";$nmapDir"
    Write-Host '[+] verifikasi:'; & "$nmapDir\nmap.exe" --version | Select-Object -First 1
} else {
    Write-Host '[!] nmap.exe tidak ditemukan — install manual dari https://nmap.org/download.html'
    exit 1
}
Write-Host '[+] Selesai.'
