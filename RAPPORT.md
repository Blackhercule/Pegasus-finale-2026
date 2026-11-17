# Rapport technique — Assainissement de Ouaga

Groupe Pegasus, Université Joseph Ki-Zerbo · Hackathon des Universités 2026, challenge 01.

Ce rapport répond à deux livrables de l'énoncé : le **rapport technique** commun (contexte,
architecture, choix, résultats, limites — E26) et le **rapport du challenge** (démarche,
paramètres, scénarios simulés, résultats et plan de gestion — E22). Il rassemble ce qui est
déjà écrit ailleurs et renvoie vers le détail plutôt que de le recopier :

| Pour le détail de… | Voir |
|---|---|
| L'architecture, les formats, les tables, l'API | [`docs/conception.md`](docs/conception.md) |
| L'installation, les technologies et leurs licences | [`README.md`](README.md) |
| Chaque exigence de l'énoncé et où elle est traitée | [`docs/couverture.md`](docs/couverture.md) |
| Ce qui a été fait, tâche par tâche, et comment c'est vérifié | [`comptes-rendus/`](comptes-rendus/) |

**Tous les chiffres de ce rapport sont mesurés**, avec la commande qui les produit. Ils ont été
relevés le 17/11/2026 dans l'environnement de développement (conteneur Linux, 4 cœurs) ; les
temps de calcul seront plus longs sur le PC de démonstration (Intel Core i5-6300U) et doivent y
être remesurés (voir « Limites »).

---

## 1. Contexte

À Ouagadougou, une large part des ordures ménagères n'atteint jamais la décharge : elle finit
en **dépotoirs sauvages**, dans les caniveaux et sur les berges, qui débordent à la saison des
pluies. La filière a plusieurs acteurs qui se passent les déchets de main en main : les
**ménages**, les **pré-collecteurs** (associations et PME abonnées, à la charrette ou au
tricycle), les **points de regroupement**, les **camions de la mairie**, et la **brigade
Laabal**, qui sensibilise et verbalise.

L'énoncé demande « un outil libre d'aide à la décision, du signalement des dépotoirs sauvages
jusqu'au plan de gestion de la ville, avec simulation de tous les acteurs », que le jury
éprouve en direct : signalements piégés, puis changement de paramètres (camions en panne,
saison des pluies, nouveau quartier), après quoi le plan doit se recalculer et rester cohérent.

## 2. Démarche

Nous avons suivi la chaîne de l'énoncé, maillon par maillon, en vérifiant chacun avant de
passer au suivant :

```
 téléphone              contrôles                carte               plan de gestion
 /signaler  ──►  signalements  ──►  dépotoirs vérifiés  ──►  points de regroupement + tournées
                 (recevable, à vérifier,                               │
                  vérifié, rejeté + motif)                             ▼
                                      paramètres ──►  simulation multi-agents ──► indicateurs
                                      (scénarios)      (ménages, pré-collecteurs,   comparés
                                                        brigade Laabal, mairie)
```

1. **Données ouvertes d'abord** (T3). Tout part d'un extrait OpenStreetMap, préparé une fois et
   versé dans le dépôt : limite de la commune, réseau de voies, bâtiments, eau, lieux. Sans
   carte, ni les contrôles, ni les tournées, ni la simulation n'ont de sens.
2. **Signalements et contrôles** (T4). Le jury injecte des pièges : chaque contrôle est une
   petite fonction qui renvoie un motif, et un piège est écarté avec son motif sans jamais faire
   tomber le serveur.
3. **Carte, plan, simulation, scénarios** (T5 à T8), chacun recalculé à la demande : rien n'est
   pré-calculé, puisque le jury change les paramètres en direct.
4. **Bien commun et déploiement** (T9, T10) : export OpenStreetMap à relire avant versement,
   installation en une commande.
5. **Ce que demande le terrain** (T12 à T17) : page d'accueil publique, partie décision
   protégée par mot de passe, signalement sans GPS depuis un lieu connu, tournées tracées par les
   rues, visages et plaques masqués avant tout enregistrement.

Chaque tâche se termine par une vérification lancée (tests, navigateur, mesures) et un compte
rendu dans `comptes-rendus/`. Principe tenu partout : **adopter des briques éprouvées, les
adapter à Ouagadougou, et n'écrire que ce qui manque entre elles** — aucune cryptographie ni
aucun algorithme d'optimisation réinventé.

