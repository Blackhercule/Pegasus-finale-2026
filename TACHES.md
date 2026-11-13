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
