# Seliu v8 · Fase 1 — dati rigenerati e verifiche

## Cosa è stato rigenerato (procedura "Rifarla da zero" del README, nel cloud)

| Livello | Copertura | Risoluzione | Fonte | Stato |
|---|---|---|---|---|
| LG | ±3.600 km | 1,8 km | ESA WorldCover 2021 + batimetria AWS Terrain Tiles | rigenerato |
| L0 | ±1.700 km | 800 m | come sopra | rigenerato |
| L1 | ±230 km | 100 m | ESA WorldCover 2021 (terre) + Sentinel-2B 29-07-2019 (acque) | rigenerato |
| **LM (nuovo)** | ±90 km, tutta Belitung e il campo di nuvole a ovest di Seliu | **15 m** | terre: mediana dei passaggi Sentinel-2 limpidi 2026 (01, 06, 08, 11, 26 agosto, 22 luglio, 22 giugno, 20 settembre); acque e nuvole: Sentinel-2B 29-07-2019 | nuovo |
| L2 | ±32 km | 10 m | mare 29-07-2019 pulito dalle nuvole, terra agosto 2026 | rigenerato |
| DEM | L2 e LM | 30 m (ricampionato) | **Copernicus GLO-30** (nuova fonte), AWS `copernicus-dem-30m` | nuovo |

Contorno di Seliu (`make_outline.py`): 1.703 punti, perimetro 20,4 km, area 16,7 km², identico al v6 → la procedura è riproducibile.

## Difetto trovato nel motore v5

`tools/inject.py` scrive ogni livello fine dentro quello più largo con un rapporto di scala arrotondato all'intero. Per L0→LG il rapporto vero è 1800/800 = 2,25, ma veniva usato 2: la regione era incollata nel livello continentale **ingrandita del 12,5 % e spostata**. Nelle viste dall'orbita e nella regione questo produce rettangoli di tono e coste doppie (visibili nel v8 a 6,8 s prima della correzione). Sostituito da `tools/inject_v8.py`, esatto per qualsiasi rapporto.

## Pontili: verifica sovrapponendo i punti all'immagine (Sentinel-2 10 m)

Immagini: `review/f1/pontili_verifica.jpg` (composito v8, 08-08-2026 grezza, 29-07-2019 grezza) e `review/f1/pontili_zoom.jpg` (griglia di 50 m).

| Punto | Coordinate in tabella | Esito |
|---|---|---|
| Pontile di Teluk Gembira | −3.1973, 107.5857 | **Sulla punta del promontorio**, dove parte il pontile. A 10 m il pontile stesso non si distingue; il punto cade sulla struttura chiara della punta, identica nel 2019 e nel 2026. ✔ |
| Pontile del villaggio di Pulau Seliu | −3.1994, 107.5449 | Il molo si vede bene (linea chiara che esce dalla costa nord-est). **La testa del molo è ~52 m a est e ~9 m a nord** del punto in tabella: il punto cade in acqua, accanto al molo. Testa del molo misurata: **−3.19932, 107.54537**. |
| Seliu centro visivo / punta sud | −3.222, 107.522 / −3.256, 107.519 | Sull'isola. ✔ |

**Proposta (da approvare):** per il punto d'arrivo della barca disegnato a schermo uso la testa del molo misurata (−3.19932, 107.54537). Lo scarto è piccolo ma nel finale in 4K vale ~10 pixel. Nessuna scritta cambia: il pontile di Seliu non ha etichetta. Finché non dai l'ok resta il punto della tabella.

## Nuvole vere del 29-07-2019

- Cumuli di bel tempo: mediana ~40 m, il 90 % sotto i 250 m, il più grande ~2 km².
- Base a ~720 m; le cupole sono ricavate dalla dimensione di ogni nuvola (alte ~0,75 × il raggio, al massimo ~420 m). La quota media di ~850 m è coerente con lo spostamento delle ombre (sole a 57,5° di elevazione, azimut 46°, ricalcolati per le 10:20 locali).
- Si concentrano sul mare aperto a ovest e sud-ovest di Seliu e sulla terraferma di Belitung a nord: la picchiata passa sopra quel campo.

## Cave di stagno

Restano tutte (non si toglie nulla dal territorio). Nel livello LM vengono dalla mediana dei passaggi 2026: sono le cave di oggi.