## 3. Architecture

```
 Téléphone ─┐                            ┌─ cartographie ── MapLibre + fond PMTiles (hors ligne)
            ├─ HTTPS :<port> ─ Caddy ─ Flask ├─ contrôles ───── Shapely (dans la commune ? dans l'eau ?)
 Navigateur ┘                  │          ├─ plan ────────── SciPy (trajets) + nos algorithmes
                               │          └─ simulation ──── Mesa (agents)
                            SQLite
```

- **Deux conteneurs** seulement (`caddy` pour HTTPS, `application` pour Flask), sur un réseau
  Docker **sans accès à Internet**. Données, fond de carte, polices et bibliothèques JavaScript
  sont servis par la machine : vérifié dans un navigateur, aucune requête ne sort (E14).
- **Deux portes** : le signalement (`/signaler/`, `/api/signalements`, `/api/signalements/lot`)
  est ouvert à tous, habitants et jury ; tout le reste (carte, plan, scénarios, dossiers,
  exports) est derrière un identifiant et un mot de passe, par **liste blanche** : une adresse
  ajoutée plus tard est fermée tant qu'on ne l'a pas ouverte exprès, et un test échoue si une
  route est ouverte par oubli (T13).
- **Quatre postes** (mairie, brigade Laabal, collecte, ONEA) se passent les dossiers : un
  signalement ouvre un dossier que la mairie confirme, que la brigade constate, puis que
  l'équipe de collecte vide. Chaque passage est daté et signé.

