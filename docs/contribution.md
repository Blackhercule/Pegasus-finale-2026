# Matrice de contribution

Livrable commun exigé par l'énoncé : « matrice de contribution par membre et par couche, avec
les briques réutilisées et leur licence ».

Équipe **PEGASUS** — Université Joseph Ki-Zerbo, Ouagadougou.

| Membre | Présence à la finale |
|---|---|
| **Ye Franck Ahmed** | présent |
| **Latif** | présent |
| **Hussen** | absent de la finale ; a participé au sprint « messagerie souveraine » dont deux briques sont reprises ici |

Nous le disons franchement plutôt que de répartir des contributions fictives : un jury qui
demande à quelqu'un d'expliquer une couche qu'il n'a jamais touchée s'en aperçoit en une
question.

## Qui a fait quoi, couche par couche

Franck et Latif ont travaillé **ensemble sur chaque couche** : il n'y a pas eu de découpage par
personne, mais un travail en binôme du début à la fin. La colonne qui compte est donc la
dernière — **qui est prêt à l'expliquer au jury**, puisque c'est le jury qui désigne.

| Couche | Franck | Latif | Hussen | Qui l'explique |
|---|---|---|---|---|
| Application de signalement (téléphone, hors ligne, vocal, mooré) | ✔ | ✔ | — | Latif |
| Contrôles des signalements et pièges | ✔ | ✔ | — | Latif |
| Masquage des visages et des plaques | ✔ | ✔ | — | Latif |
| Chaîne des postes (mairie, brigade Laabal, collecte) | ✔ | ✔ | — | Franck |
| Fuites d'eau et poste ONEA | ✔ | ✔ | — | Franck |
| Nuisances (caniveaux, abattoirs, toilettes, eaux usées) | ✔ | ✔ | — | Franck |
| Préparation des données OpenStreetMap | ✔ | ✔ | — | Latif |
| Cartographie hors ligne (MapLibre, PMTiles) | ✔ | ✔ | — | Latif |
| Plan de gestion : points de regroupement et tournées | ✔ | ✔ | — | Latif |
| Simulation multi-agents | ✔ | ✔ | — | Latif |
| Interface de décision et scénarios | ✔ | ✔ | — | Franck |
| Accès, comptes et sécurité | ✔ | ✔ | — | Franck |
| Déploiement en une commande, HTTPS local | ✔ | ✔ | ✔ (sprint) | Franck |
| Tests automatisés | ✔ | ✔ | — | Latif |
| Documentation et rapport | ✔ | ✔ | — | Franck |

> **À relire par l'équipe avant la remise.** La colonne « qui l'explique » est une répartition
> de travail, pas une excuse : le jury désigne lui-même qui répond, et ne pas savoir est
> éliminatoire. Chacun doit pouvoir expliquer **au moins** les couches où son nom est dans
> cette colonne, et avoir une idée juste des autres.

## Briques réutilisées

Aucune cryptographie ni aucun algorithme d'optimisation n'a été réinventé : on adopte des
briques éprouvées, on les adapte à Ouagadougou, et on écrit ce qui manque entre elles.

### Bibliothèques et outils

| Brique | Rôle | Licence | Lien |
|---|---|---|---|
| Flask | application et API | BSD-3-Clause | https://flask.palletsprojects.com/ |
| gunicorn | serveur d'application | MIT | https://gunicorn.org/ |
| SQLite | stockage | domaine public | https://sqlite.org/ |
| Shapely | géométrie | BSD-3-Clause | https://github.com/shapely/shapely |
| pyproj | projections | MIT | https://github.com/pyproj4/pyproj |
| SciPy | trajets sur le réseau (Dijkstra) | BSD-3-Clause | https://scipy.org/ |
| NumPy | calcul numérique | BSD-3-Clause | https://numpy.org/ |
| Mesa | simulation multi-agents | Apache-2.0 | https://github.com/projectmesa/mesa |
| pyosmium | lecture des extraits OpenStreetMap | BSD-2-Clause | https://osmcode.org/pyosmium/ |
| OpenCV | masquage des visages et des plaques | Apache-2.0 | https://opencv.org/ |
| MapLibre GL JS | carte | BSD-3-Clause | https://maplibre.org/ |
| PMTiles | fond de carte en un fichier | BSD-3-Clause | https://github.com/protomaps/PMTiles |
| Protomaps basemaps | style de la carte | BSD-3-Clause | https://github.com/protomaps/basemaps |
| Lato | police de l'interface | OFL-1.1 | https://www.latofonts.com/ |
| Noto Sans | police des étiquettes de la carte | OFL-1.1 | https://fonts.google.com/noto |
| Caddy | HTTPS local, autorité interne | Apache-2.0 | https://caddyserver.com/ |
| Docker | déploiement en une commande | Apache-2.0 | https://www.docker.com/ |
| pytest | tests | MIT | https://pytest.org/ |
| Playwright | essais dans un navigateur, tournage de la vidéo | Apache-2.0 | https://playwright.dev/ |
| ffmpeg | montage de la vidéo | LGPL-2.1+ | https://ffmpeg.org/ |

### Algorithmes repris

| Algorithme | Rôle | Source |
|---|---|---|
| Clarke et Wright (1964), « savings » | tournées des camions | article fondateur, domaine public |
| 2-opt | amélioration des tournées | classique, domaine public |
| Dijkstra | trajets sur le réseau de voies | via SciPy |
| Couverture gloutonne | emplacement des points de regroupement | classique |
| Cascades de Haar | détection des visages et des plaques | livrées avec OpenCV, Apache-2.0 |

### Notre propre travail antérieur

Repris du sprint « messagerie souveraine » de la même équipe
(dépôt `Blackhercule/Messagerie-souveraine`, commit `431bb09`), auquel **Hussen** a participé :

| Brique | Ce qu'on en reprend |
|---|---|
| `installer.sh` | l'installation en une commande, la génération des secrets dans `.env`, l'option `--changer-adresse`, et les précautions propres à Windows |
| `caddy/` | le HTTPS local avec autorité de certification interne et `default_sni`, pour que les téléphones du réseau accèdent à l'outil |

Réutiliser son propre travail est permis et de bonne pratique ; le cacher ne le serait pas.

### Données

| Donnée | Licence | Source |
|---|---|---|
| Fond de carte et objets cartographiques | ODbL | © les contributeurs d'OpenStreetMap |
| Jeu de signalements produit par l'outil | ODbL | notre collecte de terrain, compatible pour le versement dans OpenStreetMap |

## Licence de notre code

**AGPL-3.0** (`LICENSE` à la racine). Le dépôt est public : tout ce qui est produit ici est un
bien commun réutilisable par une autre commune.

## Outillage

Le développement s'est fait avec l'assistance d'un modèle de langage (Claude), ce que portent
les en-têtes `Co-Authored-By` de l'historique Git. Toute la conception, les décisions et la
vérification sont celles de l'équipe, et chaque membre répond du code qui porte son nom dans la
matrice ci-dessus.

> **À confirmer avec les organisateurs** : l'énoncé ne dit pas si les assistants de
> programmation sont autorisés en finale. La question est posée dans `ENONCE.md`. Si la réponse
> est non, cette section et l'historique Git disent déjà la vérité — c'est le bon ordre des
> choses.
