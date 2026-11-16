# Tâches

Écrit par le coordinateur. Claude Code répond dans `comptes-rendus/` (un fichier par tâche) et
ne modifie pas ce fichier.

- `T…` : une tâche à réaliser. `C…` : un correctif signalé par l'équipe.
- `E…` : une exigence de `ENONCE.md`. La référence technique est `docs/conception.md`.
- **[PC]** : à faire sur le PC de l'équipe uniquement. **[cloud ou PC]** : au choix.

| Tâche | Sujet | Où | État |
|---|---|---|---|
| T0, T1, T2 | Relevé du poste, socle d'identité du sprint | | **Annulées** : sans objet pour le challenge 01 |
| T3 | Données de Ouagadougou et fond de carte hors ligne | PC | **Fait** (16/11, 11 h). 526 km², 111 840 nœuds, 166 611 tronçons, 332 556 bâtiments, 440 plans d'eau, 226 sites de déchets d'OpenStreetMap, fond `fond.pmtiles` (16,7 Mo) |
| T4 | Signalements : réception, contrôles anti-pièges, page mobile | coordinateur | **Fait**, vérifié dans un navigateur : contrôles, regroupement en dépotoirs, page mobile avec envoi différé hors ligne |
| T5 | Carte de décision | coordinateur | **Fait**, vérifiée dans un navigateur : aucune requête vers Internet |
| T6 | Plan de gestion : points de regroupement, tournées, cohérence | coordinateur | **Fait**, vérifié dans un navigateur : recalcul en 5 s, camions en panne et saison des pluies dégradent le plan proprement |
| T7 | Simulation multi-agents | coordinateur | **Fait** : 4 498 ménages, 224 pré-collecteurs, brigade Laabal, mairie ; 30 jours en 0,2 s, reproductible |
| T8 | Scénarios : paramètres du jury, comparaison | coordinateur | **Fait** : page de comparaison avec tableau et graphique |
| T9 | Bien commun : export OpenStreetMap, autre commune | coordinateur | **Fait** : export .osm des dépotoirs vérifiés, à relire avant versement ; une autre commune se prépare avec la même commande |
| T10 | Installation en une commande, HTTPS, téléphones | PC | Écrit et poussé ; **jamais lancé sur le PC** — c'est le dernier inconnu |
| T11 | Essai complet sur le PC de l'équipe | PC | À faire : `./installer.sh`, puis essai depuis un téléphone |

**Important.** Depuis le 16/11 au matin, c'est le coordinateur qui écrit le code (les sessions de
Claude Code se heurtaient à la limite d'utilisation). Avant de commencer quoi que ce soit : fais
`git pull`, lis ce tableau, et ne refais rien de ce qui est marqué « Fait ». Si une tâche t'est
demandée alors qu'elle est déjà faite, dis-le au lieu de la refaire.

## Ce qui existe déjà dans le dépôt

