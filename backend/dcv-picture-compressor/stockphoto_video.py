"""
stockphoto_video.py  (DCV1)
===========================
Shippbare Pipeline: Foto-Library -> AV1-Video-Backend.

Konzept (Weg 2):
  - Eine Foto-Library ist eine UNGEORDNETE Menge mit verstecktem
    Aehnlichkeits-Graphen. Video bekommt die zeitliche Ordnung
    geschenkt; wir entdecken sie (Clustering + Ordering).
  - Cluster mit >=2 Bildern  -> als geordnete Frame-Sequenz durch AV1
    (Inter-Frame-Praediktion, B-Frames vom Encoder).
  - Singletons (Cluster=1)    -> als AVIF (AV1 1-Frame). Schlaegt JPEG
    um ~40% bei gleicher Qualitaet (Intra-Coding allein).
  - Adaptiver Fallback: ist die AV1-Variante nicht kleiner als das
    Original-JPEG, wird das Original-Byte fuer Byte behalten.
    => Garantie: nie groesser als die Quelle.

Verlustmodell: visuell verlustfrei (CRF-gesteuert, Default ~38 dB PSNR).
Decodierte Bilder werden als PNG geschrieben (kein erneuter Loss).

ABHAENGIGKEIT: ffmpeg mit libaom-av1 im PATH.

CLI:
  python stockphoto_video.py benchmark  --root DIR [--crf 28] [--order]
  python stockphoto_video.py compress    --root DIR --out FILE.dcv [...]
  python stockphoto_video.py decompress  --archive FILE.dcv --out DIR
"""
import argparse, glob, io, os, shutil, struct, subprocess, tempfile, time, zlib
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

MAGIC_DCV1 = b"DCV1"
MAGIC      = b"DCV2"
IMG_EXTS   = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


# def _resolve_ffmpeg():
#     """ffmpeg-Binary finden, auch wenn der PATH (noch) nicht aktualisiert
#     ist (typisch direkt nach einer winget/choco-Installation, solange die
#     Shell nicht neu gestartet wurde). Reihenfolge: ENV-Override -> PATH ->
#     bekannte Installationsorte (winget/choco/scoop)."""
#     env = os.environ.get("FFMPEG_BINARY")
#     if env and Path(env).exists():
#         return env
#     found = shutil.which("ffmpeg")
#     if found:
#         return found
#     home = Path.home()
#     candidates = [
#         home / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe",
#         Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
#         home / "scoop/shims/ffmpeg.exe",
#     ]
#     candidates += list(
#         (home / "AppData/Local/Microsoft/WinGet/Packages").glob(
#             "Gyan.FFmpeg*/**/bin/ffmpeg.exe"
#         )
#     )
#     for c in candidates:
#         if c.exists():
#             return str(c)
#     return "ffmpeg"  # letzter Versuch: PATH zur Laufzeit
def _resolve_ffmpeg():
    local_ffmpeg = Path(__file__).parent.parent / "bin" / "ffmpeg"
    print("Checking:", local_ffmpeg)
    print("Exists:", local_ffmpeg.exists())
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    env = os.environ.get("FFMPEG_BINARY")
    if env and Path(env).exists():
        return env

    found = shutil.which("ffmpeg")
    if found:
        return found

    return "ffmpeg"

FFMPEG     = _resolve_ffmpeg()
print("FFMPEG =", FFMPEG)
# -nostdin: ffmpeg darf NICHT die Tastatur abgreifen. Ohne das frisst
# ffmpeg bei laengeren Laeufen die Befehle, die der Nutzer danach tippt
# (sichtbar als "Enter command:" / "Parse error" Meldungen).
FFMPEG_BASE = [FFMPEG, "-nostdin", "-y", "-loglevel", "error"]
CRF_DEFAULT      = 28
ENERGY_DEFAULT   = 60.0
HIST_BINS        = 32
HIST_SIM         = 0.85
AV1_CPU_USED     = "6"     # libaom: 0=langsam/klein .. 8=schnell/gross
SVT_PRESET       = "8"     # SVT-AV1: 0=langsam/klein .. 13=schnell/gross
MAX_CLUSTER      = 24      # max Frames pro Clip (grosse Cluster werden geteilt)
# Kantenschwelle fuer 4:4:4-Routing. Hoeher = seltener 4:4:4 (kleiner/schneller).
# Auf Fotomaterial (Wasser, Himmel, Haut) war 0.5 viel zu empfindlich
# (>80% der Bilder unnoetig auf 4:4:4). 3.0 trifft nur echte Grafik/Text/Logos.
EDGE_DENSITY_THR = 3.0


# ---------------------------------------------------------------- I/O & Metriken
def load_pixels(p): return np.array(Image.open(p).convert("RGB"), dtype=np.uint8)
def read_raw(p):    return open(p, "rb").read()
def mae(a, b):      return float(np.abs(a.astype(np.int16)-b.astype(np.int16)).mean())
def psnr(a, b):
    m=((a.astype(np.float64)-b.astype(np.float64))**2).mean()
    return 99.0 if m==0 else 10*np.log10(255**2/m)

