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
| T11 | Essai complet sur le PC de l'équipe | PC | Fait en partie : l'installation tourne sur le PC, port 8444. Reste l'essai depuis un téléphone |
| — | Chaîne des postes (mairie, brigade Laabal, collecte), identité facultative, guidage mooré | coordinateur | **Fait** (16/11) |
| — | Fuites d'eau et poste ONEA, bordereau CSV | coordinateur | **Fait** (16/11) |
| — | Nuisances : caniveaux, abattage clandestin, toilettes en plein air, eaux usées animales | coordinateur | **Fait** (16/11) |
| — | Habillage : police Lato, couleurs des portails de l'administration | coordinateur | **Fait** (16/11) |
| — | Quatre écrans d'accueil parlés avant le formulaire de signalement | coordinateur | **Fait** (16/11). Les enregistrements mooré restent à faire par l'équipe |
| C1 | Trois erreurs 500 et limite des essais de mot de passe | coordinateur | **Fait** (16/11) |
| C2 | Un lot ne doit pas pouvoir confirmer son propre dépotoir | coordinateur | **Fait** (16/11) |
| C3 | L'installateur ne se déclarait plus prêt depuis T13 | coordinateur | **Fait** (17/11) |
| T17 | Masquer visages et plaques sur les photos | coordinateur | **Fait** (17/11), éprouvé sur de vraies photos |
| T18 | Matrice de contribution par membre et par couche | coordinateur | **Fait** (17/11) — `docs/contribution.md`, **à relire par l'équipe** |
| T19 | Jeu de signalements en GeoJSON sous licence ouverte | — | **À faire — livrable officiel manquant** |
| T20 | Rapport technique unique | Claude Code | **Fait** (17/11) |
| T21 | Vidéo de démonstration de 3 minutes | Claude Code | **Fait** (17/11), 2 min 52 s |
| — | File priorisée, tournées d'inspection, connexion par rôle, comptes individuels | coordinateur | **Fait** (17/11) |
| T22 | Refonte de l'interface en plateforme web professionnelle | Claude Code | **Fait** (17/11), six pages vérifiées par le coordinateur et fusionnées |
| C4 | Une base déjà installée ne recevait pas les colonnes `lot` et masquage | coordinateur | **Fait** (17/11) |
| C5 | La construction Docker reprend un téléchargement coupé | coordinateur | **Fait** (17/11) |
| C6 | Une date absurde (piège 2001) ne date plus le dossier entier | coordinateur | **Fait** (17/11), relevé par Claude Code pendant T22 |
| T12 | Page d'accueil publique | Claude Code | **Fait** (16/11), vérifié par le coordinateur |
| T13 | Partie décision protégée par identifiant et mot de passe | Claude Code | **Fait** (16/11), vérifié et fusionné. Correctif C1 ajouté par-dessus |
| T14 | Habillage de la partie décision : barre horizontale, menu ☰, drapeau | Claude Code | **Fait** (16/11), vérifié. Reste la bande grise au bord du fond de carte |
| T15 | Les tournées suivent les rues, comme un GPS | Claude Code | **Fait** (16/11), vérifié : 142 tournées tracées, médiane de 80 points. Recalcul 6 à 7 s — **à remesurer sur le PC** |
| T16 | Choisir un lieu connu quand la position ne marche pas | Claude Code | **Fait** (16/11), vérifié : 1 187 lieux, recherche sans accent, position imposée par le serveur |

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


---

# Tâches du 16/11 au soir — demandées par Franck

Ces cinq tâches viennent d'une même demande. **Lis-les toutes avant d'en commencer une** : T12,
T13 et T14 touchent les mêmes fichiers, et les faire dans l'ordre évite de se marcher dessus.

L'ordre conseillé est **T13 → T12 → T14 → T16 → T15**, et chacune se termine par son propre
commit : si l'une casse quelque chose, on revient dessus sans perdre les autres.

Toutes sont **[cloud ou PC]**. Aucune ne demande de téléchargement. Rappel des règles du
projet : rien ne se charge depuis Internet à l'exécution (E14), tout est en français, pas de
cryptographie écrite par nous, et le code doit pouvoir être expliqué par n'importe quel membre
de l'équipe au jury.

## T13 — La partie décision protégée par identifiant et mot de passe

