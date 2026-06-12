# DEVLOG — Entwicklungsprotokoll

Dieses Dokument hält fest, **was probiert wurde, was funktioniert hat und was nicht** — damit der nächste Entwickler keine Sackgassen erneut abläuft. Reihenfolge grob chronologisch.

---

## Ausgangspunkt

Vorgänger war ein selbstgebauter Delta-Kompressor mit 5 Strategien (Pixel-PNG, DCT, YCbCr+DCT, Global-Shift, JPEG-Delta). Real gemessen: +27 % auf 150 ähnliche Fotos, +15 % auf heterogenem Material. Nur Pixel-PNG und JPEG-Delta trugen real bei; der Rest war Komplexität ohne Gewinn.

**Kernerkenntnis 1:** Verlustfreie Pixel-Delta-Kompression auf JPEG-Quellen bringt ~0 % (−0.06 % gemessen). JPEG-Differenzen sind hochentropisch (Quantisierungsrauschen). Lossless lohnt nur auf PNG/RAW.

**Kernerkenntnis 2 (der Pivot):** Ein Cluster ähnlicher Fotos ist nichts anderes als Videoframes. Ein moderner Video-Encoder (AV1) mit Motion Compensation und B-Frames schlägt jedes selbstgebaute Delta. Gemessen bei gleicher Qualität: JPEG-Delta +70 % vs. AV1 +94 % auf demselben Cluster. → Das Eigenbau-Delta wurde verworfen, das Tool orchestriert seither AV1.

---

## Was funktioniert (im Tool)

- **Cluster-Entdeckung** in einer ungeordneten Bibliothek (shape → Histogramm-Cosinus → Thumbnail-Energie, Union-Find). Das ist der eigentliche Beitrag — Video bekommt die Frame-Reihenfolge geschenkt, eine Foto-Bibliothek nicht.
- **AV1-Video pro Cluster, AVIF pro Singleton.** AVIF (AV1-Einzelbild) schlägt JPEG bei gleicher Qualität um ~40-50 % (fair gemessen, PSNR-matched).
- **Adaptiver Fallback:** AV1-Pfad nur wenn kleiner als Original, sonst Original behalten. Garantie: nie größer.
- **4:4:4-Routing** für kantenreiche Bilder (siehe Loss-Sektion).
- **Lossless-Modus** über RGB (gbrp) + `lossless=1` — bit-exakt verifiziert (0.00 %).
- **Speichersicheres Clustering** auf Thumbnails/Histogrammen statt Vollbildern (~200 MB Peak statt mehrerer GB).
- **SVT-Selbsttest** beim Start: erkennt kaputte SVT-Builds und fällt sofort auf libaom zurück, statt pro Cluster vergeblich SVT zu versuchen.

Reale Ergebnisse: 150 Fotos 576 MB → 32 MB (−94 %); 43 Fotos 329 MB → 24.5 MB (−92.6 %); heterogene Stock-Sammlung −60 %.

---

## Loss reduzieren — was probiert wurde

Der Lossy-Eigenfehler liegt bei **~1-1.5 % mittlerer Pixelabweichung** (auf verlustfreiem PNG gemessen; gegen JPEG-Quellen ~1 %, weil das JPEG selbst schon geglättet ist — die Fehler überlappen, sie akkumulieren NICHT, separat verifiziert).

| Idee | Ergebnis | Status |
|---|---|---|
| **CRF senken** (mehr Bits) | 1.46 % @crf22 vs 1.56 % @crf34 — fast kein Effekt auf Loss, ändert nur Größe | ❌ kein Hebel |
| **4:4:4 statt 4:2:0 Chroma** | Kanten-MAE 11.66 → 1.33 (Faktor ~9!) auf kantenreichem Material; MaxDev 159 → 29 | ✅ **der echte Hebel** |
| **Lossless I-Frames einstreuen** | I-Frame ist eh schon der beste Frame (1.36 % vs 2.07 % Deltas). Verlustfrei macht nur das eine beste Bild perfekt, kostet ~200x Größe, Deltas bleiben | ❌ Sackgasse |
| **Lossless-Modus komplett** | 0.00 % bit-exakt, aber ~20-40 % statt 90 % Kompression | ✅ als Option |

**Fazit Loss:** Der einzige sinnvolle Loss-Hebel im Lossy-Modus ist **4:4:4** (per `--edge-thr` steuerbar). CRF und lossless I-Frames bringen nichts. Wer 0 % will, nimmt `--lossless` und akzeptiert die Größe. Es gibt bei AV1 **kein** "fast verlustfrei und winzig" dazwischen — das ist physikalisch, nicht behebbar.

**Warum 4:4:4 wirkt:** Der Loss sitzt nicht in der Bitmenge, sondern in der Chroma-Unterabtastung (4:2:0 wirft Farbauflösung an Kanten weg). AV1 nutzt intern bereits CfL (Chroma-from-Luma), ersetzt aber nicht die fehlende Abtastauflösung. 4:4:4 behält volle Chroma. Per-Region-Kopplung an den Kantenfilter (CDEF) ist im Codec NICHT möglich — Subsampling ist Frame-global. Daher Per-Bild-Routing über Sobel-Kantendichte.

