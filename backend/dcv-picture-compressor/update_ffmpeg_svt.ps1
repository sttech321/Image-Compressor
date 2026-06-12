# =====================================================================
# update_ffmpeg_svt.ps1  -  ffmpeg mit funktionierendem SVT-AV1 holen
# =====================================================================
# Laedt die BtbN-Build (enthaelt aktuelles, funktionierendes libsvtav1),
# entpackt sie und ersetzt die ffmpeg/ffprobe in C:\ffmpeg\bin.
# Die alte Version wird vorher nach C:\ffmpeg\bin_backup gesichert.
#
# AUSFUEHREN:
#   powershell -ExecutionPolicy Bypass -File update_ffmpeg_svt.ps1
#
# Danach: NEUES cmd-Fenster, dann testen:
#   ffmpeg -h encoder=libsvtav1
# =====================================================================

$ErrorActionPreference = "Stop"

$zipUrl  = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$dest    = "C:\ffmpeg"
$binPath = "$dest\bin"
$tmpZip  = "$env:TEMP\ffmpeg-btbn.zip"
$tmpExtr = "$env:TEMP\ffmpeg-btbn-extract"

Write-Host ""
Write-Host "=== ffmpeg SVT-AV1 Update (BtbN-Build) ===" -ForegroundColor Cyan
Write-Host ""

# --- 1. Download ------------------------------------------------------
Write-Host "[1/4] Lade BtbN-ffmpeg (~150 MB, dauert etwas)..." -ForegroundColor Yellow
Write-Host "      $zipUrl"
if (Test-Path $tmpZip) { Remove-Item $tmpZip -Force }
$ok = $false
# Methode A: BITS (folgt Umleitungen zuverlaessig, zeigt Fortschritt)
try {
    Import-Module BitsTransfer -ErrorAction Stop
    Start-BitsTransfer -Source $zipUrl -Destination $tmpZip -ErrorAction Stop
    $ok = $true
} catch {
    Write-Host "      (BITS nicht verfuegbar, versuche andere Methode...)" -ForegroundColor DarkGray
}
# Methode B: .NET WebClient (folgt ebenfalls Umleitungen)
if (-not $ok) {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        (New-Object System.Net.WebClient).DownloadFile($zipUrl, $tmpZip)
        $ok = $true
    } catch {
        Write-Host "      (WebClient fehlgeschlagen, letzter Versuch...)" -ForegroundColor DarkGray
    }
}
# Methode C: Invoke-WebRequest als Fallback
if (-not $ok) {
    $ProgressPreference = "SilentlyContinue"
    try { Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -MaximumRedirection 5 } catch {}
    $ProgressPreference = "Continue"
}

if (-not (Test-Path $tmpZip)) {
    Write-Host "Download fehlgeschlagen - keine Datei." -ForegroundColor Red
    Write-Host "Lade manuell von: https://github.com/BtbN/FFmpeg-Builds/releases" -ForegroundColor Yellow
    Write-Host "  -> ffmpeg-master-latest-win64-gpl.zip"
    Read-Host "`nEnter zum Beenden"; exit 1
}
$sizeMB = (Get-Item $tmpZip).Length/1MB
Write-Host "      Geladen: $([math]::Round($sizeMB,1)) MB"
# Groessenpruefung: echte Datei ist ~150 MB. Unter 50 MB = kaputt/Fehlerseite.
if ($sizeMB -lt 50) {
    Write-Host "FEHLER: Datei viel zu klein ($([math]::Round($sizeMB,1)) MB statt ~150 MB)." -ForegroundColor Red
    Write-Host "Der Download wurde wahrscheinlich umgeleitet/blockiert." -ForegroundColor Red
    Write-Host ""
    Write-Host "Manueller Weg (sicher):" -ForegroundColor Yellow
    Write-Host "  1. Browser oeffnen: https://github.com/BtbN/FFmpeg-Builds/releases"
    Write-Host "  2. Unter 'Latest' die Datei 'ffmpeg-master-latest-win64-gpl.zip' laden"
    Write-Host "  3. Entpacken, im Unterordner 'bin' liegt ffmpeg.exe"
    Write-Host "  4. Diese ffmpeg.exe nach C:\ffmpeg\bin kopieren (alte ersetzen)"
    Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
    Read-Host "`nEnter zum Beenden"; exit 1
}

# --- 2. Entpacken -----------------------------------------------------
Write-Host "[2/4] Entpacke..." -ForegroundColor Yellow
if (Test-Path $tmpExtr) { Remove-Item $tmpExtr -Recurse -Force }
Expand-Archive -Path $tmpZip -DestinationPath $tmpExtr -Force
$innerBin = Get-ChildItem $tmpExtr -Recurse -Directory | Where-Object { $_.Name -eq "bin" } | Select-Object -First 1
if (-not $innerBin -or -not (Test-Path "$($innerBin.FullName)\ffmpeg.exe")) {
    Write-Host "ffmpeg.exe im entpackten Archiv nicht gefunden." -ForegroundColor Red
    Read-Host "`nEnter zum Beenden"; exit 1
}

# --- 3. Alte Version sichern + ersetzen ------------------------------
Write-Host "[3/4] Sichere alte Version und ersetze..." -ForegroundColor Yellow
if (-not (Test-Path $binPath)) { New-Item -ItemType Directory -Path $binPath -Force | Out-Null }
$backup = "$dest\bin_backup"
if (-not (Test-Path $backup)) { New-Item -ItemType Directory -Path $backup -Force | Out-Null }
foreach ($exe in @("ffmpeg.exe","ffprobe.exe","ffplay.exe")) {
    if (Test-Path "$binPath\$exe") {
        Copy-Item "$binPath\$exe" "$backup\$exe" -Force
    }
    if (Test-Path "$($innerBin.FullName)\$exe") {
        Copy-Item "$($innerBin.FullName)\$exe" "$binPath\$exe" -Force
    }
}
Write-Host "      Alte Version gesichert in: $backup"

# --- 4. Verifikation --------------------------------------------------
Write-Host "[4/4] Pruefe SVT-AV1..." -ForegroundColor Yellow
& "$binPath\ffmpeg.exe" -version | Select-Object -First 1
$svt = & "$binPath\ffmpeg.exe" -hide_banner -h encoder=libsvtav1 2>$null | Select-String "Encoder libsvtav1"
Write-Host ""
if ($svt) {
    Write-Host "SVT-AV1 ist jetzt verfuegbar und einsatzbereit!" -ForegroundColor Green
    Write-Host "WICHTIG: Oeffne ein NEUES cmd-Fenster, dann laeuft --encoder svt." -ForegroundColor Green
} else {
    Write-Host "SVT-AV1 konnte nicht bestaetigt werden - melde dich mit der Ausgabe." -ForegroundColor Red
}

# Aufraeumen
Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
Remove-Item $tmpExtr -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ""
Read-Host "Enter zum Beenden"
