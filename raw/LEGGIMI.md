# Seliu Island · materiale RAW v9 (16:9, 1080p, 25 fps)

Il video è una discesa continua dall'orbita a Seliu. Non ci sono scritte, linee né grana. Durata 41 s (1025 fotogrammi): rispetto all'apertura di 28 s ci sono 3 s in più all'inizio e 10 s di deriva lenta finale su Seliu.

**Perché 1080p e non 4K:** il 4K avrebbe richiesto circa 4 volte il tempo di render, oltre il limite di 3 ore. Il motore produce anche il 4K; servono circa 6 h su questa macchina.

## File

| File | Contenuto |
|---|---|
| `seliu-v9-raw-16x9-1080p-colore-prores422hq.mov` | colore finale (grade v9) |
| `seliu-v9-raw-16x9-1080p-flat-prores422hq.mov` | "flat": nessun grade, grana o vignetta; sorgente a 16 bit |
| `seliu-v9-raw-16x9-1080p-anteprima.mp4` | anteprima H.264 del colore, con il mix |
| `seliu-v9-raw-16x9-1080p-flat-anteprima.mp4` | anteprima H.264 del flat |
| `seliu-v9-raw-spazio-10s-1080p-prores422hq.mov` | lastra di spazio senza Terra, 10 s (vedi sotto) |
| `seliu-v9-raw-grafica-voli-prores4444-alpha.mov` | archi dei voli |
| `seliu-v9-raw-grafica-scia-prores4444-alpha.mov` | scia della barca |
| `seliu-v9-raw-grafica-costa-prores4444-alpha.mov` | luce sulla costa di Seliu |
| `tracking-16x9-1080p.csv` | posizione in pixel dei luoghi, per fotogramma |
| `audio/mix.wav` | mix: −20 LUFS, picco ≤ −1 dBTP, spazio per la musica |
| `audio/ambiente.wav`, `audio/effetti.wav` | le due tracce separate (ambiente + effetti = mix prima del limiter) |
| `audio/stem/` | le singole registrazioni |
| `verifica/` | contact sheet a 1 fps, grafico della nitidezza per fotogramma e i suoi dati |
| `TITOLI-DI-CODA.txt` | crediti |