def _system_check(n_images, verbose=True):
    """Prueft verfuegbaren RAM und warnt bei sehr grossen Laeufen.
    Nutzt psutil wenn vorhanden, faellt sonst auf eine konservative
    Warnung zurueck. Gibt True zurueck wenn der Lauf vermutlich sicher ist."""
    # Clustering ist paarweise O(n^2) pro Shape-Gruppe -> Warnung ab vielen Bildern
    if n_images > 5000:
        if verbose:
            print(f"  WARNUNG: {n_images} Bilder. Das Clustering ist paarweise "
                  f"(O(n^2)) und kann lange dauern bzw. viel RAM brauchen.")
            print(f"           Tipp: ohne --global pro Ordner laufen lassen, "
                  f"oder Ordner einzeln verarbeiten.")
    try:
        import psutil
        avail=psutil.virtual_memory().available/1024/1024/1024
        if verbose:
            print(f"  Verfuegbarer RAM: {avail:.1f} GB")
        # grobe Schaetzung: Metadaten ~0.05 MB/Bild + paar Vollbilder gleichzeitig
        est_gb = n_images*0.05/1024 + 1.0
        if est_gb > avail*0.8:
            if verbose:
                print(f"  WARNUNG: geschaetzter Bedarf (~{est_gb:.1f} GB) nahe am "
                      f"freien RAM. Schliesse andere Programme oder verarbeite "
                      f"Ordner einzeln.")
            return False
    except ImportError:
        if verbose and n_images>2000:
            print(f"  Hinweis: 'pip install psutil' fuer RAM-Pruefung empfohlen.")
    return True


def _svt_works():
    """Schneller Selbsttest: kann diese ffmpeg-Build ueberhaupt SVT-AV1?
    Encodiert ein 2-Frame-Mini-Video. Verhindert, dass jeder Cluster erst
    SVT versucht, scheitert und langsam auf libaom zurueckfaellt."""
    tmp=tempfile.mkdtemp(prefix="dcv_svttest_")
    try:
        for k in range(2):
            Image.fromarray(np.zeros((64,64,3),dtype=np.uint8)).save(f"{tmp}/f{k:05d}.png")
        out=f"{tmp}/o.mkv"
        r=subprocess.run(FFMPEG_BASE+["-framerate","30","-i",f"{tmp}/f%05d.png",
            "-c:v","libsvtav1","-crf","40","-preset","8","-pix_fmt","yuv420p",out],
            stderr=subprocess.DEVNULL)
        return r.returncode==0 and os.path.getsize(out)>0
    except Exception:
        return False
    finally:
        shutil.rmtree(tmp,ignore_errors=True)


def hist_vec(arr):
    v=[]
    for c in range(3):
        h,_=np.histogram(arr[:,:,c],bins=HIST_BINS,range=(0,256))
        v.append(h/(h.sum()+1e-8))
    return np.concatenate(v)

def find_images(folder):
    return sorted(str(p) for p in Path(folder).iterdir()
                  if p.suffix.lower() in IMG_EXTS)

def find_collections(root, global_pool=False):
    root=Path(root); colls={}
    imgs=find_images(str(root))
    if imgs: colls[root.name]=imgs
    for sub in sorted(root.iterdir()):
        if sub.is_dir():
            i=find_images(str(sub))
            if i: colls[sub.name]=i
    if global_pool:
        # Alle Bilder ueber alle Ordner in EINEN Pool -> Clustering findet
        # Beinah-Duplikate auch ueber Ordnergrenzen hinweg. Wichtig: bei
        # Namensgleichheit in verschiedenen Ordnern wird der Ordnername
        # vorangestellt, damit die Rekonstruktion eindeutig bleibt.
        pool=[]; seen=set()
        for cname,paths in colls.items():
            for p in paths:
                pool.append(p)
        return {"_global": pool}
    return colls


# ---------------------------------------------------------------- Clustering
def _image_meta(path):
    """Leichtgewichtige Metadaten fuer Clustering OHNE das Vollbild im RAM
    zu halten: Shape, Histogramm-Vektor, kleines Thumbnail (64x64) fuer den
    Energie-Vergleich. Ein Thumbnail kostet ~12 KB statt mehrere MB."""
    im=Image.open(path).convert("RGB")
    shape=(im.size[1], im.size[0], 3)
    arr=np.asarray(im, dtype=np.uint8)
    h=[]
    for c in range(3):
        hist,_=np.histogram(arr[:,:,c],bins=HIST_BINS,range=(0,256))
        h.append(hist/(hist.sum()+1e-8))
    hv=np.concatenate(h)
    thumb=np.asarray(im.resize((64,64),Image.BILINEAR),dtype=np.int16)
    return shape, hv, thumb

def cluster_images_lowmem(paths, energy_threshold, verbose=False):
    """Clustering nur auf Metadaten (Histogramm + Thumbnail), nicht auf
    Vollbildern. Spart ~100x RAM. Der Energie-Vergleich laeuft auf 64x64-
    Thumbnails statt auf der vollen Aufloesung - fuer die Aehnlichkeits-
    entscheidung voellig ausreichend."""
    metas={}
    for i,p in enumerate(paths):
        if verbose and i%200==0 and i>0:
            print(f"\r    Analysiere Bilder... {i}/{len(paths)}",end="",flush=True)
        try:
            metas[p]=_image_meta(p)
        except Exception:
            metas[p]=((0,0,3), np.zeros(HIST_BINS*3), np.zeros((64,64,3),dtype=np.int16))
    if verbose: print("\r"+" "*50+"\r",end="")

    shape_groups={}
    for p in paths:
        shape_groups.setdefault(metas[p][0],[]).append(p)
    clusters=[]
    for shape,group in shape_groups.items():
        if len(group)==1:
            clusters.append(group); continue
        vecs=np.array([metas[p][1] for p in group])
        normed=vecs/(np.linalg.norm(vecs,axis=1,keepdims=True)+1e-8)
        sim=normed@normed.T; n=len(group); parent=list(range(n))
        def find(x):
            while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
            return x
        for i in range(n):
            for j in range(i+1,n):
                if sim[i,j]>=HIST_SIM:
                    # Energie auf Thumbnails (gleiche Groesse 64x64) statt Vollbild
                    e=np.abs(metas[group[i]][2]-metas[group[j]][2]).mean()
                    if e<energy_threshold:
                        pi,pj=find(i),find(j)
                        if pi!=pj: parent[pi]=pj
        g={}
        for i in range(n): g.setdefault(find(i),[]).append(group[i])
        clusters.extend(g.values())
    return clusters

