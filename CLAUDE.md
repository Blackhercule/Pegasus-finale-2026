# Groupe Pegasus — finale du Hackathon des Universités 2026

Ce fichier est lu par Claude Code au début de chaque session, sur le PC de l'équipe.

## La situation

Nous sommes trois étudiants de l'Université Joseph Ki-Zerbo (Ouagadougou), finalistes du
Hackathon des Universités 2026, dont le thème est la souveraineté technologique. L'énoncé est
dévoilé à l'ouverture. Nous avons environ deux jours pour livrer un prototype qui fonctionne,
le montrer en direct à un jury sur ce PC, et le soumettre.

Le temps est la ressource rare. Une petite solution qui marche devant le jury vaut mieux qu'une
grande solution à moitié finie : à chaque choix, prends la voie la plus simple qui répond à
l'exigence.

## Qui fait quoi

Deux Claude travaillent sur ce projet. Ils ne se parlent pas directement.

- **Toi (Claude Code, sur ce PC)** : le code, Docker, les tests, Git. Tu es le seul à pouvoir
  lancer le projet et voir ce qui se passe réellement sur cette machine.
- **Le coordinateur (Claude dans l'application, avec Franck)** : il lit l'énoncé officiel, écrit
  les tâches, rédige la documentation, la présentation et le dossier de soumission. Il ne voit
  pas ce PC : il ne connaît que ce qui est poussé sur GitHub.
- **Franck** fait le lien : il lance tes sessions et rapporte au coordinateur ce qu'il observe.

Conséquence : tout ce que le coordinateur doit savoir (ce qui est fait, ce qui a échoué, ce que
tu as décidé) doit être écrit dans `COMPTES-RENDUS.md` et poussé. Ce qui n'est pas dans le dépôt
n'existe pas pour lui.

## Les fichiers et qui les écrit

| Fichier | Contenu | Écrit par |
|---|---|---|
| `ENONCE.md` | Exigences numérotées (`E1`, `E2`…), critères de notation, échéances | Coordinateur |
| `TACHES.md` | Tâches (`T1`…) et correctifs (`C1`…) à réaliser | Coordinateur |
| `SOUMISSION.md`, `README.md`, `docs/` | Dossier de soumission, documentation, présentation | Coordinateur |
| `COMPTES-RENDUS.md` | Ta réponse à chaque tâche | Toi |
| Le code, les tests, Docker, les scripts | | Toi |

Ne modifie pas les fichiers du coordinateur : si deux personnes modifient le même fichier, Git
crée un conflit et l'équipe perd du temps. Si une tâche te paraît fausse, incomplète ou
contraire à `ENONCE.md`, dis-le dans ton compte rendu.

## Le cycle d'une tâche

Franck te dira par exemple « fais la tâche T3 ».

1. `git pull`, puis lis la tâche dans `TACHES.md` et les exigences de `ENONCE.md` qu'elle cite.
2. Réalise la tâche, et seulement elle.
3. Lance sur ce PC la vérification décrite sous « Réussi si ».
4. Ajoute ton compte rendu à la fin de `COMPTES-RENDUS.md` (le modèle est en tête du fichier).
5. Fais un commit qui contient le code et le compte rendu, puis `git push`.

### « Fait » veut dire vérifié sur ce PC

Une tâche est faite quand sa vérification a été lancée ici et a réussi, pas quand le code est
écrit. Pendant le sprint précédent, presque toutes les pannes venaient de code écrit sans avoir
pu être lancé sur ce PC (voir les pièges plus bas). Dans le compte rendu, colle la commande
lancée et la fin de sa sortie.

Si la vérification échoue et que la cause ne se trouve pas rapidement, n'insiste pas en
boucle : écris « bloqué » dans le compte rendu, avec le message d'erreur exact et ce que tu as
essayé. Pousse le compte rendu sur `main` et le code en cours sur une branche `essai-T3` (au
numéro de la tâche), pour que `main` reste toujours en état de marche et que le coordinateur
puisse lire ton essai.

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

- **Souveraineté.** Tout tourne sur la machine de l'équipe. Aucun service en ligne tiers à
  l'exécution : pas de CDN, pas d'API externe, pas d'hébergement cloud, pas de polices ou de
  scripts chargés depuis Internet. C'est le thème du concours, et le jury le vérifiera.
- **Hors ligne.** La démonstration doit démarrer sans Internet. Ce qui a besoin d'un
  téléchargement (image Docker, paquet) se fait à l'avance et se signale dans le compte rendu,
  pour que l'équipe le prépare tant qu'elle a du réseau.
- **Pas de cryptographie écrite par l'équipe.** Utilise des bibliothèques et des protocoles
  éprouvés. Un jury de cybersécurité sanctionne la cryptographie maison.
- **Données fictives uniquement**, et aucun test d'intrusion sur un système réel.
- **Aucun secret dans le dépôt.** Les mots de passe et les clés vont dans `.env` (ignoré par
  Git), avec un `.env.exemple` sans valeur réelle.
- **En français** : l'interface, les messages d'erreur, la documentation et les messages de
  commit. Le jury et les utilisateurs visés sont francophones.

## Git

- Un commit par tâche vérifiée, avec le numéro en tête : `T3 : formulaire de dépôt de demande`.
- Pousse sur `main`. Jamais de `--force`. Si le push est refusé parce que le dépôt distant a
  avancé : `git pull --rebase`, puis `git push`.
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

## Le socle réutilisable

Notre projet du sprint, `messagerie-souveraine` (dépôt `Blackhercule/Messagerie-souveraine`), est
sur ce PC dans `Documents\hackathon2026\messagerie-souveraine`. Il fonctionne ici et ses 41 tests
passent. Quand une tâche dit « reprendre depuis le socle », copie la brique plutôt que de la
réécrire, après un `git pull` dans ce dossier :

| Brique | Où | Ce qu'elle apporte |
|---|---|---|
| Installation | `installer.sh`, `.env.exemple` | Une seule commande, secrets générés, `--changer-adresse` (changer de réseau sans perdre les données), `--reinitialiser`, démarrage sans Internet |
| HTTPS local | `caddy/` | Point d'entrée unique, autorité de certification interne, accès depuis les téléphones du réseau |
| Identité | `keycloak/realm-administration.json` et l'étape `kcadm` de `installer.sh` | Connexion OIDC, second facteur TOTP obligatoire, rôles et groupes |
| Application web protégée | `console/` | Application Flask derrière Keycloak : enrôlement, révocation, journal de sécurité, QR code TOTP |
| Conteneurs | `docker-compose.yml`, `postgres/creer-bases.sh` | Réseau interne sans accès à Internet, plusieurs bases PostgreSQL |
| Tests | `tests/` | `pytest` contre l'installation Docker, connexion Keycloak automatisée (`tests/navigateur.py`) |

Ne reprends que ce que la tâche demande, et ne modifie jamais le dossier `messagerie-souveraine`
lui-même : il reste notre référence qui marche.
