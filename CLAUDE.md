# Groupe Pegasus — finale du Hackathon des Universités 2026

Ce fichier est lu par Claude Code au début de chaque session, sur le PC de l'équipe.

## La situation

Nous sommes trois étudiants de l'Université Joseph Ki-Zerbo (Ouagadougou), finalistes du
Hackathon des Universités 2026, dont le thème est l'open source. Notre sujet est le challenge
01, « Assainissement de Ouaga » : un outil libre d'aide à la décision, du signalement des
dépotoirs sauvages jusqu'au plan de gestion de la ville, avec simulation de tous les acteurs.

La finale dure du 16 au 18 novembre. Le jury teste l'outil en direct : il injecte des
signalements piégés, puis change les paramètres (camions en panne, saison des pluies, nouveau
quartier), et le plan doit se recalculer et rester cohérent.

- `ENONCE.md` : les exigences, numérotées `E1`…
- `docs/conception.md` : l'architecture, les formats de fichiers, les tables et l'API. Lis-le
  avant toute tâche de développement.

Le temps est la ressource rare. Une petite solution qui marche devant le jury vaut mieux qu'une
grande solution à moitié finie : à chaque choix, prends la voie la plus simple qui répond à
l'exigence.

## Qui fait quoi

Deux Claude travaillent sur ce projet. Ils ne se parlent pas directement.

- **Toi (Claude Code)** : le code, Docker, les tests, Git.
- **Le coordinateur (Claude dans l'application, avec Franck)** : il lit l'énoncé officiel, écrit
  les tâches, rédige la documentation, la présentation et le dossier de soumission. Il ne voit
  pas ce PC : il ne connaît que ce qui est poussé sur GitHub.
- **Franck** fait le lien : il lance tes sessions et rapporte au coordinateur ce qu'il observe.

Conséquence : tout ce que le coordinateur doit savoir (ce qui est fait, ce qui a échoué, ce que
tu as décidé) doit être écrit dans ton compte rendu et poussé. Ce qui n'est pas dans le dépôt
n'existe pas pour lui.

## Où tourne ta session

Vérifie-le en premier et écris-le en tête de ton compte rendu : cela change ce que tu peux faire.

- **Sur le PC de l'équipe** (Windows, Git Bash, Docker Desktop, Internet ouvert). C'est là que
  l'outil sera montré au jury. Les tâches marquées **[PC]** ne se font qu'ici : téléchargements
  de données, installation complète, essais avec les téléphones.
- **Dans le cloud** (conteneur Linux de Claude Code sur le web). Tu peux y développer et lancer
  les tests, mais tu ne vois pas le PC, et le réseau y est filtré : PyPI et GitHub répondent,
  pas Geofabrik, ni Docker Hub, ni les serveurs de cartes. Les données nécessaires sont dans le
  dépôt (`donnees/`). Si une tâche te demande un téléchargement impossible d'ici, écris
  « bloqué » et pourquoi, sans contourner.

## Les fichiers et qui les écrit

| Fichier | Contenu | Écrit par |
|---|---|---|
| `ENONCE.md` | Exigences numérotées (`E1`, `E2`…), critères de notation, échéances | Coordinateur |
| `TACHES.md` | Tâches (`T1`…) et correctifs (`C1`…) à réaliser | Coordinateur |
| `SOUMISSION.md`, `README.md`, `docs/` | Dossier de soumission, documentation, présentation | Coordinateur |
| `comptes-rendus/T5.md` (un fichier par tâche) | Ta réponse à la tâche | Toi |
| Le code, les tests, Docker, les scripts | | Toi |

Ne modifie pas les fichiers du coordinateur : si deux personnes modifient le même fichier, Git
crée un conflit et l'équipe perd du temps. Si une tâche te paraît fausse, incomplète ou
contraire à `ENONCE.md`, dis-le dans ton compte rendu.

## Le cycle d'une tâche

Franck te dira par exemple « fais la tâche T3 ».

1. `git pull`, puis lis la tâche dans `TACHES.md` et les exigences de `ENONCE.md` qu'elle cite.
2. Réalise la tâche, et seulement elle.
3. Lance sur ce PC la vérification décrite sous « Réussi si ».
4. Écris ton compte rendu dans `comptes-rendus/T3.md` (au numéro de la tâche), sur le modèle de
   `comptes-rendus/MODELE.md`. Un fichier par tâche : plusieurs sessions peuvent ainsi
   travailler en même temps sans conflit Git.
5. Fais un commit qui contient le code et le compte rendu, puis `git push`.

### « Fait » veut dire vérifié

Une tâche est faite quand sa vérification a été lancée et a réussi, pas quand le code est
écrit. Dans le compte rendu, colle la commande lancée et la fin de sa sortie, et dis où elle a
tourné : « fait (PC) » ou « fait (cloud) ». Ce qui n'a été vérifié que dans le cloud sera
relancé sur le PC par une tâche de vérification : pendant le sprint précédent, presque toutes
les pannes venaient de code qui n'avait jamais tourné sur ce PC (voir les pièges plus bas).

Si la vérification échoue et que la cause ne se trouve pas rapidement, n'insiste pas en
boucle : écris « bloqué » dans le compte rendu, avec le message d'erreur exact et ce que tu as
essayé. Pousse le compte rendu, et le code en cours sur une branche `essai-T3` (au numéro de la
tâche), pour que `main` reste toujours en état de marche et que le coordinateur puisse lire ton
essai.

### Ce que tu décides seul, et ce que tu fais remonter

- Les petits choix techniques (nom d'une fonction, structure d'un fichier, bibliothèque
  courante) : décide et note-le en une ligne dans le compte rendu.
- Ce qui change ce que le jury verra ou ce que l'énoncé demande (retirer une fonction, changer
  de technologie, une tâche qui se révèle beaucoup plus grosse que prévu) : arrête-toi,
  explique-le à Franck et écris-le dans le compte rendu avant de continuer.
