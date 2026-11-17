# `signalements-ouaga.geojson` — licence et provenance

## Licence

**Open Database License (ODbL) 1.0** — https://opendatacommons.org/licenses/odbl/1-0/

Vous pouvez copier, distribuer, utiliser et modifier ce jeu de données, y compris pour un usage
commercial, à trois conditions : **citer la source** (« © équipe PEGASUS, Université Joseph
Ki-Zerbo, et contributeurs, ODbL 1.0 »), **partager à l'identique** toute version modifiée de la
base, et la garder **ouverte**. C'est la licence d'OpenStreetMap : les dépotoirs de ce fichier
peuvent donc y être versés.

## Provenance

- Chaque entité est un **dépotoir sauvage** signalé par des habitants de Ouagadougou avec la
  page de signalement de l'outil « Assainissement de Ouaga », puis **vérifié** : confirmé par un
  agent de la mairie, ou vu par au moins deux appareils différents.
- Les positions viennent du GPS du téléphone (quelques mètres), ou d'un lieu connu choisi dans
  une liste quand le GPS ne marche pas (environ 150 m).
- Le fichier est produit par `python outils/exporter_signalements.py`, ou téléchargé depuis
  l'adresse `/api/export/geojson` de l'outil (réservée aux agents connectés).

## Ce que contient chaque entité

| Propriété | Sens |
|---|---|
| `id` | identifiant du dépotoir dans l'outil |
| `date_observation` | dernière fois où il a été vu (AAAA-MM-JJ) |
| `type_dechets` | `menager`, `gravats`, `mixte` ou `autre` (le plus souvent indiqué) |
| `volume_m3`, `surface_m2` | estimations des habitants (médiane) |
| `depot` | où se trouvent les ordures : `plein_air`, `bac`, `caniveau`, `fosse`, `berge`, `autre` |
| `nb_signalements`, `nb_sources` | combien de signalements, venus de combien d'appareils |
| `premier_vu`, `dernier_vu` | première et dernière observation |
| `etape` | où en est le dossier à la mairie (`signale`, `confirme`, `constat`, `a_collecter`, `collecte`) |

## Ce qu'il ne contient pas

**Aucune donnée personnelle** : ni nom, ni téléphone, ni photo, ni message vocal, ni pièce
d'identité, ni pseudonyme de l'appareil, ni commentaire libre. Les propriétés publiées sont
choisies une à une dans le code (`application/export_geojson.py`), et un test automatique le
vérifie.

## État au 17/11/2026

Le fichier est **vide** : la collecte de terrain de l'équipe (exigence E7) n'est pas encore
faite. Les dépotoirs de la démonstration sont fictifs et ne doivent jamais y figurer. Après la
collecte, relancer `python outils/exporter_signalements.py`, relire le fichier, puis le verser.
