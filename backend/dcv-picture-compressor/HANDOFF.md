# HANDOFF — Übergabe für den nächsten Thread

Kurzer Stand und offene Fäden, damit du (mit Sonnet) nicht bei null startest.

## Wo wir stehen

Funktionierendes Tool `stockphoto_video.py`, auf echten Daten verifiziert:
- 150 Fotos: 576 MB → 32 MB (−94 %), Roundtrip sauber
- 43 Fotos: 329 MB → 24.5 MB (−92.6 %), alle 43 bit-vollständig zurück, ~1 % Abweichung
- Lossless-Modus: 0.00 % bit-exakt verifiziert (auf PNG)

Repo-Dateien sind fertig: `README.md`, `DEVLOG.md`, `LICENSE` (MIT), `requirements.txt`, `.gitignore`, die ffmpeg-Installer (`install_ffmpeg.ps1`, `update_ffmpeg_svt.ps1`).

## VOR dem Launch unbedingt erledigen

1. **Namen einsetzen:** In `LICENSE` und README steht "Felix"/"Felix Zipp" — vollständigen Namen/Handle prüfen.
2. **Ein sauberer End-to-End-Test mit der AKTUELLEN Version:** `compress` → `decompress` → `vergleich` auf einem frischen Ordner. Diese Woche kamen `--lossless`, SVT-Selbsttest, Cluster-Cap, `--speed` dazu — einzeln getestet, aber nicht alle zusammen auf der echten Maschine in einem Durchlauf.
3. **README-Befehle gegen den echten Code prüfen** (CLI hat sich oft geändert). Aktuell korrekt laut Code: `benchmark/compress/decompress/vergleich`, Flags `--crf --encoder --speed --order --edge-thr --global --lossless`.
4. **Optional umbenennen:** Datei heißt noch `stockphoto_video.py`. Wenn das Repo "dcv" o.ä. heißt, Datei + README-Befehle angleichen.

## Offene technische Fäden

- **Cluster-Parallelisierung (`--jobs N`)** — der große offene Speed-Hebel. NICHT eingebaut, weil auf 1-Kern-Sandbox nicht testbar. Auf Felix' Mehrkern-PC testen: lohnt sich `--jobs 2/4` gegen `--jobs 1 --speed 12`? Achtung: SVT nutzt intern schon alle Kerne, Konkurrenz möglich. Sauberer Refactor: parallele Encode-Phase (alle Blobs erzeugen) getrennt vom sequenziellen Schreiben in der Reihenfolge. Worker-Funktion muss auf Modul-Ebene liegen (Windows ProcessPool).
- **Lossless auf echten RAW/PNG testen** — bisher nur synthetisches PNG. Felix wollte das auf echten verlustfreien Quellen sehen.
- **`--edge-thr 0` Messung** — wie viel Loss spart 4:4:4-für-alle, was kostet es an Größe? Auf echtem Ordner messen.
- **Schwellen-Tuning** (`--energy`): höher = größere Cluster = evtl. mehr Kompression, aber Vorsicht, ab einem Punkt kostet zu großzügiges Clustern mehr als es spart. Messen.

## Strategische Fragen (offen, kein Code)

- **Open Source vs. lizenzieren:** Tendenz Open Source (Wall um eine AV1-Orchestrierung ist dünn, Reputationsgewinn für RIM > fragiler Lizenzumsatz). Felix' Entscheidung.
- **RIM-Bezug** (eigener Thread): die Mannigfaltigkeits-/Penrose-Idee braucht zuerst die EINE Messung — clustern transformierte Daten auf der Struktur oder füllen sie den Raum? τ-Abstände ähnlicher vs. unähnlicher Bilder, `tick=0`. Das entscheidet, ob "Seed + Winkel"-Transport trägt.

## Git-Quickstart (für Felix)

```bash
cd "delta kompressor"
git init
git add README.md DEVLOG.md LICENSE requirements.txt .gitignore stockphoto_video.py install_ffmpeg.ps1 update_ffmpeg_svt.ps1
git commit -m "Initial release: AV1-backed photo library compressor"
# dann auf GitHub ein leeres Repo anlegen und:
git remote add origin https://github.com/DEINNAME/dcv.git
git branch -M main
git push -u origin main
```
NICHT committen: testdata/, *.dcv, benchmark_log.txt, die großen Bilderordner (steht im .gitignore).