**Pourquoi.** Aujourd'hui, la carte de décision, le plan de gestion et les chiffres de la ville
sont servis à qui connaît l'adresse. Seul le **signalement** doit rester ouvert à tous : c'est
la partie qui s'adresse à l'habitant. Tout le reste s'adresse à la mairie, à la brigade Laabal,
à l'équipe de collecte et à l'ONEA, et doit demander à savoir qui entre.

**Ne crée aucun mécanisme nouveau.** Les comptes existent déjà (`application/reglages.py`,
quatre postes, mots de passe tirés par `installer.sh` et rangés dans `.env`), la session et le
jeton anti-CSRF aussi, et `@agent_requis` sait déjà filtrer par poste. Il s'agit d'étendre ce
qui marche, pas d'inventer.

**Ce qui doit rester public**, sans quoi la démonstration ne marche plus :

- la page `/signaler/` et tout ce qu'elle charge : son script, sa feuille de style, son
  `service-worker.js`, son manifeste, ses audios, `/vendor/…` ;
- `POST /api/signalements` et `POST /api/signalements/lot` — c'est par là que les habitants
  **et le jury** envoient leurs signalements, pièges compris ;
- `GET /api/fichiers/public/…` (les photos de dépotoirs). Les fichiers `prive/` demandent déjà
  une session : n'y touche pas.

**Ce qui doit être protégé** : toutes les pages `/decision/…` et toutes les adresses d'API
qu'elles utilisent — `/api/depotoirs`, `/api/plan`, `/api/scenario`, `/api/comparer`,
`/api/parametres`, `/api/comptes`, `/api/chaine`, `/api/dossiers…`, `/api/fuites…`,
`/api/nuisances…`, `/api/export/…`.

Écris le filtre **en liste blanche**, pas en liste noire : tout est protégé sauf ce qui est
explicitement ouvert. Une liste noire laisse passer la prochaine adresse qu'on ajoutera en
l'oubliant, et un jury de cybersécurité cherche exactement cela.

Quand une page `/decision/…` est demandée sans session, sers une page de connexion
(`interface/decision/connexion.html`) qui, une fois le mot de passe accepté, renvoie à la page
demandée. Quand c'est une adresse d'API, réponds **401** avec un JSON : les pages savent déjà
le traiter (`montrerConnexion`).

**Réussi si** :

- `python -m pytest -q` est vert, avec de nouveaux tests qui vérifient, sans session, que
  chaque adresse protégée répond 401 et que chaque adresse publique répond normalement ;
- un test parcourt la liste des routes de Flask et **échoue si une route n'est ni dans la liste
  blanche ni protégée** : c'est ce test qui empêchera d'oublier la prochaine ;
- dans un navigateur : `/decision/` sans session montre la connexion ; après connexion, la
  carte s'affiche ; `/signaler/` fonctionne toujours sans aucune connexion.

**À mettre dans le compte rendu** : la liste blanche exacte, et un rappel bien visible que
**le jury devra se connecter pour voir la carte** — l'équipe doit avoir le mot de passe sous la
main le jour de la démonstration.

## T12 — Une page d'accueil publique

**Pourquoi.** Quelqu'un qui reçoit l'adresse ne sait pas où il tombe. Aujourd'hui `/` ouvre
directement la carte de décision — qui, après T13, demandera un mot de passe : la première
chose que verrait un habitant serait donc un refus.

**Ce qu'il faut.** Une nouvelle page servie à `/`, dans `interface/accueil/`. Elle dit en
quelques lignes ce qu'est l'outil et à qui il s'adresse, puis offre **deux portes** :

1. un grand bouton **« Signaler »** vers `/signaler/` — c'est l'action principale, il doit être
   le plus gros élément de la page, lisible par quelqu'un qui ne lit pas bien ;
2. un lien plus discret **« Espace des services »** vers `/decision/`, pour la mairie, la
   brigade Laabal, l'équipe de collecte et l'ONEA.

Montre aussi, sans connexion, **trois chiffres publics** : le nombre de signalements reçus, le
nombre de dépotoirs recensés, le nombre de dossiers traités. Ajoute pour cela une seule adresse
publique `GET /api/publics` qui ne renvoie que ces trois nombres — **jamais de position, jamais
de détail**, sinon T13 ne sert plus à rien.

**Ne change rien à la page de signalement** : ni son parcours, ni ses quatre écrans d'accueil
parlés, ni son fonctionnement hors ligne. Franck y tient.

**Réussi si** : `/` ouvre la page d'accueil sans aucune connexion ; le bouton mène au
formulaire qui fonctionne comme avant ; les trois chiffres s'affichent ; un test vérifie que
`/api/publics` ne renvoie que trois nombres.

