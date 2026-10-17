# Seliu v9 · Fase 0 — ripartenza

Stato: **in attesa della tua approvazione**.

## 1. Ambiente ricostruito

- Repository: la v8 è sul ramo `seliu-v8`. Il ramo di lavoro v9 (`ccr-b489045a-8o2pzb`) riparte da lì.
- Materiale Drive scaricato in `input/` (non va nel repository). Lo zip v5 è già tutto dentro `engine/` (stessi documenti, stessi strumenti).
- Dati rigenerati da zero con `engine/tools/rebuild_data.sh`, uno script unico e riprendibile che segue il README v8. Ci ho aggiunto Himawari-8, che nel README mancava. Ci sono voluti 1 h 12 min.
- Blender 4.5.3 LTS è installato in `/home/user/blender`. Per ora non serve: il motore resta quello numpy della v8.

## 2. Verifica: un fotogramma della v8 rifatto

Ricetta v8: `SELIU_FMT=16x9 SELIU_LOOK=warm render_v8.py frames … --final --w 1920 --h 1080 --ss 1.0`.
Ho passato il mio PNG nella stessa codifica H.264 della v8 e l'ho confrontato con il video consegnato (immagini in `v9/review/f0/confronto_v8_*.jpg`: v8, rifatto, differenza ×10).

| Fotogramma | PSNR (senza grana: sfocatura 3 px) | Pixel con differenza > 4/255 | Esito |
|---|---|---|---|
| 24,0 s (Seliu) | 51,8 dB | 0,06 % | **identico** (resta solo la grana e la codifica) |
| 7,0 s (voli) | 46,4 dB | 2,4 % | identico, tranne il mare intorno a Belitung |
| 12,0 s (BELITUNG) | 38,2 dB | 26 % | stessa immagine; il mare periferico di Belitung (livello L1, 100 m) ha toni un po' diversi |

- **Suono:** `sound_v8.py --target -16` rifà il mix v8 **bit per bit**.
- **Livello LM (Belitung 15 m):** identico al file di controllo della v8.
- **La differenza a 7–12 s** sta solo nel livello L1. Ho escluso due cause (L1 senza Belitung iniettata; Seliu iniettata dopo), ma non l'ho trovata. Probabilmente la v8 è stata renderizzata con un L1 di una versione intermedia. Non insisto: nella v9 quella zona cambia comunque (punto 10 qui sotto).

## 3. Giudizio sulla v8: verificato, e cause trovate

| Tuo rilievo | Verifica | Causa nel codice |
|---|---|---|
| 0–5 s orbita quasi ferma | Il moto c'è (2,8–4,7 px a fotogramma), ma è solo uno zoom radiale lento: l'inquadratura non cambia. | `timeline_v8.py`: dalla prima alla seconda chiave cambia soprattutto la distanza. Mancano spostamento laterale e rotazione. |
| Nuvole piatte, bordi netti, "neve" a 7–8 s | confermato | Le nuvole Himawari sono un livello piatto a 1–2 km, con soglia dura (`smoothstep`) e luce quasi uniforme. Sono abbastanza bianche da leggersi come neve sulla terra. |
| Macchia tonda in basso al centro | confermata, è il **riflesso speculare del sole**: gaussiana di 7°, +0,032 costante | `render_v8.py` (glint). Nelle immagini Sentinel il riflesso c'è già: qui è doppio e sembra un alone dell'obiettivo. |
| Belitung velata e morbida (10–14 s) | confermata | **Causa principale:** a quell'altezza il motore sceglie L1 (100 m, terre colorate per classi ESA, cioè sintetiche) invece del livello vero LM (Sentinel-2, 15 m). La soglia di `level_weights` scarta LM sopra i ~40 m per pixel, e a 12 s siamo a 140 m. In più c'è la foschia Rayleigh, che sul mare scuro pesa più del mare stesso. |
| Turchese troppo ciano (15–18 s) | confermato | Grade (`cyan_den`, look caldo) uniforme, senza distinguere mare profondo e basso fondale. |
| Grafica da app, finale affollato, scritte piccole | confermato (luogo 36 px, nota 42 px a 1080) | Sistema v6 in `motion_gfx.py`. |
| Suono scuro, mancano gli alti | confermato | Vento filtrato sotto 7 kHz e tono d'orbita a 55 Hz con armoniche. |