- Un défaut que tu remarques en dehors de ta tâche : ne le corrige pas en passant, signale-le
  dans le compte rendu. À deux jours d'une démonstration, chaque modification non demandée est
  un risque de panne.

## Les règles du projet

- **Aucune dépendance en ligne à l'exécution** (E14). Tout tourne sur la machine de l'équipe :
  pas de CDN, pas d'API externe, pas de tuiles de carte, de polices ou de scripts chargés depuis
  Internet. Télécharger des données ouvertes une fois, pendant la préparation, est permis : on
  les range dans le dépôt avec leur source et leur licence.
- **OpenStreetMap n'est jamais modifié par le code.** L'outil produit un fichier d'export ;
  c'est un membre de l'équipe qui le relit et le verse. Des signalements de test ou piégés
  envoyés par erreur abîmeraient une carte utilisée par tout le monde.
- **Hors ligne.** La démonstration doit démarrer sans Internet. Ce qui a besoin d'un
  téléchargement (image Docker, paquet) se fait à l'avance et se signale dans le compte rendu,
  pour que l'équipe le prépare tant qu'elle a du réseau.
- **Pas de cryptographie écrite par l'équipe.** Utilise des bibliothèques et des protocoles
  éprouvés. Un jury de cybersécurité sanctionne la cryptographie maison.
- **Aucune donnée personnelle.** Les signalements de dépotoirs sont réels, collectés par
  l'équipe sur le terrain (E7), mais on n'enregistre ni nom, ni numéro, ni visage. Les comptes
  et les jeux d'essai sont fictifs. Aucun test d'intrusion sur un système réel.
- **Open source.** Le code est publié sous licence libre (`LICENSE` à la racine) et ne repose
  que sur des composants open source. Chaque fois que tu ajoutes un composant (image Docker,
  bibliothèque, outil), note son nom, sa licence et le lien de son projet dans le compte rendu :
  le règlement demande de citer chaque technologie avec sa licence.
- **Un code que chaque membre peut expliquer.** Le jury désigne lui-même le membre qui explique
  une fonction, et ne pas savoir l'expliquer est éliminatoire. Écris un code simple et lisible,
  commenté en français là où l'intention ne se devine pas, et explique dans le compte rendu
  comment fonctionne ce que tu as ajouté, surtout ce qui touche à la sécurité.
