# Testi pronti per aggiornare i documenti del progetto

Il container cloud in cui ho lavorato non vede il tuo PC: questi testi vanno incollati a mano (oppure dammi accesso e li applico io).

---

## A. Da incollare in `claude/progetto-seliu-island.md`, sezione "Video di Seliu"

### Apertura v6 (15-10-2026), versione finita del gruppo, e libreria RAW
- **v6, da usare.** `Video Seliu\v5\delivery\v6\`: 16:9 e 9:16, grade cinematografico, testi e linee animati, contorno di Seliu disegnato, effetti sonori (−16 LUFS, senza musica). La direzione grafica è di uno specialista indipendente: `docs\05-direzione-grafica.md`.
- **Libreria RAW.** `Video Seliu\v5\delivery\raw\`: 9 riprese lente 2560×1440 senza testo, discesa continua senza testo, lastre georeferenziate, matte, tracking, suono in tracce separate. Guida per Claude: `LEGGIMI_PER_CLAUDE.md`.

### Apertura v5 (15-10-2026), prima versione con testo statico
- **File (solo riferimento):** `Seliu - ORDINATO\Video Seliu\v5\delivery\reference\seliu-apertura-v5-16x9-con-testo.mp4`, 1920×1080, 25 s; superata dalla v6.
- **Struttura:** un'unica discesa continua.
  - Orbita, con il bordo dell'atmosfera.
  - Regione: voli diretti da Singapore e Jakarta.
  - Belitung.
  - Seliu di tre quarti, in luce, con la traversata da Teluk Gembira ("15–20 min by boat").
  - Il verticale termina guardando da Teluk Gembira verso Seliu.
- **Immagini:** solo dati aperti Copernicus Sentinel-2 ed ESA WorldCover. Il mare di Seliu viene dalla scena limpida del 29-07-2019; la terraferma da agosto 2026, perché Seliu è cambiata (radura a nord-ovest, lotti disboscati). Le nuvole sono quelle reali del 29-07-2019, in 3D con le loro ombre.
- **Dati confermati dal cliente il 15-10-2026:**
  - pontile di Teluk Gembira a 3.1973 S, 107.5857 E;
  - approdo al pontile del villaggio di Pulau Seliu a 3.1994 S, 107.5449 E;
  - voli diretti da Singapore (Scoot) e da Jakarta;
  - "15–20 min by boat".
- **Titoli di coda obbligatori:** vedi `v5\docs\02-fonti-e-dati.md` (attribuzioni Copernicus, ESA WorldCover CC BY 4.0, GEBCO/ETOPO/SRTM, date delle immagini).
- **Musica:** non ancora scelta. Il suono v5 è solo ambiente (vento d'alta quota, jet lontano, discesa, risacca, fuoribordo) ed è pensato per stare sotto la musica.
- **Rifarla o modificarla:** `v5\README.md` (Python; percorso della camera in `tools/timeline.py`, scritte in `tools/overlay.py`).
- **Versioni precedenti:** v2, v3, v3-cinema, v4 restano come archivio; v5 e v6 le sostituiscono.

---

## B. Nota per `_sync`

```
[2026-10-15] Video Seliu — apertura v6 (finita) + libreria RAW consegnate (cartella v5)
- Nuova cartella: Seliu - ORDINATO\Video Seliu\v5\ (delivery/, docs/, tools/, README.md)
- v6: 16:9 + 9:16, 25 s, grafica animata + contorno di Seliu + sfx, -16 LUFS, senza musica
- RAW: 9 riprese lente, discesa senza testo, lastre, matte, tracking, stems (delivery\raw, guida LEGGIMI_PER_CLAUDE.md)
- Dati confermati dal cliente: pontile Teluk Gembira 3.1973 S 107.5857 E, voli diretti SIN/CGK, "15–20 min by boat"
- Attenzione: Seliu è cambiata dal 2019 (radura NW). Il video usa la terraferma di agosto 2026
- Da fare: scegliere la musica; inserire i titoli di coda (testo in v5\docs\02-fonti-e-dati.md)
- Aggiornato: progetto-seliu-island.md → sezione "Video di Seliu"
```
