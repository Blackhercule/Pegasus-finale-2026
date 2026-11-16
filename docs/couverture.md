# Couverture des exigences

Chaque exigence de `ENONCE.md`, où elle est traitée, et ce qui manque encore. Mis à jour au fil
du travail ; ce qui n'est pas fait est écrit comme tel.

| N° | Exigence | Où | État |
|---|---|---|---|
| E1 | Cartographie des dépotoirs et signalements vérifiés | `interface/decision/`, `application/signalements/` | **Fait.** Carte hors ligne ; un dépotoir est vérifié par un agent ou par deux sources indépendantes |
| E2 | Emplacement des points de regroupement | `application/plan/` (`placer_les_points`) | **Fait.** Couverture gloutonne, portée de 800 m, eau et abords d'écoles exclus |
| E3 | Tournées optimisées | `application/plan/` (`calculer_les_tournees`) | **Fait.** Algorithme des économies (Clarke et Wright) puis 2-opt, capacité et journée de travail respectées |
| E4 | Simulation multi-agents : ménages, pré-collecteurs, brigade Laabal, mairie | `application/simulation/` | **Fait.** Les quatre acteurs, un jour par pas de temps, reproductible |
| E5 | Paramètres modifiables pour comparer des scénarios | `/api/comparer`, `interface/decision/scenarios.html` | **Fait.** Tableau et graphique côte à côte |
| E6 | Carte ouverte (OpenStreetMap, Open Buildings) | `donnees/preparer.py` | **Partiel.** OpenStreetMap : limites, voies, bâtiments, eau, lieux. Open Buildings : non intégré, les bâtiments d'OpenStreetMap ont suffi (332 556 sur la commune) |
| E7 | Signalements collectés par l'équipe dans son secteur | page mobile `/signaler/` | **L'outil est prêt ; la collecte sur le terrain reste à faire par l'équipe** |
| E8 | Paramètres de départ fixés avec la mairie | `donnees/ouagadougou/parametres.json` | **En attente.** Les valeurs actuelles sont des hypothèses, signalées comme telles ; un seul fichier à changer |
| E9 | Jeu de test caché du jury | `/api/signalements/lot` | **Fait.** Le lot accepte JSON, GeoJSON et CSV, et répond ligne par ligne |
| E10 | Signalements piégés injectés par le jury | `application/signalements/controles.py`, `tests/pieges.json` | **Fait.** Douze motifs, 42 pièges testés automatiquement |
| E11 | Changement de paramètres : le plan se recalcule et reste cohérent | `/api/plan`, `controles_de_coherence` | **Fait.** Camions en panne, saison des pluies, nouveau quartier ; recalcul en 5 s ; huit contrôles affichés |
| E12 | Carte des dépotoirs versée dans OpenStreetMap | `/api/export/osm` | **Fait côté outil.** Le versement lui-même est un geste humain, après relecture dans JOSM |
| E13 | Simulateur réutilisable par d'autres communes | `donnees/preparer.py`, `donnees/<commune>/` | **Fait.** Rien n'est propre à Ouagadougou : une commande, un nom de commune |
| E14 | Aucune dépendance à des données indisponibles | tout le dépôt | **Fait.** Données, fond de carte et bibliothèques sont dans le dépôt ; vérifié dans un navigateur : aucune requête sortante |
| E15 | Épreuve en direct impossible à préparer | — | **Fait.** Les paramètres du jury passent par l'API ; rien n'est pré-calculé ni écrit en dur |
| E16 | Code sous licence libre et bien commun | `LICENSE` (AGPL-3.0), `README.md` | **Fait.** Chaque brique citée avec sa licence |
| E17 | Cartographie, optimisation, simulation multi-agents, mobile | — | **Fait.** Les quatre sont présents, le mobile par la page de signalement |

## Ce qui reste à faire

1. **Collecter de vrais signalements** dans notre secteur (E7). C'est la seule exigence qui ne
   dépend pas du code.
2. **Obtenir les paramètres de la mairie** (E8), et la position exacte de la décharge.
3. **Vérifier l'installation sur le PC de l'équipe**, et l'accès depuis un téléphone.
4. **Verser les dépotoirs vérifiés dans OpenStreetMap** après relecture (E12).
