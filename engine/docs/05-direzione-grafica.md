# Seliu v6 — Direzione grafica, colore e suono della grafica

Responsabile indipendente di titoli, linee, color grading e SFX della grafica. Questo documento spiega cosa ho deciso e perché. Il codice è in `tools/`. Le prove sono in `review/gfx/`.

## 0. Come si usa (catena di composizione)
```
RAW (frames/raw_16x9/fNNNNN.png + .json camera)
  → grade_cine.grade(img, t)               # look cinematografico
  → motion_gfx.draw(img, t, cam, fmt)      # testi, punti, archi, rotta, contorno di Seliu
  → × fade(t)                              # nero iniziale 0,05–1,0 s (come timeline.fade)
  → grade_cine.finish(img, seed=frame)     # grana e dither, uint8
```
- `tools/gfx_comp.py` esegue l'intera catena: `python3 tools/gfx_comp.py frames OUT --fmt 16x9` per la sequenza, `stills OUT t1 t2 … --sheet` per le prove.
- La camera si ricostruisce dal JSON del fotogramma con `render.Camera(...)`.
- Tempi misurati a 1080p su macchina carica: grade 0,5–0,9 s, grafica 0,2–0,65 s, grana 0,2 s.
- Il contorno viene da `tools/make_outline.py` → `data/seliu_outline_lonlat.json`.

## 1. Principi
1. **Il film prima della mappa.** La grafica è luce sul territorio, mai un'interfaccia. Non ci sono riquadri, icone, scala, bussola, legende o crediti a schermo, e l'aeroporto non è mai nominato.
2. **Ogni elemento è ancorato a un luogo vero.** Tutto passa da `cam.project(ecef(lat, lon))`, quindi la grafica si muove con la camera reale delle lastre.
3. **Una sola famiglia di gesti.** Ogni cosa nasce con decelerazione morbida (out-cubic/expo) e muore dissolvendosi con sfocatura. Non ci sono rimbalzi, overshoot o scale-pop: sarebbero linguaggio da Instagram.
4. **Solo i dati approvati.** I testi a schermo sono esattamente: SINGAPORE, JAKARTA, *Direct flights*, BELITUNG, BANGKA BELITUNG ISLANDS · INDONESIA, TELUK GEMBIRA, *15–20 min by boat*, SELIU ISLAND, OFF THE SOUTH-WEST COAST OF BELITUNG. Non compaiono altri numeri.

## 2. Sistema tipografico
Il carattere è uno solo, **Jost** (OFL, già del brand), e la gerarchia si costruisce con il peso variabile. Non ho aggiunto un secondo font: un serif corsivo avrebbe aggiunto "lusso", ma su un telefono i corsivi serif sottili si rompono, e la coerenza con il brand pesa di più.

| Ruolo | Esempio | px (base 1080) | Peso | Tracking | Animazione |
|---|---|---|---|---|---|
| Titolo | BELITUNG, SELIU ISLAND | **96** | 360 | 0,40 em (entra da 0,56) | lettere |
| Sottotitolo | BANGKA BELITUNG ISLANDS · INDONESIA | **34** | 500 | 0,18 em | tendina dal centro |
| Luogo | SINGAPORE, JAKARTA, TELUK GEMBIRA | **36** | 500 | 0,20 em | lettere da sinistra |
| Nota | *Direct flights*, *15–20 min by boat* | **42** | 400 corsivo | 0,02 em | tendina morbida |

- **Inchiostro.** Bianco caldo #FFF7E8.
- **Leggibilità senza riquadri.**
  - Ombra morbida (σ 3,2 px, spostata di 1,5 px verso il basso).
  - Seconda ombra larga molto tenue.
  - Sotto i titoli, una "foschia" scura (scrim) quasi invisibile, che sui reef chiari dà contrasto.
  - Il bagliore caldo dei titoli è appena percettibile.
- **Crenatura.** Le avanzate tengono conto delle coppie di lettere (`getlength` a coppie).
- **Area sicura.** 5 % / 7 % in 16:9. In 9:16 è 7 % ai lati, 12 % in alto e 14 % in basso, per lasciare spazio all'interfaccia del telefono.
- **Testi troppo lunghi.** Si riducono in proporzione e non escono mai dall'inquadratura.

