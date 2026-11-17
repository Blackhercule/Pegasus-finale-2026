# Guidage parlé en mooré

Ces fichiers rendent la plateforme utilisable par quelqu'un qui ne lit pas le français. Ce sont
de **vrais enregistrements**, faits par un locuteur natif : il n'existe pas de synthèse vocale
fiable pour le mooré, et une voix humaine est de toute façon mieux comprise. Rien n'est
téléchargé à l'exécution — les fichiers sont servis par notre propre machine.

## Ce qu'il faut enregistrer

Quatorze fichiers, au format **MP3**, nommés exactement comme ci-dessous. Le texte français donne le
sens ; dites-le naturellement en mooré, lentement, dans un endroit calme.

### Les écrans d'accueil

Ce sont les messages qui s'enchaînent à l'ouverture de la page, avant le formulaire. Chacun a
son écran ; « Continuer » passe au suivant, et le dernier ouvre le formulaire.

**Le nombre d'écrans suit les fichiers réellement présents.** La page demande au chargement
lesquels existent et n'affiche que ceux-là. Déposer `accueil-2.mp3` ici fait donc apparaître
son écran tout seul, sans toucher au code ; tant qu'il manque, aucun écran muet n'est montré.
Pour changer un titre ou un texte affiché à côté, il n'y a que la liste `ACCUEIL_PREVUS` en
haut de `signaler.js` à modifier.

État au 17/11 : `accueil-1.mp3` est enregistré (17 s). Les trois autres restent à faire.

| Fichier | Ce qu'il faut dire, en mooré |
|---|---|
| `accueil-1.mp3` | **enregistré** — « Bonjour, bienvenue sur la plateforme d'assainissement de Ouagadougou. » |
| `accueil-2.mp3` | « Vous pouvez signaler un tas d'ordures, ou une fuite d'eau sur une conduite. » |
| `accueil-3.mp3` | « Touchez les grandes images, ou parlez : vous n'avez rien à écrire. » |
| `accueil-4.mp3` | « Vous pouvez signaler sans donner votre nom ni votre numéro. Ne vous inquiétez pas, nous nous occupons du reste. » |

### Le guidage étape par étape

Ceux-là se déclenchent quand on touche le haut-parleur d'une étape du formulaire.

| Fichier | Ce qu'il faut dire, en mooré |
|---|---|
| `bienvenue.mp3` | « Bonjour, bienvenue sur la plateforme d'assainissement. Vous pouvez dire où se trouve le tas d'ordures, ou bien une fuite d'eau, et dans quel quartier. Donner votre nom n'est pas obligatoire. » |
| `nature.mp3` | « Que voulez-vous signaler ? Un tas d'ordures, ou une fuite d'eau sur une conduite ? Touchez l'image qui correspond. » |
| `position.mp3` | « Nous cherchons l'endroit où vous êtes. Sortez à l'air libre et patientez un instant. » |
| `taille.mp3` | « Quelle est la taille du tas ? Un sac, une brouette, une charrette, ou un camion ? » |
| `depot.mp3` | « Où sont les ordures ? À même le sol, dans un bac, dans un caniveau, dans une fosse, ou au bord de l'eau ? » |
| `ampleur.mp3` | « Quelle est l'ampleur de la fuite ? L'eau suinte seulement, elle gicle, ou bien la rue est inondée ? » |
| `photo.mp3` | « Prenez une photo du tas d'ordures. » |
| `vocal.mp3` | « Appuyez sur le bouton et dites où se trouve le tas, et depuis combien de temps il est là. Parlez en mooré si vous préférez. » |
| `identite.mp3` | « Si vous acceptez d'être témoin, préparez votre CNIB pour une photo, puis positionnez bien le téléphone pour vous prendre en photo. Ne vous inquiétez pas, nous nous occupons du reste. Cette partie n'est pas obligatoire. » |
| `merci.mp3` | « Merci. Votre signalement est enregistré. La mairie va le vérifier. » |

Les deux fichiers `nature.mp3` et `ampleur.mp3` servent au signalement des fuites d'eau :
une fuite se transmet à l'ONEA, pas aux camions.

## Comment enregistrer

1. Avec l'enregistreur vocal d'un téléphone, dans une pièce calme, à 20 cm de la bouche.
2. Convertir en MP3 si besoin : `ffmpeg -i voix.m4a -b:a 64k bienvenue.mp3`
3. Déposer les fichiers dans ce dossier, puis `git add` et `git push`.

Tant qu'un fichier manque, la page fonctionne normalement : le bouton ne fait simplement
aucun bruit. Il n'y a donc aucun risque à n'en enregistrer que quelques-uns.

## À dire au jury

Les quatorze messages couvrent tout le parcours, pour les deux natures de signalement. Une
personne qui ne lit pas peut signaler un dépotoir ou une fuite d'eau de bout en bout : elle
écoute, elle touche de grands boutons illustrés, elle parle.
