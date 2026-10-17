# Seliu Island · apertura v9 (28 s, 16:9 1080p)

È l'apertura del video per Compass Rose Indonesia: un'unica camera fisica che dall'orbita arriva su Seliu, passando per i voli diretti da Singapore e Jakarta, Belitung, la picchiata fra le nuvole vere del 29-07-2019 e infine la traversata da Teluk Gembira. Le immagini sono tutte vere (Sentinel-2, Himawari-8, catalogo stellare Yale): niente AI e niente Google Earth.

## Consegne (`v9/`)

| File | Cosa |
|---|---|
| `seliu-apertura-v9-16x9-1080p.mp4` | finale con le scritte (grafica A), ambiente −16 LUFS |
| `seliu-apertura-v9-16x9-1080p-pulita.mp4` | stessa immagine senza scritte né grafica |
| `seliu-apertura-v9-16x9-1080p-RAW-10bit.mov` | lastra RAW: niente grade, grana o scritte; HEVC 10 bit 4:4:4 per la correzione colore |
| `seliu-apertura-v9-16x9-1080p-con-intro.mp4` | 33,6 s: intro del marchio (5,6 s) + l'apertura, ambiente −16 LUFS |
| `audio/seliu-v9-ambiente-web_-16LUFS.wav` | ambiente da solo, per il web |
| `audio/seliu-v9-ambiente-letto-musica_-20LUFS.wav` | ambiente a −20 LUFS, come letto sotto la musica |
| `audio/stem/` | 9 stem (48 kHz, 24 bit), alla stessa scala del mix a −20 |
| `audio/seliu-v9-con-intro-ambiente-web.wav` | suono della versione con l'intro |
| `audio/BRIEF-MUSICA.md`, `audio/FONTI-SUONI.md` | brief per la musica e fonti dei suoni |
| `TITOLI-DI-CODA.txt` | crediti dei dati, dei suoni e del carattere |
| `review/f3/` | contact sheet, fotogrammi a misura di telefono |
| `FASE0.md`–`FASE2.md`, `INTRO-PIANO.md`, `STATO.md` | percorso, decisioni, stato |

## Codice (`engine/tools/`)

| File | Cosa fa |
|---|---|
| `render_v9.py` | motore |
| `timeline_v9.py` | camera |
| `grade_v9.py` | colore |
| `motion_gfx_v9.py` | grafica |
| `sound_v9.py` | ambiente |
| `intro_v9.py`, `sound_intro_v9.py` | intro del marchio |
| `rebuild_data.sh` | rigenera tutti i dati, che non sono nel repository |
| `fix_l0_seam.py` | toglie una giuntura del mosaico su Sumatra |

## Comandi

```bash
cd engine && bash tools/rebuild_data.sh && python3 tools/fix_l0_seam.py
SELIU_FMT=16x9 SELIU_LOOK=warm SELIU_GFX=A python3 tools/render_v9.py frames ../frames/v9_16x9 --final \
  --clean_dir ../frames/v9_16x9_clean --raw_dir ../frames/v9_16x9_raw --w 1920 --h 1080 --ss 1.25 --workers 3
python3 tools/sound_v9.py ../frames/snd --fmt 16x9 --target -16      # (e --target -20 per letto e stem)
# intro: i primi fotogrammi del volo senza dissolvenza, poi l'intro
SELIU_NOFADE=1 SELIU_FMT=16x9 SELIU_LOOK=warm SELIU_GFX=A python3 tools/render_v9.py frames ../frames/v9_16x9_nofade --final --from_ 0 --to 1.0 --workers 3
INTRO_WORKERS=3 python3 tools/intro_v9.py ../frames/intro ../frames/v9_16x9_nofade
python3 tools/sound_intro_v9.py ../v9/audio/seliu-v9-ambiente-web_-16LUFS.wav ../v9/audio/seliu-v9-con-intro-ambiente-web.wav --tail_fade 0.01
```

Tempi su questa macchina (3 processi): ~3 h per i 700 fotogrammi, ~40 min per l'intro.