## 3. Animazione dei testi
- **Lettere (titoli e luoghi).** Ogni lettera ha la sua curva:
  - opacità con out-cubic;
  - sfocatura da 0,11 em a 0 con out-quart;
  - risalita di 0,14 em con out-expo.
- **Sfasamento.** 0,55 s distribuiti dal centro verso l'esterno per i titoli, da sinistra a destra per i luoghi. Il tracking si stringe da +0,16 em al valore nominale in 2,2 s (out-expo). Nei titoli continua poi una deriva quasi impercettibile (+0,004 em/s), così il titolo "respira" e non è mai fermo come in una slide.
- **Uscita.** Le lettere sfumano a ritroso con sfocatura crescente, una leggera risalita e il tracking che si allarga (+0,08 em).
- **Tendina (note e sottotitoli).** Una maschera con il bordo morbido (35 % della larghezza) scorre dal centro o da destra a sinistra. *15–20 min by boat* si apre da destra a sinistra, nella direzione della barca.
- **Parallasse.** I titoli sono su un "piano" più vicino all'obiettivo:
  - BELITUNG si muove al 45 % del movimento del suolo, a metà fra l'isola e il centro dell'inquadratura;
  - SELIU ISLAND si muove al 75 % e resta agganciato alla costa nord dell'isola.
- **Mosso di movimento.** Ogni blocco di testo riceve un mosso direzionale pari al suo spostamento a schermo in 1/50 s (otturatore a 180°), misurato dalla camera della timeline.

## 4. Linee, punti, rotta
- **Punti.** Crescono in 0,45 s (out-cubic) con un unico anello sottile (1,3 px) che si allarga 5 volte e si spegne in 1 s, come un "ping" discreto. C'è un alone caldo.
- **Archi dei voli.** Sono gli stessi cerchi massimi sollevati della v5. Su questi:
  - **disegno** in 2,8 s in-out cubic, come un aereo: accelera, crociera, si posa;
  - **scia** più luminosa vicino alla testa (+38 %), che si calma su un tratto di base;
  - **testa a cometa**: punto pieno, una breve striscia luminosa (il suo mosso) e un bagliore dorato;
  - **uscita** (8,2–9,3 s): la linea si cancella **dall'origine verso Belitung**. Il movimento scorre dentro l'isola e accompagna la picchiata.
- **Rotta in barca.** È la curva dolce sul mare aperto della v5 (indicativa) fra i due pontili veri:
  - disegno in-out sine in 2,6 s, la velocità costante di una barca;
  - testa luminosa con scia;
  - punto d'arrivo al pontile del villaggio.

## 5. Il contorno di Seliu (richiesta del cliente)
- **Dato.** È la costa reale estratta dalla maschera terra di `L2_comp.npy` (Sentinel-2 10 m, terraferma agosto 2026), cioè la componente connessa che contiene (riga 3250, colonna 3090), con i buchi riempiti. Il contorno è sub-pixel (×4, livello 0,5), lisciato a 25 m e ricampionato a 12 m.
  - Il risultato ha 1.703 punti, un perimetro di 20,4 km e un'area di 16,7 km².
  - È stato verificato sovrapponendolo all'immagine: segue il bordo vegetazione/spiaggia.
  - Né l'area né il perimetro vanno a schermo.
