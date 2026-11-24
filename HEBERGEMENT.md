# Mettre l'application en ligne gratuitement (Render)

But : obtenir une adresse du type `https://gestion-cave-xxxx.onrender.com` que Latif (ou le
patron) ouvre depuis chez lui, sur son téléphone ou son PC, sans rien installer.

Render est un hébergeur qui propose un **plan gratuit** pour un site web et une base de données
PostgreSQL. Le fichier `render.yaml` du dépôt lui décrit tout : il suffit de lui montrer le dépôt.

## Ce qu'il faut

- Un compte GitHub qui a accès au dépôt privé de l'application.
- Un compte Render : <https://render.com> → **Get Started** → **GitHub** (connexion avec GitHub).

## Les étapes (environ 10 minutes)

1. Sur Render, cliquez **New +** → **Blueprint**.
2. **Connect a repository** : la première fois, Render demande l'autorisation d'accéder à GitHub.
   Choisissez **Only select repositories**, cochez le dépôt de l'application (il est privé : sans
   cette autorisation Render ne le voit pas), puis validez.
3. Choisissez le dépôt (et la branche `main`). Render lit `render.yaml` et affiche ce qu'il va créer :
   - `cave-base` : base de données PostgreSQL (**Free**) ;
   - `gestion-cave` : le site web (**Free**).
4. Render demande la valeur de **`PATRON_MOT_DE_PASSE`** : tapez le mot de passe du compte patron
   (8 caractères minimum, pas un mot courant). Notez-le : c'est lui qui servira à se connecter.
5. Cliquez **Apply** (ou **Deploy Blueprint**). La construction prend quelques minutes ; on suit
   son avancement dans **Logs**. À la fin, on doit lire :
   `Compte patron créé : identifiant « patron ».`
   puis `Données de démonstration chargées : … ventes`.
6. Ouvrez le service **gestion-cave** : son adresse (`https://gestion-cave-….onrender.com`) est
   affichée en haut. Connectez-vous avec l'identifiant **`patron`** et le mot de passe choisi.
7. Envoyez cette adresse à Latif. Pour qu'il essaie aussi l'espace d'un gérant : page **Gérants**
   → **Mot de passe** sur « Awa Ouédraogo » (compte de démonstration), puis il se connecte avec
   l'identifiant `awa`.

Chaque fois que du code est poussé sur la branche `main`, Render redéploie tout seul. Les données
sont conservées : le compte patron et les données de démonstration ne sont créés qu'une fois.

## À savoir sur le plan gratuit

Conditions de Render telles que je les connais ; je n'ai pas pu ouvrir le site de Render depuis ma
session pour les revérifier, regardez <https://render.com/docs/free> en cas de doute.

- **Mise en veille** : sans visite pendant environ 15 minutes, le site s'endort. La visite suivante
  le réveille, mais la première page met **jusqu'à une minute** à s'afficher. C'est normal.
- **La base gratuite expire** environ **30 jours** après sa création (Render prévient par e-mail).
  C'est suffisant pour un essai. Pour garder les données plus longtemps, voir plus bas.
- Une seule base gratuite par compte Render.
- Si Render demande une carte bancaire pour vérifier le compte : je n'ai pas pu vérifier depuis
  ma session s'il le fait encore. Les services marqués **Free** ne sont pas facturés.

## Passer à une vraie utilisation

Pour une vraie cave, deux réglages changent, dans Render → **gestion-cave** → **Environment** :

1. **`DONNEES_DEMO`** → `non` (pas de données fictives).
2. Une **base qui n'expire pas**. Deux possibilités :
   - passer la base Render sur une offre payante ;
   - ou créer une base PostgreSQL gratuite chez **Neon** (<https://neon.tech>), copier son adresse
     de connexion (`postgresql://…`) et la coller dans la variable **`DATABASE_URL`** du service
     (en remplaçant la valeur liée à `cave-base`).

   Au déploiement suivant, l'application crée ses tables dans la nouvelle base, puis le compte
   patron avec `PATRON_MOT_DE_PASSE`.

## Si ça ne marche pas

| Ce qu'on voit | Que faire |
|---|---|
| La construction échoue avec « Mot de passe du patron refusé » | Le mot de passe est trop court ou trop courant. Changez `PATRON_MOT_DE_PASSE` dans **Environment**, puis **Manual Deploy**. |
| Les logs disent « PATRON_MOT_DE_PASSE n'est pas défini » | Ajoutez la variable dans **Environment**, puis **Manual Deploy**. |
| « Bad Request (400) » | Ouvrez le site par son adresse `onrender.com` ; pour un nom de domaine à vous, ajoutez-le dans la variable `ALLOWED_HOSTS`. |
| Mot de passe du patron oublié | Dans **Environment** : `PATRON_MOT_DE_PASSE` = le nouveau mot de passe, et ajoutez `REINITIALISER_MOT_DE_PASSE_PATRON` = `oui`. **Manual Deploy**, connectez-vous, puis remettez `REINITIALISER_MOT_DE_PASSE_PATRON` à `non` (sinon chaque déploiement réécrit le mot de passe). Les données sont conservées. |
| Mot de passe d'un gérant oublié | Le patron lui en donne un nouveau : page **Gérants** → **Mot de passe**. |

## Autres hébergeurs

L'application est une application Django classique (Python, PostgreSQL, gunicorn). Elle peut
aller ailleurs : il suffit de fournir les variables `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`,
`PRODUCTION=1` et `PATRON_MOT_DE_PASSE`, de lancer `bash build.sh` pour la construction et
`gunicorn config.wsgi:application` pour le démarrage.
