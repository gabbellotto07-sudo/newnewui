# Seliu v8 — stato (16-10-2026)

## Fatto
- **Dati rigenerati** da fonti pubbliche: LG, L0, L1, L2 (Seliu 10 m: mare 29-07-2019, terra agosto 2026) e il nuovo **LM** (Belitung intera, 15 m: terra e mare dalla mediana dei passaggi Sentinel-2 limpidi giugno–settembre 2026). Rilievo **Copernicus GLO-30**. Nuvole vere: cumuli del 29-07-2019 (Sentinel-2) vicino a Seliu, e **Himawari-8 del 29-07-2019 03:20 UTC** (stesso istante) per l'orbita e la regione, alla quota vera ricavata dall'infrarosso termico.
- **Motore v8** (`engine/tools/render_v8.py`): globo vero, 5 livelli senza stacchi, atmosfera fisica (Rayleigh + Mie, foschia che cambia con la quota), orizzonte e lembo, rilievo, cumuli 2.5D con ombre sotto il sole vero (elev. 57,5°, az. 46°), riflesso del sole sul mare, mosso dal movimento reale della camera, rollio da velivolo.
- **Camera** (`timeline_v8.py`): 28 s, discesa continua; la camera si ferma sotto il titolo BELITUNG, picchiata sopra il campo di cumuli a sud-ovest di Seliu, tre quarti finale da sud-sud-est con deriva da elicottero fino all'ultimo fotogramma (mai ferma).
- **Colore** (`grade_v8.py`): look "B caldo" scelto; verde naturale (niente lime), sabbia e cave con spalla morbida (cave tenute, non tolte), niente tinte lavanda, luce su Seliu +34 % / −38 % intorno.
- **Grafica**: sistema v6 invariato (Jost, #FFF7E8), tempi riallineati a 28 s in `motion_gfx_v8.py`.
- **Suono** (`sound_v8.py`): registrazioni vere Mixkit (vento d'alta quota, vento della discesa che segue la velocità reale della camera, aria sulle nuvole, respiro di ~0,85 s prima di Seliu, mare e risacca in stereo largo, brezza, fuoribordo lontano da destra a sinistra), tocchi di carta/aria sotto la grafica. Mix: **−16 LUFS, −1,2 dBTP, LRA 6,5**, mono −1 LU, telefono (300 Hz–8 kHz) −4 LU.
- **Consegnato**: `v8/seliu-apertura-v8-16x9-1080p.mp4` (1920×1080, 25 fps), versione pulita senza scritte, mix e stem in `v8/audio/`.

## Decisioni prese in autonomia (da confermare)
1. Look **B caldo** per l'arrivo (preferito anche dalla revisione indipendente).
2. Nuvole regionali **Himawari-8** dello stesso istante (sono nuvole vere della scena; nessuna nuvola inventata). Licenza JMA da verificare.
3. Nuvole sopra la **terraferma** di Belitung tolte (permesso: solo rimozione); restano i cumuli sul mare.
4. Mare di Belitung (LM) dalla mediana 2026 invece che dal 29-07-2019 (quel giorno il mare a ovest era pieno di cumuli); intorno a Seliu resta il mare limpido del 2019.
5. Motore numpy invece di Blender (confronto in `review/f2/keyframes/CONFRONTO_KF4_…`): ~50× più veloce, resa paragonabile.
6. Profondità di campo non usata (a 5–20 km farebbe effetto plastico).
7. Mosso: calcolato dal movimento reale della camera sul fotogramma finito (un render per fotogramma) per stare nei tempi.

## Aperto
- **9:16**: non renderizzato. La camera verticale è già in `timeline_v8.py` (SELIU_FMT=9x16); servono gli strumenti per rifarlo in un'altra sessione (rigenerare i dati: ~2–3 h; render ~3 h).
- **4K**: non fatto (≈100 s a fotogramma: ~50 h per i 28 s). Consegna solo 1080p.
- **Musica**: da scegliere (brief in `v8/audio/BRIEF-MUSICA.md`); poi mix finale −14/−16 LUFS.
- **Pontile di Seliu**: la testa del molo vera è ~52 m a est del punto in tabella (`v8/VERIFICA-DATI.md`); la rotta usa ancora il punto in tabella.
- Il suono **va ascoltato in cuffia** da una persona prima della pubblicazione.
- Licenze: Mixkit SFX Free License e Himawari-8 (JMA) da verificare.
