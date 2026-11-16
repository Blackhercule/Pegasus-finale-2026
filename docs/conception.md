# Conception — outil d'aide à la décision pour l'assainissement de Ouagadougou

Écrit par le coordinateur. C'est la référence commune des tâches : formats de fichiers, tables,
adresses de l'API et vocabulaire. Si une tâche et ce document se contredisent, signale-le dans
le compte rendu au lieu de trancher seul.

## La chaîne

```
 téléphone               contrôles                 carte               plan de gestion
 /signaler  ──►  signalements  ──►  dépotoirs vérifiés  ──►  points de regroupement + tournées
                 (recevable, à vérifier,                               │
                  vérifié, rejeté + motif)                             ▼
                                       paramètres ──►  simulation multi-agents ──► indicateurs
                                       (scénarios)      (ménages, pré-collecteurs,   comparés
                                                         brigade Laabal, mairie)
```

## Choix techniques

Tout est en Python, avec le moins de services possible. Trois raisons : le PC est un i5 sans
carte graphique ; le jury fait recalculer le plan en direct, donc chaque calcul doit tenir en
quelques secondes ; chaque membre doit pouvoir expliquer le code.

| Besoin | Brique adoptée | Licence | Pourquoi celle-ci |
|---|---|---|---|
| Application et API | Flask, servi par gunicorn | BSD-3, MIT | Déjà utilisé par l'équipe au sprint |
| Stockage | SQLite (module `sqlite3` de Python) | Domaine public | Un seul fichier, aucun service à démarrer |
| Géométrie | Shapely, pyproj | BSD-3, MIT | Point dans un polygone, distances en mètres |
| Trajets sur le réseau | SciPy (`scipy.sparse.csgraph.dijkstra`) | BSD-3 | Toutes les durées entre 200 points en quelques secondes, et les vitesses se changent à la volée (saison des pluies) |
| Tournées | OR-Tools (module de routage) | Apache-2.0 | Capacités, horaires, plusieurs camions, visites abandonnées avec pénalité |
| Simulation multi-agents | Mesa | Apache-2.0 | Bibliothèque de référence en Python pour les modèles à base d'agents |
| Carte | MapLibre GL JS + PMTiles (fond Protomaps tiré d'OpenStreetMap) | BSD-3 ; données ODbL | Un seul fichier de fond de carte servi par notre machine : aucune tuile demandée à Internet |
| Données | OpenStreetMap (extrait Geofabrik), Open Buildings | ODbL ; CC BY-4.0 ou ODbL | Demandées par l'énoncé |
| HTTPS local | Caddy, repris du sprint | Apache-2.0 | Un téléphone ne donne sa position et sa caméra qu'à une page en HTTPS |

Deux conteneurs seulement : `caddy` (HTTPS, fichiers de l'interface, fond de carte) et
`application` (Flask). Pas de PostGIS, pas d'OSRM, pas de Keycloak : chacun ajouterait une image
à télécharger, de la mémoire et une cause de panne, pour un gain que la taille d'une ville ne
justifie pas.

L'interface est en HTML, CSS et JavaScript simples, sans étape de construction. Les
bibliothèques JavaScript sont copiées dans `interface/vendor/` : rien n'est chargé depuis un CDN.

## Arborescence

```
application/           paquet Python de l'application Flask
  signalements/        réception, contrôles, regroupement en dépotoirs, vérification
  reseau/              graphe routier, durées entre points
  plan/                points de regroupement, tournées, contrôles de cohérence
  simulation/          modèle multi-agents
  scenarios/           paramètres, exécution, comparaison
interface/             pages servies telles quelles
  signaler/            page mobile (application web installable, saisie hors ligne)
  decision/            carte et tableau de bord
  vendor/              bibliothèques JavaScript, polices et pictogrammes du fond de carte
donnees/
  preparer.py          fabrique les fichiers d'une commune à partir d'un extrait OpenStreetMap
  ouagadougou/         fichiers de la commune (voir plus bas)
tests/                 pytest
comptes-rendus/        un fichier par tâche
caddy/  docker-compose.yml  installer.sh
```

## Fichiers d'une commune (`donnees/<commune>/`)

Coordonnées en WGS 84 (longitude, latitude). Pour les distances en mètres, projeter en UTM
(Ouagadougou : EPSG:32630). Une autre commune se décrit avec les mêmes fichiers : c'est ce qui
rend l'outil réutilisable (E13).

| Fichier | Contenu |
|---|---|
| `commune.json` | `nom`, `bbox` [ouest, sud, est, nord], `epsg_metrique`, date et source de l'extrait |
| `commune.geojson` | Limite de la commune (polygone) |
| `secteurs.geojson` | Arrondissements et secteurs : propriétés `nom`, `niveau` |
| `eau.geojson` | Plans d'eau (barrages, retenues) et lits de cours d'eau, en polygones |
| `reseau_noeuds.csv.gz` | `id, lon, lat` |
| `reseau_troncons.csv.gz` | `depart, arrivee, longueur_m, classe, revetu, sens_unique` — `classe` est la valeur `highway` d'OpenStreetMap, `revetu` vaut 1, 0 ou vide si inconnu |
| `zones.geojson` | Grille de carreaux de 250 m sur la commune : `id`, `nb_batiments`, `surface_batie_m2`, `secteur` |
| `lieux.geojson` | Points utiles : écoles, centres de santé, marchés, décharges et installations de déchets déjà cartographiées, avec `type` et `nom` |
| `fond.pmtiles` | Fond de carte, zooms 0 à 15 |
| `parametres.json` | Paramètres de départ (voir « Paramètres ») |

## Signalements

Table `signalements` : `id`, `id_client` (identifiant choisi par l'appareil, pour ne pas compter
deux fois un envoi répété), `latitude`, `longitude`, `precision_m`, `date_observation`,
`date_reception`, `taille` (`petit`, `moyen`, `grand`, `tres_grand`), `volume_m3`, `type`
(`menager`, `gravats`, `mixte`, `autre`), `commentaire`, `photo`, `source` (pseudonyme de
l'appareil ou nom du lot), `statut`, `motifs`, `depotoir_id`.

Aucune donnée personnelle : pas de nom, pas de numéro de téléphone. La `source` est un
identifiant aléatoire créé par le téléphone.

### Statuts

| Statut | Sens | Entre dans le plan ? |
|---|---|---|
| `recevable` | A passé tous les contrôles automatiques | Oui, sauf en mode strict |
| `a_verifier` | Douteux : un agent doit trancher | Non |
| `verifie` | Confirmé par un agent, ou par plusieurs sources indépendantes | Oui |
| `rejete` | Contrôle échoué ; le motif est conservé et affiché | Non |

Le paramètre `mode_strict` (faux par défaut) ne garde que les `verifie`.

### Contrôles et motifs

Chaque contrôle est une petite fonction qui renvoie un code de motif ou rien. Un signalement
piégé ne doit jamais provoquer une erreur du serveur : il est rejeté avec son motif.

| Motif | Déclenché quand | Effet |
|---|---|---|
| `format_invalide` | Champ obligatoire absent, mauvais type, texte trop long | `rejete` |
| `coordonnees_invalides` | Latitude ou longitude non numérique, infinie, hors des bornes, ou (0, 0) | `rejete` |
| `coordonnees_inversees` | Hors commune, mais dans la commune une fois latitude et longitude échangées | `rejete` |
| `hors_commune` | Hors de `commune.geojson` | `rejete` |
| `dans_l_eau` | Dans un polygone de `eau.geojson` | `rejete` |
| `date_future` | Date d'observation après maintenant (tolérance de 10 minutes) | `rejete` |
| `date_trop_ancienne` | Plus ancienne que `anciennete_max_jours` | `a_verifier` |
| `volume_invraisemblable` | Volume négatif, nul ou supérieur à `volume_max_m3` | `rejete` |
| `doublon_exact` | Même `id_client`, ou même source, même position et même date | ignoré, la réponse renvoie le premier |
| `rafale_meme_source` | Plus de `rafale_max` signalements d'une source en `rafale_fenetre_min` minutes | `a_verifier` |
| `precision_insuffisante` | `precision_m` supérieure à `precision_max_m` | `a_verifier` |
| `photo_invalide` | Le fichier n'est pas une image ou dépasse la taille permise | `rejete` |

### Dépotoirs

Un dépotoir regroupe les signalements pris en compte situés à moins de `rayon_regroupement_m`
(30 m par défaut) les uns des autres. Un nouveau signalement proche d'un dépotoir existant le
**confirme** au lieu d'en créer un second. Table `depotoirs` : `id`, `latitude`, `longitude`,
`volume_m3` (médiane des signalements), `nb_signalements`, `nb_sources`, `premier_vu`,
`dernier_vu`, `etat` (`actif`, `nettoye`). Deux sources différentes suffisent à passer ses
signalements à `verifie`.

### API

| Méthode et adresse | Rôle |
|---|---|
| `POST /api/signalements` | Un signalement (JSON, ou formulaire avec photo). Répond `201` avec `statut` et `motifs`, ou `200` pour un doublon |
| `POST /api/signalements/lot` | Un lot : tableau JSON, GeoJSON ou CSV. Répond un résultat par ligne, jamais une erreur globale |
| `GET /api/signalements?statut=…` | Liste, filtrable |
| `GET /api/depotoirs` | GeoJSON des dépotoirs |
| `POST /api/signalements/<id>/verifier` et `/rejeter` | Décision d'un agent connecté |
| `GET /api/export/osm` | Dépotoirs vérifiés au format `.osm`, pour relecture avant versement (E12) |

## Plan de gestion

1. **Demande.** Chaque carreau de `zones.geojson` reçoit une population proportionnelle à sa
   surface bâtie, de sorte que le total égale le paramètre `population`. Déchets produits =
   population × `kg_par_habitant_jour`.
2. **Points de regroupement.** On choisit leur nombre et leur emplacement parmi les nœuds du
   réseau, pour réduire la distance entre les ménages et leur point, sans dépasser la capacité
   d'un point ni la distance qu'un pré-collecteur peut parcourir. Les sites déjà existants,
   donnés par la mairie, sont gardés. Exclus : l'eau, et les abords immédiats des écoles et des
   centres de santé.
3. **Tournées.** Chaque jour, les camions disponibles vident les points qui en ont besoin et
   évacuent vers la décharge, en respectant capacité et horaires. Les dépotoirs vérifiés sont
   des opérations de nettoyage, classées par volume et par proximité de l'eau. Si tout ne tient
   pas, les visites les moins prioritaires sont **abandonnées et nommées**, jamais oubliées.
4. **Contrôles de cohérence**, calculés et affichés avec chaque plan : capacité de chaque camion
   respectée ; durée de travail respectée ; chaque point desservi à sa fréquence ou listé comme
   non desservi ; budget tenu ou dépassement chiffré ; aucun trajet par une voie impraticable ;
   déchets produits = collectés + non collectés.

## Simulation multi-agents

Un pas de temps vaut un jour. La graine aléatoire est fixée : deux lancements du même scénario
donnent le même résultat.

| Agent | Ce qu'il fait |
|---|---|
| Ménages (un agent par carreau, portant son nombre de ménages) | Produisent des déchets. Abonnés : remis au pré-collecteur. Non abonnés : apportés au point de regroupement s'il est proche et non saturé, sinon jetés au dépotoir le plus proche, qui grossit |
| Pré-collecteurs | Desservent leurs abonnés selon leur capacité et leur fréquence, déposent au point de regroupement. Ralentis sur les voies non revêtues en saison des pluies |
| Brigade Laabal | Patrouille là où l'on jette le plus. Sensibilise d'abord, verbalise en cas de récidive : la part de dépôts sauvages baisse dans les carreaux visités, les abonnements montent |
| Mairie | Fait rouler les camions selon le plan, vide les points, nettoie des dépotoirs dans la limite du budget. Subit les pannes |

Indicateurs par jour et cumulés : tonnes produites, collectées, jetées en dépotoir ; nombre et
volume des dépotoirs ; taux de collecte ; points saturés ; coût et solde du budget.

## Paramètres

Un scénario est un jeu de paramètres. Les valeurs de départ viennent de `parametres.json` et
seront fixées avec la mairie (E8) ; d'ici là ce sont des hypothèses, marquées comme telles.

`population`, `taille_menage`, `kg_par_habitant_jour`, `taux_abonnement`, `tarif_abonnement`,
`nb_camions`, `capacite_camion_m3`, `heures_travail`, `camions_en_panne`,
`frequence_collecte_jours`, `capacite_point_m3`, `distance_max_precollecte_m`, `budget_mensuel`,
`cout_km`, `cout_jour_camion`, `saison` (`seche`, `pluies`), `vitesses_kmh` par classe de voie
et par saison, `nouveaux_quartiers` (polygone et population), `effectif_brigade`,
`mode_strict`, et les seuils des contrôles de signalements.

Les trois changements annoncés par l'énoncé sont des paramètres : `camions_en_panne`, `saison`,
`nouveaux_quartiers`.
