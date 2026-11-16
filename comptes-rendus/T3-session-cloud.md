# T3 — bloqué (cloud) — 16/11 10 h 15

Ce fichier ne s'appelle pas `T3.md` exprès : la session du PC écrira le vrai `T3.md`, et deux
fichiers du même nom créés par deux sessions donneraient un conflit Git.

- Session : dans le cloud (conteneur Linux, `uname -sr` → `Linux 6.18.44-fc-v470`). La demande
  de Franck (« clone dans `Documents\hackathon2026`, puis fais T3 ») était écrite pour le PC,
  mais elle est arrivée dans cette session cloud.
- Réalisé : rien de T3. La tâche est marquée **[PC]**, et ses deux téléchargements sont refusés
  d'ici. Je n'ai rien contourné et je n'ai écrit aucun code, pour ne pas doubler le travail de
  la session du PC.
- Vérification : les deux sources de T3, essayées depuis ce conteneur.
  ```
  $ curl -sS -I --max-time 20 https://download.geofabrik.de/africa/burkina-faso-latest.osm.pbf
  curl: (56) CONNECT tunnel failed, response 403
  $ curl -sS -I --max-time 20 https://build.protomaps.com/
  curl: (56) CONNECT tunnel failed, response 403
  ```
  Le journal du proxy donne la cause : `gateway answered 403 to CONNECT (policy denial or other
  refusal)` pour `download.geofabrik.de:443` et `build.protomaps.com:443`. C'est la règle
  réseau de l'environnement cloud, pas une panne passagère.
- Comment ça marche : sans objet (aucun code ajouté).
- Composants ajoutés : aucun.
- Décisions : pas de `donnees/preparer.py` ni de `interface/vendor/` écrits d'ici, même en
  partie. Sans l'extrait, le script ne pourrait pas être lancé pour Ouagadougou, et le relevé
  du poste comme les « Réussi si » de T3 ne se font que sur le PC.
- Problèmes : voir « Vérification ». Rien d'autre essayé, selon la règle « sans contourner ».
- À savoir :
  - T3 reste entièrement à faire. Franck doit redonner la même demande à Claude Code lancé sur
    le PC (Git Bash dans `Documents\hackathon2026`, commande `claude`).
  - Cette session cloud est libre et à jour de `main` (`d1f6c53`). Elle peut prendre T4, qui
    est « cloud ou PC », si Franck le demande et si aucune autre session ne la fait déjà.
    Aucune branche autre que `main` et celle-ci n'existe sur le dépôt à 10 h 15.
- Commit : sur la branche `claude/taches-t0-t1-t2-1konj2` (commit « T3 : bloqué »).
