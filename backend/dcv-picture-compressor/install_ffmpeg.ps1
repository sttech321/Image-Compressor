# =====================================================================
# install_ffmpeg.ps1  -  ffmpeg automatisch installieren (Windows)
# =====================================================================
# Laedt den ffmpeg-Build (essentials, mit libaom-av1) von gyan.dev,
# entpackt ihn nach C:\ffmpeg und fuegt C:\ffmpeg\bin dauerhaft zum
# PATH hinzu. Kein 7-Zip noetig (nutzt die .zip-Variante).
#
# AUSFUEHREN:
#   1. Rechtsklick auf diese Datei -> "Mit PowerShell ausfuehren"
#   ODER
#   2. PowerShell oeffnen und eingeben:
#        powershell -ExecutionPolicy Bypass -File install_ffmpeg.ps1
#
# Danach: NEUES cmd/PowerShell-Fenster oeffnen, dann testen:
#        ffmpeg -encoders | findstr av1
# =====================================================================

$ErrorActionPreference = "Stop"

# Hinweis: gyan bietet den "full"-Build nur als .7z an (PowerShell kann .7z
# nicht ohne Zusatztool entpacken). Der "essentials"-Build ist als .zip
# verfuegbar UND enthaelt libaom -> also genau den AV1-Encoder, den wir
# brauchen. Daher nehmen wir essentials.zip: kein 7-Zip noetig.
$zipUrl   = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$dest     = "C:\ffmpeg"
$binPath  = "$dest\bin"
$tmpZip   = "$env:TEMP\ffmpeg-release-essentials.zip"
$tmpExtr  = "$env:TEMP\ffmpeg-extract"

Write-Host ""
Write-Host "=== ffmpeg Installer ===" -ForegroundColor Cyan
Write-Host ""

# --- 0. Schon vorhanden? ---------------------------------------------
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "ffmpeg ist bereits im PATH gefunden worden:" -ForegroundColor Green
    ffmpeg -version | Select-Object -First 1
    Write-Host "Nichts zu tun. (Falls du neu installieren willst, loesche C:\ffmpeg und starte erneut.)"
    Read-Host "`nEnter zum Beenden"
    exit 0
}

# --- 1. Download ------------------------------------------------------
Write-Host "[1/4] Lade ffmpeg herunter (~103 MB, kann etwas dauern)..." -ForegroundColor Yellow
Write-Host "      $zipUrl"
# Schnellerer Download durch abgeschaltete Fortschrittsanzeige
$ProgressPreference = "SilentlyContinue"
try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip
} catch {
    Write-Host "Download fehlgeschlagen. Pruefe deine Internetverbindung." -ForegroundColor Red
    Write-Host "Alternativ manuell laden von: https://www.gyan.dev/ffmpeg/builds/"
    Read-Host "`nEnter zum Beenden"; exit 1
}
$ProgressPreference = "Continue"
Write-Host "      Fertig: $([math]::Round((Get-Item $tmpZip).Length/1MB,1)) MB"

# --- 2. Entpacken -----------------------------------------------------
Write-Host "[2/4] Entpacke..." -ForegroundColor Yellow
if (Test-Path $tmpExtr) { Remove-Item $tmpExtr -Recurse -Force }
Expand-Archive -Path $tmpZip -DestinationPath $tmpExtr -Force

# gyan-Zip enthaelt einen Unterordner wie "ffmpeg-7.x-full_build"
$inner = Get-ChildItem $tmpExtr -Directory | Select-Object -First 1
if (-not $inner) {
    Write-Host "Konnte den entpackten Ordner nicht finden." -ForegroundColor Red
    Read-Host "`nEnter zum Beenden"; exit 1
}

# --- 3. Nach C:\ffmpeg verschieben -----------------------------------
Write-Host "[3/4] Installiere nach $dest ..." -ForegroundColor Yellow
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
Move-Item -Path $inner.FullName -Destination $dest

if (-not (Test-Path "$binPath\ffmpeg.exe")) {
    Write-Host "ffmpeg.exe wurde nicht gefunden unter $binPath" -ForegroundColor Red
    Read-Host "`nEnter zum Beenden"; exit 1
}

# --- 4. PATH dauerhaft setzen (Benutzer-Ebene, keine Admin-Rechte) ---
Write-Host "[4/4] Fuege $binPath zum PATH hinzu..." -ForegroundColor Yellow
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binPath*") {
    $newPath = if ($userPath) { "$userPath;$binPath" } else { $binPath }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "      PATH aktualisiert."
} else {
    Write-Host "      PATH enthielt den Eintrag bereits."
}
# auch in der aktuellen Session verfuegbar machen
$env:Path += ";$binPath"

# --- Aufraeumen + Verifikation ---------------------------------------
Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
Remove-Item $tmpExtr -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Installation abgeschlossen ===" -ForegroundColor Green
& "$binPath\ffmpeg.exe" -version | Select-Object -First 1
Write-Host ""
Write-Host "Pruefe AV1-Encoder (libaom-av1)..." -ForegroundColor Cyan
$encoders = & "$binPath\ffmpeg.exe" -hide_banner -encoders 2>$null
$av1 = $encoders | Select-String "av1"
$hasLibaom = $encoders | Select-String "libaom-av1"
if ($hasLibaom) {
    $av1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Green }
    Write-Host ""
    Write-Host "libaom-av1 ist vorhanden - alles bereit!" -ForegroundColor Green
    Write-Host "WICHTIG: Oeffne ein NEUES cmd-Fenster, damit der PATH dort greift." -ForegroundColor Green
    Write-Host "Dann funktioniert 'ffmpeg ...' ueberall."
} elseif ($av1) {
    Write-Host "  Es gibt AV1-Encoder, aber libaom-av1 fehlt:" -ForegroundColor Yellow
    $av1 | ForEach-Object { Write-Host "  $_" }
    Write-Host "  Das Tool nutzt libaom-av1 - bei Problemen melde dich." -ForegroundColor Yellow
} else {
    Write-Host "  Kein AV1-Encoder gefunden - ungewoehnlich." -ForegroundColor Red
}
Write-Host ""
Read-Host "Enter zum Beenden"