Le détail (arborescence, fichiers d'une commune, tables, statuts, motifs, API) est dans
[`docs/conception.md`](docs/conception.md).

## 4. Choix techniques

| Besoin | Brique | Licence | Pourquoi |
|---|---|---|---|
| Application et API | Flask + gunicorn | BSD-3, MIT | Déjà maîtrisé par l'équipe ; peu de code à expliquer |
| Stockage | SQLite | domaine public | Un seul fichier, aucun service à démarrer |
| Géométrie | Shapely, pyproj | BSD-3, MIT | « Ce point est-il dans la commune ? dans un barrage ? » |
| Trajets | SciPy (Dijkstra) | BSD-3 | Toutes les durées entre arrêts en un appel ; vitesses changées à la volée (saison) |
| Simulation | Mesa | Apache-2.0 | Bibliothèque de référence des modèles à base d'agents en Python |
| Carte hors ligne | MapLibre GL JS, PMTiles, Protomaps | BSD-3 ; données ODbL | Un seul fichier de fond de carte servi par notre machine |
| Masquage des visages et plaques | OpenCV (détecteurs livrés dans le paquet) | Apache-2.0 | Hors ligne, sans modèle à télécharger |
| HTTPS local | Caddy | Apache-2.0 | Un téléphone ne donne sa position et sa caméra qu'à une page HTTPS |

La liste complète, avec les liens, est dans [`README.md`](README.md#technologies-et-licences).
Notre code est sous **AGPL-3.0**.

**Pourquoi si peu de services.** Le PC de démonstration est un i5 sans carte graphique, et le
jury fait recalculer le plan en direct. Pas de PostGIS, pas d'OSRM, pas de serveur de cartes :
chacun ajouterait une image à télécharger, de la mémoire et une cause de panne, pour un gain
que la taille d'une ville ne justifie pas.

**Les deux algorithmes du plan**, en une phrase chacun :

- **Points de regroupement** : couverture gloutonne. À chaque tour, on ouvre l'emplacement du
  réseau qui couvre le plus de déchets encore non couverts, à moins de 800 m d'un carreau
  habité ; l'eau et les abords des écoles et centres de santé sont exclus.
- **Tournées** : algorithme des économies de Clarke et Wright (1964), puis amélioration 2-opt.
  On part d'un aller-retour par arrêt, on fusionne les tournées qui font gagner le plus de
  trajet tant que la benne et la journée le permettent, puis on répartit entre les camions ;
  ce qui ne rentre pas est **laissé de côté et nommé**. Les tracés suivent les rues : ils
  viennent du même calcul de Dijkstra que les durées (T15).

## 5. Données

Source : extrait OpenStreetMap du Burkina Faso (Geofabrik, données du 15/11/2026, 85 Mo),
préparé par `donnees/preparer.py` ; résultat versé dans `donnees/ouagadougou/`. Chiffres lus
dans [`donnees/ouagadougou/commune.json`](donnees/ouagadougou/commune.json) :

| Élément | Valeur |
|---|---|
| Surface de la commune | 526,6 km² |
| Réseau de voies (plus grande partie d'un seul tenant) | 111 840 nœuds, 166 611 tronçons ; 388 nœuds isolés écartés |
| Revêtement connu | 24,8 % des tronçons |
| Bâtiments | 332 556, regroupés en 4 498 carreaux bâtis de 250 m |
| Plans d'eau / cours d'eau | 440 / 3 194 |
| Lieux nommés servant de repère (T16) | 1 187 : 99 marchés, 28 universités, 43 collèges, 861 écoles, 156 lieux de santé |
| Sites de déchets déjà cartographiés | 226 (219 décharges, 7 installations) |
| Secteurs et arrondissements | **0** (absents de l'extrait, voir « Limites ») |

Données © les contributeurs d'OpenStreetMap, licence ODbL. Open Buildings n'a pas été intégré :
les 332 556 bâtiments d'OpenStreetMap couvrent déjà la commune.

## 6. Paramètres

Tous les paramètres du plan et de la simulation sont dans **un seul fichier documenté**,
[`donnees/ouagadougou/parametres.json`](donnees/ouagadougou/parametres.json) (E19) ; ils se
changent sans toucher au code, et le jury les change en direct par le tableau de bord ou par
l'API. Les valeurs de départ :

| Paramètre | Valeur | Statut |
|---|---|---|
| `population` | 2 900 000 | hypothèse |
| `kg_par_habitant_jour` | 0,55 | hypothèse |
| `densite_dechets_t_m3` | 0,35 | hypothèse |
| `taille_menage` | 6,2 | hypothèse |
| `taux_abonnement` / `tarif_abonnement` | 35 % / 1 500 F CFA par mois | hypothèses |
| `nb_camions` / `capacite_camion_m3` / `heures_travail` | 24 / 12 m³ / 8 h | hypothèses |
| `frequence_collecte_jours` / `capacite_point_m3` | 3 jours / 30 m³ | hypothèses |
| `distance_max_precollecte_m` | 800 m | hypothèse |
| `budget_mensuel` / `cout_km` / `cout_jour_camion` | 45 M / 900 / 25 000 F CFA | hypothèses |
| `vitesses_kmh` | par classe de voie et par saison ; voie non revêtue ×0,75 (sèche), ×0,55 (pluies) | hypothèses |
| `effectif_brigade` | 60 | hypothèse |
| Seuils des contrôles de signalements | rayon de regroupement 30 m, précision max 100 m, volume max 500 m³, etc. | choix de l'équipe |

**Toutes les valeurs de la filière sont des hypothèses** de l'équipe, en attendant les
paramètres fixés avec la mairie (E8). Les trois changements annoncés par l'énoncé sont des
paramètres : `camions_en_panne`, `saison`, `nouveaux_quartiers`.

## 7. Scénarios simulés et résultats

### Comment ils sont mesurés

```bash
python outils/mesurer_scenarios.py
```

L'outil lance l'application en mémoire, avec une base vide et les vraies données de
Ouagadougou, y dépose les dix dépotoirs fictifs du jeu de démonstration (chacun vu par deux
téléphones, donc vérifié), puis demande chaque scénario comme le tableau de bord
(`POST /api/scenario`, 30 jours simulés) et chronomètre la réponse.

### Résultats (sortie de la commande, 17/11/2026)

| Scénario | Points de regroupement | Tournées | Arrêts non desservis | km/jour | Coût mensuel (F CFA) | Taux de collecte (30 j simulés) | Temps de calcul |
|---|---|---|---|---|---|---|---|
| Référence (`parametres.json`) | 224 | 146 | 21 | 2 685 | 181 992 300 | 16,3 % | 6,2 s |
| Saison des pluies | 224 | 120 | 38 | 1 960 | 142 911 900 | 11,1 % | 5,7 s |
| 8 camions en panne sur 24 | 224 | 106 | 47 | 1 655 | 124 171 500 | 11,1 % | 5,4 s |
| Nouveau quartier de 150 000 habitants | 235 | 149 | 20 | 2 731 | 185 489 700 | 15,3 % | 6,0 s |
| Abonnement à 60 % | 342 | 162 | 77 | 2 510 | 189 275 400 | 10,4 % | 8,4 s |
| Collecte tous les 2 jours | 149 | 147 | 16 | 2 604 | 180 563 400 | 21,6 % | 4,8 s |

Les **temps de calcul** comprennent le plan et 30 jours de simulation. Le recalcul du seul plan,
mesuré dans le navigateur du clic sur « Recalculer » à la réponse, prend **6,2 s** (6,3 s en
saison des pluies) — voir [`comptes-rendus/T15.md`](comptes-rendus/T15.md).

### Ce que montrent les scénarios

- **Les trois changements du jury dégradent le plan proprement**, sans le casser : saison des
  pluies et camions en panne réduisent le nombre de tournées (voies plus lentes, moins de
  camions) ; les arrêts qui ne tiennent plus dans la journée sont **nommés comme non desservis**
  (21 → 38 → 47), jamais oubliés. Un nouveau quartier ajoute 11 points de regroupement là où
  vivent les nouveaux habitants.
- **La fréquence de passage est le levier le plus fort** parmi ceux essayés : passer tous les
  2 jours au lieu de 3 fait monter la collecte simulée de 16,3 % à 21,6 % pour un coût
  presque identique.
- **Les huit contrôles de cohérence** sont recalculés et affichés avec chaque plan. Dans le
  scénario de référence, cinq sont tenus (capacité des camions, durée de travail, aucun passage
  en double, budget, bilan des déchets) et trois sont **en alerte, et chiffrés** : arrêts non
  desservis faute de camions ou de temps, 32 363 habitants à plus de 800 m d'un point, 60 points
  saturés. Un plan qui affiche ses manques vaut mieux qu'un plan qui les cache.
- **Ordre de grandeur, et c'est la vraie conclusion** : avec les hypothèses actuelles, la ville
  produit 4 557 m³ de déchets par jour (2,9 millions d'habitants × 0,55 kg, à 0,35 t/m³) ;
  146 rotations de 12 m³ en emportent au plus 1 752 m³, soit 38 %. **La flotte supposée ne peut
  pas suivre la production**, quel que soit l'algorithme. C'est exactement le type de constat
  qu'un outil d'aide à la décision doit rendre visible — à confirmer avec les vrais chiffres de
  la mairie.

## 8. Plan de gestion (scénario de référence)

Mesuré par `POST /api/scenario` (base vide, paramètres de `parametres.json`) :

| Élément | Valeur |
|---|---|
| Demande | 2 900 000 habitants répartis sur 4 498 carreaux bâtis ; 1 595 t, soit 4 557 m³ par jour |
| Points de regroupement | 224, à 465 m en moyenne des ménages ; 75 à vider le jour du plan |
| Décharge | déduite d'OpenStreetMap : groupe de 31 sites autour de (12,4258 ; −1,5147), à confirmer |
| Tournées | 142 tournées, 24 camions, journée la plus chargée 8,0 h sur 8 h ; 2 735 km par jour |
| Coût | 180,3 M F CFA par mois, pour un budget de 45 M F CFA (voir « Limites » sur le solde) |
| Collecte le jour du plan | 1 471 m³ sur 4 557 m³ produits, soit 32 % |
| Simulation sur 30 jours | 17,8 % collectés, 94 488 m³ partis en dépotoirs, 1 595 verbalisations par la brigade |

Le plan s'affiche sur la carte de décision : points de regroupement dimensionnés selon leur
volume, tournées tracées par les rues, dépotoirs vérifiés à nettoyer, et les contrôles de
cohérence dans le panneau ☰.

## 9. Robustesse : l'épreuve en direct

- **Signalements piégés** (E10) : 42 pièges (`tests/pieges.json`) passent automatiquement dans
  les tests — coordonnées inversées, point (0, 0), latitude « douze », date future, volume
  négatif, point dans un barrage, mille copies du même tas, champs manquants… Chacun est écarté
  avec son motif. Une attaque plus large (une soixantaine d'entrées hostiles, dont des nombres de
  400 chiffres et des demi-caractères Unicode) a trouvé trois réponses 500, corrigées et
  couvertes par des tests (C1 ; [`comptes-rendus/T4-verification.md`](comptes-rendus/T4-verification.md)).
- **Mots de passe** : dix échecs en cinq minutes sur un identifiant, puis deux minutes de refus.
- **Tests automatisés** : `python -m pytest -q` → **175 passed, 1 skipped** (17/11). Ils couvrent
  contrôles, pièges, chaîne des postes, plan, simulation, fuites, nuisances, accès, masquage et
  tracés. Le test sauté vérifie la détection d'OpenCV sur une vraie photo, à déposer par
  l'équipe dans `tests/photos/` (dossier non publié).

## 10. Limites

C'est la partie à lire en premier. Ce qui suit est vrai aujourd'hui ; chaque point dit ce qu'il
faudrait pour le lever.

1. **Les paramètres sont des hypothèses.** Population, production par habitant, densité des
   déchets, flotte, budget, tarifs, vitesses : aucune valeur ne vient encore de la mairie (E8).
   Les résultats du § 7 décrivent donc nos hypothèses, pas Ouagadougou. Il suffit de changer
   `parametres.json` : l'outil ne suppose rien d'autre.
2. **Le « budget tenu » repose sur une hypothèse forte.** Le contrôle compte les abonnements
   (245,6 M F CFA par mois au scénario de référence) comme une recette de la mairie. En réalité,
   les abonnements vont surtout aux pré-collecteurs. Sans eux, le coût des tournées (180,3 M F
   CFA par mois) fait **quatre fois le budget** de 45 M. À trancher avec la mairie ; le contrôle
   devrait alors être corrigé.
3. **Le plan et la simulation ne mesurent pas la même chose.** Le plan annonce 32 % collectés
   le jour du plan ; la simulation 17,8 % en moyenne sur 30 jours (points qui saturent, pannes,
   dépôts sauvages qui s'accumulent). Les deux chiffres sont justes chacun dans leur sens, mais
   un jury peut s'étonner de l'écart : il faut l'expliquer.
4. **Le scénario « abonnement à 60 % » donne une collecte plus faible** (10,4 %) que la
   référence (16,3 %), avec plus de points (342) et plus d'arrêts non desservis (77) : plus
   d'abonnés apportent plus aux points, et la flotte ne suit pas. C'est cohérent avec la
   limite 1, mais c'est contre-intuitif et mérite d'être vérifié. Ce scénario est aussi le seul
   qui dépasse 8 s ici (8,4 s).
5. **La décharge est déduite d'OpenStreetMap** : le centre du groupe de sites le plus dense (31
   sites). La mairie doit donner la vraie position (paramètre `decharge`).
6. **Les arrondissements et secteurs manquent dans l'extrait OpenStreetMap** : les carreaux n'ont
   pas de secteur rattaché. Le plan couvre la **commune entière** ; le livrable « plan de gestion
   **d'un arrondissement** » (E20) demande soit leurs limites (à obtenir de la mairie), soit un
   découpage tracé à la main.
7. **La population est répartie au prorata de la surface bâtie** : un quartier d'entrepôts compte
   comme un quartier d'habitation.
8. **La distance entre un ménage et son point est prise à vol d'oiseau** (à l'échelle d'un
   quartier, à pied ou à charrette). Les camions, eux, suivent le vrai réseau. Une rivière ou un
   mur peut donc séparer un ménage d'un point déclaré « à portée ».
9. **Le masquage des visages et des plaques (T17) n'est pas infaillible.** Les détecteurs
   d'OpenCV ratent un visage très de profil ou de dos, un visage minuscule au fond de la photo,
   une plaque d'un format qu'ils ne connaissent pas ou vue en biais. Le nombre de zones masquées
   est montré à l'agent, et le masquage manuel existe côté serveur, mais son bouton sur le poste
   de travail n'est pas encore branché. La CNIB et le portrait du déclarant ne sont **pas**
   floutés, volontairement : ce sont les pièces qu'il choisit de donner pour être témoin ; elles
   restent privées et s'effacent à la clôture.
10. **Un signalement depuis un lieu connu (sans GPS) est approximatif** : ± 150 m, marqué comme
    tel, et il arrive « à vérifier » (T16).
11. **Les temps de calcul sont mesurés dans le cloud.** Le PC de démonstration est plus lent ;
    les 6 s de recalcul y seront plus longues. À remesurer sur le PC avant l'épreuve.
12. **Les signalements réels de notre secteur (E7) ne sont pas encore collectés.** L'outil est
    prêt ; les dix dépotoirs utilisés pour les mesures sont fictifs.

## 11. Reproduire ces résultats

```bash
pip install -r requirements.txt
python -m pytest -q                      # les tests
python outils/mesurer_scenarios.py       # le tableau du § 7
./installer.sh                           # l'outil complet, en une commande (Docker)
```
