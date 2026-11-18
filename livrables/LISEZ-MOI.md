# Livrables

## `Demonstration-Assainissement-de-Ouaga.mp4`

Vidéo de démonstration (E23) : 3 min 01 s, 1280 × 720, voix et musique (refaite le 18/11 avec l'appel à la mairie, la vérification signée et le nouvel habillage vert).

- **Images** : les vraies pages de l'outil, filmées dans un navigateur (`outils/filmer.mjs`).
- **Voix** : voix de synthèse française lisant le bandeau de chaque scène, sans le modifier.
  Produite hors ligne par [Piper](https://github.com/OHF-Voice/piper1-gpl) (GPL-3.0) avec la
  voix **« siwis » (qualité medium)**, entraînée sur le corpus SIWIS de l'Université
  d'Édimbourg (<https://datashare.is.ed.ac.uk/handle/10283/2353>), licence **CC BY 4.0**.
- **Musique** : composée par programme dans `outils/musique_de_fond.py` (aucun morceau
  emprunté) ; même licence que le code (AGPL-3.0).
- **Montage** : `outils/monter_video.py` avec ffmpeg.

Pour la refaire, voir `comptes-rendus/T21.md`.