## 4. Come procedo (Fase 1)

**Immagine (stessa camera della v8 da 4 s in poi):**
- **7.** Orbita con deriva laterale e rotazione lenta dal primo fotogramma, e discesa che parte entro 2 s. Velocità misurata a schermo, mai a scatti.
- **8.** Nuvole Himawari al doppio del dettaglio (banda rossa a 0,5 km, dato vero), bordi morbidi fisici, luce e ombra dalla quota vera delle cime (infrarosso), base più scura, ombre al suolo. Nessuna nuvola aggiunta.
- **9.** Riflesso del sole quasi tolto.
- **10.** Belitung dal livello vero a 15 m (mipmap), foschia ridotta in quota.
- **11.** Mare graduato per profondità: blu più scuro al largo, turchese solo sui bassi fondali chiari, saturazione più bassa.

**Grafica:** un modulo nuovo, `motion_gfx_v9.py`, con un gesto diverso per ogni ruolo:
- titolo: maschera o luce;
- luogo: dissolvenza;
- nota: tendina.

E inoltre:
- archi in 3D con la coda che svanisce;
- scia della barca sul mare in prospettiva;
- luce che percorre la costa una volta sola;
- finale in tre tempi;
- dimensioni +30 % o più.

Ti porto le direzioni **A** e **B** sugli stessi 4 fotogrammi (voli ~7 s, BELITUNG ~12 s, SELIU ISLAND ~20 s, traversata ~23,5 s), più gli stessi 4 con le correzioni d'immagine.

## 5. Pareri onesti su alcune indicazioni

1. **Direzione B e profondità di campo.** A 5–200 km di distanza un obiettivo vero non sfoca nulla. Se sfoco solo le scritte, sembrano appoggiate su un plastico (effetto tilt-shift). Al posto della profondità di campo userò la foschia della scena (le lettere lontane si velano come il mare) e un'ombra lieve sul mare. Anche così te la mostro.
2. **Direzione B e telefono.** Scritte stese sul mare con la camera inclinata a 60° si schiacciano in verticale di circa la metà. Per restare leggibili devono essere molto grandi nel mondo. Temo che B funzioni bene per SELIU ISLAND e TELUK GEMBIRA e meno per i voli, dove la scala è continentale. Se B ti piace, probabilmente la soluzione migliore è ibrida (B su Seliu, A altrove). Decidi tu guardando.
3. **+30 % sul telefono.** Nel 16:9 visto su un telefono verticale largo 390 px, anche un nome di luogo +30 % (≈47 px a 1080) diventa ~9,5 px. È al limite. Proverò anche +45 % e ti mostro i due a 390 px.
4. **Suoni.** Mixkit è raggiungibile e ha venti d'alta quota veri. Per scaricare i file originali da Freesound (non le anteprime MP3 a 128 kbps) serve un tuo accesso. Per Sonniss GDC mi serve il link al pacchetto (è molto grande). Se non mi dai nessuno dei due, uso Mixkit e ti segno tutto in `audio/FONTI-SUONI.md`.
5. **Nuvole in orbita.** Himawari è l'unica fonte vera di quell'istante e ha 0,5–2 km di dettaglio. Avranno volume e bordi morbidi, ma da 3.000 km non potranno avere il dettaglio di una foto ravvicinata. Inventarlo violerebbe la regola "solo nuvole reali".

## 6. Note tecniche
- Disco: dopo la ricostruzione restano ~15 GB liberi; ho cancellato i file grezzi già consumati (lo script li riscarica).
- Tempi misurati: ~11–17 s a fotogramma a 1080p (4 CPU). 28 s di 16:9 ≈ 2,5–3,5 h; il 9:16 altrettanto. Il 4K (~50 h) non è sostenibile qui.