| Dossier | Contenu |
|---|---|
| `donnees/preparer.py`, `donnees/fond_de_carte.py`, `preparer-ouagadougou.sh` | Préparation des données d'une commune et du fond de carte |
| `donnees/ouagadougou/` | Les fichiers de la commune, déjà produits |
| `application/` | Application Flask : `geo.py` (dans la commune ? dans l'eau ?), `reseau.py` (durées de trajet), `signalements/` (contrôles, dépotoirs), API |
| `interface/signaler/` | Page mobile de signalement, utilisable hors ligne |
| `interface/decision/` | Carte de décision |
| `interface/vendor/` | Bibliothèques de la carte, servies par notre machine |



---

## T3 — Données de Ouagadougou et fond de carte hors ligne [PC]

> **État au 16/11, 11 h.** La session du PC a été arrêtée par la limite d'utilisation avant
> d'écrire le script. Le coordinateur a donc écrit et testé `donnees/preparer.py`,
> `donnees/fond_de_carte.py` et `preparer-ouagadougou.sh`, et copié les bibliothèques de la carte
> dans `interface/vendor/`. **Ne les réécris pas.** Il reste à lancer `./preparer-ouagadougou.sh`
> sur le PC, ce que Franck fait à la main. La page d'essai (point 4) passe dans la tâche T5.

**Pourquoi.** Rien ne fonctionne sans la carte : ni les contrôles (dans la commune ? dans un
barrage ?), ni les tournées, ni la simulation. L'énoncé exige de ne dépendre d'aucune donnée
indisponible (E14) et de s'appuyer sur OpenStreetMap et Open Buildings (E6). Le réseau de la
salle est partagé entre seize équipes : ces téléchargements se font maintenant, une fois, et
leurs résultats vont dans le dépôt pour que toutes les sessions, y compris dans le cloud, les
aient par un simple `git pull`.

**À faire.**

1. **Relevé du poste**, dans le compte rendu : mémoire vive, espace disque libre, versions de
   `git`, `docker`, `python`, `node` et `java` (« absent » si l'outil manque), images Docker
   présentes. N'installe rien pour ce relevé.
2. **`donnees/preparer.py`** : à partir d'un extrait OpenStreetMap `.osm.pbf` et d'une commune
   (nom, et sa limite administrative trouvée dans l'extrait), il écrit dans `donnees/<commune>/`
   les fichiers décrits dans `docs/conception.md`, section « Fichiers d'une commune » :
   `commune.json`, `commune.geojson`, `secteurs.geojson`, `eau.geojson`, `reseau_noeuds.csv.gz`,
   `reseau_troncons.csv.gz`, `zones.geojson`, `lieux.geojson`.
   - Source : l'extrait du Burkina Faso de Geofabrik,
     `https://download.geofabrik.de/africa/burkina-faso-latest.osm.pbf`. L'extrait brut n'est pas
     mis dans le dépôt (ajoute-le à `.gitignore`) ; note sa date et sa taille.
   - Le réseau ne garde que les voies où un camion ou une charrette peut passer, et seulement sa
     plus grande partie d'un seul tenant, pour qu'un trajet existe toujours entre deux points.
   - Les bâtiments viennent d'OpenStreetMap. Si le téléchargement d'Open Buildings pour la zone
     est rapide, complète avec lui les carreaux où OpenStreetMap n'a aucun bâtiment ; sinon
     note-le comme reste à faire, sans y passer plus de vingt minutes.
   - Le script doit pouvoir servir à une autre commune sans être modifié (E13) : le nom de la
     commune et le chemin de l'extrait sont des arguments.
3. **Fond de carte** `donnees/ouagadougou/fond.pmtiles`, zooms 0 à 15, sur l'emprise de la
   commune avec une marge : extrait du fond Protomaps avec l'outil `pmtiles extract`. Copie dans
   `interface/vendor/` tout ce qu'il faut pour l'afficher sans Internet : MapLibre GL JS (script
   et feuille de style), `pmtiles`, le style Protomaps, les polices et les pictogrammes
   (`protomaps/basemaps-assets`). Note la version et la licence de chaque élément.
   - Si le fond Protomaps est inaccessible ou trop lent d'ici, ne t'acharne pas : fabrique un
     fond simple à partir de nos propres fichiers (voies par classe, eau, limites), et dis-le.
4. **Page d'essai** `interface/decision/carte-essai.html` : le fond de carte centré sur
   Ouagadougou, avec la limite de la commune et les plans d'eau par-dessus. Elle ne doit faire
   aucune requête vers Internet.
5. **Dépôt.** Mets les fichiers produits dans le dépôt si chacun pèse moins de 40 Mo. Au-delà,
   ne force pas : dis lequel dépasse et de combien.

**Réussi si**, sur le PC :

- `python donnees/preparer.py --aide` explique les arguments, et un lancement complet pour
  Ouagadougou se termine en affichant le nombre de nœuds, de tronçons, de carreaux bâtis, de
  secteurs et de plans d'eau, ainsi que la surface de la commune en km² ;
- un trajet calculé entre deux coins opposés de la ville existe (le réseau est d'un seul tenant) ;
- la page d'essai affiche Ouagadougou avec le Wi-Fi coupé, ou bien l'onglet « Réseau » du
  navigateur ne montre aucune requête hors de la machine ;
- tout est poussé, et le compte rendu liste les fichiers avec leur taille.

**À ajouter au compte rendu** : le relevé du poste ; les niveaux administratifs trouvés pour les
arrondissements et les secteurs ; ce qu'OpenStreetMap contient déjà sur les déchets à Ouagadougou
(décharge, centres de collecte, bacs) ; la part des tronçons dont le revêtement est connu ; la
durée de chaque téléchargement.

---

## T4 — Signalements : réception, contrôles anti-pièges, page mobile [cloud ou PC]

**Pourquoi.** C'est le début de la chaîne et la première moitié de l'épreuve : le jury injecte
des signalements piégés (E10), et seuls les signalements vérifiés doivent apparaître sur la
carte (E1). L'équipe doit aussi collecter de vrais signalements dans son secteur (E7), donc la
page mobile doit exister tôt. Un piège ne doit jamais faire planter le serveur ni entrer dans
le plan : il est écarté, et son motif est affiché.

**À faire.** Suis `docs/conception.md`, sections « Arborescence » et « Signalements » : la
table, les statuts, les motifs, les dépotoirs et l'API y sont fixés.

1. **Application** : paquet `application/` (Flask), base SQLite créée au démarrage, réglages lus
   dans l'environnement, `Dockerfile` et un `docker-compose.yml` avec le seul service
   `application` pour l'instant (Caddy et l'installation viendront avec T10).
2. **Contrôles** : une fonction par motif du tableau de la conception, chacune testée seule.
   Les seuils viennent de `donnees/ouagadougou/parametres.json` (crée-le avec des valeurs par
   défaut raisonnables, marquées « hypothèse »). La limite de la commune et l'eau sont lues dans
   `commune.geojson` et `eau.geojson` ; tant que T3 ne les a pas livrés, les tests utilisent de
   petits polygones d'essai rangés dans `tests/`.
3. **Regroupement en dépotoirs** et passage à `verifie` quand deux sources différentes
   confirment le même dépotoir.
4. **API** : les six adresses de la conception. Le lot accepte un tableau JSON, un GeoJSON ou un
   CSV, et répond ligne par ligne. Les décisions d'un agent (`/verifier`, `/rejeter`) demandent
   une connexion : un compte d'agent, mot de passe lu dans l'environnement et comparé par
   `werkzeug.security`, session Flask, jeton contre les formulaires forgés.
5. **Page mobile** `interface/signaler/` : une seule page en français, utilisable d'une main.
   Position du téléphone avec sa précision affichée, photo prise sur place et réduite avant
   l'envoi, taille et type du dépotoir, commentaire facultatif. Sans réseau, le signalement est
   gardé sur le téléphone et envoyé au retour du réseau ; la page reste ouvrable hors ligne une
   fois chargée. Chaque appareil crée son pseudonyme aléatoire ; aucune donnée personnelle.
6. **Page de vérification** `interface/decision/verifier.html` : la liste des signalements par
   statut, le motif de chaque rejet, les boutons « Vérifier » et « Rejeter », et l'envoi d'un
   fichier de lot.
7. **Jeu de pièges** `tests/pieges.json` : au moins quarante signalements piégés, avec pour
   chacun le motif attendu. Pense à ce qu'un jury de cybersécurité essaierait : coordonnées non
   numériques, infinies, nulles, inversées, à 100 km, au milieu d'un barrage ; dates futures ou
   absurdes ; volumes négatifs ou gigantesques ; champs manquants, en trop, du mauvais type ;
   textes très longs, balises HTML, guillemets et morceaux de SQL ; mille copies du même point ;
   la même source en rafale ; un lot vide ; un fichier qui n'est pas une image.

**Sécurité.** Requêtes SQL toujours paramétrées. Tout texte venu d'un signalement est affiché
échappé, jamais inséré comme du HTML. Taille des requêtes et des photos limitée. Le type d'une
photo se lit dans son contenu, pas dans son nom. En-têtes de sécurité sur chaque réponse, sans
script écrit dans les pages.

**Réussi si** :

- `python -m pytest -q` est vert, avec un test par motif et un test qui envoie tout
  `tests/pieges.json` en un lot : aucun piège n'est pris en compte, chacun reçoit le motif
  attendu, et le serveur ne répond jamais par une erreur 500 ;
- un signalement valide envoyé deux fois n'est compté qu'une fois ; deux signalements proches
  venant de deux sources donnent un seul dépotoir, vérifié ;
- la page mobile ouverte sur `http://localhost` enregistre un signalement, et un signalement
  saisi serveur arrêté part tout seul quand le serveur revient.

**À ajouter au compte rendu** : la liste des pièges et leur motif ; ce que tu n'as pas pu
vérifier sans téléphone ni HTTPS (la position et la caméra exigent HTTPS hors de `localhost` :
cela sera vérifié sur le PC avec T10).