## T14 — Habillage de la partie décision : barre horizontale, menu ☰, drapeau

**Pourquoi.** Tout est aujourd'hui dans un bandeau vertical à gauche : les sections, les
couches, les réglages du plan, les contrôles de cohérence. C'est chargé, et sur un petit écran
c'est inutilisable.

**Ce qu'il faut.**

1. **Une barre horizontale en haut**, la même sur toutes les pages `/decision/…`, qui porte les
   sections : Carte, Dépotoirs, Fuites d'eau, Nuisances, Vérifier, Simulation, Scénarios. La
   section ouverte est marquée. À droite de la barre : le nom du poste connecté et le bouton
   pour en changer.

2. **Un bouton ☰ en haut à droite** qui ouvre un panneau contenant **tout le reste** : les
   couches, les réglages du plan de gestion, les contrôles de cohérence, le dépotoir
   sélectionné, et ce qui est aujourd'hui en bas de page. Le panneau se referme en touchant à
   côté ou sur Échap. La carte occupe alors tout l'écran.

3. **Le drapeau du Burkina Faso en fond de la barre** : un dégradé du rouge vers le vert, avec
   **l'étoile jaune à droite**.

Trois précautions pour le drapeau. Dessine-le en **CSS et en SVG dans la page** — aucun fichier
image chargé, E14 l'interdit. Pose un voile sombre par-dessus (`rgba(0,0,0,.35)` par exemple)
pour que le texte blanc reste lisible : un drapeau illisible ne sert personne. Et garde-le
**sobre** — c'est un symbole national, pas une décoration.

Conserve la police Lato et les couleurs déjà en place, et ne touche pas à la page de
signalement : cette tâche ne concerne que `/decision/…`.

**Réussi si** : les sept pages de décision portent la même barre ; le menu ☰ ouvre et ferme
tous les réglages ; la carte occupe tout l'écran quand le panneau est fermé ; tout reste
utilisable sur un écran de téléphone (420 px de large) ; aucune requête ne sort vers Internet.

**À mettre dans le compte rendu** : une capture d'écran de la barre, et dis comment tu as
dessiné le drapeau.

## T16 — Choisir un lieu connu quand la position ne marche pas

**Pourquoi.** Le signalement repose aujourd'hui entièrement sur la géolocalisation. Elle est
refusée, imprécise ou absente plus souvent qu'on ne croit : téléphone ancien, position coupée,
intérieur d'un bâtiment, ou simplement un habitant qui refuse de la donner. Sans elle, il n'y a
aucun moyen de signaler, et le signalement est perdu.

**Ce qu'il faut.** Quand la position échoue — ou sur demande, par un lien « Je ne peux pas être
localisé » toujours visible — proposer de **choisir un lieu connu** dans une liste cherchable :
marchés, universités, collèges, écoles, centres de santé.

**La bonne nouvelle : les données sont déjà là.** `donnees/ouagadougou/lieux.geojson` contient
déjà, avec leur nom et leur position, **99 marchés**, **31 universités**, **46 collèges**,
937 écoles et 181 lieux de santé. Rien à télécharger, rien à régénérer.

Ce qu'il reste à faire :

- produire, au démarrage de l'application, la liste des lieux **nommés** avec leur type et leur
  position, servie publiquement par `GET /api/lieux` ;
- la faire mettre en cache par le `service-worker.js` de la page de signalement, pour que le
  choix fonctionne **hors ligne** comme le reste du formulaire ;
- dans le formulaire, un champ de recherche qui filtre sur le nom sans accent ni casse (chercher
  « marche gounghin » doit trouver « Marché de Gounghin ») ; choisir un lieu renseigne la
  position ;
- laisser la personne **préciser à côté de quoi** en texte libre (« derrière le marché, côté
  nord ») : beaucoup de marchés non construits ne sont pas dans OpenStreetMap, et le repère
  donné à la main vaut mieux que rien.

**Le point le plus important.** Une position déduite d'un lieu n'a pas la précision d'un GPS,
et l'agent qui la lit doit le savoir, sinon il envoie une équipe au mauvais endroit. Ajoute donc
deux colonnes aux signalements, par le mécanisme `AJOUTS` de `application/base.py` (qui sait
déjà faire évoluer une base déjà installée sans la casser) : `source_position` (`gps` ou
`lieu`) et `lieu_nom`. Affiche-les clairement sur les postes de travail, et donne à ces
signalements une `precision_m` honnête — l'ordre de 150 m, pas zéro.