**Formati:**
- **Video:** ProRes 422 HQ 10 bit, Rec.709. Fotogramma 0 = 0,00 s.
- **Grafiche:** ProRes 4444 con alfa dritto, durata intera (1025 fotogrammi, trasparenti quando non c'è niente), da sovrapporre a 0,00 s. Sono indipendenti dal video: si possono rifare a mano usando il tracking.
- **Audio:** WAV 48 kHz / 24 bit, 41 s, allineato a 0,00 s.

**Lastra di spazio:** è identica al primo fotogramma del video, fissa per 10 s. Stesso cielo #0B1222 e stesse stelle. Messa prima del video (o dissolta nel video) non dà stacchi: la camera parte da ferma.

## Tempi chiave (secondi dall'inizio del video)

| Tempo | Cosa |
|---|---|
| 0,0 | stelle; la camera è ferma e comincia ad abbassarsi lentamente |
| 1,2 | la Terra entra dal basso (movimento continuo, nessuna frusta) |
| 3,0 | la camera finisce di inclinarsi; da qui è l'apertura di 28 s, spostata di +3 s |
| 7,0–8,0 | partono gli archi Singapore → arrivo e Jakarta → arrivo (spariscono entro 11 s) |
| 13,3 | Belitung al centro, la camera quasi ferma (era il titolo BELITUNG) |
| 15,4 | inizio della picchiata |
| 20,8 | fine della picchiata, fuori dalle nuvole: Seliu davanti |
| 20,85–23,25 | la luce percorre la costa di Seliu (poi resta come bagliore) |
| 21,45 | momento per il titolo SELIU ISLAND |
| 23,55 | momento per TELUK GEMBIRA |
| 24,15–26,95 | la scia della barca, che si spegne fra 27,4 e 30,7 |
| 31,0–41,0 | deriva lenta su Seliu, mai ferma |

Teluk Gembira esce dal quadro a destra verso 36,5 s durante la deriva (si vede nel CSV).

## Tracking (`tracking-16x9-1080p.csv`)

Le colonne sono `frame`, `time_s`, poi per ogni luogo `_x`, `_y` (px su 1920×1080, origine in alto a sinistra), `_vis` e `_dist_km` (distanza dalla camera).

- `_vis` vale 1 quando il punto è davanti alla camera, non nascosto dalla Terra e dentro il quadro.
- Le coordinate fuori dal quadro restano valide, utili per gli ingressi.

| Luogo | Coordinate |
|---|---|
| Singapore (Changi) | 1.3644, 103.9915 |
| Jakarta (CGK) | −6.1256, 106.6559 |
| aeroporto di arrivo (Tanjung Pandan) | −2.7455, 107.7546 |
| Belitung (centro) | −2.86, 107.93 |
| Teluk Gembira | −3.1973, 107.5857 |
| pontile di Seliu | −3.1994, 107.5449 |
| centro di Seliu | baricentro del contorno vero, −3.2220, 107.5299 |

## Cosa è cambiato nell'immagine rispetto alla v9

1. **Cambio di livello di dettaglio (~14 s):**
   - nessuna soglia: ogni pixel campiona sempre il livello più dettagliato che lo copre, con mipmap trilineare;
   - i livelli si incontrano solo nello spazio, ai bordi sfumati. Lì i colori del livello fine sono tarati su quello più grossolano (`harmonize` in `render_v9.py`).
2. **Mosso:** segue sempre la velocità reale della camera, senza soglia (prima si spegneva sotto 0,75 px, a ~23 s). **Profondità di campo:** non è mai stata usata nel motore, quindi non ci sono cambi.
3. **Nuvole:**
   - Himawari (regione, 4–12 s): più leggere e con bordi più morbidi;
   - cumuli Sentinel-2: disegnati in volume solo dove sono più grandi di un pixel. Quando sono più piccoli del pixel resta solo un velo debole e morbido: niente macchie né strisce "di neve";
   - solo nuvole reali, nessuna aggiunta.
4. **Fiocchi ai bordi del quadro su Belitung:** erano cumuli lontani disegnati come cupole sotto la risoluzione del pixel. Spariscono con il punto 3.
5. **Belitung (8–17 s), coerente con il globo:**
   - **Colore:** visti da lontano, i riquadri più dettagliati (Belitung a 15 m, la regione a 100 m) prendono i toni a grande scala del globo, con la catena di tarature LG ← L0 ← L1 ← LM ← L2. Passano ai loro colori veri solo avvicinandosi (dettaglio a terra da 300 a 25 m per pixel), quindi in modo continuo.
   - **Nitidezza:** il passaggio fra i livelli non segue più i lati del riquadro. È una zona larga, arrotondata e irregolare (una "macchia"), dove il dettaglio scende pian piano fino a quello del livello esterno: nessuna linea dritta, nessun quadrato.
   - **Mare aperto:** da lontano la sua trama fine (onde, riflessi) è limitata alla risoluzione del livello esterno e torna piena solo da vicino. Così non c'è un anello più dettagliato intorno a Belitung.
   - **Luminosità:** il mare intorno a Belitung non si scurisce più (stessa luminosità media da 12,5 a 15,5 s). Il velo blu-viola è tolto solo in parte, per non spegnere il blu.
6. **Cielo:** nero-blu #0B1222 uguale in tutto il video. Le stelle reali (Yale Bright Star Catalogue, magnitudine < 4, posizioni del 29-07-2019 03:20 UTC) restano sempre, discrete. Nella versione a colori il cielo non viene toccato dal grade.
7. **Ingresso della Terra:** 3 s in più all'inizio. La camera parte guardando sopra la Terra e si abbassa con una curva morbida, senza accelerazioni brusche, fino al primo fotogramma della vecchia apertura.

## Rifare il render

```bash
cd engine
SELIU_FMT=16x9 SELIU_LOOK=warm SELIU_GFX=A python3 tools/render_v9.py frames ../frames/raw/x --raw_out ../frames/raw \
  --from_ -3 --to 38 --w 1920 --h 1080 --ss 1.0 --workers 4
python3 tools/raw_tracking.py ../raw/tracking-16x9-1080p.csv
python3 tools/sound_v9.py ../frames/snd --fmt 16x9 --target -20 && python3 tools/raw_audio.py ../frames/snd ../raw/audio
```

Per il 4K: `--w 3840 --h 2160` e `python3 tools/raw_tracking.py OUT.csv 3840 2160`.

## Verifica (`verifica/`)

- **Contact sheet a 1 fps:** nessun salto di colore o di luce fra i livelli.
- **Nitidezza per fotogramma** (|Laplaciano| medio della luminanza, al centro e in una griglia 4×4).
- **Con la Terra in quadro (dopo 4 s)**, il cambio tipico da un fotogramma all'altro è dello 0,4 %.
- **Intorno al vecchio punto del pop (~17 s qui):** nessun gradino.
- **Dove si spegneva il mosso (~26 s qui):** al massimo il 2 %.
- **L'unico picco** (fino al 24 %) è a 18,8–19,1 s, nella cella in basso a sinistra: durante la picchiata sopra il campo di cumuli veri, nuvole e ombre attraversano la cella in pochi fotogrammi. È un cambio di contenuto e non di livello: al centro, nello stesso momento, il cambio è del 5–6 %.
- **I salti molto grandi prima dei 4 s** sono l'ingresso della Terra nelle celle che prima erano solo cielo.