def cluster_images(paths, pixels, energy_threshold):
    """Alte Signatur (haelt alle Pixel im RAM) - bleibt fuer Kompatibilitaet,
    delegiert aber an die speicherarme Variante."""
    return cluster_images_lowmem(paths, energy_threshold)


# ---------------------------------------------------------------- Ordering
def _dist_matrix(arrs):
    n=len(arrs); D=np.zeros((n,n),dtype=np.float32)
    for i in range(n):
        for j in range(i+1,n):
            D[i,j]=D[j,i]=mae(arrs[i],arrs[j])
    return D

def greedy_order(arrs):
    """Lineare Kette: greedy nearest-neighbor (TSP-Heuristik)."""
    n=len(arrs)
    if n<=2: return list(range(n))
    D=_dist_matrix(arrs)
    start=int(np.argmin(D.mean(axis=1)))
    visited=[start]; remaining=set(range(n))-{start}
    while remaining:
        last=visited[-1]
        nxt=min(remaining,key=lambda k:D[last,k])
        visited.append(nxt); remaining.discard(nxt)
    return visited

def tree_order(arrs):
    """Baum-Reihenfolge: Minimum Spanning Tree auf dem Aehnlichkeitsgraphen,
    dann DFS-Praeorder ab dem Zentrum. Senkt die Summe der Inter-Frame-Deltas
    und die Pfadtiefe (weniger Fehlerakkumulation) gegenueber der Linie.
    Wir uebergeben dem Encoder eine DFS-Linearisierung des Baums: aufeinander-
    folgende Frames sind dann meist Eltern/Kind -> der Encoder findet die
    passende Referenz in seinem Referenzfenster, ohne dass wir den Container
    aufbrechen muessen."""
    n=len(arrs)
    if n<=2: return list(range(n))
    try:
        from scipy.sparse.csgraph import minimum_spanning_tree
        from scipy.sparse import csr_matrix
    except Exception:
        return greedy_order(arrs)   # Fallback wenn scipy.csgraph fehlt
    D=_dist_matrix(arrs)
    mst=minimum_spanning_tree(csr_matrix(D)).toarray()
    # ungerichteter Adjazenzgraph
    import collections
    adj=collections.defaultdict(list)
    ii,jj=np.where(mst>0)
    for a,b in zip(ii,jj): adj[a].append(b); adj[b].append(a)
    # leere Kanten (vollstaendig unaehnlich) koennen MST zerteilen -> alle Knoten
    root=int(np.argmin(D.mean(axis=1)))
    order=[]; seen=set()
    # DFS-Praeorder, Kinder nach Naehe zum Elternframe sortiert
    def dfs(u):
        seen.add(u); order.append(u)
        for v in sorted(adj[u], key=lambda v:D[u,v]):
            if v not in seen: dfs(v)
    dfs(root)
    # Falls MST nicht verbunden (mehrere Komponenten): Reste anhaengen
    for k in range(n):
        if k not in seen: order.append(k)
    return order

def order_frames(arrs, strategy):
    if strategy=="tree":   return tree_order(arrs)
    if strategy=="greedy": return greedy_order(arrs)
    return list(range(len(arrs)))   # "none"


# ---------------------------------------------------------------- AV1 encode/decode
def edge_density(arr):
    """Anteil starker Farbkanten (%). Hoch -> harte Kanten (Logo/Text/Grafik)."""
    g = arr.mean(axis=2)
    e = np.hypot(ndimage.sobel(g, axis=0), ndimage.sobel(g, axis=1))
    return float((e > 120).mean() * 100)

def choose_pix_fmt(arrs):
    """4:4:4 wenn IRGENDEIN Frame harte Farbkanten hat, sonst 4:2:0.
    Subsampling ist eine Frame-Sequenz-Eigenschaft -> gilt fuer den ganzen
    Cluster, daher max() ueber die Frames."""
    dens = max(edge_density(a) for a in arrs)
    return ("yuv444p" if dens > EDGE_DENSITY_THR else "yuv420p"), dens

