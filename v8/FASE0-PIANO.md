# Seliu v8 · Fase 0 — lettura, verifiche e piano

Stato: **in attesa di approvazione** (punto di controllo 1).

## 1. Cosa ho verificato sul riferimento (`preview risultato finale.mp4`)

| Nota | Verifica mia | Esito |
|---|---|---|
| Lampo fra le nuvole 14,6–15,4 s | luminanza media da 85 (15,0 s) a 107 (15,5 s): +26 % in mezzo secondo | **confermato** |
| Belitung "sporca" 12–15 s | terre ESA a 100 m stirate dal mosso, coste a gradini, cave bianche come rumore, nuvole come fiocchi | **confermato** |
| Verde lime su Seliu | la lastra grezza Sentinel-2 (rigenerata) ha un verde naturale e scuro: il lime nasce dal grade (`look.json`: saturazione 1,14, esposizione 2,85) più la "luce" +28 % | **confermato, causa trovata** |
| Audio −16 LUFS, LRA 7 | −16,0 LUFS, LRA 7,0 | confermato |
| "Quasi tutta l'energia sotto i 200 Hz" | 0–200 Hz = 40 %; 200 Hz–2 kHz = **49 %**; 2–8 kHz = 11 %; sopra 8 kHz = 1 % | **diverso**: il suono è scuro e sta proprio nella banda dove andrà la melodia |
| Respiro di 0,2 s a 16,2 s | calo largo da 15,6 a 17,2 s, con il fondo a −34 dB per ~0,6 s | **diverso**: più che un buco breve è un vuoto lungo e indefinito; va comunque ridisegnato |
| Sole del 29/07/2019 | calcolato: elevazione 57,5°, azimut 46° (10:20 locali) | confermato |

**Fatto fisico importante sulle nuvole.** Le nuvole vere del 29/07/2019 intorno a Seliu sono cumuli piccoli di bel tempo:
- dimensione mediana ~40 m, il 90 % sotto i 250 m, la più grande ~2 km²;
- cupole alte al massimo ~110 m, base a ~750 m;
- quasi tutte sul **mare aperto a ovest di Seliu** (10–30 km), più alcune sulla terraferma di Belitung a nord.

Da 40 km di quota sembreranno sempre piccole, perché lo sono. Per vederle "scorrere sotto e poi accanto" la camera deve scendere fra 1,5 e 3 km sopra quel campo di nuvole, cioè sul mare aperto, dove l'ingrandimento dei 10 m non si nota.

## 2. Motore: prova affiancata e tempi misurati

Container: 4 CPU, 15 GB RAM, nessuna GPU.

Stessa camera (inquadratura finale del riferimento, 24,9 s) e stessi dati (lastra L2 rigenerata, DEM Copernicus GLO-30):
`review/f0/ab_motori.jpg` (sopra: finale; sotto: camera bassa a 2 km sul campo di nuvole a ovest, guardando Seliu). Esposizione pareggiata. Nella riga sotto il motore numpy mostra il nero oltre la lastra di Seliu perché per la prova ho caricato solo L2, e perché oggi non ha cielo né orizzonte a bassa quota: è una delle cose da aggiungere.

| | Motore numpy attuale | Blender 4.5.14 LTS, Cycles CPU |
|---|---|---|
| 960×540 | ~2 s | 32 s (senza nuvole), 100 s (con nuvole volumetriche) |
| 1920×1080 | **10 s** | **112 s** senza nuvole · **355 s** con nuvole |
| 3840×2160 | **52 s** | ~4× il 1080p (stima: ~24 min con nuvole) |
| 700 fotogrammi (28 s) | ~2 h a 1080p · ~10 h in 4K (prima dei miglioramenti, che stimo ×1,5–2) | ~22 h senza nuvole, ~69 h con nuvole a 1080p · ~280 h in 4K |

**Cosa ho visto.**
- Sull'inquadratura finale Blender **non dà un salto visibile**: la differenza fra le due immagini è quasi tutta di grade. Il rilievo vero conta poco: su Seliu il DEM è quasi tutto chioma degli alberi (mediana 17 m, massimo 57 m); sulla costa di Belitung arriva a ~340 m, ma da 16 km di distanza si percepisce appena.
- Il vantaggio reale di Blender sono le **nuvole volumetriche con ombre** e il cielo fisico all'orizzonte. Però le nuvole vere sono cumuli piccoli e bassi: una cupola di 100 m con le sue ombre si ottiene in modo credibile anche con un modello "2.5D" a campo di altezze (cupole ombreggiate dal sole vero, con autombra e bordi morbidi) dentro il motore numpy, a una frazione del costo.
- La **profondità di campo** non la userei: a 3–16 km di distanza un obiettivo reale non ha sfocatura, e sfocare fa sembrare il paesaggio un plastico (effetto tilt-shift). È proprio uno degli indizi del "fatto al computer".
- Il 4K in Blender (~7–8 min a fotogramma con le nuvole, cioè centinaia di ore) non è sostenibile qui. Con il motore numpy sì.

