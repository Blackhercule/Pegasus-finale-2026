"""La chaîne de traitement d'un dépotoir, de la déclaration jusqu'au ramassage.

Un signalement n'envoie pas directement un camion : il ouvre un dossier qui passe de poste en
poste, et chaque passage est daté et signé. C'est ainsi que les responsabilités se situent.

    signalé  ──►  confirmé   ──►  constat    ──►  à collecter  ──►  collecté
    (habitant)    (agent de      (brigade        (mairie)          (équipe de
                   la mairie)     Laabal)                           collecte)

À chaque étape, un seul poste a le droit d'agir, et il ne peut faire avancer un dossier que
d'un cran. Un dossier peut aussi être classé sans suite par l'agent de la mairie (par exemple
si le tas n'existe plus sur place).
"""

import datetime
import json

from .base import signer

# Pour chaque étape : qui agit, et vers quoi elle mène.
CHAINE = {
    "signale": {
        "nom": "Signalé", "poste": "mairie", "suivante": "confirme",
        "action": "Confirmer sur le terrain",
        "explication": "Un agent de la mairie se déplace ou appelle, et confirme que le tas existe.",
    },
    "confirme": {
        "nom": "Confirmé", "poste": "brigade", "suivante": "constat",
        "action": "Faire le constat",
        "explication": "La brigade Laabal se rend sur les lieux, sensibilise les riverains et "
                       "verbalise en cas de récidive.",
    },
    "constat": {
        "nom": "Constat fait", "poste": "mairie", "suivante": "a_collecter",
        "action": "Programmer le ramassage",
        "explication": "La mairie inscrit le dépotoir dans les tournées des camions.",
    },
    "a_collecter": {
        "nom": "À collecter", "poste": "collecte", "suivante": "collecte",
        "action": "Déclarer le ramassage fait",
        "explication": "L'équipe de collecte vide le dépotoir et le déclare ramassé.",
    },
    "collecte": {
        "nom": "Collecté", "poste": None, "suivante": None,
        "action": None, "explication": "Le dossier est clos. Le tas a été enlevé.",
    },
    "classe": {
        "nom": "Classé sans suite", "poste": None, "suivante": None,
        "action": None, "explication": "La mairie a classé le dossier : le tas n'existe plus, "
                                       "ou le signalement était infondé.",
    },
}

POSTES = {
    "mairie": "Mairie — confirmation et programmation",
    "brigade": "Brigade Laabal — constat sur place",
    "collecte": "Équipe de collecte — ramassage",
    "onea": "ONEA — réparation des conduites d'eau",
}


class ErreurDossier(Exception):
    pass


def maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Dossiers:
    def __init__(self, connexion):
        self.co = connexion

    # ------------------------------------------------------------------ lecture
    def liste(self, etape: str = None, poste: str = None, limite: int = 300) -> list:
        """Les dossiers, éventuellement filtrés par étape, ou par le poste qui doit agir."""
        requete = "SELECT * FROM depotoirs"
        valeurs, conditions = [], []
        if etape:
            conditions.append("etape = ?")
            valeurs.append(etape)
        elif poste:
            attendues = [cle for cle, e in CHAINE.items() if e["poste"] == poste]
            if not attendues:
                return []
            conditions.append("etape IN (%s)" % ",".join("?" * len(attendues)))
            valeurs.extend(attendues)
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        requete += " ORDER BY volume_m3 DESC LIMIT ?"
        valeurs.append(limite)
        return [self._enrichir(dict(l)) for l in self.co.execute(requete, valeurs)]

    def detail(self, id_depotoir: int, avec_declarants: bool = False) -> dict:
        ligne = self.co.execute("SELECT * FROM depotoirs WHERE id = ?", (id_depotoir,)).fetchone()
        if ligne is None:
            raise ErreurDossier("Dossier inconnu.")
        dossier = self._enrichir(dict(ligne))
        dossier["journal"] = [dict(l) for l in self.co.execute(
            "SELECT date, poste, auteur, etape, detail FROM journal_dossier"
            " WHERE depotoir_id = ? ORDER BY id", (id_depotoir,))]
        colonnes = ("id, date_observation, date_reception, taille, volume_m3, type, depot,"
                    " visages_masques, plaques_masquees,"
                    " longueur_m, largeur_m, commentaire, photo, message_vocal, source, statut, motifs,"
                    " precision_m, source_position, lieu_nom")
        if avec_declarants:
            # Identité facultative : réservée aux agents connectés, jamais servie au public.
            colonnes += ", declarant_nom, declarant_telephone, photo_cnib, photo_visage"
        signalements = [dict(l) for l in self.co.execute(
            f"SELECT {colonnes} FROM signalements WHERE depotoir_id = ? ORDER BY id", (id_depotoir,))]
        for s in signalements:
            s["motifs"] = json.loads(s.get("motifs") or "[]")
        dossier["signalements"] = signalements
        # C12 : les décisions de la page Vérifier entrent aussi dans « Qui a fait quoi ».
        for s in self.co.execute(
                "SELECT id, statut, decide_par, decide_le FROM signalements"
                " WHERE depotoir_id = ? AND decide_par IS NOT NULL", (id_depotoir,)):
            dossier["journal"].append({
                "date": s["decide_le"], "poste": "mairie", "auteur": s["decide_par"],
                "etape": "Signalement n° %d %s" % (s["id"], "écarté" if s["statut"] == "rejete" else "vérifié"),
                "detail": ""})
        dossier["journal"].sort(key=lambda e: e["date"] or "")
        signer(self.co, dossier["journal"])
        return dossier

    @staticmethod
    def _enrichir(dossier: dict) -> dict:
        etape = CHAINE.get(dossier.get("etape") or "signale", CHAINE["signale"])
        dossier["etape_nom"] = etape["nom"]
        dossier["poste_attendu"] = etape["poste"]
        dossier["action_attendue"] = etape["action"]
        dossier["explication_etape"] = etape["explication"]
        return dossier

    def comptes_par_etape(self) -> dict:
        comptes = {cle: 0 for cle in CHAINE}
        for ligne in self.co.execute("SELECT etape, COUNT(*) n FROM depotoirs GROUP BY etape"):
            comptes[ligne["etape"]] = ligne["n"]
        return comptes

    # ------------------------------------------------------------------ écriture
    def avancer(self, id_depotoir: int, poste: str, auteur: str, detail: str = "") -> dict:
        """Fait passer le dossier à l'étape suivante. Seul le poste attendu en a le droit."""
        dossier = self.detail(id_depotoir)
        etape = CHAINE.get(dossier["etape"], CHAINE["signale"])
        if etape["suivante"] is None:
            raise ErreurDossier("Ce dossier est déjà clos (%s)." % etape["nom"].lower())
        if etape["poste"] != poste:
            raise ErreurDossier(
                "C'est au poste « %s » d'agir à cette étape, pas à « %s »."
                % (POSTES.get(etape["poste"], etape["poste"]), POSTES.get(poste, poste)))
        suivante = etape["suivante"]
        self.co.execute("UPDATE depotoirs SET etape = ? WHERE id = ?", (suivante, id_depotoir))
        if suivante == "collecte":
            # Le tas est enlevé : il sort du plan de gestion.
            self.co.execute("UPDATE depotoirs SET etat = 'nettoye' WHERE id = ?", (id_depotoir,))
        self._noter(id_depotoir, poste, auteur, suivante, detail)
        self.co.commit()
        return self.detail(id_depotoir)

    def classer(self, id_depotoir: int, poste: str, auteur: str, motif: str) -> dict:
        """Classe le dossier sans suite. Réservé à la mairie."""
        if poste != "mairie":
            raise ErreurDossier("Seule la mairie peut classer un dossier sans suite.")
        dossier = self.detail(id_depotoir)
        if dossier["etape"] in ("collecte", "classe"):
            raise ErreurDossier("Ce dossier est déjà clos.")
        self.co.execute("UPDATE depotoirs SET etape = 'classe', etat = 'nettoye' WHERE id = ?",
                        (id_depotoir,))
        self._noter(id_depotoir, poste, auteur, "classe", motif or "sans motif précisé")
        self.co.commit()
        return self.detail(id_depotoir)

    def _noter(self, id_depotoir: int, poste: str, auteur: str, etape: str, detail: str) -> None:
        self.co.execute(
            "INSERT INTO journal_dossier (depotoir_id, date, poste, auteur, etape, detail)"
            " VALUES (?,?,?,?,?,?)",
            (id_depotoir, maintenant(), poste, auteur, etape, (detail or "")[:500]))

    def effacer_identites(self, id_depotoir: int) -> int:
        """Efface les pièces d'identité d'un dossier clos.

        La CNIB n'est demandée que pour une procédure : une fois le dossier clos, elle n'a plus
        de raison d'être conservée."""
        curseur = self.co.execute(
            "UPDATE signalements SET photo_cnib = NULL, photo_visage = NULL,"
            " declarant_telephone = NULL WHERE depotoir_id = ?", (id_depotoir,))
        self.co.commit()
        return curseur.rowcount
