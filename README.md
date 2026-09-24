# CTFSuite

Toolkit multi-fungsi untuk **CTF & pentesting** di Windows: backend Python
(FastAPI) + UI desktop Flutter (Material 3, dark). Semua operasi berjalan
sebagai *job* async dengan output live via WebSocket, dan setiap eksekusi
selalu melewati **preview perintah** dulu.

> ⚠️ **Wajib baca [DISCLAIMER.md](DISCLAIMER.md)** — hanya untuk sistem milik
> sendiri atau yang punya izin eksplisit.

---

## Fitur

| Modul | Isi |
|---|---|
| **Smart Setup** | Pre-flight check semua komponen → status matrix (ok/missing/outdated/broken), install idempotent (yang sudah OK di-skip), diagnostics engine + **Doctor mode**, log per run |
| **Recon** | Nmap (preset quick/full/UDP/service/vuln/http), parser XML, ringkasan attack surface |
| **Web** | Crawler same-origin, form analyzer → attack map OWASP, scanner OWASP Top 10 (header, XSS, SQLi error, SSTI, cmd injection, LFI, path sensitif), SQLMap runner, auth-bypass tester (default creds, SQLi login, JWT alg:none, cookie tamper) |
| **Crypto** | Auto-decoder berlapis (base64/hex/morse/binary/brainfuck/JWT/caesar/xor...), hash identify + crack wordlist, cipher klasik (Vigenère, IoC), RSA attacks (small-e, common factor, Fermat, Wiener) |
| **Pwn** | Cyclic pattern + offset finder, ELF/PE analyzer + protections, generator skrip exploit pwntools (bof, ret2libc, fmtstr, shellcode) |
| **Shells** | Payload generator (bash/nc/python/perl/PS), webshell PHP/JSP generator, webshell client (probe param + exec), reverse shell listener TCP |
| **Report** | Kumpulkan temuan dari job → laporan Markdown/HTML dengan ringkasan severity |

## Arsitektur

```
frontend/   Flutter Desktop (Windows) — spawn backend otomatis saat start
backend/
  app/
    api/        routes: setup, jobs, recon, web, crypto, pwn, shells, report, settings
    core/       job manager (streaming + WS), process wrapper, smart setup engine
    modules/    recon, web, crypto, pwn, shells, report
  tools/        sqlmap & wordlists (diunduh oleh Smart Setup)
  tests/        pytest (25 test)
scripts/        demo_target.py, setup_admin_nmap.ps1
start.bat       launcher
```

- Backend: `http://127.0.0.1:8765` (port otomatis dipilih bebas saat di-spawn UI)
- Semua job: `GET /api/jobs`, output live: `WS /api/jobs/{id}/ws`
- Setup events: `WS /api/setup/events`

## Menjalankan

```bat
:: 1. (sekali) install dependensi backend — atau biarkan Smart Setup yang melakukannya
cd backend
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt

:: 2. test cepat
.venv\Scripts\python -m pytest

:: 3. jalankan UI (backend ikut ter-spawn)
start.bat
```

Saat pertama kali dibuka: **disclaimer** → lalu buka tab **Setup** → klik
**Jalankan Setup**. Komponen yang sudah terinstall dan versinya cukup akan
**di-skip**, tidak diinstall ulang. Kalau ada yang gagal, tombol **Doctor**
memberi diagnosis + saran perbaikan.

## Testing end-to-end dengan demo target

```bash
python scripts/demo_target.py   # http://127.0.0.1:5000 (localhost only)
```

Target rentan sengaja dibuat untuk semua probe modul Web: SQLi error-based
(`/search?id=`), reflected XSS (`/xss?q=`), traversal (`/file?path=`), command
injection (`/cmd?host=`), SSTI (`/tpl?name=`), login dengan default creds &
SQLi bypass, plus file sensitif (`/.git/HEAD`, `/robots.txt`).

## Catatan penting

- **Build Windows**: `flutter build windows` butuh **Visual Studio 2022
  dengan workload "Desktop development with C++"**. Bila belum ada, Flutter
  menolak build — install dari https://visualstudio.microsoft.com/ lalu jalankan
  ulang `start.bat`. Tanpa VS, kode UI tetap bisa diverifikasi via
  `flutter analyze` (0 error).
- **Antivirus**: Windows Defender bisa mengkarantina file payload/sqlmap.
  Disarankan menambahkan folder project + `backend\tools` ke exclusion Defender
  (Windows Security → Virus & threat protection → Exclusions).
- **Nmap**: install via winget membutuhkan persetujuan **UAC**. Bila gagal,
  jalankan `scripts/setup_admin_nmap.ps1` sebagai Administrator.
- **pwntools** opsional (gagal build di Python 3.14 karena dependensi
  `unicorn`) — modul pwn punya implementasi fallback sendiri; skrip exploit
  hasil generator ditujukan untuk dijalankan di mesin lain yang punya pwntools.
- **Hasil scan otomatis = heuristik**. Verifikasi manual sebelum ditindak.

## Struktur API ringkas

```
GET  /api/health                    GET  /api/setup/status
POST /api/setup/run|cancel|retry/N  GET  /api/setup/doctor
GET  /api/jobs · /api/jobs/{id}     POST /api/jobs/{id}/cancel
POST /api/recon/nmap/preview|run    GET  /api/recon/nmap/presets
POST /api/web/crawl|owasp|auth-bypass|jwt|cookie-tamper
POST /api/web/sqlmap/preview|run    POST /api/web/forms/analyze
POST /api/crypto/solve|hash|hash/identify|hash/crack|ciphers|rsa/analyze
POST /api/pwn/analyze|offset|exploit GET /api/pwn/pattern|templates
POST /api/shells/payloads|webshell|webshell/exec|webshell/probe|listener/*
POST /api/report/generate           GET  /api/report/list
GET/PUT /api/settings               GET  /api/settings/wordlists
```