**Proposta.** Resto sul motore numpy e lo potenzio (sezione 3). Per il fotogramma chiave "dentro le nuvole" della Fase 2 ti porto due varianti affiancate: nuvole 2.5D numpy e nuvole volumetriche Blender (che userei solo per quei ~3 s, composte sopra il suolo numpy). Decidi tu guardandole.

## 3. Cosa cambierei e perché

1. **Camera (2–12 s): da "mappa che zooma" a velivolo.**
   - Inclinazione fra 35° e 60° per quasi tutta la discesa, con il lembo e poi l'orizzonte nella parte alta dell'inquadratura fino a ~9 s.
   - Rollio da velivolo di 2–4°, legato alle virate, mai rotazioni attorno al centro.
   - Atmosfera fisica: foschia che dipende dalla quota della camera e del suolo (densità esponenziale), cielo all'orizzonte che si scalda scendendo.
   - Accelerazione e frenata misurate in velocità a schermo (curva liscia, controllo automatico degli scatti).
2. **Belitung 12–15 s: dati a 10 m nel corridoio della picchiata.** Composito Sentinel-2 senza nuvole (mediana di più passaggi 2025–2026 della stagione secca) sul quadrante sud-ovest di Belitung, armonizzato con la terraferma di agosto 2026. Le cave restano: le tengo con contrasto locale e saturazione più bassi sul bianco, senza toglierle. Niente mosso stirato sulle terre: il mosso segue la velocità vera della camera.
3. **Nuvole e passaggio (14–18 s): niente velo.** Dopo Belitung la camera scende sul mare aperto a sud-ovest, dove le nuvole c'erano davvero, a ~2,5 km di quota. Le cupole scorrono sotto e di lato, con le ombre sul mare nella direzione del sole vero. Poi una virata ampia, con rollio, che mette Seliu davanti in luce. La luminanza media è controllata fotogramma per fotogramma: nessun salto oltre il 3 % per fotogramma.
4. **Seliu (17–28 s): luce, non saturazione.**
   - Tre quarti da sud-sud-est (Seliu a sinistra, Teluk Gembira a destra, la barca da destra a sinistra come nel brief).
   - Ingrandimento ≤ 1,5× il nativo a 1080p, controllato numericamente sul centro dell'isola.
   - Grade: saturazione dell'isola ≤ 1, verde spostato verso il profondo, sabbia meno bianca (spalla più morbida, +25 % di luce sull'isola e −30 % intorno con il matte). Foschia stratificata davanti e dietro.
   - Deriva finale "da elicottero" di ≥ 4,5 s (orbita lenta di pochi gradi più una lieve spinta), che finisce in un'inquadratura pulita per lo stacco al drone.
5. **9:16.** Stesso volo; dopo Belitung ruota a ovest da Teluk Gembira verso Seliu (come oggi), con le nuvole vere e volumetriche all'orizzonte. Aree sicure verificate sulle lastre vere.
6. **4K.** Lavoro a 3840×2160 se le misure lo confermano (vedi tabella), consegna 2160p e 1080p.

**Ritmo proposto (28 s):**

| s | Atto |
|---|---|
| 0–0,6 | dissolvenza dal nero, camera già in moto |
| 0–4 | orbita: lembo, prima luce |
| 4–10 | regione, SINGAPORE / JAKARTA, archi, *Direct flights*; la camera si piega verso Belitung |
| 10–13,5 | BELITUNG nasce mentre la camera rallenta |
| 13,5–17 | picchiata sul mare a sud-ovest, fra le nuvole vere, virata |
| 17–17,8 | respiro (anche nel suono) |
| 17,8–21 | Seliu nella luce, contorno, SELIU ISLAND |
| 21–23,5 | TELUK GEMBIRA, traversata, *15–20 min by boat* |
| 23,5–28 | respiro finale su Seliu, deriva lenta, uscita |

## 4. Suono: cosa mi serve

- **Freesound:** l'API risponde, ma per scaricare i file originali (WAV/FLAC) serve un account. Con una semplice chiave API si scaricano solo le anteprime MP3 a 128 kbps, che non bastano per un master. Mi servono una chiave API ("client credentials") e un accesso OAuth: ti do io un link, tu accedi e mi incolli il codice.
- Uso anche Mixkit (raggiungibile) e, se mi dai il link, il Sonniss GDC bundle (è molto grande: scarico solo i file scelti, se il pacchetto lo permette).

## 5. Repository

Questa sessione **non ha un repository GitHub collegato**: i commit restano solo nel container, che non è permanente. Crea un repository vuoto (es. `seliu-apertura-v8`), assicurati che GitHub sia collegato su https://claude.ai/connect-github con l'app Claude installata su quel repository, e dimmi il nome: lo collego e ci spingo tutto.