**Réussi si** : avec la géolocalisation refusée, on peut signaler de bout en bout en choisissant
« Université Joseph Ki-Zerbo de Ouagadougou » ; le signalement arrive marqué `source_position =
lieu`, sa position est celle du lieu, et le poste de la mairie l'affiche comme tel ; la
recherche fonctionne hors ligne ; `pytest` est vert avec un test sur la recherche sans accent et
un test sur le marquage de la provenance.

## T15 — Les tournées suivent les rues, comme un GPS

**Pourquoi.** Les distances et les durées des tournées sont **déjà** calculées sur le vrai
réseau de voies (Dijkstra sur `reseau_noeuds` / `reseau_troncons`) : les chiffres sont justes.
Mais la carte, elle, relie les arrêts par des **traits droits** (`tourneesEnLignes` dans
`interface/decision/carte.js`). Un jury qui voit un trait traverser un quartier en diagonale
croira que le calcul est faux. C'est un défaut d'affichage, pas de calcul — et c'est justement
pour cela qu'il faut le corriger : il décrédibilise un travail qui est bon.

**Ce qu'il faut.** Que la ligne de chaque tournée suive les rues, de la décharge au premier
arrêt, d'un arrêt au suivant, et jusqu'au retour.

**Comment.** `scipy.sparse.csgraph.dijkstra` accepte `return_predecessors=True`. La matrice des
distances entre arrêts est déjà calculée avec lui : demande les prédécesseurs **au même appel**
plutôt que d'en faire un second, puis remonte le chemin nœud par nœud. Ajoute à chaque tournée
une `geometrie` (une liste de `[lon, lat]`), et fais que `carte.js` l'utilise quand elle est
là — **en gardant le trait droit comme repli** si elle manque, pour qu'une tournée sans chemin
trouvé reste visible au lieu de disparaître.

**Surveille le temps de calcul.** Le plan se recalcule aujourd'hui en 5 secondes, et le jury
change les paramètres en direct : c'est un budget, pas une estimation. Le PC est un i5 sans
carte graphique. Mesure avant et après. Si tu dépasses 8 secondes, allège la géométrie
(un point sur deux, ou Douglas-Peucker) plutôt que de renoncer — et dis-le dans le compte rendu.

**Réussi si** : sur la carte, les tournées épousent les rues ; le recalcul reste sous
8 secondes, chiffre mesuré et collé dans le compte rendu ; une tournée dont le chemin n'a pas
été trouvé s'affiche encore en trait droit au lieu de disparaître ; `pytest` est vert, avec un
test qui vérifie que la géométrie renvoyée commence et finit à la décharge et passe par tous les
arrêts dans l'ordre.

---

# Tâches du 17/11 — les livrables officiels

L'énoncé officiel est arrivé le 17/11 au matin (`enonce/challenges-finaux-2026.pdf`). Il liste
des livrables que la photo d'ouverture ne mentionnait pas. Trois choses nous manquent
complètement, et ce sont des livrables **nommés**, pas des améliorations.

Ordre de priorité : **T17 d'abord** (c'est une fonctionnalité, pas un document), puis T18, T19,
T20, T21. Un commit par tâche.

## T17 — Masquer automatiquement les visages et les plaques sur les photos

**Pourquoi.** C'est le premier livrable du challenge, mot pour mot : « Application de
signalement hors connexion, **qui masque automatiquement les visages et les plaques
d'immatriculation sur les photos** ». Nous ne le faisons pas du tout. C'est aussi la règle que
nous nous étions donnée — aucune donnée personnelle — et un jury de cybersécurité ira voir.

**Faisable hors ligne, vérifié.** `opencv-python-headless==4.10.0.84` livre les détecteurs dans
le paquet lui-même, sans aucun modèle à télécharger : `haarcascade_frontalface_default.xml`,
`haarcascade_profileface.xml` (visages de profil, fréquents sur une photo prise de loin),
`haarcascade_russian_plate_number.xml` et `haarcascade_license_plate_rus_16stages.xml`. Garde
cette version : OpenCV 5 ne livre plus ces fichiers. Ajoute-la à `requirements.txt`, et signale
dans le compte rendu que l'image Docker grossit d'environ 90 Mo.

