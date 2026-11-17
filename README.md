# Assainissement de Ouaga — outil libre d'aide à la décision

Du **signalement** des dépotoirs sauvages jusqu'au **plan de gestion** de la ville, avec
**simulation de tous les acteurs**. Tout s'installe en une commande sur une seule machine et
fonctionne **sans Internet**.

Équipe **PEGASUS** — Université Joseph Ki-Zerbo (UJKZ) · Hackathon des Universités 2026,
challenge 01.

> Les signalements de démonstration sont fictifs. Aucune donnée personnelle n'est collectée.

## Ce que fait l'outil

| Étape | Ce qu'on obtient |
|---|---|
| **Signaler** | Une page qui s'ouvre sur n'importe quel téléphone : un **tas d'ordures** (position, photo, taille et superficie, mode de dépôt) ou une **fuite d'eau** (ampleur, quartier). On peut **parler plutôt qu'écrire**, et se faire **guider en mooré**. Elle fonctionne **sans réseau** et envoie toute seule au retour de la connexion. |
| **Vérifier** | Chaque signalement passe treize contrôles automatiques. Un signalement douteux est écarté **avec son motif**, jamais silencieusement. Un agent tranche les cas limites. |
| **Traiter** | Le signalement ouvre un dossier qui passe de poste en poste : mairie, brigade Laabal, mairie, équipe de collecte. Chaque passage est daté et signé. |
| **Alerter l'ONEA** | Une fuite d'eau suit sa propre chaîne : la mairie la confirme et la transmet, l'ONEA déclare la réparation. Un **bordereau CSV** se télécharge pour l'envoi. |
| **Orienter** | Caniveau bouché, abattage clandestin, toilettes vidées en pleine rue, eaux usées de poissonnerie : la mairie reçoit et **oriente vers le service compétent**, que la nature du signalement désigne. |
| **Cartographier** | Les dépotoirs sur un fond OpenStreetMap servi par notre propre machine, avec les 226 sites de déchets déjà cartographiés. |
| **Planifier** | Emplacement des points de regroupement, tournées des camions, jour par jour, avec les coûts. |
| **Simuler** | Ménages, pré-collecteurs, brigade Laabal et mairie, un jour par pas de temps. |
| **Comparer** | On change la population, les abonnements, les camions, la fréquence ou la saison, et on voit l'effet. |
| **Partager** | Les dépotoirs vérifiés s'exportent au format d'OpenStreetMap, pour relecture puis versement. |

## La chaîne de traitement

Un signalement n'envoie pas directement un camion. Il ouvre un dossier qui avance d'un poste à
l'autre, et chaque poste a son compte :

```
  signalé ──► confirmé ──► constat ──► à collecter ──► collecté
 (habitant)   (mairie)    (brigade     (mairie)       (équipe de
                           Laabal)                     collecte)
```

Un poste ne peut faire avancer un dossier que d'un cran, et seulement quand c'est son tour :
la brigade qui tenterait de confirmer à la place de la mairie se voit refuser. La mairie peut
aussi classer un dossier sans suite, avec son motif. Tout est relisible dans le journal du
dossier : qui, quand, quoi.

## Les fuites d'eau, et pourquoi elles sont là

Une conduite percée n'est pas qu'une affaire de plomberie. L'eau qui coule des jours durant
fait une mare : la mare élève des moustiques, détrempe la chaussée qui se creuse, et quand elle
atteint un tas d'ordures elle en emporte le jus dans les caniveaux. C'est un problème
d'assainissement avant d'être un problème de réseau.

Mais la mairie ne touche pas aux conduites : seul l'**ONEA** intervient sur les siennes. L'outil
fait donc ce qu'il peut faire — recevoir, confirmer, transmettre, et garder la trace :

```
  signalée  ──►  transmise à l'ONEA  ──►  réparée
 (habitant)      (agent de la mairie)      (ONEA)
```

Une fuite n'entre **jamais** dans les tournées des camions : ce n'est pas un tas à ramasser.
Elle est signalée depuis la même page que les dépotoirs, elle subit **les mêmes contrôles** de
position et de date, et deux appareils qui signalent la même fuite la confirment, comme pour un
dépotoir. L'ampleur retenue est la **plus grave** signalée : entre « ça suinte » et « la rue est
noyée », c'est la seconde qui décide de l'urgence.