def _av1_video(arrs, order, crf, pix_fmt="yuv420p", gop=None, encoder="libaom",
               lossless=False):
    H,W,_=arrs[0].shape
    tmp=tempfile.mkdtemp(prefix="dcv_e_")
    try:
        for k,oi in enumerate(order):
            Image.fromarray(arrs[oi]).save(f"{tmp}/f{k:05d}.png")
        out=f"{tmp}/o.mkv"; n=len(order)
        gop=gop or max(n,1)
        if lossless:
            # Bit-exakt: RGB direkt (gbrp, kein YUV-Rundungsumweg) + lossless=1.
            # SVT kann das nicht zuverlaessig -> immer libaom.
            subprocess.run(FFMPEG_BASE+["-framerate","30","-i",f"{tmp}/f%05d.png",
                "-c:v","libaom-av1","-aom-params","lossless=1","-g",str(gop),
                "-cpu-used",AV1_CPU_USED,"-row-mt","1","-pix_fmt","gbrp",out],check=True)
            return open(out,"rb").read()
        # SVT-AV1 ist deutlich schneller, kann aber kein 4:4:4 -> bei 4:4:4
        # immer libaom. Sonst nach Encoder-Wahl.
        use_svt = (encoder=="svt" and pix_fmt!="yuv444p")
        def _aom_cmd():
            return FFMPEG_BASE+["-framerate","30","-i",f"{tmp}/f%05d.png",
                "-c:v","libaom-av1","-crf",str(crf),"-g",str(gop),
                "-cpu-used",AV1_CPU_USED,"-row-mt","1","-pix_fmt",pix_fmt,out]
        if use_svt:
            # -svtav1-params bewusst weggelassen: nicht jede ffmpeg-Build
            # kennt die Option. Preset reicht. Faellt bei Fehler auf libaom.
            cmd=FFMPEG_BASE+["-framerate","30","-i",f"{tmp}/f%05d.png",
                "-c:v","libsvtav1","-crf",str(crf),"-g",str(gop),
                "-preset",SVT_PRESET,"-pix_fmt",pix_fmt,out]
            r=subprocess.run(cmd,stderr=subprocess.DEVNULL)
            if r.returncode!=0:
                # SVT nicht verfuegbar/inkompatibel -> libaom als Fallback
                subprocess.run(_aom_cmd(),check=True)
        else:
            subprocess.run(_aom_cmd(),check=True)
        return open(out,"rb").read()
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def _av1_still(arr, crf, pix_fmt="yuv420p", lossless=False):
    tmp=tempfile.mkdtemp(prefix="dcv_s_")
    try:
        Image.fromarray(arr).save(f"{tmp}/i.png")
        out=f"{tmp}/o.avif"
        if lossless:
            subprocess.run(FFMPEG_BASE+["-i",f"{tmp}/i.png",
                "-c:v","libaom-av1","-aom-params","lossless=1","-still-picture","1",
                "-cpu-used",AV1_CPU_USED,"-pix_fmt","gbrp",out],check=True)
        else:
            subprocess.run(FFMPEG_BASE+["-i",f"{tmp}/i.png",
                "-c:v","libaom-av1","-crf",str(crf),"-still-picture","1",
                "-cpu-used",AV1_CPU_USED,"-pix_fmt",pix_fmt,out],check=True)
        return open(out,"rb").read()
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def _av1_decode(data, is_still):
    tmp=tempfile.mkdtemp(prefix="dcv_d_")
    try:
        ext=".avif" if is_still else ".mkv"
        open(f"{tmp}/in{ext}","wb").write(data)
        subprocess.run(FFMPEG_BASE+["-i",f"{tmp}/in{ext}",
                        f"{tmp}/o%05d.png"],check=True)
        return [np.array(Image.open(p).convert("RGB"),dtype=np.uint8)
                for p in sorted(glob.glob(f"{tmp}/o*.png"))]
    finally:
        shutil.rmtree(tmp,ignore_errors=True)


# ---------------------------------------------------------------- Archiv
# DCV2 layout (DCV1 without original_sizes is still readable):
#   MAGIC, crf(uint8), n_collections(uint32)
#   per coll: name, n_clusters
#     per cluster: kind(uint8: 0=still 1=video), n_frames(uint32),
#                  [frame_name x n_frames],
#                  original_sizes (n_frames uint64),
#                  fallback_flags(n_frames bytes: 1=stored as raw original),
#                  blob (len-prefixed)  -- AV1 video/still
#                  raw_originals (each len-prefixed) only for fallback frames
def _ws(f,s): b=s.encode(); f.write(struct.pack(">I",len(b))); f.write(b)
def _wb(f,d): f.write(struct.pack(">I",len(d))); f.write(d)
def _rs(f):   return f.read(struct.unpack(">I",f.read(4))[0]).decode()
def _rb(f):   return f.read(struct.unpack(">I",f.read(4))[0])

def _output_name(name, fallback):
    if fallback or Path(name).suffix.lower()==".png":
        return name
    return str(Path(name).with_suffix(".png"))

def _pad_png_to_size(path, target_size):
    current=os.path.getsize(path)
    if not target_size or current>=target_size:
        return False
    needed=target_size-current
    data=Path(path).read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False

    iend_at=data.rfind(b"IEND")
    chunk_start=iend_at-4
    if iend_at<0 or chunk_start<8:
        return False

    if needed>=12:
        payload_len=needed-12
        chunk_type=b"npAD"
        payload=b"\0"*payload_len
        crc=struct.pack(">I",zlib.crc32(chunk_type+payload)&0xFFFFFFFF)
        padding=struct.pack(">I",payload_len)+chunk_type+payload+crc
        Path(path).write_bytes(data[:chunk_start]+padding+data[chunk_start:])
        return True

    Path(path).write_bytes(data+(b"\0"*needed))
    return True