**Le point qui compte le plus.** Le masquage se fait **à la réception, avant l'enregistrement**,
dans `enregistrer_fichier()` (`application/__init__.py`). L'image d'origine ne doit **jamais**
toucher le disque : ni en fichier temporaire, ni en copie « au cas où ». C'est la différence
entre « nous floutons les visages » et « nous gardons les visages mais nous les cachons », et
c'est exactement ce qu'un jury viendra vérifier. Dis-le dans le compte rendu.

Floute par un **flou gaussien de forte intensité** ou un pavé plein, jamais un pixelisé léger
qu'on peut défaire. Agrandis chaque zone détectée d'environ 20 % : une cascade cadre souvent
juste et laisse le menton ou le bord de la plaque dehors.

**Sois honnête sur ce que ça rate.** Ces détecteurs ne voient pas tout : un visage très de
côté, une plaque burkinabè qui n'a pas le format sur lequel la cascade a été entraînée. Donc :

- compte les zones trouvées et range le nombre avec le signalement ;
- sur les postes de travail, affiche « n visage(s) et n plaque(s) masqués automatiquement » à
  côté de la photo, et **un bouton pour masquer une zone à la main** si l'agent en voit une qui
  reste. Un agent qui peut corriger vaut mieux qu'un détecteur qu'on prétend parfait ;
- écris la limite dans le rapport plutôt que de la laisser découvrir au jury.

**Réussi si** : une photo contenant un visage ressort floutée, et le fichier enregistré sur le
disque ne contient plus le visage d'origine (vérifie-le en relisant le fichier, pas l'écran) ;
une photo sans visage ressort intacte ; un fichier qui n'est pas une image est toujours rejeté
comme avant ; `pytest` est vert avec un test qui compare les pixels de la zone avant et après ;
le temps de traitement d'une photo de téléphone reste sous 2 secondes.

## T18 — La matrice de contribution par membre et par couche

**Pourquoi.** Livrable commun, nommé : « matrice de contribution par membre et par couche, avec
les briques réutilisées et leur licence ». Elle n'existe pas. Et elle se relie au critère
éliminatoire : le jury désigne lui-même qui explique une fonction.

**Ce qu'il faut**, dans `docs/contribution.md` : un tableau dont les lignes sont les couches
(signalement mobile, contrôles, chaîne des postes, cartographie, plan, simulation, interface de
décision, déploiement, tests, documentation) et les colonnes les trois membres de l'équipe, qui
dit qui a fait quoi et surtout **qui sait l'expliquer**.

Puis un second tableau des briques réutilisées : nom, rôle, licence, lien. Reprends la table de
technologies du `README.md`, et **ajoute ce qui vient de notre sprint** (`installer.sh`,
`caddy/`) en le disant franchement — réutiliser son propre travail est permis et bien vu, le
cacher ne l'est pas.

Franck doit remplir les noms : ne les invente pas. Mets des cases à compléter.

## T19 — Le jeu de signalements en GeoJSON, sous licence ouverte

**Pourquoi.** Livrable nommé, et c'est notre « bien commun » : « la première carte ouverte des
dépotoirs de Ouaga ».

**Ce qu'il faut** : une adresse `GET /api/export/geojson` qui sort les dépotoirs **vérifiés**
en GeoJSON, et un fichier `donnees/signalements-ouaga.geojson` versé dans le dépôt. Aucune
donnée personnelle dedans : ni nom, ni téléphone, ni photo, ni source. Ajoute à côté un
`donnees/signalements-ouaga.LICENCE.md` qui donne la licence (ODbL, comme OpenStreetMap, pour
que le versement reste compatible) et la provenance.

**Réussi si** : un test vérifie que l'export ne contient aucun champ de déclarant et que chaque
entité a une position et une date.

## T20 — Le rapport technique

**Pourquoi.** Livrable commun : « rapport technique (contexte, architecture, choix, résultats,
limites) », et livrable du challenge : « démarche, paramètres, scénarios simulés, résultats et
plan de gestion ».

**Ce qu'il faut** : `RAPPORT.md` à la racine, qui rassemble ce qui est déjà écrit dans `docs/`
plutôt que de le réécrire. Les chiffres doivent être **mesurés**, pas estimés : nombre de
points de regroupement, de tournées, taux de collecte, coût mensuel, temps de recalcul. Colle
les commandes qui les produisent.

La section « limites » est la plus importante pour un jury : les paramètres qui sont des
hypothèses tant que la mairie n'a pas donné les siens, la décharge déduite d'OpenStreetMap, les
arrondissements absents de l'extrait, les distances à vol d'oiseau entre un ménage et son point,
et ce que le masquage de T17 ne détecte pas.