Le bordereau à transmettre est un fichier **CSV** (`/api/export/onea`), pas un envoi
automatique : l'outil ne sort pas de la machine (E14), et l'ONEA n'a pas d'interface publique de
dépôt. Un agent l'imprime ou l'envoie, et note en retour le numéro que l'ONEA lui donne.

## Six choses à signaler, trois destinations

Tout ne se ramasse pas, et tout ne relève pas du même service. C'est la **nature** du
signalement qui décide où il va :

| Ce qu'on signale | Qui intervient après la mairie |
|---|---|
| Tas d'ordures | les tournées des camions |
| Fuite d'eau sur une conduite | **ONEA** |
| Caniveau bouché | **équipe de collecte** (curage) |
| Déversement de toilettes en plein air | **ONEA** (assainissement) |
| Abattage clandestin d'animaux | **brigade Laabal** (constat, verbalisation) |
| Eaux usées de poisson et de poulet | **brigade Laabal** |

Cette répartition est une hypothèse de l'équipe, **à confirmer avec la mairie** : la changer
demande de modifier une ligne par nature dans `application/nuisances.py`, rien d'autre.

Deux règles valent pour toutes les natures. Le regroupement ne se fait qu'**à nature égale** :
un caniveau bouché et un abattage clandestin au même carrefour sont deux problèmes, deux
services, deux dossiers. Et la gravité retenue est la **plus forte** signalée, jamais la
moyenne : entre « un peu bouché » et « ça déborde dans la rue », c'est la seconde qui décide
de l'ordre de passage.

## Parler plutôt qu'écrire, et comprendre le mooré

- **Message vocal** : on décrit le lieu à la voix, en mooré, en dioula ou en français. Un agent
  de la mairie l'écoute depuis son poste. Aucune transcription automatique n'est tentée : il
  n'en existe pas de fiable hors ligne pour ces langues, et une fausse transcription serait pire
  que pas de transcription.
- **Guidage parlé en mooré** : un bouton fait parler chaque étape. Ce sont de **vrais
  enregistrements** faits par un locuteur natif (`interface/signaler/audio/moore/`), pas de la
  synthèse vocale. Une personne qui ne lit pas peut ainsi signaler de bout en bout.

## Les visages et les plaques sont masqués avant d'être enregistrés

Quelqu'un qui passe derrière un tas d'ordures n'a rien demandé à personne. Son visage ne doit
pas finir dans une base municipale parce qu'il passait là, et une plaque d'immatriculation
désigne un propriétaire.

Chaque photo de signalement est donc analysée **à la réception**, et les visages et plaques
trouvés sont noyés sous un flou épais. Le point qui compte : **l'image d'origine ne touche
jamais le disque** — pas de fichier temporaire, pas de copie « au cas où ». C'est la différence
entre masquer et cacher, et c'est vérifiable : relisez le fichier enregistré, le visage n'y est
plus.

Tout se fait sur la machine, hors ligne : les détecteurs sont livrés dans OpenCV, rien n'est
envoyé nulle part.

**Ce que la détection rate**, parce qu'il vaut mieux le dire que le laisser découvrir : un
visage vu très de côté, un visage minuscule au fond de l'image, une plaque dont le format
s'éloigne de ceux sur lesquels les détecteurs ont été entraînés. Chaque photo affiche donc à
l'agent combien de zones ont été masquées, et il peut en masquer d'autres à la main.

**Et ce qu'elle voit de trop.** Les détecteurs de plaques se déclenchent volontiers sur
n'importe quel rectangle contrasté : une planche, une banderole, un panneau. Sur une photo de
dépotoir il y en a partout, et masquer au hasard effacerait le tas d'ordures lui-même,
c'est-à-dire ce que le signalement apporte. Chaque zone trouvée est donc écartée si sa forme ou
sa taille ne colle pas à ce qu'on cherche. Sur nos photos d'essai, ce filtre a supprimé trois
fausses plaques sur trois, sans faire perdre un seul visage.

