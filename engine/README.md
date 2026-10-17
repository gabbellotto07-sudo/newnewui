# Seliu Island — Apertura v5 (materiale per rifarla)

25 secondi, una sola discesa continua: dall'orbita alla regione (voli diretti da Singapore e Jakarta), poi Belitung, poi Seliu e la traversata da Teluk Gembira.

## Consegna
**v6: versione finita del gruppo (15-10-2026)**
- `delivery/v6/seliu-apertura-v6-16x9.mp4` (master, 1920×1080, 25 s, −16 LUFS) e `-web.mp4` (32 MB). Verticale: `seliu-apertura-v6-9x16.mp4` (1080×1920, mix con stereo ristretto per il telefono).
- Contenuto: grade cinematografico; testi animati lettera per lettera; archi dei voli con testa a cometa; contorno di Seliu che si disegna lungo la costa vera e passa la mano alla luce; traversata animata; 28 effetti sonori della grafica sopra l'ambiente.
- Decisioni grafiche: di uno specialista indipendente, documentate in `docs/05-direzione-grafica.md`. Catena: `tools/gfx_comp.py` (RAW → `grade_cine.py` → `motion_gfx.py` → grana); tempi modificabili da un solo punto, il dizionario `T` in `motion_gfx.py`.

**RAW: libreria per montare altre versioni**: `delivery/raw/` (guida: `delivery/raw/LEGGIMI_PER_CLAUDE.md`)
- `shots/`: 9 riprese lente da 10 s, 2560×1440, ProRes + mp4 + matte della luce su Seliu + tracking CSV.
- `descent/`: la discesa continua di 25 s senza testo, con tracking.
- `plates/`: lastre a 16 bit di 4 scale, georeferenziate, con nuvole come alfa, maschere e coordinate dei luoghi in pixel.
- `audio_stems/`: mix, 10 tracce separate, 2 tappeti da 60 s.

**v5 (riferimento)**: `delivery/reference/seliu-apertura-v5-16x9-con-testo.mp4`.
**Documenti**: `docs/`, cioè bibbia di produzione, fonti e dati (**titoli di coda**), diario delle revisioni, direzione grafica, testi per `_sync` e per il documento di progetto.

## Rifarla da zero (Linux, Python 3.11+)
```bash
pip install rasterio pyproj mgrs opencv-python-headless scipy numpy pillow soundfile pyloudnorm
export GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
# 1. dati (Sentinel-2 e ESA WorldCover da AWS S3 pubblico, batimetria AWS Terrain Tiles)
python3 tools/fetch_dem.py LG 6; python3 tools/fetch_dem.py L0 8; python3 tools/fetch_dem.py L1 11; python3 tools/fetch_dem.py L2 13
python3 tools/fetch_esa.py LG; python3 tools/fetch_esa.py L0; python3 tools/fetch_esa.py L1
for s in S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MYB_20190818_0_L2A S2B_48MZB_20190818_0_L2A \
         S2B_48MYB_20240712_0_L2A S2B_48MYB_20230618_0_L2A S2A_48MYB_20260808_0_L2A S2C_48MYB_20260826_0_L2A \
         S2B_48MYB_20260801_0_L2A S2C_48MYB_20250702_0_L2A; do python3 tools/fetch_s2.py L2 $s; done
for s in S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MZC_20190729_0_L2A S2B_48MYC_20190729_0_L2A; do python3 tools/fetch_s2.py L1 $s; done
# 2. livello Seliu: mare del 2019 pulito dalle nuvole (clean plate in tools/cleanplate_L2.json), terra di agosto 2026
python3 tools/composite.py L2 data/L2_comp.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MYB_20190818_0_L2A S2B_48MZB_20190818_0_L2A S2B_48MYB_20240712_0_L2A S2B_48MYB_20230618_0_L2A
cp data/L2_comp.npy data/L2_comp_2019land.npy
python3 tools/land_update.py S2A_48MYB_20260808_0_L2A S2C_48MYB_20260826_0_L2A S2B_48MYB_20260801_0_L2A S2C_48MYB_20250702_0_L2A S2B_48MYB_20240712_0_L2A
python3 tools/make_light.py            # maschera della luce su Seliu
# 3. livelli larghi, nuvole 3D, coerenza fra livelli
python3 tools/build_level.py L1 S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MZC_20190729_0_L2A S2B_48MYC_20190729_0_L2A
python3 tools/build_level.py L0; python3 tools/build_level.py LG
python3 tools/extract_clouds.py L2 data/L2_comp_2019land.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A
python3 tools/extract_clouds.py L1 data/L1_tex.npy S2B_48MYB_20190729_1_L2A S2B_48MZB_20190729_0_L2A S2B_48MZC_20190729_0_L2A S2B_48MYC_20190729_0_L2A
python3 tools/inject.py L2 L1; python3 tools/inject.py L1 L0; python3 tools/inject.py L0 LG
# 4. render, suono, montaggio
tools/render_clean.sh        # RAW senza testo (tools/render_all.sh = versione con scritte)
(cd tools && python3 sound.py ../audio/sfx_v5.wav)
tools/encode.sh
```

## Dove cambiare cosa
| Cosa | File |
|---|---|
| Percorso della camera, tempi, durata | `tools/timeline.py` (16:9 e 9:16) |
| Scritte, dimensioni, tempi di entrata | `tools/overlay.py` |
| Look (esposizione, contrasto, foschia, vignetta) | `tools/look.json` |
| Luce su Seliu, nuvole, ombre, sole | `tools/render.py` |
| Luoghi e coordinate | `tools/geo.py` |
| Suono | `tools/sound.py` |

Anteprima rapida: `python3 tools/render.py stills out/ 5.6 11 23 --w 960 --h 540 --ss 1`
(per il verticale: `SELIU_FMT=9x16 ... --w 540 --h 960`).