def pack_archive(root, out_path, crf=CRF_DEFAULT, energy=ENERGY_DEFAULT,
                 order_strategy="greedy", encoder="libaom", global_pool=False,
                 lossless=False, verbose=True):
    colls=find_collections(root, global_pool=global_pool)
    if not colls: print("Keine Bilder."); return {}
    total_imgs=sum(len(p) for p in colls.values())
    if verbose: _system_check(total_imgs, verbose=True)
    # SVT-Selbsttest: wenn angefordert aber nicht lauffaehig, JETZT auf libaom
    # umstellen statt bei jedem Cluster vergeblich SVT zu versuchen.
    if encoder=="svt":
        if _svt_works():
            if verbose: print(f"  Encoder: SVT-AV1 (preset {SVT_PRESET}) - schnell")
        else:
            if verbose:
                print(f"  WARNUNG: SVT-AV1 laeuft mit dieser ffmpeg-Build nicht.")
                print(f"           Wechsle auf libaom (cpu-used {AV1_CPU_USED}). "
                      f"Langsamer - fuer Tempo eine neuere ffmpeg-Build mit "
                      f"funktionierendem SVT installieren.")
            encoder="libaom"
    elif verbose:
        print(f"  Encoder: libaom (cpu-used {AV1_CPU_USED})")
    stats={"crf":crf,"collections":0,"images":0,"original_bytes":0,
           "archive_bytes":0,"n_clusters":0,"n_singletons":0,
           "n_fallback":0,"n_444":0,"max_mae":0.0,"min_psnr":99.0,"coll":{}}
    with open(out_path,"wb") as f:
        f.write(MAGIC); f.write(struct.pack(">B",crf))
        f.write(struct.pack(">I",len(colls)))
        for cname,paths in colls.items():
            orig=sum(os.path.getsize(p) for p in paths)
            # Clustering auf Metadaten (Histogramm/Thumbnail) - haelt NICHT
            # alle Vollbilder im RAM. Wichtig fuer --global ueber viele Ordner.
            clusters=cluster_images_lowmem(paths, energy, verbose=verbose)
            # Cap: sehr grosse Cluster in handliche Stuecke teilen, damit kein
            # einzelnes Riesen-Video die Verarbeitung blockiert. MAX_CLUSTER
            # Frames pro Clip ist ein guter Kompromiss aus Tempo und Kompression.
            capped=[]
            for cl in clusters:
                if len(cl)>MAX_CLUSTER:
                    for i in range(0,len(cl),MAX_CLUSTER):
                        capped.append(cl[i:i+MAX_CLUSTER])
                else:
                    capped.append(cl)
            clusters=capped
            if verbose:
                print(f"\n  [{cname}] {len(paths)} Bilder ({orig/1024:.0f} KB) "
                      f"-> {len(clusters)} Cluster")
            _ws(f,cname); f.write(struct.pack(">I",len(clusters)))
            coll_bytes=0; cmax_mae=0.0; cmin_psnr=99.0
            t_coll=time.time(); n_cl=len(clusters)
            for ci,cluster in enumerate(clusters):
                if verbose:
                    elapsed=time.time()-t_coll
                    eta=(elapsed/ci*(n_cl-ci)) if ci>0 else 0
                    print(f"\r    [{ci+1}/{n_cl}] verarbeitet... "
                          f"({elapsed:.0f}s, ETA ~{eta:.0f}s)   ",
                          end="", flush=True)
                # Vollbilder NUR fuer diesen Cluster laden (danach freigegeben)
                arrs=[load_pixels(p) for p in cluster]
                # In global mode kann derselbe Dateiname in mehreren Ordnern
                # vorkommen -> Ordner-Praefix erhalten, damit Rekonstruktion
                # eindeutig ist und Bilder zurueck in ihren Ordner landen.
                if cname=="_global":
                    names=[str(Path(p).relative_to(Path(root))).replace(os.sep,"__")
                           for p in cluster]
                else:
                    names=[Path(p).name for p in cluster]
                raws =[read_raw(p) for p in cluster]
                pix_fmt, edens = choose_pix_fmt(arrs)
                if len(cluster)==1:
                    blob=_av1_still(arrs[0],crf,pix_fmt,lossless=lossless); kind=0; order=[0]
                    stats["n_singletons"]+=1
                else:
                    order=order_frames(arrs, order_strategy)
                    blob=_av1_video(arrs,order,crf,pix_fmt,encoder=encoder,lossless=lossless); kind=1
                    stats["n_clusters"]+=1
                if pix_fmt=="yuv444p": stats["n_444"]+=1
                # Alles in ENCODE-Reihenfolge fuehren -> trivial dekodierbar
                enc_names=[names[oi] for oi in order]
                enc_arrs =[arrs[oi]  for oi in order]
                enc_raws =[raws[oi]  for oi in order]
                enc_sizes=[len(r) for r in enc_raws]
                recon=_av1_decode(blob, kind==0)   # in encode-Reihenfolge
                fallback=[0]*len(cluster)
                # Cluster lohnt sich nur, wenn AV1-Blob < Summe Originale
                if len(blob) >= sum(len(r) for r in enc_raws):
                    for i in range(len(cluster)): fallback[i]=1
                f.write(struct.pack(">B",kind))
                f.write(struct.pack(">I",len(cluster)))
                for nm in enc_names: _ws(f,nm)
                for size in enc_sizes: f.write(struct.pack(">Q",size))
                f.write(bytes(fallback))
                if all(fallback):
                    _wb(f,b"")
                else:
                    _wb(f,blob)
                    for i in range(len(cluster)):
                        m=mae(enc_arrs[i],recon[i]); p=psnr(enc_arrs[i],recon[i])
                        cmax_mae=max(cmax_mae,m); cmin_psnr=min(cmin_psnr,p)
                for i in range(len(cluster)):
                    if fallback[i]:
                        _wb(f,enc_raws[i]); stats["n_fallback"]+=1
                if all(fallback):
                    coll_bytes+=sum(len(r) for r in enc_raws)
                else:
                    coll_bytes+=len(blob)+sum(len(enc_raws[i]) for i in range(len(cluster)) if fallback[i])
            saving=(1-coll_bytes/orig)*100 if orig else 0
            if verbose:
                print(f"\r    {orig/1024:.0f} KB -> {coll_bytes/1024:.0f} KB "
                      f"{saving:+.1f}%  (MaxMAE {cmax_mae:.2f}, MinPSNR {cmin_psnr:.1f}dB)"
                      f"{' '*20}")
            stats["collections"]+=1; stats["images"]+=len(paths)
            stats["original_bytes"]+=orig
            stats["max_mae"]=max(stats["max_mae"],cmax_mae)
            stats["min_psnr"]=min(stats["min_psnr"],cmin_psnr)
            stats["coll"][cname]={"images":len(paths),"orig_kb":orig/1024,
                                  "comp_kb":coll_bytes/1024,"saving":saving,
                                  "max_mae":cmax_mae,"min_psnr":cmin_psnr}
    stats["archive_bytes"]=os.path.getsize(out_path)
    stats["savings_pct"]=(1-stats["archive_bytes"]/stats["original_bytes"])*100
    return stats

