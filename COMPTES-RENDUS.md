# Comptes rendus

Écrit par Claude Code, lu par le coordinateur. Un compte rendu par tâche, ajouté à la fin du
fichier, sur ce modèle :

```
## T3 — fait | partiel | bloqué — 16/11 14 h 20

- Réalisé : ce qui a été fait, en deux ou trois lignes.
- Vérification : la commande lancée sur ce PC et la fin de sa sortie.
- Comment ça marche : l'explication que chaque membre de l'équipe doit pouvoir redonner au jury.
- Composants ajoutés : nom, licence et lien du projet (ou « aucun »).
- Décisions : les choix techniques pris seul, une ligne chacun.
- Problèmes : message d'erreur exact et ce qui a été essayé (si partiel ou bloqué).
- À savoir : ce qui demande Internet, ce que l'équipe doit faire à la main, défauts remarqués
  ailleurs.
- Commit : identifiant court (et nom de la branche d'essai si bloqué).
```

Écris ce qui est vrai, pas ce qui est espéré : « non vérifié » ou « bloqué » aide davantage
l'équipe qu'un « fait » qui tombe en panne devant le jury.

---

## T0 — bloqué — 16/11 9 h 15

- Réalisé : rien de ce que la tâche demande. Cette session de Claude Code ne tourne pas sur le
  PC de l'équipe : elle a été lancée dans un conteneur cloud (Claude Code sur le web), qui ne
  voit ni le PC, ni son Docker Desktop, ni le dossier `messagerie-souveraine`. Le relevé demandé
  par T0 doit décrire le PC ; un relevé de ce conteneur tromperait le coordinateur, donc je ne
  l'ai pas écrit comme tel.
- Vérification : ce qui prouve que la session n'est pas sur le PC.
  ```
  $ uname -a
  Linux vm 6.18.44-fc-v470 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux
  $ head -1 /etc/os-release
  PRETTY_NAME="Ubuntu 24.04.5 LTS"
  $ ls ~/Documents
  ls: cannot access '/root/Documents': No such file or directory
  ```
  J'ai aussi demandé la liste des dossiers du PC partagés avec cette session (Remote Control) :
  elle est vide, donc aucun moyen d'atteindre le PC d'ici.
- Comment ça marche : sans objet (aucun code ajouté).
- Composants ajoutés : aucun.
- Décisions :
  - T1 et T2 non commencées : la consigne était de s'arrêter à la première tâche bloquée, et
    leurs « Réussi si » exigent aussi une vérification sur le PC.
  - Compte rendu poussé sur la branche `claude/taches-t0-t1-t2-1konj2` et non sur `main` : une
    session cloud n'a le droit de pousser que sur sa propre branche sans accord explicite.
- Problèmes : pas de message d'erreur, c'est l'environnement qui n'est pas le bon. Essayé :
  recherche du dossier du socle (absent), recherche d'un dossier du PC partagé (aucun).
- À savoir :
  - Pour faire T0, Franck doit lancer Claude Code **sur le PC** : ouvrir un terminal Git Bash
    dans le dossier `Pegasus-finale-2026` du PC et lancer `claude`, ou utiliser l'application
    Claude Desktop sur le PC. La même demande (« fais T0, puis T1, puis T2 ») y fonctionnera.
  - Information utile au coordinateur, à ne pas confondre avec le relevé du PC : dans ce
    conteneur cloud, Docker démarre (Docker 29.9.2, Compose v5.6.1, 4 processeurs, 15 Go de
    mémoire, Python 3.13, Node 22) et le dépôt `Blackhercule/Messagerie-souveraine` est
    accessible. Une session cloud pourrait donc préparer le code de T1 et T2 sur une branche et
    le vérifier sous Linux ; il resterait à le vérifier sur le PC (Windows, Git Bash), là où
    les pannes du sprint sont apparues. Je ne l'ai pas fait : c'est à l'équipe de le décider.
  - Rien n'a été installé ni modifié sur le PC ou dans le dossier du socle.
- Commit : voir `git log` de la branche `claude/taches-t0-t1-t2-1konj2` (commit « T0 : bloqué »).
