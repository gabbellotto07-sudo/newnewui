# Seliu Island — apertura v8 (28 s)

Un'unica camera fisica: un satellite che diventa un aereo, poi un elicottero. Dall'orbita alla regione (voli diretti da Singapore e Jakarta), poi Belitung, la picchiata fra le nuvole vere del 29-07-2019 e Seliu in luce, con la traversata da Teluk Gembira.

## Struttura del repository (ramo `seliu-v8`)

| Cartella | Contenuto |
|---|---|
| `engine/tools/` | motore Python: dati, renderer v8, grade, grafica, suono, controlli |
| `engine/docs/` | documentazione v5/v6 (bibbia, fonti, diario, direzione grafica) |
| `engine/fonts/` | Jost (OFL) |
| `v8/` | consegne, documenti di fase, audio, contact sheet |
| `review/` | prove e fotogrammi delle fasi (JPG/MP4 leggeri) |

I dati (`data/`) e le sequenze di fotogrammi (`frames/`) **non sono nel repository**: si rigenerano.

## Rifarla da zero nel cloud (Linux, Python 3.11+, ~30 GB di disco, 15 GB di RAM)

```bash
pip install rasterio pyproj mgrs opencv-python-headless scipy numpy pillow soundfile pyloudnorm OpenEXR
cd engine && ln -s ../data data && mkdir -p ../data review
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR CPL_VSIL_CURL_ALLOWED_EXTENSIONS=.tif

# 1. Seliu (L2, 10 m): mare 29-07-2019 pulito, terra agosto 2026 (README v5, passo 2)
for s in S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MYB_20190818_0_L2A S2B_48MZB_20190818_0_L2A \
         S2B_48MYB_20240712_0_L2A S2B_48MYB_20230618_0_L2A S2A_48MYB_20260808_0_L2A S2C_48MYB_20260826_0_L2A \
         S2B_48MYB_20260801_0_L2A S2C_48MYB_20250702_0_L2A; do python3 tools/fetch_s2.py L2 $s; done
python3 tools/composite.py L2 data/L2_comp.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MYB_20190818_0_L2A S2B_48MZB_20190818_0_L2A S2B_48MYB_20240712_0_L2A S2B_48MYB_20230618_0_L2A
cp data/L2_comp.npy data/L2_comp_2019land.npy
python3 tools/land_update.py S2A_48MYB_20260808_0_L2A S2C_48MYB_20260826_0_L2A S2B_48MYB_20260801_0_L2A S2C_48MYB_20250702_0_L2A S2B_48MYB_20240712_0_L2A
python3 tools/make_light.py
python3 tools/extract_clouds.py L2 data/L2_comp_2019land.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A
python3 tools/make_outline.py

# 2. livelli larghi LG / L0 / L1 (resumable)
tools/fetch_all_v5.sh

# 3. Belitung (LM, 15 m) e rilievo (Copernicus GLO-30)
for d in "20190729 S2B" "20260808 S2A" "20260801 S2B" "20260806 S2C" "20260811 S2B" "20260826 S2C" "20260920 S2B" "20260722 S2B" "20260622 S2B"; do
  set -- $d; python3 tools/fetch_lm.py $1 $2; done
python3 tools/fetch_cop.py L2; python3 tools/fetch_cop.py LM
python3 tools/build_lm.py 20190729 20260808 20260801 20260806 20260811 20260826 20260920 20260722 20260622
# coerenza fra i livelli (esatta per qualsiasi rapporto di scala)
python3 tools/build_level.py L0; python3 tools/build_level.py LG
python3 tools/inject_v8.py LM L1; python3 tools/inject_v8.py L1 L0; python3 tools/inject_v8.py L0 LG

# 4. render (riprende da dove si era fermato), suono, montaggio
python3 tools/render_v8.py frames ../frames/v8_16x9 --final --w 3840 --h 2160 --ss 1.0 --shard 0/2   # e 1/2 in parallelo
SELIU_FMT=9x16 python3 tools/render_v8.py frames ../frames/v8_9x16 --final --w 1080 --h 1920
python3 tools/sound_v8.py ../v8/audio/stems --fmt 16x9
```

## Dove si cambia cosa

| Cosa | File |
|---|---|
| Percorso della camera, durata, luce su Seliu, calore del colore | `engine/tools/timeline_v8.py` (tabella `KEYS`, 16:9 e 9:16) |
| Tempi delle scritte, delle linee e del contorno | `engine/tools/motion_gfx_v8.py` (dizionario `T`) |
| Testi, dimensioni, gesti della grafica | `engine/tools/motion_gfx.py` (sistema tipografico v6, `docs/05-direzione-grafica.md`) |
| Colore | `engine/tools/grade_v8.py` (sopra `grade_cine.py`) |
| Atmosfera, nuvole, rilievo, livelli | `engine/tools/render_v8.py` (costanti in testa al file) |
| Suono | `engine/tools/sound_v8.py`, fonti in `v8/audio/FONTI-SUONI.md` |
| Luoghi e coordinate | `engine/tools/geo.py` |

Controlli rapidi: `python3 tools/cam_check.py` (posizione dei luoghi a schermo e velocità, senza render), `python3 tools/kf_test.py OUT.jpg t1 t2 …` (fotogrammi graduati a 960 px), `python3 tools/audio_check.py MIX.wav PREFISSO` (loudness, mono, telefono, spettrogramma).
