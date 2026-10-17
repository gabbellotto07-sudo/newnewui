# Seliu v5 — Fonti, dati e verifiche

Ogni elemento sullo schermo è vero e verificabile. Questa è la lista completa.

## Scritte a schermo

| Scritta | Dato | Verifica |
|---|---|---|
| SINGAPORE | Punto su Changi (1.3644 N, 103.9915 E): i voli partono da lì | — |
| JAKARTA | Punto su Soekarno-Hatta (6.1256 S, 106.6559 E) | — |
| Direct flights | Voli diretti verso Tanjung Pandan (TJQ, H.A.S. Hanandjoeddin, 2.7455 S, 107.7546 E). Singapore: Scoot; Jakarta: più compagnie | Skyscanner / Trip.com (luglio 2026); **confermato dal cliente il 15-10-2026** |
| BELITUNG · Bangka Belitung Islands · Indonesia | — | — |
| TELUK GEMBIRA | Pontile sulla punta del promontorio, 3.1973 S, 107.5857 E, letto su Sentinel-2 del 29-07-2019 e del 08-08-2026 | **Confermato dal cliente il 15-10-2026** |
| 15–20 min by boat | Traversata dal pontile di Teluk Gembira al pontile del villaggio di Pulau Seliu (3.1994 S, 107.5449 E) | Nota del cliente; confermato il 15-10-2026 |
| SELIU ISLAND · Off the south-west coast of Belitung | — | — |

Il nome dell'aeroporto non compare (nota del cliente).
La linea dei voli è un arco di cerchio massimo leggermente sollevato: indica il collegamento, non la rotta esatta di volo.
La linea della traversata è una curva dolce sul mare aperto fra i due pontili, non una rotta nautica.

## Immagini

| Livello | Dove si vede | Fonte | Data |
|---|---|---|---|
| Continentale (±3.600 km) | apertura dall'orbita | ESA WorldCover 2021, mosaico Sentinel-2 senza nuvole | 2021 |
| Regione (±1.700 km) | voli | ESA WorldCover 2021 | 2021 |
| Belitung (±230 km) | discesa | ESA WorldCover 2021 (terre) + Copernicus Sentinel-2B (acque della piattaforma di Belitung) | 2021 / 29-07-2019 |
| Seliu (±32 km, 10 m) — mare | arrivo | Copernicus Sentinel-2B L2A, scena eroe (acqua, reef, luce) | **29-07-2019** |
| Seliu (±32 km, 10 m) — terraferma | arrivo | Copernicus Sentinel-2 L2A più recenti: 08-08-2026, 26-08-2026, 01-08-2026 (buchi di nuvole: 02-07-2025, 12-07-2024) | **agosto 2026** |
| Riempimento nuvole sulla terraferma | — | Sentinel-2 del 18-08-2019, 12-07-2024, 18-06-2023 | |
| Mare aperto | regione e Belitung | colore ricavato dalla scena eroe in funzione della profondità; batimetria AWS Terrain Tiles (GEBCO / ETOPO1 / SRTM) | |
| Nuvole in 3D | discesa e arrivo | le nuvole reali della scena del 29-07-2019, staccate dal suolo e rimesse a ~850 m (quota ricavata dalle loro ombre e dal sole: elevazione 57°, azimut 47°) | 29-07-2019 |

**Interventi sull'immagine.**
- Solo rimozione di nuvole e delle loro ombre ("clean plate"). Nessun edificio, cava, strada o costa è stato tolto o aggiunto.
- La luce su Seliu è una correzione colore morbida: +20 % sull'isola e sul reef, −24 % intorno. Non è un contorno.
- Mare del 2019, terra del 2026. La scena del 29-07-2019 è la più limpida su oltre 800 passaggi dal 2019 al 2026 sul canale fra Seliu e Belitung, e la usiamo per il mare. Il confronto con agosto 2026 mostra però che **Seliu è cambiata**: c'è una grande radura rettangolare a nord-ovest e diversi lotti disboscati. Per non mostrare agli investitori un'isola che non esiste più, la terraferma viene dalle scene di agosto 2026. Il pontile di Teluk Gembira è invariato.

## Suono

Il suono è sintetizzato da zero (`tools/sound.py`): niente campioni di terzi e niente licenze. Non c'è musica: verrà scelta più avanti.
Il mix è a −20 LUFS integrati con picchi sotto −3 dBFS, per lasciare spazio alla musica.

## Carattere

Jost (Indestructible Type), licenza SIL Open Font License 1.1: `fonts/OFL.txt`.

## Titoli di coda (da inserire alla fine del video completo)

```
Satellite imagery
Contains modified Copernicus Sentinel data (2019, 2023, 2024, 2025, 2026), processed by ESA
© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)
processed by ESA WorldCover consortium (CC BY 4.0)
Bathymetry and terrain: AWS Terrain Tiles — GEBCO, ETOPO1 (NOAA), SRTM (NASA/USGS)
Seliu Island: land August 2026, sea 29 July 2019
```

## Riferimenti consultati

- Skyscanner, SIN–TJQ: https://www.skyscanner.com.sg/routes/sin/tjq/singapore-changi-to-belitung-tanjung-pandan.html
- Trip.com, SIN–TJQ: https://sg.trip.com/flights/singapore-to-tanjung-pandan/airfares-sin-tjq/
- Posbelitung, pontile di Teluk Gembira verso Pulau Seliu (2018): https://belitung.tribunnews.com/2018/11/01/dermaga-penyeberangan-teluk-gembira-menuju-desa-pulau-seliu-hampir-ambruk?page=all
- Jadesta (Kemenpar), Desa Wisata Pulau Seliu: https://jadesta.kemenpar.go.id/desa/pulau_seliu
- Dati: https://registry.opendata.aws/sentinel-2-l2a-cogs/ · https://esa-worldcover.org · https://registry.opendata.aws/terrain-tiles/
