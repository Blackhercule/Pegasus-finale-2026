"""Repasser le masquage sur les photos déjà enregistrées.

Le masquage se fait à la réception. Une photo reçue AVANT une amélioration du détecteur, ou
avant que le masquage existe sur la machine, garde donc ses visages. Ce petit outil reprend
toutes les photos de signalement déjà sur le disque et les masque avec le détecteur actuel.

Sur le PC, une fois l'image reconstruite et l'outil redémarré :

    MSYS_NO_PATHCONV=1 docker compose exec application python -m application.remasquer

On peut le relancer sans crainte : un visage déjà flouté n'est plus détecté, la photo ressort
alors telle quelle et n'est pas réécrite.

Seule la photo du signalement est traitée. La photo de la CNIB et le portrait du déclarant,
donnés volontairement pour témoigner, ne sont jamais floutés (voir FICHIERS_JOINTS).
"""

import os
import sqlite3
import sys

from . import anonymiser


def remasquer(base: str, dossier_photos: str) -> dict:
    co = sqlite3.connect(base, timeout=10)
    co.row_factory = sqlite3.Row
    bilan = {"photos": 0, "masquees": 0, "visages": 0, "plaques": 0, "introuvables": 0}
    lignes = co.execute(
        "SELECT photo, MIN(id) AS id FROM signalements WHERE photo IS NOT NULL GROUP BY photo"
    ).fetchall()
    for ligne in lignes:
        chemin = os.path.join(dossier_photos, ligne["photo"])
        # Le chemin vient de notre propre base (« public/<empreinte> ») ; on vérifie quand même
        # qu'il ne sort pas du dossier des photos.
        if (not os.path.realpath(chemin).startswith(os.path.realpath(dossier_photos) + os.sep)
                or not os.path.isfile(chemin)):
            bilan["introuvables"] += 1
            continue
        bilan["photos"] += 1
        with open(chemin, "rb") as f:
            avant = f.read()
        apres, comptes = anonymiser.masquer(avant)
        if not comptes["visages"] and not comptes["plaques"]:
            continue
        # On écrit à côté, puis on remplace d'un coup : une coupure au milieu ne laisse jamais
        # une photo à moitié écrite.
        provisoire = chemin + ".masquage"
        with open(provisoire, "wb") as f:
            f.write(apres)
        os.replace(provisoire, chemin)
        # Plusieurs signalements peuvent partager la même photo (même empreinte) : tous sont
        # mis à jour.
        co.execute(
            "UPDATE signalements SET visages_masques = COALESCE(visages_masques, 0) + ?,"
            " plaques_masquees = COALESCE(plaques_masquees, 0) + ? WHERE photo = ?",
            (comptes["visages"], comptes["plaques"], ligne["photo"]))
        co.commit()
        bilan["masquees"] += 1
        bilan["visages"] += comptes["visages"]
        bilan["plaques"] += comptes["plaques"]
    co.close()
    return bilan


def main() -> int:
    if not anonymiser.disponible():
        print("Masquage indisponible : OpenCV n'est pas installé dans cette image.")
        return 1
    base = os.environ.get("BASE_DONNEES", "/travail/signalements.sqlite")
    dossier = os.environ.get("DOSSIER_PHOTOS", os.path.join(os.path.dirname(base), "photos"))
    bilan = remasquer(base, dossier)
    print("Photos relues : %(photos)d — photos masquées : %(masquees)d "
          "(%(visages)d visage(s), %(plaques)d plaque(s))" % bilan)
    if bilan["introuvables"]:
        print("Photos introuvables sur le disque : %d" % bilan["introuvables"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