- **Aucun secret dans le dépôt.** Les mots de passe et les clés vont dans `.env` (ignoré par
  Git), avec un `.env.exemple` sans valeur réelle.
- **En français** : l'interface, les messages d'erreur, la documentation et les messages de
  commit. Le jury et les utilisateurs visés sont francophones.

## Git

- Un commit par tâche vérifiée, avec le numéro en tête : `T3 : formulaire de dépôt de demande`.
- Sur le PC, pousse sur `main`. Dans le cloud, pousse sur `main` si Franck te l'a dit dans sa
  demande ; sinon sur ta branche, et le coordinateur la fusionnera. Jamais de `--force`. Si le
  push est refusé parce que le dépôt distant a avancé : `git pull --rebase`, puis `git push`.
- Les scripts shell doivent garder des fins de ligne Unix (`.gitattributes` s'en charge) :
  sinon ils ne fonctionnent plus dans les conteneurs Linux.

## Ce PC

Windows 10, Docker Desktop, Git Bash (MINGW64), Python et Node.js. Processeur i5, pas de carte
graphique dédiée : évite ce qui demande beaucoup de calcul. Le dossier de l'utilisateur contient
des espaces (`C:\Users\YE FRANCK AHMED\…`) : mets toujours les chemins entre guillemets.

### Pièges déjà rencontrés sur ce PC

- **Chemins transformés par Git Bash.** Un argument qui commence par `/` et qui est destiné à un
  conteneur (`docker compose exec … /opt/…`) est réécrit en chemin Windows. Préfixe la commande
  par `MSYS_NO_PATHCONV=1`.
- **`curl -o /dev/null` échoue** (erreur 23) dans Git Bash. Écris `curl … >/dev/null 2>&1`.
- **Port refusé alors qu'il est libre** (« accès interdit », vu avec 8081). Windows réserve des
  plages de ports : choisis un autre port, ou relance le service dans une invite administrateur
  (`net stop winnat` puis `net start winnat`).
- **HTTPS par adresse IP derrière Caddy dans Docker.** Les navigateurs n'envoient pas de SNI
  pour une adresse IP : il faut `default_sni` dans le bloc global du `Caddyfile`, sinon
  `ERR_SSL_PROTOCOL_ERROR`.
- **Certificat de l'autorité interne.** Sous Windows : `certutil -user -addstore Root fichier.crt`.
  Sans cela, le navigateur affiche « Non sécurisé ».
- **Accents cassés en Python.** Ouvre toujours les fichiers avec `encoding="utf-8"`.
- **`npm` introuvable depuis Python.** Sous Windows c'est `npm.cmd` : cherche-le avec
  `shutil.which("npm")`.
- **Codes TOTP refusés alors qu'ils sont justes.** L'horloge de Docker Desktop dérive après une
  mise en veille : `wsl --shutdown`, puis relancer Docker Desktop.
- **Démarrage à froid.** Juste après `docker compose up`, des services comme Keycloak mettent du
  temps à répondre. Dans les scripts, attends qu'ils répondent vraiment plutôt qu'une durée
  fixe ; un test chronométré peut échouer au tout premier lancement.
- **Git demande « Unlink of file failed. Should I try again? ».** Un programme tient le fichier
  ouvert : réponds `n` et ferme ce programme.

## Ce qu'on reprend du sprint

Notre messagerie du sprint (dépôt `Blackhercule/Messagerie-souveraine`, commit `431bb09`)
fonctionne sur ce PC. On n'en reprend que ce qui sert ici, quand une tâche le demande :

- `installer.sh` : installation en une commande, secrets générés dans `.env`,
  `--changer-adresse` pour changer de réseau, précautions propres à Windows ;
- `caddy/` : HTTPS local avec autorité de certification interne et `default_sni`, pour que les
  téléphones du réseau accèdent à l'outil ;
- la façon d'écrire les tests avec `pytest`.

Keycloak, la console et Synapse ne servent pas à ce challenge. Ne modifie jamais le dossier
`messagerie-souveraine` du PC : il reste notre référence qui marche.
