# Guidage parlé en mooré

Ces fichiers rendent la plateforme utilisable par quelqu'un qui ne lit pas le français. Ce sont
de **vrais enregistrements**, faits par un locuteur natif : il n'existe pas de synthèse vocale
fiable pour le mooré, et une voix humaine est de toute façon mieux comprise. Rien n'est
téléchargé à l'exécution — les fichiers sont servis par notre propre machine.

## Ce qu'il faut enregistrer

Huit fichiers, au format **MP3**, nommés exactement comme ci-dessous. Le texte français donne le
sens ; dites-le naturellement en mooré, lentement, dans un endroit calme.

| Fichier | Ce qu'il faut dire, en mooré |
|---|---|
| `bienvenue.mp3` | « Bonjour, bienvenue sur la plateforme d'assainissement. Vous pouvez dire où se trouve le tas d'ordures et dans quel quartier. Donner votre nom n'est pas obligatoire. » |
| `position.mp3` | « Nous cherchons l'endroit où vous êtes. Sortez à l'air libre et patientez un instant. » |
| `taille.mp3` | « Quelle est la taille du tas ? Un sac, une brouette, une charrette, ou un camion ? » |
| `depot.mp3` | « Où sont les ordures ? À même le sol, dans un bac, dans un caniveau, dans une fosse, ou au bord de l'eau ? » |
| `photo.mp3` | « Prenez une photo du tas d'ordures. » |
| `vocal.mp3` | « Appuyez sur le bouton et dites où se trouve le tas, et depuis combien de temps il est là. Parlez en mooré si vous préférez. » |
| `identite.mp3` | « Si vous acceptez d'être témoin, préparez votre CNIB pour une photo, puis positionnez bien le téléphone pour vous prendre en photo. Ne vous inquiétez pas, nous nous occupons du reste. Cette partie n'est pas obligatoire. » |
| `merci.mp3` | « Merci. Votre signalement est enregistré. La mairie va le vérifier. » |

## Comment enregistrer

1. Avec l'enregistreur vocal d'un téléphone, dans une pièce calme, à 20 cm de la bouche.
2. Convertir en MP3 si besoin : `ffmpeg -i voix.m4a -b:a 64k bienvenue.mp3`
3. Déposer les fichiers dans ce dossier, puis `git add` et `git push`.

Tant qu'un fichier manque, la page fonctionne normalement : le bouton ne fait simplement
aucun bruit. Il n'y a donc aucun risque à n'en enregistrer que quelques-uns.

## À dire au jury

Les huit messages couvrent tout le parcours. Une personne qui ne lit pas peut signaler un
dépotoir de bout en bout : elle écoute, elle touche de grands boutons illustrés, elle parle.