## T21 — La vidéo de démonstration de 3 minutes

**Pourquoi.** Livrable commun et livrable du challenge. La nôtre fait 2 min 18 s, montre
l'ancien habillage, et ne contient ni les fuites d'eau, ni les nuisances, ni l'accueil parlé,
ni la page d'accueil, ni les itinéraires par les rues.

**Le scénario est imposé par l'énoncé** : « du signalement à la tournée, puis un changement de
paramètres et le plan recalculé ». Suis cet ordre.

Les outils existent : `outils/donnees_demonstration.py`, `outils/filmer.mjs`,
`outils/monter_video.py`. **Fais-la durer entre 2 min 45 s et 3 min** : plus court donne
l'impression d'avoir moins à montrer, plus long risque d'être coupé.

---

# T22 — Refonte de l'interface en plateforme web professionnelle

Demandée par Franck le 17/11, d'après un prompt écrit pour un autre projet (« OUA-GREEN ») et
adapté ici à **notre** travail : seules les parties qui correspondent à ce que nous avons sont
gardées, et le design est refait.

**Lis toute la tâche avant d'écrire une ligne.** Elle est longue parce que la démonstration
devant le jury a lieu demain, et que tout ce qui marche aujourd'hui doit encore marcher ce
soir.

## Le cadre, non négociable

### Une branche à part, jamais `main`

Travaille sur la branche **`refonte-interface`**, créée depuis `main` à jour. **Ne pousse
jamais sur `main`**, même si Franck te le demande pour cette tâche : `main` doit rester prêt pour
la démonstration à tout moment. Le coordinateur vérifie chaque page et la fusionne lui-même.

**Un commit par page**, dans l'ordre donné plus bas. Si tu n'as le temps d'en finir que trois,
on fusionne ces trois-là et on présente le reste dans sa version actuelle. Une page à moitié
refaite ne doit jamais être dans un commit.

### Ce qui est interdit

- **Toucher au serveur** : rien dans `application/`, rien dans `donnees/`, rien dans les tests
  existants. La refonte est uniquement dans `interface/`.
- **Créer une adresse d'API.** Toutes celles dont tu as besoin existent : voir le tableau
  ci-dessous. Si une page te semble impossible sans nouvelle adresse, arrête-toi et écris-le
  dans le compte rendu, ne contourne pas.
- **Ajouter une technologie** : pas de framework, pas de bibliothèque de graphiques, pas de
  préprocesseur CSS. Du HTML, du CSS et du JavaScript sans dépendance, comme aujourd'hui. Les
  graphiques se dessinent en SVG à la main, comme dans `scenarios.js` et `simulation.js`.
- **Charger quoi que ce soit depuis Internet** (E14) : aucune police, aucune icône, aucune
  image, aucun script venu d'ailleurs. Les icônes sont en SVG dans la page ou en caractères.
- **Supprimer une fonctionnalité qui marche.** La liste de ce qui doit encore marcher est plus
  bas : vérifie-la entièrement avant chaque commit.

### Deux pièges techniques

**La politique de sécurité du contenu interdit tout JavaScript dans le HTML.** `script-src`
vaut `'self'` : un bloc `<script>` écrit dans la page, un `onclick="…"`, un `href="javascript:…"`
sont refusés par le navigateur, sans message visible. Tout le JavaScript va dans des fichiers
`.js`. Le CSS en ligne est permis.

**Tout ce qui vient d'un habitant s'affiche avec `textContent`, jamais en HTML.** Le commentaire
d'un signalement, le nom d'un quartier, un nom de lieu sont tapés par n'importe qui — et le jury
injectera des signalements piégés. Garde les fonctions `echapper()` / `proteger()` existantes, ou
construis avec `createElement`.

## Ce qui est gardé du prompt d'origine, et ce qui est écarté

| Point du prompt | Décision | Pourquoi |
|---|---|---|
| 1. Accueil | **gardé** | page publique existante (`/`) |
| 2. Explorer | **gardé** | les données existent, derrière la connexion |
| 3. Carte interactive | **gardé, en dernier** | c'est la page de l'épreuve en direct : la plus risquée |
| 4. Signaler | **gardé, toutes fonctions conservées** | sans l'envoi de vidéo, voir plus bas |
| 5. Détails d'un signalement | **gardé, sans commentaires ni réactions** | l'historique existe déjà : c'est le journal |
| 6. Espace citoyen, profils | **écarté** | les habitants n'ont pas de compte, et c'est voulu : le signalement est anonyme |
| 7. Classement des citoyens | **écarté** | il faudrait identifier les habitants, et récompenser le nombre de signalements encourage les faux |
| 8. Notifications | **écarté** | demande un serveur et une identité des habitants |
| 9. Opérations citoyennes | **écarté** | l'inscription demande un stockage, donc le serveur |
| 10. Administration | **gardé** | un tableau de bord, à partir des adresses existantes |
| Commentaires, réactions | **écarté** | demande un stockage, donc le serveur |
| Envoi de vidéos | **écarté** | le serveur ne l'accepte pas, et masquer les visages sur une vidéo est une autre affaire |

