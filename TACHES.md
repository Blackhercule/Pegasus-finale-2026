# Tâches

Écrit par le coordinateur. Claude Code répond dans `COMPTES-RENDUS.md` et ne modifie pas ce
fichier.

- `T…` : une tâche à réaliser.
- `C…` : un correctif, pour quelque chose qui ne marche pas sur le PC et que l'équipe a signalé.
- `E…` : une exigence de `ENONCE.md`.

L'état de chaque tâche (fait, partiel, bloqué) se lit dans `COMPTES-RENDUS.md`.

---

## T0 — Vérifier le poste et le cycle de travail

**Pourquoi.** Avant le jour J, on veut savoir ce qui est installé sur ce PC et s'assurer que le
cycle « tâche → compte rendu → push » fonctionne. Le coordinateur s'appuiera sur ce relevé pour
écrire des tâches adaptées à la machine.

**À faire.** Cette tâche ne fait que relever : n'installe rien et ne modifie rien.

1. Relever les versions de `git`, `docker`, `docker compose`, `python`, `pip`, `node`, `npm` et
   `ffmpeg`. Noter « absent » pour un outil qui manque.
2. Vérifier que Docker tourne (`docker info`) et lister les images présentes (`docker images`) :
   ce sont celles dont on disposera sans Internet.
3. Noter l'espace disque libre et la mémoire vive du PC.
4. Dans le dossier du socle `messagerie-souveraine` : noter le dernier commit
   (`git log -1 --oneline`) et s'il y a des modifications locales (`git status -sb`).

**Réussi si** le relevé figure dans `COMPTES-RENDUS.md` sous « T0 », et que le commit est poussé
sur `main`.

---

## T1 — Mettre en place le socle souverain (sans la messagerie)

**Pourquoi.** Le thème n'est pas encore connu, mais la finale porte sur l'adoption, l'adaptation
et l'amélioration de solutions open source. Quelle que soit la solution retenue, elle aura
besoin de la même base : une installation en une commande, un point d'entrée HTTPS, une
connexion avec second facteur, et une console pour enrôler et révoquer les agents. Cette base
existe et fonctionne dans notre messagerie du sprint. On la reprend ici sans la partie
messagerie, pour que la solution du thème n'ait plus qu'à s'y brancher.

**Ce qu'on doit obtenir.**

```
Navigateur ── HTTPS :8443 ── Caddy ──┬── /           page d'accueil du portail (statique)
                                     ├── /auth/*     Keycloak (mot de passe + code TOTP)
                                     └── /console*   console de sécurité (Flask)
                        PostgreSQL (base keycloak) · réseau Docker interne sans Internet
```

**Source.** Pars d'une copie fraîche du dépôt du sprint, pour ne dépendre ni de l'état ni des
modifications locales du dossier `messagerie-souveraine` de ce PC :
`git clone --depth 1 https://github.com/Blackhercule/Messagerie-souveraine` dans un dossier
temporaire hors de ce dépôt (commit attendu : `431bb09`).

**Avant de démarrer.** Le socle utilise les mêmes ports que la messagerie (8443, et 8081 sur
127.0.0.1). Si ses conteneurs tournent, arrête-les avec `docker compose stop` depuis son
dossier : rien n'est effacé, et c'est la seule action permise dans ce dossier.

**À reprendre, en retirant tout ce qui concerne Synapse, Matrix et Element.**

1. `docker-compose.yml` : projet nommé `pegasus-finale` ; services `postgres`, `keycloak`,
   `console` et `caddy` seulement. Le réseau interne sans accès à Internet est conservé.
2. `caddy/` : l'image ne télécharge plus Element. Le `Caddyfile` garde le bloc global avec
   `default_sni`, les en-têtes de sécurité, le blocage de `/auth/admin/*`, les routes `/auth/*`
   et `/console*`, et l'administration de Keycloak sur `127.0.0.1:8081`. La racine `/` sert une
   page d'accueil statique en français, sans aucune ressource externe : un titre « Portail
   souverain de l'administration », un lien vers la console, et un emplacement « Application :
   à venir ».
3. `keycloak/realm-administration.json` : retire le client `synapse` ; le nom affiché du royaume
   devient « Portail souverain de l'administration ». Le reste ne change pas (politique TOTP,
   protection contre les essais répétés, groupes, rôle, comptes de démonstration).