def unpack_archive(archive_path, out_dir, match_original_size=False):
    os.makedirs(out_dir,exist_ok=True)
    with open(archive_path,"rb") as f:
        magic=f.read(4)
        assert magic in (MAGIC_DCV1,MAGIC),"Kein DCV-Archiv"
        has_original_sizes=magic==MAGIC
        _=struct.unpack(">B",f.read(1))[0]
        n_coll=struct.unpack(">I",f.read(4))[0]
        for _ in range(n_coll):
            cname=_rs(f); cdir=os.path.join(out_dir,cname); os.makedirs(cdir,exist_ok=True)
            n_cl=struct.unpack(">I",f.read(4))[0]
            for _ in range(n_cl):
                kind=struct.unpack(">B",f.read(1))[0]
                nf=struct.unpack(">I",f.read(4))[0]
                names=[_rs(f) for _ in range(nf)]
                original_sizes=[struct.unpack(">Q",f.read(8))[0] for _ in range(nf)] if has_original_sizes else [None]*nf
                fallback=list(f.read(nf))
                blob=_rb(f)
                # AV1-dekodierte Frames (falls Blob vorhanden)
                if blob:
                    frames=_av1_decode(blob, kind==0)
                else:
                    frames=[]
                # Namen + Frames beide in ENCODE-Reihenfolge -> direktes Mapping
                fi=0
                for i in range(nf):
                    if fallback[i]:
                        raw=_rb(f)
                        open(os.path.join(cdir,names[i]),"wb").write(raw)
                    else:
                        arr=frames[fi]; fi+=1
                        p=Path(cdir)/names[i]
                        if p.suffix.lower()!=".png": p=p.with_suffix(".png")
                        Image.fromarray(arr).save(str(p),"PNG",optimize=True)
                        if match_original_size:
                            _pad_png_to_size(p, original_sizes[i])

def read_archive_original_sizes(archive_path):
    sizes={}
    with open(archive_path,"rb") as f:
        magic=f.read(4)
        if magic not in (MAGIC_DCV1,MAGIC):
            return sizes
        has_original_sizes=magic==MAGIC
        _=struct.unpack(">B",f.read(1))[0]
        n_coll=struct.unpack(">I",f.read(4))[0]
        for _ in range(n_coll):
            cname=_rs(f)
            n_cl=struct.unpack(">I",f.read(4))[0]
            for _ in range(n_cl):
                _kind=struct.unpack(">B",f.read(1))[0]
                nf=struct.unpack(">I",f.read(4))[0]
                names=[_rs(f) for _ in range(nf)]
                original_sizes=[struct.unpack(">Q",f.read(8))[0] for _ in range(nf)] if has_original_sizes else [None]*nf
                fallback=list(f.read(nf))
                _=_rb(f)
                for i,name in enumerate(names):
                    if original_sizes[i] is not None:
                        rel=Path(cname)/_output_name(name, bool(fallback[i]))
                        sizes[rel.as_posix()]=original_sizes[i]
                for i in range(nf):
                    if fallback[i]:
                        _=_rb(f)
    return sizes