Deux exceptions, et elles sont voulues : la photo de CNIB et le portrait du déclarant ne sont
pas floutés. Ce sont les pièces qu'il a **choisi** de donner pour être témoin ; les flouter les
viderait de leur sens. Elles ne sont jamais servies au public et s'effacent à la clôture du
dossier.

## Identité du déclarant : facultative

Le signalement fonctionne **sans donner son nom**. Qui accepte d'être témoin dans une procédure
peut ajouter son nom, son téléphone, une photo de sa CNIB et une photo de lui-même. Ces
renseignements :

- ne sont **jamais servis au public** : il faut être un agent connecté pour les voir ;
- sont rangés à part des photos de dépotoirs, dans un dossier servi sous contrôle ;
- s'effacent en un clic à la clôture du dossier, depuis le poste de la mairie.

## Installation

Il faut **Docker** (Docker Desktop sous Windows) et, pour la première préparation des données,
une connexion à Internet.

```bash
git clone https://github.com/Blackhercule/Pegasus-finale-2026
cd Pegasus-finale-2026
./preparer-ouagadougou.sh      # données de la commune + fond de carte (une seule fois)
./installer.sh                 # construit et démarre tout
```

Pour que les téléphones du réseau local y accèdent, donnez l'adresse IP du poste :

```bash
./installer.sh --changer-adresse 192.168.1.20
```

L'installateur affiche ensuite les adresses et le mot de passe de l'agent :

- carte de décision : `https://<adresse>:8443/decision/`
- postes de travail (mairie, brigade, collecte) : `https://<adresse>:8443/decision/dossiers.html`
- caniveaux, abattoirs, eaux usées : `https://<adresse>:8443/decision/nuisances.html`
- fuites d'eau (mairie et ONEA) : `https://<adresse>:8443/decision/fuites.html`
- vérification des signalements : `https://<adresse>:8443/decision/verifier.html`
- simulation : `https://<adresse>:8443/decision/simulation.html`
- comparaison de scénarios : `https://<adresse>:8443/decision/scenarios.html`
- signalement (téléphone) : `https://<adresse>:8443/signaler/`

L'installateur affiche un mot de passe par poste. Ils sont tirés au hasard et rangés dans
`.env`, qui n'est jamais publié.

Le HTTPS s'appuie sur une **autorité de certification interne**, créée sur la machine. Installez
`ca-assainissement.crt` sur les postes et les téléphones (`certutil -user -addstore Root
ca-assainissement.crt` sous Windows) : sans lui, un navigateur de téléphone refuse de donner la
position et l'appareil photo.

Une autre commune se prépare avec la même commande :

```bash
python donnees/preparer.py --extrait pays.osm.pbf --commune Bobo-Dioulasso
```

## Comment c'est construit

```
 Téléphone ─┐                            ┌─ cartographie ── MapLibre + fond PMTiles (hors ligne)
            ├─ HTTPS :8443 ─ Caddy ─ Flask ├─ contrôles ───── Shapely (dans la commune ? dans l'eau ?)
 Navigateur ┘                  │          ├─ plan ────────── SciPy (trajets) + nos algorithmes
                               │          └─ simulation ──── Mesa (agents)
                            SQLite
```

Deux conteneurs seulement, sur un réseau sans accès à Internet. Aucun service tiers n'est
nécessaire au fonctionnement : ni carte en ligne, ni API externe, ni police chargée d'ailleurs.

### Les deux algorithmes, en une phrase chacun

- **Où poser les points de regroupement** : couverture gloutonne. À chaque tour on ouvre
  l'emplacement qui dessert le plus de déchets encore non couverts, à moins de 800 m d'un
  carreau habité.
- **Quelles tournées** : algorithme des économies de **Clarke et Wright (1964)**. On part d'un
  aller-retour par arrêt, puis on fusionne les tournées qui font gagner le plus de trajet, tant
  que la benne et la journée de travail le permettent. Les tournées sont enfin réparties entre
  les camions ; ce qui ne rentre pas est **laissé de côté et nommé**.

Aucune cryptographie ni aucun algorithme d'optimisation n'a été réinventé : on adopte des
briques éprouvées, on les adapte à Ouagadougou, et on ajoute ce qui manque entre elles.

## Face à l'épreuve en direct