Ce que tu écartes, n'en mets **aucune trace** dans l'interface : pas de bouton grisé « bientôt »,
pas d'onglet vide. Un jury qui clique sur une promesse vide le note.

## L'identité visuelle

**Notre identité, pas celle d'un réseau social.** Inspire-toi de la clarté de ces plateformes —
grilles de cartes, colonnes bien séparées, galeries de photos — sans en copier l'allure. Le
public est une mairie et des habitants de Ouagadougou, pas des abonnés.

À garder, parce que l'équipe l'a choisi :
- la police **Lato**, déjà dans `interface/vendor/polices/lato/` ;
- le **bleu marine `#1e2455`**, le blanc, le **jaune vif `#ffff00`** en accent sur fond sombre
  seulement (illisible sur blanc : prends `#8a7a00`) ;
- la **barre au drapeau** de T14 (`barre.js`, `barre.css`) sur toutes les pages de décision.

À soigner : les espacements, une seule échelle de tailles de texte, des états de survol et de
focus visibles (on navigue aussi au clavier), et des pages qui ne débordent jamais. **Conçu
d'abord pour un ordinateur de 1366 px**, puis adapté à une tablette et à un téléphone de 420 px.

## Les pages, dans l'ordre

L'ordre va **des pages nouvelles aux pages existantes** : une page nouvelle ne peut rien
casser, une page refaite le peut. Si le temps manque, c'est la carte qu'on ne fait pas.

### 1. Tableau de bord d'administration — nouvelle page `/decision/tableau-de-bord.html`

Ce que la mairie voit d'un coup d'œil : combien de dossiers à chaque étape des trois chaînes
(dépotoirs, fuites, nuisances), combien par nature, les dossiers les plus urgents (la file
priorisée), les chiffres du plan de gestion, et une petite carte. Des graphiques en barres en
SVG, pas plus de quatre : un tableau de bord surchargé ne se lit pas.

Une fois la page faite, fais-y arriver la **mairie** à la connexion : c'est une ligne dans
`PAGE_DU_POSTE` de `interface/decision/connexion.js`. Les autres postes gardent leur page.

### 2. Explorer — nouvelle page `/decision/explorer.html`

Les signalements en **grille de cartes**, chacune avec sa photo, sa nature, son quartier, son
étape et sa note d'urgence. Des filtres par nature, par étape et par quartier, qui s'appliquent
sans recharger la page. Un clic sur une carte ouvre la page de détail.

Les photos sont déjà masquées (T17). Une carte sans photo garde la même hauteur que les autres.

### 3. Détail d'un signalement — nouvelle page `/decision/signalement.html?type=…&id=…`

Une page par dossier : la **galerie** de ses photos, ses informations, le **message vocal** s'il
y en a un, la note d'urgence **avec ses raisons**, et l'**historique** — c'est le journal du
dossier, qui dit qui a fait quoi et quand. Les boutons d'action de l'étape (confirmer, constater,
classer…) y sont aussi, pour le poste qui en a le droit : réemploie les appels déjà écrits dans
`dossiers.js`, `fuites.js` et `nuisances.js`.

L'identité facultative du déclarant n'apparaît que si le serveur la renvoie (agent connecté).
Ne la demande pas autrement.

### 4. Accueil — refaire `/` (`interface/accueil/`)

Page **publique** : elle ne peut montrer que ce qui est public, c'est-à-dire les trois chiffres
de `/api/publics`. **Pas de fil des signalements** : leurs positions sont réservées aux agents
depuis T13, et une page publique qui les afficherait annulerait cette protection.

Ce qu'elle doit dire : ce qu'est l'outil, les six choses qu'on peut signaler, comment ça marche
en trois étapes, et deux portes — **« Signaler »**, la plus grosse, et « Espace des services ».