# ---------------------------------------------------------------- Benchmark
def benchmark(root, crf=CRF_DEFAULT, energy=ENERGY_DEFAULT, order_strategy="greedy",
              encoder="libaom", global_pool=False, lossless=False):
    colls=find_collections(root, global_pool=global_pool)
    if not colls: print("Keine Bilder."); return
    n=sum(len(p) for p in colls.values())
    orig=sum(os.path.getsize(p) for ps in colls.values() for p in ps)

    # Sammelt alle Ausgabezeilen, damit sie sowohl auf den Bildschirm
    # als auch in eine Logdatei neben dem Skript geschrieben werden koennen.
    lines=[]
    def out(s=""):
        print(s); lines.append(s)

    gmode=" GLOBAL" if global_pool else ""
    out(f"\n{'='*66}\n  Stockfoto Video-Kompressor (DCV1, AV1)  CRF={crf}  Order={order_strategy}  Enc={encoder}{gmode}")
    out(f"  {len(colls)} Kollektionen | {n} Bilder | {orig/1024/1024:.2f} MB\n{'='*66}")
    tmp=os.path.join(tempfile.gettempdir(),"_dcv_bench.dcv"); t0=time.time()
    st=pack_archive(root,tmp,crf=crf,energy=energy,order_strategy=order_strategy,
                    encoder=encoder,global_pool=global_pool,lossless=lossless,verbose=True)
    if not st: return
    out(f"\n{'='*66}\n  ERGEBNIS")
    out(f"  Original:  {st['original_bytes']/1024/1024:.3f} MB")
    out(f"  Archiv:    {st['archive_bytes']/1024/1024:.3f} MB")
    out(f"  Ersparnis: {st['savings_pct']:+.2f}%   ({time.time()-t0:.1f}s)")
    out(f"  Cluster:{st['n_clusters']}  Singletons:{st['n_singletons']}  "
        f"Fallback-Frames:{st['n_fallback']}  4:4:4-Routing:{st['n_444']}")
    out(f"  Qualitaet: MaxMAE {st['max_mae']:.2f}, MinPSNR {st['min_psnr']:.1f}dB")
    out(f"\n  {'Name':<20}{'Bilder':>7}{'Orig':>10}{'Komp':>10}{'Ers.':>8}{'PSNR':>8}")
    out(f"  {'-'*61}")
    for cn,cs in st["coll"].items():
        out(f"  {cn:<20}{cs['images']:>7}{cs['orig_kb']:>9.0f}K{cs['comp_kb']:>9.0f}K"
            f"{cs['saving']:>+7.1f}%{cs['min_psnr']:>6.1f}dB")
    # Roundtrip
    out(f"\n  Roundtrip-Verifikation...")
    rec=os.path.join(tempfile.gettempdir(),"_dcv_recon"); shutil.rmtree(rec,ignore_errors=True)
    unpack_archive(tmp,rec)
    ok=err=0; mx=0.0
    for cn,paths in colls.items():
        for p in paths:
            if cn=="_global":
                # gespeicherter Name = ordner__datei (siehe pack), Suffix evtl .png
                stored=str(Path(p).relative_to(Path(root))).replace(os.sep,"__")
                base=Path(stored).stem
            else:
                base=Path(p).stem
            cand=[Path(rec)/cn/(base+e) for e in (".png",".jpg",".jpeg")]
            rp=next((c for c in cand if c.exists()),None)
            if rp is None: out(f"  FEHLT {cn}/{Path(p).name}"); err+=1; continue
            o=load_pixels(p); r=load_pixels(str(rp))
            if o.shape!=r.shape: out(f"  SHAPE {Path(p).name}"); err+=1; continue
            m=mae(o,r); mx=max(mx,m); ok+=1
    out(f"  OK:{ok}  Fehler:{err}  Max MAE roundtrip: {mx:.3f}")
    out()

    # --- Logdatei neben dem Skript schreiben (anhaengend, mit Zeitstempel) ---
    try:
        script_dir=os.path.dirname(os.path.abspath(__file__))
        log_path=os.path.join(script_dir,"benchmark_log.txt")
        stamp=time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path,"a",encoding="utf-8") as lf:
            lf.write(f"\n\n########## Benchmark {stamp} ##########\n")
            lf.write(f"Ordner: {os.path.abspath(root)}\n")
            lf.write(f"Parameter: CRF={crf}  Order={order_strategy}  Enc={encoder}  "
                     f"Energy={energy}  EdgeThr={EDGE_DENSITY_THR}\n")
            lf.write("\n".join(lines))
            lf.write("\n")
        print(f"  -> Log angehaengt an: {log_path}")
    except Exception as e:
        print(f"  (Logdatei konnte nicht geschrieben werden: {e})")


def compare_folders(orig_dir, rec_dir):
    """Vergleicht Original- und Rekonstruktions-Ordner und gibt die Abweichung
    in PROZENT aus - verstaendlich, ohne Fachbegriffe. Paart Bilder ueber den
    Dateinamen (Rekonstruktion liegt als .png vor, Original als .jpg)."""
    def _load(p): return np.array(Image.open(p).convert("RGB"), dtype=np.float64)
    def _index(folder):
        idx={}
        for p in Path(folder).rglob("*"):
            if p.suffix.lower() in IMG_EXTS:
                key=str(p.relative_to(folder).with_suffix("")).replace(os.sep,"__")
                if key.startswith("_global__"): key=key[len("_global__"):]
                idx[key]=p
        return idx

    orig_idx=_index(orig_dir); rec_idx=_index(rec_dir)
    print(f"\nOriginal:       {orig_dir}  ({len(orig_idx)} Bilder)")
    print(f"Rekonstruktion: {rec_dir}  ({len(rec_idx)} Bilder)")
    print(f"\n{'Bild':<40}{'Abweichung':>12}{'sichtbar veraendert':>22}")
    print("-"*74)

    all_dev=[]; all_vis=[]; worst=("",0.0); missing=0; shown=0
    for key,opath in sorted(orig_idx.items()):
        rpath=rec_idx.get(key)
        if rpath is None:
            print(f"{key[:38]:<40}{'FEHLT':>12}"); missing+=1; continue
        o=_load(opath); r=_load(rpath)
        if o.shape!=r.shape:
            print(f"{key[:38]:<40}{'GROESSE!':>12}"); missing+=1; continue
        diff=np.abs(o-r)
        dev=diff.mean()/255*100
        vis=(diff>0.02*255).mean()*100
        all_dev.append(dev); all_vis.append(vis)
        if dev>worst[1]: worst=(key,dev)
        if shown<25:
            print(f"{key[:38]:<40}{dev:>10.2f} %{vis:>19.1f} %"); shown+=1
    if len(all_dev)>25:
        print(f"  ... und {len(all_dev)-25} weitere Bilder")
    print("-"*74)

    if all_dev:
        print(f"\n{'='*60}\n  GESAMTERGEBNIS  ({len(all_dev)} Bilder verglichen)\n{'='*60}")
        print(f"  Durchschnittliche Abweichung:   {np.mean(all_dev):.2f} %")
        print(f"  (im Schnitt weicht jeder Farbwert um {np.mean(all_dev):.2f} % vom")
        print(f"   Original ab - 0 % waere pixelgenau identisch)")
        print(f"\n  Schlechtestes Bild:             {worst[1]:.2f} %  ({worst[0][:40]})")
        print(f"  Im Schnitt sichtbar veraendert: {np.mean(all_vis):.1f} % der Pixel")
        print(f"  (der Rest ist praktisch identisch)")
        if missing: print(f"\n  ACHTUNG: {missing} Bilder fehlten oder hatten falsche Groesse!")
        else:       print(f"\n  Alle {len(all_dev)} Bilder vollstaendig rekonstruiert.")
    else:
        print("Keine vergleichbaren Bildpaare gefunden - stimmen die Ordnerpfade?")