- **Signalements piégés** : ils passent par les mêmes contrôles que les autres, fuites d'eau comprises. Coordonnées
  inversées, point (0, 0), latitude « abc », date dans le futur, volume négatif ou démesuré,
  point au milieu d'un barrage, mille copies du même tas, champs manquants ou de mauvais type,
  fichier audio qui n'en est pas un : chacun est écarté avec son motif, et le serveur ne tombe
  jamais. Le jeu d'essai (`tests/pieges.json`) en contient 42.
- **Changement de paramètres** : camions en panne, saison des pluies, nouveau quartier sont de
  simples paramètres. Le plan se recalcule en 5 secondes et affiche ses propres contrôles de
  cohérence : capacité des camions, durée de travail, arrêts non desservis (nommés), points
  saturés, budget.

## Technologies et licences

| Brique | Rôle | Licence |
|---|---|---|
| [Flask](https://flask.palletsprojects.com/) + [gunicorn](https://gunicorn.org/) | application et API | BSD-3, MIT |
| [SQLite](https://sqlite.org/) | stockage | domaine public |
| [Shapely](https://github.com/shapely/shapely), [pyproj](https://github.com/pyproj4/pyproj) | géométrie et projections | BSD-3, MIT |
| [SciPy](https://scipy.org/), [NumPy](https://numpy.org/) | trajets sur le réseau, calculs | BSD-3 |
| [Mesa](https://github.com/projectmesa/mesa) | simulation multi-agents | Apache-2.0 |
| [pyosmium](https://osmcode.org/pyosmium/) | lecture des extraits OpenStreetMap | BSD-2 |
| [MapLibre GL JS](https://maplibre.org/), [PMTiles](https://github.com/protomaps/PMTiles), [Protomaps basemaps](https://github.com/protomaps/basemaps) | carte hors ligne | BSD-3 |
| [Lato](https://www.latofonts.com/) | police de l'interface | OFL-1.1 |
| [Noto Sans](https://fonts.google.com/noto) (via `smp-noto-glyphs`) | polices de la carte | OFL-1.1, paquet MIT |
| [OpenCV](https://opencv.org/) | masquage des visages et des plaques | Apache-2.0 |
| [Caddy](https://caddyserver.com/) | HTTPS local | Apache-2.0 |
| [Docker](https://www.docker.com/) | déploiement en une commande | Apache-2.0 |

Données cartographiques © les contributeurs d'**OpenStreetMap**, licence **ODbL**.
Notre code est publié sous **AGPL-3.0** (`LICENSE`).

## Limites connues

- Les **paramètres de départ sont des hypothèses** tant que la mairie ne nous a pas donné les
  siens : population, production par habitant, flotte, budget, tarif d'abonnement. Ils se
  changent tous dans `donnees/ouagadougou/parametres.json`, sans toucher au code.
- La **décharge principale** est déduite d'OpenStreetMap (le groupe de sites le plus dense) :
  à confirmer avec la mairie.
- Les **arrondissements et secteurs** ne sont pas cartographiés dans l'extrait OpenStreetMap
  utilisé : les carreaux n'ont donc pas de secteur rattaché.
- La répartition de la population au prorata de la **surface bâtie** est une approximation :
  un quartier d'entrepôts est compté comme un quartier d'habitation.
- Les distances entre un ménage et son point de regroupement sont prises **à vol d'oiseau** ;
  les tournées des camions, elles, suivent le vrai réseau de voies.

## Pour les développeurs

```bash
pip install -r requirements.txt
python -m pytest tests/ -q        # 175 tests : contrôles, pièges, chaînes, plan, simulation, fuites, export
```

| Dossier | Contenu |
|---|---|
| `application/` | l'application : `geo.py`, `reseau.py`, `signalements/`, `dossiers.py`, `fuites.py`, `nuisances.py`, `anonymiser.py`, `plan/`, `simulation/` |
| `interface/` | pages servies telles quelles ; `vendor/` contient les bibliothèques de la carte |
| `donnees/` | préparation des données d'une commune et fichiers produits |
| `tests/` | tests automatisés, dont le jeu de 42 signalements piégés |
| `docs/` | proposition de l'équipe, conception, note sur les données |