- **Disegno (15,9–18,3 s, f398–f458).** Due teste partono insieme dal punto di costa più vicino al pontile del villaggio, cioè dove più tardi arriverà la barca, e percorrono la costa nei due versi. Si incontrano sul lato sud-ovest. La curva è in-out cubic: lenta all'inizio, rapida a metà, si posa alla chiusura.
- **Colore.** Champagne caldo (#FFE6B3) con bagliore oro. Un primo test in bianco spariva sulla spiaggia bianca. Sotto la linea c'è un filo scuro molto leggero (26 %) che la stacca dalla sabbia.
- **Passaggio alla luce.** Alla chiusura (18,3 s) il bagliore lungo tutto il contorno fa un "flash" che decade in circa 0,9 s. In quel momento la luce su Seliu delle lastre (16–20 s) sta salendo.
  - Poi il contorno **si posa**: opacità al 58 %, spessore −22 %, bagliore ridotto.
  - Resta come un filo delicato fino alla fine: il protagonista torna a essere la luce.
- **Riflesso d'arrivo (22,5–24,7 s).** Quando la barca tocca il pontile, una sola luce corre lungo la costa nei due versi e si spegne. Succede una volta, non in loop.

## 6. Timing (25 s, 25 fps; tutto in `motion_gfx.T`)
| s | f | Evento |
|---|---|---|
| 0,05–1,0 | 1–25 | dissolvenza dal nero |
| 2,30 / 2,45 | 58 / 61 | SINGAPORE: punto, poi lettere |
| 2,80 / 2,95 | 70 / 74 | JAKARTA: punto, poi lettere |
| 4,20–7,00 | 105–175 | arco Singapore → Belitung |
| 4,70–7,50 | 118–188 | arco Jakarta → Belitung |
| 5,30 | 133 | *Direct flights* (tendina) |
| 7,00 / 7,50 | 175 / 188 | arrivi: punto + anello, secondo riflesso |
| 7,55 | 189 | BELITUNG (piccolo, accanto all'arrivo) |
| 8,20–9,30 | 205–233 | le linee si ritirano dentro Belitung, le scritte si sciolgono |
| 10,40 | 260 | BELITUNG titolo (lettere dal centro) |
| 10,90 / 11,15 | 273 / 279 | filo sottile dal centro / sottotitolo |
| 13,00–13,75 | 325–344 | uscita del titolo |
| 15,90–18,30 | 398–458 | contorno di Seliu (due teste dal pontile) |
| 17,20 / 18,05 | 430 / 451 | SELIU ISLAND / sottotitolo |
| 18,30 | 458 | chiusura del contorno: flash → si posa entro circa 20,9 s |
| 19,00 / 19,15 | 475 / 479 | TELUK GEMBIRA: punto / lettere |
| 19,80–22,40 | 495–560 | rotta in barca |
| 21,00 | 525 | *15–20 min by boat* (da destra a sinistra) |
| 22,40 | 560 | arrivo al pontile del villaggio |
| 22,50–24,70 | 563–618 | riflesso lungo la costa |
| 22,4–25,0 | 560–625 | fermo finale: oltre 2,5 s di respiro su un'immagine completa |

**Impaginazione finale (16:9).**
- SELIU ISLAND e il sottotitolo stanno sopra l'isola, nella foschia.
- La nota sulla barca sta sopra la rotta, al 40 % del tragitto da Teluk Gembira, sul mare aperto.
- TELUK GEMBIRA sta a destra del suo punto. Verso la fine, se la scritta uscirebbe dall'area sicura, va sotto il punto. Il lato si decide una volta sola, dalla posizione a fine ripresa, così l'etichetta non salta mai a metà.

**9:16.**
- Titoli centrati.
- Etichette dei luoghi sotto i punti.
- Nota della barca a destra della rotta, che lì è verticale.
- Verificato con la camera 9:16 della timeline su una lastra neutra (`review/gfx/layout_9x16_placeholder.jpg`): tutto resta dentro l'area sicura.

## 7. Colore (`grade_cine.py`)
L'obiettivo è un film, non un "filtro". La verità del satellite resta.

1. **Bilanciamento ed esposizione** in luce lineare, variabili nel tempo:
   - orbita più fredda e profonda;
   - Seliu più calda (+3,5 % R, −4 % B) e più luminosa (+4 %).
2. **Contrasto filmico** sulla luminanza, che conserva tinta e saturazione:
   - pendenza 1,22–1,26 attorno al punto medio reale di ogni atto (0,40 orbita, 0,54 Seliu);
   - piede morbido, quindi neri mai schiacciati, leggermente sollevati e freddi;
   - **spalla**: i bianchi rientrano dolcemente fino a ~0,975 e non tagliano mai.
3. **Colore selettivo:**
   - turchese dei bassi fondali più "denso" (−12/13 % di luminanza, meno saturo), così l'acqua è ricca e non sembra una piscina;
   - vegetazione appena più profonda;
   - vibranza solo sui colori poco saturi;
   - saturazione globale ≤ 1.
4. **Split-toning lieve.** Ombre verso il teal, alte luci calde, più calde all'arrivo.
5. **Profondità.** Contrasto locale a grande raggio (calcolato a 1/8 della risoluzione), con protezione di neri e bianchi.
6. **Halation.** Alone rosso-arancio da pellicola attorno ai bianchi più forti (reef, cime delle nuvole), dosato al 5–8 %.
7. **Vignetta ellittica e filtro graduato.**
   - Vignetta: 26 % in orbita, 15 % su Seliu.
   - Filtro graduato freddo in alto (8–10 %) a partire dalla discesa: il mare lontano si scurisce e l'occhio va all'isola in luce.
8. **`finish()`.**
   - Grana fine (~1,3 px) pesata sui mezzitoni, con il 20 % di componente cromatica.
   - Dither triangolare a 1 LSB.
   - Nessuna banda nei cieli e nei gradienti del mare, anche dalle lastre a 8 bit.

Confronto RAW/grade: il mare regionale e quello di Belitung sono più profondi, Seliu stacca di più sul suo intorno, la sabbia è calda e non bianca piatta. Nessuna tinta innaturale.

## 8. SFX della grafica (`sfx_cues.json`, `sfx_synth.py`)
- **Ruolo.** Gli SFX sono "luce che si sente": piccoli, precisi, sotto l'ambiente v5 e sotto la musica. Non ci sono "braam", impatti o whoosh da trailer.
- **Sintesi.** Tutto è sintetizzato da zero (seni, rumore filtrato, stanza sintetica): nessun campione.
- **Mix.** 48 kHz / 24 bit, **−26 LUFS integrati** (6 dB sotto l'ambiente a −20), picco ≤ −3 dBFS, niente sopra ~9 kHz (niente fruscio).
- **Lessico:**
  - **glint**: parziali di campana inarmoniche, una per punto (Jakarta un tono sotto Singapore);
  - **letters_air**: granelli d'aria, uno per lettera, sfasati come le lettere;
  - **line_shimmer**: grappolo di seni acuti con modulazione e un filo d'aria, panoramica che segue la testa. Per la rotta in barca il registro è più basso e "acquatico" e la panoramica va da destra a sinistra;
  - **title_swell**: gonfiore caldo di accordo aperto più aria filtrata, su BELITUNG e SELIU ISLAND (Seliu una terza sopra);
  - **riser**: salita lenta di rumore filtrato con un glissando di una quinta (14,4–18,3 s). Si nasconde sotto il bloom, senza colpo finale;
  - **outline_shimmer**: campanelle pentatoniche granulari, una voce per testa (sinistra/destra), la densità segue la velocità del disegno;
  - **flash_bloom**: accordo morbido (La maggiore aperto) alla chiusura del contorno;
  - **arrival_tick**, **rule_tick**, **wipe_breath**, **dissolve**, **glint_pass**: dettagli a −36/−39 dB.
- **Panoramica.** Deriva dalla posizione a schermo in 16:9. Per il 9:16 va ridotta della metà.
- **File.** `audio/sfx_gfx_v6.wav`. Per rigenerarlo: `python3 tools/sfx_synth.py`.

## 9. Rischi aperti
- **Le lastre 16:9 non sono complete.** Nel momento della prova mancano circa 100 fotogrammi (f320–f623, uno ogni tre): il render è in corso. Le prove usano il fotogramma disponibile più vicino.
- **Il 9:16 non è stato provato su lastre vere**, solo con la camera della timeline su lastra neutra: `frames/raw_9x16` non esiste ancora. Va guardato quando arriva.
- **Il contorno segue il bordo della vegetazione** (la maschera "terra"), non il bordo esterno della spiaggia o del reef. È la costa geografica corretta, ma sulle spiagge larghe la linea sta "dentro" il bianco.
- **Il suono della grafica è verificato solo con spettrogramma e misure.** Va ascoltato in cuffia insieme all'ambiente v5 prima della pubblicazione.
- **La rotta in barca resta indicativa** (curva dolce), come nella v5.
- **Il "flash" del contorno è legato ai tempi della luce sulle lastre** (16–20 s in `timeline.glow`). Se la timeline cambia, va riallineato `T["outline"]`.
