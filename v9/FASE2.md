# Seliu v9 · Fase 2 — animatic

Stato: **in attesa della tua approvazione** per il render finale (Fase 3).

## Dove guardare (`v9/review/f2/`)

| File | Cosa |
|---|---|
| `seliu-v9-animatic-16x9.mp4` | animatic 960×540, grafica A, suono provvisorio (solo ambiente, −16 LUFS) |
| `seliu-v9-animatic-9x16.mp4` | stesso volo in verticale, 540×960 |
| `contact-16x9-1fps.jpg`, `contact-9x16-1fps.jpg` | un fotogramma al secondo |
| `telefono_390px_16x9.png`, `telefono_390px_9x16.png` | leggibilità su un telefono da 6" |
| `../../audio/` | mix provvisori, misure, spettrogramma, fonti dei suoni, brief musica |

Va ascoltato in cuffia **e** dall'altoparlante del telefono. Io misuro, ma non posso ascoltare: **serve comunque il tuo ascolto in cuffia** prima della consegna.

## Cosa c'è di nuovo rispetto alla Fase 1

- **Grafica A** (la tua scelta), comete discrete per i voli.
- **9:16:** stesso viaggio. Dopo Belitung la camera guarda lungo la traversata (Seliu in alto, Teluk Gembira in basso): è l'unico modo per tenere in quadro le due sponde in verticale. I titoli stanno in alto a sinistra, sul mare lontano, perché in basso ci sono la traversata e l'interfaccia del telefono.
- **Spazio** (tua richiesta, discussa con un revisore che fa il direttore della fotografia):
  - **lembo dell'atmosfera fisico:** sottile e stratificato (bianco-ciano, blu, una traccia viola d'ozono), con una leggera diffusione nell'obiettivo; non più l'alone largo e uniforme della v8;
  - **stelle vere:** catalogo Yale Bright Star, posizioni reali per il 29-07-2019 alle 03:20 UTC, solo fino a magnitudine 4, quindi poche decine in quadro, tenui (fino al ~10 % del bianco). Si spengono fra 1,2 e 2,2 s, come un'esposizione che si adatta alla Terra illuminata;
  - **nero neutro**, non più blu-navy;
  - **esclusi:** luna (era una falce sottile vicino al sole, non visibile), aurora (impossibile lì e di giorno), Via Lattea, riflessi d'obiettivo;
  - **nell'animatic a 960 px le stelle quasi non si vedono:** sono puntini di 1–1,5 px pensati per il 1080p. Le giudichi nel render finale.
- **Nuvole regionali:**
  - finestra Himawari allargata, perché nel 9:16 si vedeva il bordo dritto del ritaglio;
  - tolte le nuvole viste di taglio dal satellite verso il bordo del suo disco (oltre i 66°): erano stirate in righe;
  - è solo una rimozione, nessuna nuvola aggiunta.
- **Ritmo della camera:**
  - una leggera deriva da velivolo fra 1 e 17 s;
  - la picchiata dopo BELITUNG accelera in ~1,6 s invece di partire di colpo: il controllo di velocità aveva trovato uno scatto a 12,8–13,2 s;
  - nel finale una lenta spinta in avanti sotto la deriva (~0,7 px a fotogramma a 1080p, prima 0,33), mai ferma;
  - dissolvenza dal nero in 0,9 s.
- **Suono** (`engine/tools/sound_v9.py`, fonti in `audio/FONTI-SUONI.md`):
  - **meno grave nella prima metà:** nei primi 14 s l'energia sotto i 200 Hz scende dal 55 % della v8 al ~10 %;
  - **aria rarefatta in quota:** due registrazioni vere di vento (Mixkit), solo il fruscio sopra 2,5 kHz. Fra 2 e 24 kHz si passa dallo 0,1 % della v8 a circa il 40 %;
  - tolto il tono sintetico d'orbita, che suonava come un ronzio;
  - tolto il "tic" di carta sotto i titoli;
  - il **respiro prima di Seliu** (17,0–17,85 s) resta, ma con bordi morbidi: un calo di ~8 dB, non un buco;
  - la barca segue la scia nuova.

**Misure** (mix provvisorio, 16:9):

| Misura | Valore |
|---|---|
| loudness integrata | −16,0 LUFS (con la musica l'ambiente scenderà a ~−20) |
| picco vero | −1,2 dBTP |
| LRA | 4,5 LU |
| mono rispetto allo stereo | −1,9 LU |
| simulazione altoparlante del telefono (300 Hz–8 kHz) | −3,4 LU |
| bande 0–200 Hz / 200 Hz–2 kHz / 2–8 kHz / >8 kHz | 13 % / 57 % / 25 % / 5 % |

## Autocritica fatta prima di mostrartelo
1. **Contact sheet a 1 fps:** nessun salto di luce o di colore fra i livelli.
2. **Telefono a 390 px:**
   - 9:16: tutto leggibile, sottotitoli compresi;
   - 16:9: luoghi e note leggibili, sottotitoli al limite.
3. **Velocità a schermo** (`engine/tools/speed_check.py`):
   - massimo ~52 px a fotogramma a 1080p, alla picchiata, con mosso vero;
   - uno scatto trovato e corretto (12,8 s);
   - la frenata a 17,6–17,8 s è voluta (il respiro).
4. **Loudness e mono:** misure qui sopra.
5. **Revisione indipendente:** un agente che non aveva visto il lavoro ha guardato l'animatic fotogramma per fotogramma.

**Corretto dopo la revisione:**
- finale quasi fermo;
- scia poco visibile nel 16:9 (ora più larga e luminosa);
- ronzio tonale a 0–13 s;
- ingresso del grave a 13 s troppo netto;
- bordi del respiro troppo netti;
- click a 10,4 s;
- dissolvenza dal nero troppo corta.

**Non seguito, perché contraddice il brief o le regole sui dati:**
- **"Un unico gesto per tutte le scritte":** hai chiesto un gesto per ruolo.
- **"Togliere il riflesso che scorre sulla spiaggia":** è la luce sulla costa che hai chiesto. L'ho tenuta, una volta sola.
- **"Far attraversare i cumuli alla camera in primo piano":** servirebbero nuvole volumetriche ravvicinate che i dati veri (cumuli di 40–250 m visti dal satellite) non danno senza inventarle. La camera passa sopra il campo vero di cumuli, con le loro ombre.
- **"Terminatore sul globo":** alle 10:20 locali il terminatore è sull'Africa, fuori quadro.
- **"Le scritte sembrano appoggiate sopra":** è la direzione A scelta, coerente con un documentario.

## Ancora aperto
- **Musica:** da scegliere, brief aggiornato ai tempi v9 in `audio/BRIEF-MUSICA.md`. Il mix finale aspetta la traccia.
- **Licenze da verificare da parte tua:** Mixkit e Himawari-8 (JMA).
- **9:16, 1–2 s:** in un angolo in basso compare per meno di un secondo la costa nord-ovest dell'Australia, che è reale. Si può togliere girando ancora l'orbita verticale; non l'ho fatto per non stravolgerla.

## Fase 3 (dopo il tuo ok)
- Render finale 1920×1080 e 1080×1920, versioni pulite senza scritte, grana e grade. Circa **2,5–3 h a formato** su questa macchina.
- Mix e stem, contact sheet, titoli di coda, README e STATO.
