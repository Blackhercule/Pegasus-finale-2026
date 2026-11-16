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

## Énoncé reçu (hors tâche) — 16/11 9 h 50

- Réalisé : Franck m'a transmis une photo de la feuille de l'énoncé. Je l'ai rangée telle
  quelle dans `enonce/challenge-01-assainissement-de-ouaga.jpg` et transcrite ci-dessous.
  Aucun développement commencé : `ENONCE.md` est vide et aucune tâche ne porte sur ce sujet.
- Transcription (mot pour mot, sans interprétation) :

  > HACKATHON DES UNIVERSITÉS 2026 · FINALE
  > **Deux challenges pour la f…** (titre coupé par le bord de la photo)
  > Thème de l'année : **l'Open Source**. Proposition à valider par le jury.
  >
  > **01 — Assainissement de Ouaga**
  > Un outil libre d'aide à la décision, du signalement des dépotoirs sauvages jusqu'au plan
  > de gestion de la ville, avec simulation de tous les acteurs.
  >
  > CE QUE L'OUTIL FAIT
  > · Cartographie des dépotoirs et signalements vérifiés
  > · Plan de gestion : emplacement des points de regroupement, tournées optimisées
  > · Simulation multi-agents : ménages, pré-collecteurs, brigade Laabal, mairie
  > · Paramètres modifiables et mis à jour (population, abonnements, camions, fréquences,
  >   budget) pour comparer des scénarios
  >
  > DONNÉES
  > Carte ouverte (OpenStreetMap, Open Buildings), signalements collectés par chaque équipe
  > dans son secteur, paramètres de départ fixés avec la mairie. Le jury garde un jeu de test
  > caché.
  >
  > ÉPREUVE EN DIRECT
  > Le jury injecte des signalements piégés, puis change les paramètres (camions en panne,
  > saison des pluies, nouveau quartier). Le plan doit se recalculer et rester cohérent.
  >
  > BIEN COMMUN
  > La première carte ouverte des dépotoirs de Ouaga, versée dans OpenStreetMap, et un
  > simulateur réutilisable par d'autres communes.
  >
  > Étiquettes : Cartographie · Optimisation · Simulation multi-agents · Mobile
  >
  > Bandeau du bas : CHAQUE SUJET ✓ Aucune dépendance à des données indisponibles ✓ Une
  > épreu… (coupé)

- Ce qui manque sur la photo : la fin du titre, le challenge 02 en entier, la suite du bandeau
  du bas, et tout ce qui concerne les échéances, les livrables, les critères de notation et la
  façon de soumettre. Il faut d'autres photos pour remplir ces parties de `ENONCE.md`.
- À savoir, pour le coordinateur :
  - La feuille annonce le thème « l'Open Source », alors que `CLAUDE.md` parle de
    « souveraineté technologique ».
  - Le socle de T1 et T2 (Keycloak, second facteur, console d'enrôlement) ne répond à aucune
    des quatre fonctions demandées par ce challenge (carte, plan de gestion, simulation,
    scénarios). Si l'équipe choisit le challenge 01, ces deux tâches sont à revoir avant
    d'y passer du temps.
  - Deux règles de `CLAUDE.md` entrent en tension avec cet énoncé et demandent une décision :
    « données fictives uniquement » (l'énoncé demande des signalements collectés sur le
    terrain) et « aucun service en ligne tiers » (l'énoncé demande de verser la carte dans
    OpenStreetMap, ce qui est une publication en ligne).
  - À télécharger tant qu'il y a du réseau, si ce challenge est retenu : l'extrait
    OpenStreetMap de Ouagadougou, les données Open Buildings de la zone, et de quoi afficher
    un fond de carte sans Internet. Sans cela la démonstration hors ligne n'aura pas de carte.
  - Le PC est un i5 sans carte graphique : l'optimisation des tournées et la simulation
    devront rester légères, d'autant que le jury fait recalculer le plan en direct.
  - T0 reste bloquée (voir plus haut) : le relevé du PC n'est toujours pas fait.
- Commit : sur la branche `claude/taches-t0-t1-t2-1konj2` (commit « Énoncé : photo du
  challenge 01 »).
