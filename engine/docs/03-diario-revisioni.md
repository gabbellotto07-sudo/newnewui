# Seliu v5 — Diario di produzione e revisioni interne

## Giro 1 · Dati e immagini
- **Cartografa.** Tre sorgenti satellitari aperte (Sentinel-2 su AWS, ESA WorldCover, batimetria AWS Terrain Tiles), tutte in un'unica proiezione azimutale equidistante centrata su Seliu, così la discesa non ha mai un salto di proiezione.
- **Scelta della scena eroe.** Ho confrontato a vista oltre 800 passaggi Sentinel-2 dal 2019 al 2026. Il 29-07-2019 è l'unico giorno davvero limpido sul canale fra Seliu e Belitung.
- **Rimozione delle nuvole.** Tre tentativi automatici sono falliti: cancellavano i reef, che Sentinel-2 classifica come "nuvole". Si è passati a un clean plate a mano: 30 nuvole e ombre indicate una per una nella zona dell'arrivo, riempimento con altre date solo sui bassi fondali, riempimento morbido solo in mare aperto.
- **Avvocata.** Approva le fonti; impone l'attribuzione nei titoli di coda.

## Giro 2 · Prima bozza (24 s)
- **Revisione interna.** Il percorso camera funziona. Sei difetti corretti:
  - cuciture fra le tessere ESA;
  - "rettangoli" di tono nel mare;
  - salto di colore fra i livelli, risolto scrivendo ogni livello fine dentro quello più largo con la stessa sfumatura del motore;
  - inquadratura iniziale stretta;
  - Seliu che entrava tardi nell'inquadratura;
  - terre ESA più slavate di quelle di Seliu, ora tarate sulla terraferma del livello Seliu.
- **Revisore indipendente (regia + avvocata).** Veto condizionato e bozza bocciata: "è ancora una mappa che zooma".
  - Avvocata: pontile e voli da confermare; batimetria senza attribuzione; data delle immagini; la luce su Seliu non c'è.
  - Regia: manca il tre quarti; Seliu non è il soggetto; aloni chiari lungo le coste; ritmo; leggibilità.
  - Tutto corretto: camera fino a 52° di inclinazione nel finale, luce su Seliu (+20 %) e Belitung tenuta indietro (−24 %), niente anello turchese lungo tutte le coste, Belitung nominata appena arrivano i voli, Seliu a 17,4 s, scritte più grandi.

## Giro 3 · Bozza mostrata al cliente → ok con conferme
- **Il cliente conferma** il pontile di Teluk Gembira, i voli diretti e la traversata "15–20 min by boat".
- **Il cliente chiede:** apertura cinematografica che emozioni, qualità alta, immersiva anche dal telefono.
- **Regia.** Si parte dall'orbita (bordo dell'atmosfera) e la camera si piega verso la regione. Le nuvole vere del 29-07-2019 diventano uno strato 3D a ~850 m, con parallasse e ombre sotto il sole reale (elevazione 57°, azimut 47°). Nel finale la camera "respira" come un elicottero in hovering. Durata: 25 s.
- **Motion designer.** Sfocatura di movimento (otturatore a 3 campioni) solo nella picchiata.
- **Colorista.** Leggero alone sui bianchi (reef, cime delle nuvole), grana fine. Sopra Belitung i cumuli visti da 100+ km sembrano rumore: restano solo quelli sul mare.
- **Tipografo.** Scala per il telefono:
  - città 30 px, note 32–36 px, BELITUNG 84 px, SELIU ISLAND 84 px su base 1080;
  - titoli centrati sempre dentro l'inquadratura;
  - SELIU ISLAND spostato sopra l'isola, nella foschia, con un filo sottile verso l'isola.
- **Montatore.** Nuova versione **verticale 9:16**. Stesso volo; dopo Belitung la camera ruota fino a guardare verso ovest dal pontile di Teluk Gembira: la traversata sale dal basso verso Seliu, con le nuvole vere sull'orizzonte.
- **Avvocata · veto (risolto).** Il confronto 2019/2026 mostra che Seliu è cambiata (radura a nord-ovest, lotti disboscati). Mostrare il 2019 sarebbe fuorviante. Soluzione: terraferma da agosto 2026, mare limpido del 2019, date dichiarate nei titoli di coda.
- **Sound designer.** Ritiming a 25 s:
  - un bordone basso e ampio per l'orbita;
  - jet lontano sui voli;
  - aria che sale nella picchiata;
  - due soffi passando sopra i cumuli;
  - risacca sul reef, brezza;
  - fuoribordo da Teluk Gembira a Seliu mentre si traccia la rotta;
  - mix a −20 LUFS, pronto per la musica.

## Giro 4 · Revisione indipendente del master → correzioni finali
- **Avvocata:** nessun veto. I titoli di coda con le attribuzioni sono obbligatori; se i 25 s vengono usati da soli (teaser o social), serve una riga di credito anche lì.
- **Regia:** quattro correzioni, tutte applicate prima del render definitivo:
  1. Seliu spicca per luce: +28 % sull'isola e sul reef, −32 % intorno, con una schiarita che entra fra 16 e 20 s. L'isolotto vicino resta più in ombra.
  2. Scritte secondarie più grandi per il telefono: città 36 px, note 38–40 px, sottotitoli 30 px, Teluk Gembira 34 px (base 1080). Sul telefono va servita la versione 9:16.
  3. Le linee dei voli si dissolvono entro 9,6 s, prima che compaia BELITUNG.
  4. Il nero iniziale è sotto 1 s (dissolvenza 0,05–1,0 s), perché dopo il clic su "Watch the video" non sembri un caricamento bloccato.
- **Ancora aperto:** il suono va ascoltato in cuffia da una persona prima della pubblicazione.

## Giro 5 · RAW e v6 (richieste del cliente del 15-10-2026)
- **Il cliente chiede** il video "raw", senza testo, e poi tutto il materiale grezzo per il suo Claude specialista: movimenti lenti, scelta libera di zoom, motion e testi.
  - Si costruisce una libreria: 9 riprese lente (smootherstep), la discesa continua senza testo, lastre georeferenziate a 16 bit, matte della luce, tracking per fotogramma, suono in tracce separate e una guida per Claude.
- **Il cliente chiede poi una versione finita del gruppo.** Vuole un grade più cinematografico e immersivo, testi e linee animati con strumenti di motion design, **l'animazione del contorno disegnato** di Seliu (prima esclusa; ora richiesta dal cliente) ed effetti sonori. Le decisioni grafiche vanno affidate a uno specialista indipendente.
- **Specialista grafico indipendente.** Ha deciso e realizzato `grade_cine.py`, `motion_gfx.py`, `sfx_synth.py` e il contorno della costa vera (`data/seliu_outline_lonlat.json`), con 3 giri di prova. Vedi `05-direzione-grafica.md`.
- **Regia.** Revisione del contact sheet v6: nessun difetto bloccante. Mix finale: ambiente v5 + SFX della grafica a −16 LUFS, adatto al web senza musica.
- **Incidente tecnico.** Un processo di render è stato chiuso dal sistema per memoria esaurita. Ho rigenerato i 102 fotogrammi mancanti e ridotto il parallelismo a 2 processi.

## Limiti noti (onesti)
- La risoluzione nativa è 10 m: nel finale l'immagine è ingrandita circa 2× con supersampling. Non si vedono singoli alberi o case.
- La linea della traversata è indicativa (curva dolce fra i due pontili), non una rotta nautica.
- Il suono è stato verificato con spettrogrammi e misure di loudness, non con un ascolto umano: va ascoltato in cuffia prima della pubblicazione.