### 5. Signaler — refaire l'allure de `/signaler/`, sans rien retirer

**Le design change, le comportement non.** Tout ceci doit marcher exactement comme avant :
- les **écrans d'accueil parlés en mooré**, qui suivent les fichiers présents ;
- le bouton **🔊 Mooré** et le guidage parlé de chaque étape ;
- les **six natures**, et les étapes qui changent et se renumérotent selon la nature ;
- la **position GPS**, et le **choix d'un lieu connu** quand elle échoue (T16) ;
- la **photo**, le **message vocal**, l'**identité facultative** avec CNIB et portrait ;
- la **file d'attente hors ligne**, qui envoie toute seule au retour du réseau.

Si tu renommes ou ajoutes un fichier dans `interface/signaler/`, mets à jour la liste `FICHIERS`
de `service-worker.js` **et** change le nom du cache (`signaler-v3` → `signaler-v4`) : sinon les
téléphones déjà passés sur la page garderont l'ancienne version, et la page cassera hors ligne.

### 6. Carte interactive — refaire `/decision/` (en dernier, seulement s'il reste du temps)

Une liste latérale des signalements, la carte sur le reste de l'écran, un clic dans la liste
centre la carte. **C'est la page de l'épreuve en direct** : le jury y change les paramètres et
regarde le plan se recalculer. Le panneau ☰, toutes les couches, tous les réglages du plan, le
bouton « Recalculer » et les contrôles de cohérence doivent marcher exactement comme avant.

## Les adresses à ta disposition

Toutes existent, aucune n'est à créer. Celles marquées « agent » demandent une connexion.

| Adresse | Accès | Ce qu'elle rend |
|---|---|---|
| `GET /api/publics` | public | trois chiffres, rien d'autre |
| `GET /api/lieux` | public | les lieux connus (marchés, écoles…) |
| `GET /api/fichiers/public/…` | public | une photo de signalement (déjà masquée) |
| `GET /api/session` | public | qui est connecté, son poste, son jeton |
| `GET /api/dossiers`, `/api/fuites`, `/api/nuisances` | agent | les listes, classées par urgence, avec `priorite.note` et `priorite.raisons` |
| `GET /api/dossiers/<id>`, `/api/fuites/<id>`, `/api/nuisances/<id>` | agent | un dossier : ses signalements, photos, voix, journal |
| `GET /api/chaine`, `/api/fuites/chaine`, `/api/nuisances/chaine` | agent | les étapes et le nombre de dossiers à chacune |
| `GET /api/comptes` | agent | les signalements par statut |
| `GET /api/depotoirs`, `/api/fuites/carte`, `/api/nuisances/carte` | agent | GeoJSON pour la carte |
| `GET /api/plan` | agent | le plan de gestion (prend 5 à 7 s : ne l'appelle pas au chargement du tableau de bord) |
| `GET /api/inspection` | agent | la tournée du jour |

Les actions (`POST …/avancer`, `…/classer`) demandent l'en-tête `X-Jeton` : réemploie la
fonction `appel()` des pages existantes, qui le pose.

## Ce qui doit encore marcher avant chaque commit

1. `python -m pytest -q` : **212 tests, tous verts**, sans en avoir modifié un seul.
2. Dans un navigateur, sans erreur de console et **sans aucune requête vers Internet** :
   - signaler un tas d'ordures depuis le téléphone (420 px), avec photo ;
   - signaler une fuite d'eau, puis signaler sans GPS en choisissant un lieu ;
   - se connecter avec `onea` et arriver sur les fuites ; avec `agent` et arriver sur sa page ;
   - suivre un dossier mairie → brigade → mairie → collecte, jusqu'à « collecté » ;
   - injecter le lot de pièges du jury depuis « Vérifier », et voir les motifs de rejet ;
   - sur la carte, mettre 14 camions en panne et la saison des pluies, recalculer, lire les
     contrôles de cohérence ;
   - « Me déconnecter », et retrouver la page de connexion.
3. Chaque page refaite, vue à **1366 px** et à **420 px** : rien ne déborde.

## Le compte rendu

Dans `comptes-rendus/T22.md`, sur le modèle habituel, avec pour **chaque page** : une capture
avant et après à 1366 px, une à 420 px, la liste des vérifications ci-dessus avec leur résultat,
et ce qui n'a pas pu être fait et pourquoi. Range les captures dans `comptes-rendus/captures/`.

Dis clairement, en tête, **quelles pages sont prêtes à fusionner** et lesquelles ne le sont pas.
