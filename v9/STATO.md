# Seliu v9 · stato (16-10-2026)

## Consegnato
- **Finale 16:9 1080p** (`seliu-apertura-v9-16x9-1080p.mp4`):
  - 28 s, grafica A;
  - ambiente −16 LUFS, −1,2 dBTP, 0,6 s di sfumata finale solo nel mix web.
- **Versione pulita** e **lastra RAW** (HEVC 10 bit 4:4:4, senza grade, grana né scritte).
- **Versione con intro del marchio** (`…-con-intro.mp4`, 33,6 s):
  - la rosa avorio nasce dalle stelle vere, compaiono COMPASS ROSE e INDONESIA in oro;
  - la rosa diventa una stella che corre verso la camera e le passa accanto;
  - la camera la insegue girandosi di colpo, la Terra entra in quadro e la stella diventa una cadente sopra il lembo;
  - la panoramica atterra sul primo fotogramma del volo con la stessa velocità, senza stacco.
- **Audio** in `audio/`:
  - mix web −16 e letto −20 LUFS;
  - 9 stem;
  - suono della versione con intro (intro ~−23 LUFS, un'onda bassa d'aria al passaggio della stella, niente colpi né whoosh da trailer).
- **Documenti:** `TITOLI-DI-CODA.txt`, `README.md`; contact sheet in `review/f3/`.

## Correzioni dopo la revisione indipendente del finale
- **Giuntura nel mosaico** sulla costa sud di Sumatra (6,8–8,3 s): corretta nei dati (`fix_l0_seam.py`) e rifatti i fotogrammi interessati.
- **Audio che si chiudeva di colpo** a 28 s: aggiunta una sfumata di 0,6 s, solo nel mix web. Il letto per la musica e gli stem restano interi per il montaggio.

## Non seguito (contraddice una tua indicazione o le regole sui dati)
- **"La luce sulla costa sembra una grafica":** è la traccia che resta come bagliore, come mi avevi chiesto.
- **"La nota della barca si apre da destra a sinistra":** è il gesto scelto in Fase 1, nella direzione della barca.
- **"SINGAPORE è a est della punta":** è il punto di Changi che mi hai dato.

## Ancora aperto
- **Ascolto in cuffia da parte tua:** io misuro ma non ascolto.
- **Musica:** brief in `audio/BRIEF-MUSICA.md`.
- **Licenze da verificare:** Himawari-8 (JMA) e Mixkit.
- **9:16:** non renderizzato, come chiesto (solo 16:9).