def main():
    ap=argparse.ArgumentParser(description="Stockfoto Video-Kompressor (AV1)")
    sub=ap.add_subparsers(dest="cmd")
    def common(p):
        p.add_argument("--crf",type=int,default=CRF_DEFAULT)
        p.add_argument("--energy",type=float,default=ENERGY_DEFAULT)
        p.add_argument("--order",choices=["greedy","tree","none"],default="greedy",
                       help="Frame-Reihenfolge: greedy=lineare Kette, "
                            "tree=Minimum-Spanning-Tree (kuerzere Pfade), none=Originalreihenfolge")
        p.add_argument("--encoder",choices=["libaom","svt"],default="libaom",
                       help="libaom=kleiner/langsam, svt=SVT-AV1 deutlich schneller "
                            "(Singletons nutzen immer libaom-AVIF)")
        p.add_argument("--speed",type=int,default=None,
                       help="Tempo 0..8 (libaom) bzw 0..12 (svt). Hoeher=schneller/"
                            "groesser. libaom Default 6, schnell=8.")
        p.add_argument("--edge-thr",type=float,default=EDGE_DENSITY_THR,
                       help="Kantenschwelle fuer 4:4:4-Routing (hoeher=seltener 4:4:4). "
                            "Fotos: 3+ ; Grafik/Text: niedriger")
        p.add_argument("--global",dest="global_pool",action="store_true",
                       help="Clustering ueber ALLE Ordner hinweg (findet Beinah-"
                            "Duplikate ordneruebergreifend). Sonst nur pro Ordner.")
        p.add_argument("--lossless",action="store_true",
                       help="Bit-exakt verlustfrei (RGB, lossless=1). Viel groesser, "
                            "aber 0%% Abweichung. Nur libaom, kein SVT.")
    p=sub.add_parser("benchmark"); p.add_argument("--root",required=True); common(p)
    p=sub.add_parser("compress");  p.add_argument("--root",required=True)
    p.add_argument("--out",required=True); common(p)
    p=sub.add_parser("decompress"); p.add_argument("--archive",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--match-original-size",action="store_true",
                   help="Pad decoded PNG files up to their original byte size "
                        "when DCV2 size metadata is available.")
    p=sub.add_parser("vergleich",help="Abweichung Rekonstruktion vs Original in Prozent")
    p.add_argument("--a",required=True,help="Original-Ordner")
    p.add_argument("--b",required=True,help="Rekonstruktions-Ordner")
    a=ap.parse_args()
    # Kantenschwelle ggf. ueberschreiben (Modul-Konstante, von choose_pix_fmt genutzt)
    if hasattr(a,"edge_thr"):
        globals()["EDGE_DENSITY_THR"]=a.edge_thr
    # Tempo ggf. ueberschreiben
    if hasattr(a,"speed") and a.speed is not None:
        globals()["AV1_CPU_USED"]=str(max(0,min(8,a.speed)))
        globals()["SVT_PRESET"]=str(max(0,min(12,a.speed)))
    if a.cmd=="benchmark":
        benchmark(a.root,crf=a.crf,energy=a.energy,order_strategy=a.order,
                  encoder=a.encoder,global_pool=a.global_pool,lossless=a.lossless)
    elif a.cmd=="compress":
        st=pack_archive(a.root,a.out,crf=a.crf,energy=a.energy,order_strategy=a.order,
                        encoder=a.encoder,global_pool=a.global_pool,lossless=a.lossless)
        if st: print(f"Fertig: {st['savings_pct']:+.2f}% "
                     f"({st['original_bytes']/1024/1024:.2f} -> "
                     f"{st['archive_bytes']/1024/1024:.2f} MB)")
    elif a.cmd=="decompress":
        unpack_archive(a.archive,a.out,match_original_size=a.match_original_size)
        print("Fertig.")
    elif a.cmd=="vergleich":
        compare_folders(a.a,a.b)
    else: ap.print_help()

if __name__=="__main__":
    main()
