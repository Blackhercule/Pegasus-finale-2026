# Scénario de démonstration devant le jury

Durée visée : **8 minutes**, plus les questions. Trois membres, trois rôles. Tout se passe sur
le PC de l'équipe, **sans Internet** : couper le Wi-Fi avant de commencer est le plus parlant.

## Avant d'entrer

- [ ] Docker Desktop démarré, `./installer.sh --changer-adresse <IP du PC>` lancé, page de
      décision ouverte dans un onglet, page de vérification dans un second.
- [ ] Certificat `ca-assainissement.crt` installé sur le PC **et** sur le téléphone de démo.
- [ ] Un téléphone connecté au même réseau (ou en partage de connexion depuis le téléphone).
- [ ] Les signalements réellement collectés dans notre secteur sont déjà dans la base.
- [ ] Le fichier de pièges `tests/pieges.json` est accessible pour le jury.
- [ ] Les huit enregistrements en mooré sont dans `interface/signaler/audio/moore/`.
- [ ] Les trois comptes (`agent`, `brigade`, `collecte`) sont notés, mots de passe à portée.
- [ ] Un dossier de démonstration est déjà à l'étape « confirmé », pour montrer la suite de la
      chaîne sans tout refaire en direct.
- [ ] Wi-Fi du PC coupé.

## Refaire la vidéo de démonstration

Avec l'application qui tourne :

```bash
python outils/donnees_demonstration.py      # dossiers à toutes les étapes de la chaîne
node outils/filmer.mjs                      # filme les sept scènes dans /tmp/video
python outils/monter_video.py               # assemble, sous-titre, écrit le fichier
```

Rien n'est mis en scène : ce sont les vraies pages avec les vraies données.

## Déroulé

| Temps | Qui | Ce qu'on montre | Ce qu'on dit |
|---|---|---|---|
| 0:00 | YE | La carte de décision, Wi-Fi coupé | « Tout tourne sur cette machine : le fond de carte, les données, les calculs. Aucune connexion. » |
| 0:40 | KIEMA | Sur le téléphone : signaler un dépotoir dans la salle. Toucher le bouton **Mooré** : l'étape parle. Mesurer le tas, choisir « dans un caniveau », **parler** au lieu d'écrire | « Vingt secondes, et sans savoir lire : la page parle en mooré, et on peut décrire le lieu à la voix. Sans réseau, ça part tout seul plus tard. » |
| 1:20 | YE | Le point apparaît sur la carte | « Il faut deux sources différentes pour qu'un dépotoir soit vérifié : un seul signalement ne suffit pas. » |
| 1:40 | TRAORE | Poste **Mairie** : ouvrir le dossier, écouter le message vocal, confirmer. Puis poste **Brigade Laabal** : faire le constat. Puis **mairie** : programmer. Puis **collecte** : déclarer le ramassage | « Un signalement n'envoie pas un camion : il ouvre un dossier qui passe de poste en poste. Chaque passage est daté et signé, et c'est ainsi que les responsabilités se situent chez les riverains. » Montrer qu'un poste ne peut pas agir à la place d'un autre. |
| 2:40 | TRAORE | Page de vérification : charger `tests/pieges.json` | « Voici 42 signalements piégés. Regardez : chacun est écarté avec son motif — coordonnées inversées, point au milieu d'un barrage, date dans le futur, volume négatif… Et le serveur tient. » |
| 3:20 | TRAORE | Montrer que la carte n'a pas bougé | « Aucun piège n'entre dans le plan. » |
| 3:40 | YE | Le plan : points de regroupement, tournées, contrôles de cohérence | « 224 points placés par couverture gloutonne, les tournées par l'algorithme des économies de Clarke et Wright. Le plan dit lui-même ce qu'il n'arrive pas à faire. » |
| 4:40 | YE | Le jury choisit : camions en panne, saison des pluies, nouveau quartier | « Ce sont des paramètres, pas du code. » Recalcul en 5 secondes, les arrêts abandonnés sont nommés. |
| 5:40 | KIEMA | Page de comparaison de scénarios | « Ajouter des camions ne suffit pas : de 24 à 45 camions, le taux de collecte ne bouge presque pas. Il faut aussi passer tous les jours et faire monter les abonnements : on passe alors de 18 % à 38 %. » |
| 6:30 | TRAORE | La simulation : les quatre acteurs | « Ménages, pré-collecteurs, brigade Laabal, mairie. La brigade fait reculer les dépôts sauvages, mais seulement là où un point de regroupement n'est pas déjà saturé. » |
| 7:15 | YE | L'export OpenStreetMap | « Les dépotoirs vérifiés deviennent un bien commun. Le code ne publie jamais tout seul : un humain relit dans JOSM avant de verser. » |
| 7:45 | YE | `python -m pytest tests/ -q` | « 55 tests, dont les 42 pièges. » |

## Questions attendues, et la réponse courte

| Question | Réponse |
|---|---|
| « D'où vient la population par quartier ? » | Répartie au prorata de la surface bâtie d'OpenStreetMap, de sorte que le total égale la population donnée en paramètre. C'est une approximation, et elle est écrite dans les limites connues. |
| « Pourquoi pas une bibliothèque d'optimisation ? » | Parce que nous devons pouvoir expliquer chaque ligne au jury, et parce que l'algorithme des économies tient en vingt lignes et recalcule en 5 secondes sur un portable. |
| « Et si le jury envoie 10 000 signalements ? » | Le lot est traité ligne par ligne ; les doublons fusionnent, les pièges sont écartés. Le serveur ne répond jamais par une erreur globale. |
| « Qu'est-ce qui est à vous, et qu'est-ce qui est repris ? » | Repris : la carte, la géométrie, les trajets, les agents. À nous : les contrôles des signalements, la chaîne entre postes, le placement des points, les tournées, les contrôles de cohérence, la simulation de la filière et toute l'interface. |
| « Pourquoi demander la CNIB ? » | On ne la demande pas : le signalement marche sans nom. Elle n'est proposée qu'à qui accepte d'être témoin dans une procédure, elle n'est visible que d'un agent connecté, et la mairie l'efface en un clic à la clôture. |
| « Le mooré, c'est de la synthèse vocale ? » | Non : ce sont des enregistrements d'un locuteur natif. Aucune synthèse fiable n'existe pour le mooré, et surtout pas hors ligne. Dans l'autre sens, on ne tente aucune transcription : l'agent écoute le message lui-même. |
| « Que faut-il pour l'utiliser dans une autre commune ? » | Son extrait OpenStreetMap et son fichier de paramètres. Une seule commande. |

## Si quelque chose tombe en panne

1. **La carte ne s'affiche pas** : vérifier que les conteneurs tournent (`docker compose ps`),
   puis recharger. Le fond de carte est un simple fichier, il ne dépend de rien d'extérieur.
2. **Le téléphone refuse la position** : le certificat n'est pas installé. Montrer la page
   depuis le navigateur du PC à la place.
3. **Le recalcul est long** : réduire la durée simulée à 15 jours.
4. **Docker ne démarre pas** : lancer l'application sans conteneur, en dernier recours :
   `pip install -r requirements.txt` puis
   `AGENT_MOT_DE_PASSE=demo SECRET_SESSION=demo python -m gunicorn --bind 0.0.0.0:8000 application.wsgi:app`
   (sans HTTPS : le téléphone ne pourra pas donner sa position, le reste fonctionne).
