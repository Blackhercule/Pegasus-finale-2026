# Soumission

Préparé par le coordinateur au fil du hackathon, pour n'avoir plus qu'à copier-coller dans le
formulaire. Responsable de la soumission dans l'équipe : _à désigner_.

## Textes prêts à coller

- **Nom du projet** : Assainissement de Ouaga — outil libre d'aide à la décision
- **Équipe** : PEGASUS — Université Joseph Ki-Zerbo (UJKZ)
- **Membres** : YE Franck Ahmed, TRAORE Hussen Izedine, KIEMA Abdoul-Latif
- **Description courte** : Du signalement des dépotoirs sauvages jusqu'au plan de gestion de la ville, avec simulation de tous les acteurs. Installé en une commande sur une seule machine, il fonctionne sans Internet.
- **Description longue** : voir `docs/proposition.md`. En résumé : nous adoptons des briques
  open source éprouvées (OpenStreetMap, MapLibre, SciPy, Mesa), nous les adaptons à Ouagadougou
  (limites de la commune, réseau de voies revêtues ou non, saison des pluies, acteurs réels de
  la filière), et nous ajoutons ce qui manque entre elles : des contrôles qui écartent les
  signalements piégés en expliquant pourquoi, un plan qui se recalcule en cinq secondes et
  affiche ses propres contrôles de cohérence, la comparaison de scénarios, et l'export vers
  OpenStreetMap.
- **Lien du dépôt** : https://github.com/Blackhercule/Pegasus-finale-2026  (à rendre public avant la soumission)
- **Lien ou fichier de la vidéo** : `Demonstration-Assainissement-de-Ouaga.mp4` (2 min 12 s) — refaire avec `outils/filmer.mjs` puis `outils/monter_video.py`
- **Présentation** :

## Avant d'envoyer

- [ ] Le dernier `git push` est fait et le dépôt est **public** (si l'énoncé le demande).
- [ ] Le `README.md` explique comment installer et lancer le projet.
- [ ] Chaque exigence obligatoire de `ENONCE.md` est couverte, ou son absence est expliquée.
- [ ] La vidéo et la présentation respectent le format et la taille demandés.
- [ ] Aucun secret (mot de passe, clé, `.env`) n'est dans le dépôt.
- [ ] La soumission part au moins deux heures avant la limite.
- [ ] Une capture d'écran de la confirmation est gardée.