---

## Geschwindigkeit erhöhen — was probiert wurde

**Profiling (gemessen):** Encoding = 78 % der Zeit, Decoding 14 %, Clustering 6 %, Laden 3 %. → Nur Encoding-Optimierung zählt.

| Idee | Ergebnis | Status |
|---|---|---|
| **SVT-AV1 statt libaom** | preset 6 ~gleiche Größe wie libaom, ~2x schneller; preset 8 ~5x schneller bei +10 % Größe. Skaliert mit CPU-Kernen | ✅ großer Hebel (wenn Build funktioniert) |
| **libaom cpu-used 4 → 6 → 8** | jeweils schneller, minimal größer | ✅ einfacher Hebel (`--speed`) |
| **Cluster-Cap (max 24 Frames/Clip)** | verhindert Riesen-Videos, die alles blockieren | ✅ Sicherheitsnetz |
| **Greedy/Tree-Ordering** | Pfad −26 % (greedy), MST −6..18 % Delta-Summe — aber Datei nur +2 % bzw. −0.16 %. Encoder baut intern eigenen Referenz-DAG, ignoriert externe Ordnung | ❌ kaum Wirkung |
| **Parallelverarbeitung mehrerer Cluster** | NICHT eingebaut. Risiko: SVT nutzt intern schon alle Kerne → Konkurrenz. Auf 1-Kern-Testumgebung sogar langsamer (0.9x). Ungetestet auf Mehrkern | ⏳ OFFEN — siehe HANDOFF |

**Fazit Speed:** Erster Hebel ist `--encoder svt --speed 10/12`. Auf Felix' Windows-Build war SVT zunächst kaputt (`-svtav1-params` unbekannt → entfernt; dann ganzer libsvtav1 fehlerhaft → BtbN-Build nötig, siehe `update_ffmpeg_svt.ps1`). Der GROSSE offene Hebel ist echte Cluster-Parallelisierung, aber sie muss auf einer Mehrkern-Maschine getestet werden, bevor sie vertrauenswürdig ist.

---

## Verworfene Architektur-Ideen (nicht erneut versuchen)

- **Synthetischer Mittelwert-Seed** als gemeinsame Referenz: liegt zwar näher an allen Membern, aber kostet als Extra-I-Frame mehr Bits als er spart. Datei wird größer (−5..−38 %). ❌
- **Expliziter Referenz-Baum** (jede Kante eigener 2-Frame-Clip): kostet 3-4.5x MEHR, weil jede Verzweigung einen frischen I-Frame zahlt. AV1 baut intern schon einen Referenz-DAG. ❌
- **Delta zweiter Ordnung** (Delta der Deltas): wird größer (+16-18 %), weil Foto-Deltas unkorreliert sind. Funktioniert nur bei gleichmäßiger Bewegung (Audio, Sensorzeitreihen). ❌
- **Penrose-Wasserzeichen als Fehlerkorrektur:** Fehlerkorrektur und Wasserzeichen sind Gegenteile; selbstgebaute Krypto/FEC schlägt nie Reed-Solomon/PAR2. Für Verlustschutz → PAR2 neben das Archiv. Für Echtheit → separates Siegel, kein FEC. ❌ (als FEC)
- **Kompression als Verschlüsselung** (I-Frames/Deltas trennen, Fake-Frames): ist Verschleierung, keine Verschlüsselung. Deltas sind hochstrukturiert, Clustering rekonstruiert die Zuordnung trivial. Richtig wäre: erst komprimieren, dann AES (7-Zip/VeraCrypt) auf das fertige `.dcv`. ❌

---

## Wichtige technische Details für den nächsten Entwickler

- **Archivformat DCV1:** MAGIC "DCV1", crf-Byte, n_collections, dann pro Collection name + n_clusters, pro Cluster: kind (0=still/1=video), n_frames, Namen (in ENCODE-Reihenfolge!), fallback-flags, blob, dann raw-Originale für Fallback-Frames. Namen werden in Encode-Reihenfolge gespeichert, damit Decode trivial mappt (keine Permutation persistiert).
- **Global-Modus:** flacht alle Ordner in einen Pool `_global`, Namen mit `ordner__datei` Präfix gegen Kollisionen. `vergleich` strippt das Präfix wieder.
- **Lossless-Pfad:** MUSS `-pix_fmt gbrp` + `-aom-params lossless=1`. yuv444+crf0 ist NICHT bit-exakt (YUV-Rundung, maxdiff 2). Nur gbrp gibt maxdiff 0.
- **SVT kann kein 4:4:4** → bei 4:4:4 immer libaom, auch wenn `--encoder svt`.
- **ffmpeg immer mit `-nostdin`** aufrufen, sonst frisst es bei langen Läufen die Tastatureingaben des Nutzers ("Enter command / Parse error").
- **Decode-Bilder als PNG schreiben**, nie als JPEG (zweiter Lossy-Schritt sonst).