4. `postgres/creer-bases.sh` : seule la base `keycloak` est créée.
5. `console/` : supprime `messagerie.py` et tout ce qui l'appelle.
   - Révoquer : compte désactivé dans Keycloak, sessions fermées, retiré des groupes.
   - Téléphone perdu : sessions fermées, nouveau mot de passe provisoire, second facteur remplacé.
   - La recopie des habilitations vers un fichier, et le fil d'exécution qui la répète, n'ont
     plus de lecteur : retire-les. Le groupe `habilites-confidentiel` et sa case dans la console
     restent.
   - Le journal garde les actions de la console et les connexions vues par Keycloak.
   - Dans les textes affichés, « messagerie » devient « portail », et les paragraphes sur le
     chiffrement des messages et les salons disparaissent. Dans `second_facteur.py`, l'émetteur
     devient « Portail souverain ».
   - Là où la console annonçait un nombre d'appareils déconnectés, annonce le nombre de sessions
     Keycloak fermées si tu l'obtiens simplement ; sinon retire ce nombre.
6. `installer.sh` et `.env.exemple` : mêmes options (`--changer-adresse`, `--reinitialiser`),
   sans les secrets de Synapse. L'attente du démarrage vérifie Keycloak et la console. Le
   certificat de l'autorité s'appelle `ca-portail.crt`. Garde toutes les précautions propres à
   Windows déjà présentes dans le script : chacune corrige une panne rencontrée sur ce PC.
7. `outils/code_totp.py` : tel quel.

Ne reprends pas `synapse/`, `element/`, `tests/` (c'est la tâche T2) ni `docs/` (coordinateur).

**Réussi si**, sur ce PC :

- `./installer.sh` va jusqu'à « prêt » et affiche le récapitulatif ;
- `docker compose ps` montre les quatre services en marche ;
- `https://localhost:8443/` renvoie la page d'accueil, `https://localhost:8443/console/` redirige
  vers la connexion Keycloak, et `https://localhost:8443/auth/admin/` répond 404 (avec
  `curl --ssl-no-revoke --cacert ca-portail.crt`) ;
- une vraie connexion à la console réussit avec `admin.securite` / `Demo-Admin-2026` et le code
  donné par `python outils/code_totp.py admin.securite` : le tableau de bord s'affiche, et
  l'enrôlement d'un agent fictif montre son mot de passe provisoire et son QR code. Franck peut
  le faire dans le navigateur : note qui l'a vérifié ;
- `grep -ril "synapse\|matrix" . --exclude-dir=.git --exclude=CLAUDE.md --exclude=TACHES.md --exclude=COMPTES-RENDUS.md`
  ne renvoie rien.

**À ajouter au compte rendu** : la sortie de `docker stats --no-stream` une fois tout démarré
(la mémoire restante décidera quelle solution ce PC peut héberger), et les images Docker qu'il a
fallu télécharger.

---

## T2 — Tests automatisés du socle

**Pourquoi.** Au sprint, les tests automatisés rapportaient des points et nous ont évité des
pannes devant le jury. Chaque garantie du socle doit se vérifier en une commande, avant et après
le branchement de la solution du thème.

**À faire.** Depuis la même copie du dépôt du sprint, reprends `tests/` (`conftest.py`,
`navigateur.py`, `requirements.txt`) et garde les tests qui ne dépendent pas de la messagerie, en
les adaptant au socle :

- accès : second facteur exigé, compte inconnu refusé, administration de Keycloak non exposée ;
- console : connexion obligatoire, agent sans le rôle refusé, formulaire sans jeton refusé,
  en-têtes de sécurité, journal qui signale les intrusions, habilitation donnée puis retirée, un
  administrateur ne peut pas se révoquer lui-même ;
- enrôlement : la première connexion impose un nouveau mot de passe, le second facteur remis
  fonctionne ;
- révocation : l'agent révoqué ne peut plus se connecter et ses sessions sont fermées ;
- téléphone perdu : l'ancien second facteur ne fonctionne plus, le nouveau fonctionne.

Les tests de chiffrement, de classification et d'échange Matrix ne sont pas repris, ni le
dossier `tests/e2ee/`.

Vérifie aussi à la main le changement de réseau : `./installer.sh --changer-adresse <adresse IP
du PC>`, connexion à la console par cette adresse, puis retour à `localhost` par la même
commande.

**Réussi si** `cd tests && python -m pytest -q` est entièrement vert deux fois de suite sur ce
PC (le premier lancement après un démarrage à froid peut être lent), et que le changement
d'adresse a fonctionné dans les deux sens.

**À signaler dans le compte rendu.** Dans la messagerie, c'était Synapse qui refusait une
identité valide mais non enrôlée (hors du groupe `agents`, comme `visiteur.externe`). Le socle
seul n'a plus ce contrôle : note-le comme point ouvert, il sera repris quand la solution du thème
sera branchée.
