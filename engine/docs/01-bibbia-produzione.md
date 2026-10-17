# Seliu Island — Apertura v5 · Bibbia di produzione

Documento della "casa di produzione" interna: chi decide cosa, cosa abbiamo deciso e perché.
Riferimento: `seliu-apertura-v3-cinema.mp4` (direzione giusta, esecuzione da superare).

## La squadra

| Ruolo | Responsabilità | Diritto di veto |
|---|---|---|
| **Regista** | Visione, ritmo, approvazione finale interna | sì (creativo) |
| **Cartografa / data** | Fonti satellitari, proiezione, posizioni esatte, verifica dati | sì (su un dato) |
| **Motion designer** | Camera, curva della discesa, linee di rotta | — |
| **Tipografo** | Font, gerarchia, ancoraggio e tempi delle scritte | — |
| **Colorista** | Look "luce di giorno", continuità fra le scale, luce su Seliu | — |
| **Sound designer** | Paesaggio sonoro dall'alta quota al livello del mare | — |
| **Montatore** | Tempi, respiro, durata 20–25 s, ritmo delle entrate | — |
| **Avvocata del cliente e del brand** | Tutela il cliente e Seliu: verità dei dati, licenze, tono, niente promesse | **sì, assoluto** |

## Prima riunione — analisi della v3-cinema

**Regista.** La direzione è giusta: una discesa sola. Però la v3 è ancora "una mappa che zooma":
camera sempre perpendicolare, nessuna sensazione di quota, nessun punto in cui l'aria diventa mare.
Voglio una camera che si comporti come un elicottero o un satellite che scende: prima la curvatura
della Terra, poi la foschia, poi l'isola vista di tre quarti, come la vedrebbe un occhio umano che arriva.

**Colorista.** Nella v3 il mare regionale è un blu saturo uniforme e il passaggio Belitung → Seliu
cambia sorgente in modo visibile (frame a 10 s: sfocatura e salto di colore). La luce è piatta.
Seliu "risalta" solo per il contorno dorato, che la tua nota vieta.

**Cartografa.** La v3 usa immagini di cui non conosciamo la licenza. Propongo solo dati aperti con
licenza chiara: Copernicus Sentinel-2 (ESA) e ESA WorldCover. Per l'isola uso una scena reale:
**29 luglio 2019, Sentinel-2B**, eccezionalmente limpida sul canale fra Seliu e Belitung (scelta su
oltre 800 passaggi 2019–2026 confrontati a vista). È la stessa giornata anche per Belitung, così
acqua, luce e nuvole sono di un solo giorno vero.

**Avvocata.** Bene la licenza: Copernicus chiede l'attribuzione, che va nei **titoli di coda**
(nota del cliente: niente crediti a schermo). Poi tre punti fermi:
1. Ogni scritta deve essere vera e verificabile: "Direct flights" solo da città con volo diretto
   attivo (Singapore: Scoot; Jakarta: più compagnie). Niente durate di volo a schermo: cambiano con gli orari.
2. "15–20 min by boat" parte dal **vero pontile** di Teluk Gembira, non da un punto qualunque della costa.
3. Le nuvole possono restare solo se sono vere. Niente nuvole inventate.

**Motion designer.** Le nuvole vere della stessa scena le possiamo staccare dal suolo e rimettere a
circa 1 km di quota: la camera le vede passare in parallasse e le loro ombre cadono sul mare nel
punto giusto. Così Seliu resta nella luce perché quel giorno lì non c'erano nuvole: non è un trucco.

**Avvocata.** Accettato, purché le ombre seguano la direzione reale del sole di quella scena.

**Tipografo.** Poche scritte, tutte ancorate a un luogo: Singapore, Jakarta, "Direct flights",
BELITUNG, Teluk Gembira, la traversata, SELIU ISLAND. Un solo carattere (Jost, licenza OFL),
maiuscoletto spaziato per i luoghi, minuscolo per le note. Bianco caldo, nessun riquadro, nessuna icona.

**Sound designer.** Tre strati che si passano il testimone: aria rarefatta (vento alto, ronzio
lontano di un jet mentre si disegnano i voli), discesa (il vento cresce e si apre), arrivo (risacca
sul reef, brezza, un fuoribordo lontano quando nasce la rotta in barca). Niente musica: lasciamo spazio
a quella che il cliente sceglierà. Il mix deve funzionare anche con le casse di un laptop.

**Montatore.** 24 secondi. Il primo suono arriva prima dell'immagine. L'ultima inquadratura deve
respirare almeno 3 secondi fermi su Seliu prima del taglio al resto del video.

## Decisioni

- **Una sola camera** su un globo vero (curvatura reale), tre livelli di immagini fusi senza stacchi:
  - Regione: ESA WorldCover 2021 (mosaico Sentinel-2 senza nuvole) + batimetria per il mare.
  - Belitung: scene Sentinel-2 del 29-07-2019 per l'acqua, terre dal mosaico ESA.
  - Seliu: scena Sentinel-2B del 29-07-2019 a 10 m, pulita a mano (clean plate) dalle nuvole.
- **Inquadratura finale di tre quarti** (camera inclinata ~42°) da sud-sud-est: Seliu a sinistra,
  il pontile di Teluk Gembira a destra, la traversata attraversa l'inquadratura.
- **Luce invece del contorno**: Seliu illuminata, il resto leggermente più scuro, ombre di nuvole
  vere che passano intorno.
- **Niente elementi da app**: nessuna scala, bussola, legenda, crediti a schermo.

## Dati da verificare con il cliente

- Coordinate del pontile di Teluk Gembira (letto su immagini 2019 e 2026: 3.1974 S, 107.5858 E)
  da confrontare con quelle in `progetto-seliu-island.md`.
