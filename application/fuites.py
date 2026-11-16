"""Fuites sur le réseau d'eau potable : du signalement jusqu'à la réparation par l'ONEA.

Pourquoi un outil d'assainissement s'occupe des conduites d'eau : une fuite qui coule pendant
des jours fait une mare au milieu du quartier. La mare attire les moustiques, détrempe la
chaussée qui se creuse, et quand elle atteint un tas d'ordures elle en emporte le jus dans les
caniveaux. C'est un problème d'assainissement avant d'être un problème de plomberie.

Mais la mairie ne touche pas aux conduites : seul l'**ONEA** (Office national de l'eau et de
l'assainissement) intervient sur son réseau. Le rôle de l'outil est donc de recevoir le
signalement, de le faire confirmer par la mairie, et de le transmettre à l'ONEA sous une forme
qu'il peut traiter — puis de garder la trace de la réparation.

    signalée   ──►  transmise à l'ONEA  ──►  réparée
    (habitant)      (agent de la mairie)     (ONEA)

Une fuite n'entre jamais dans les tournées des camions : ce n'est pas un tas à ramasser.
"""

import datetime
import json
import sqlite3

from .geo import distance_m
from .signalements.controles import REJET

# Ampleurs, du plus petit au plus gros. L'ordre sert à trier le bordereau de l'ONEA :
# une inondation passe avant un suintement.
URGENCE = {"inondation": 3, "jet": 2, "suintement": 1}

AMPLEUR_NOMS = {
    "suintement": "Suintement (le sol est humide, l'eau perle)",
    "jet": "Jet d'eau visible (la conduite est percée, l'eau gicle)",
    "inondation": "Inondation (l'eau coule en nappe, la rue est noyée)",
}

# La chaîne d'une fuite. Comme pour les dépotoirs : un seul poste agit à chaque étape, et il ne
# peut avancer que d'un cran.
CHAINE_EAU = {
    "signale": {
        "nom": "Signalée", "poste": "mairie", "suivante": "transmis",
        "action": "Confirmer et transmettre à l'ONEA",
        "explication": "Un agent de la mairie vérifie que la fuite existe, puis l'inscrit au "
                       "bordereau transmis à l'ONEA.",
    },
    "transmis": {
        "nom": "Transmise à l'ONEA", "poste": "onea", "suivante": "repare",
        "action": "Déclarer la réparation faite",
        "explication": "L'ONEA intervient sur sa conduite et déclare la fuite réparée.",
    },
    "repare": {
        "nom": "Réparée", "poste": None, "suivante": None,
        "action": None, "explication": "La conduite est réparée. Le dossier est clos.",
    },
    "classe": {
        "nom": "Classée sans suite", "poste": None, "suivante": None,
        "action": None, "explication": "La mairie a classé le dossier : pas de fuite sur place, "
                                       "ou signalement infondé.",
    },
}


class ErreurFuite(Exception):
    pass


def maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Fuites:
    """Enregistrement, regroupement et suivi des fuites d'eau.

    Le regroupement suit la même règle que les dépotoirs : deux personnes qui signalent la même
    fuite ne créent pas deux dossiers, la seconde confirme la première. Le rayon est plus serré
    qu'un tas d'ordures — une fuite est un point précis sur une conduite, pas un tas étalé."""

    RAYON_M = 40

    def __init__(self, connexion, parametres: dict):
        self.co = connexion
        self.rafale_max = parametres["controles"]["rafale_max"]
        self.rafale_min = parametres["controles"]["rafale_fenetre_min"]

    # ------------------------------------------------------------------ écriture
    def enregistrer(self, examine: dict, verifier_rafale: bool = True) -> dict:
        """Range un signalement de fuite déjà contrôlé. Même contrat que Depotoirs.enregistrer."""
        deja = self.deja_recu(examine.get("id_client"))
        if deja:
            return deja

        motifs = list(examine["motifs"])
        statut = examine["statut"]
        if verifier_rafale and statut != REJET and self.rafale(examine.get("source", "")):
            motifs.append("rafale_meme_source")
            statut = "a_verifier"

        try:
            curseur = self.co.execute(
                "INSERT INTO signalements (id_client, nature, latitude, longitude, precision_m,"
                " date_observation, date_reception, ampleur, quartier, commentaire, photo, source,"
                " statut, motifs, declarant_nom, declarant_telephone, photo_cnib, photo_visage,"
                " message_vocal, source_position, lieu_nom)"
                " VALUES (?,'fuite_eau',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (examine.get("id_client"), examine.get("latitude"), examine.get("longitude"),
                 examine.get("precision_m"), examine.get("date_observation"), maintenant(),
                 examine.get("ampleur"), examine.get("quartier"), examine.get("commentaire", ""),
                 examine.get("photo"), examine.get("source", "inconnue"),
                 statut, json.dumps(motifs, ensure_ascii=False),
                 examine.get("declarant_nom"), examine.get("declarant_telephone"),
                 examine.get("photo_cnib"), examine.get("photo_visage"),
                 examine.get("message_vocal"),
                 examine.get("source_position") or "gps", examine.get("lieu_nom")))
        except sqlite3.IntegrityError:
            # Même envoi arrivé deux fois en même temps : le premier a gagné.
            self.co.rollback()
            return self.deja_recu(examine.get("id_client")) or {
                "id": None, "statut": "rejete", "nouveau": False, "motifs": ["format_invalide"]}

        identifiant = curseur.lastrowid
        fuite = self.rattacher(identifiant) if statut != REJET else None
        self.co.commit()
        statut_final = self.co.execute("SELECT statut FROM signalements WHERE id = ?",
                                       (identifiant,)).fetchone()["statut"]
        return {"id": identifiant, "nature": "fuite_eau", "statut": statut_final,
                "nouveau": True, "motifs": motifs, "fuite_id": fuite}

    def deja_recu(self, id_client):
        if not id_client:
            return None
        deja = self.co.execute("SELECT id, statut, motifs, fuite_id FROM signalements"
                               " WHERE id_client = ?", (id_client,)).fetchone()
        if deja is None:
            return None
        return {"id": deja["id"], "nature": "fuite_eau", "statut": deja["statut"], "nouveau": False,
                "motifs": json.loads(deja["motifs"] or "[]"), "fuite_id": deja["fuite_id"]}

    def rafale(self, source: str) -> bool:
        depuis = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(minutes=self.rafale_min)).isoformat(timespec="seconds")
        (nombre,) = self.co.execute(
            "SELECT COUNT(*) FROM signalements WHERE source = ? AND date_reception > ?",
            (source, depuis)).fetchone()
        return nombre >= self.rafale_max

    def rattacher(self, id_signalement: int):
        """Rattache le signalement à la fuite proche, ou en ouvre une."""
        s = self.co.execute("SELECT * FROM signalements WHERE id = ?", (id_signalement,)).fetchone()
        if s["latitude"] is None or s["longitude"] is None:
            return None
        proche, distance_proche = None, None
        degre = self.RAYON_M / 111000 * 1.5          # on ne compare qu'aux voisines immédiates
        for f in self.co.execute(
                "SELECT * FROM fuites WHERE etat = 'active' AND latitude BETWEEN ? AND ?"
                " AND longitude BETWEEN ? AND ?",
                (s["latitude"] - degre, s["latitude"] + degre,
                 s["longitude"] - degre, s["longitude"] + degre)):
            distance = distance_m(s["longitude"], s["latitude"], f["longitude"], f["latitude"])
            if distance <= self.RAYON_M and (distance_proche is None or distance < distance_proche):
                proche, distance_proche = f, distance
        if proche is None:
            curseur = self.co.execute(
                "INSERT INTO fuites (latitude, longitude, premier_vu, dernier_vu) VALUES (?,?,?,?)",
                (s["latitude"], s["longitude"], s["date_observation"], s["date_observation"]))
            identifiant = curseur.lastrowid
        else:
            identifiant = proche["id"]
        self.co.execute("UPDATE signalements SET fuite_id = ? WHERE id = ?",
                        (identifiant, id_signalement))
        self.recalculer(identifiant)
        return identifiant

    def recalculer(self, id_fuite: int) -> None:
        """Position, ampleur et quartier d'une fuite, d'après ses signalements retenus.

        La position est prise au milieu (médiane) : un signalement décalé ne déplace pas la
        fuite. L'ampleur retenue est la PLUS GRAVE signalée — entre « ça suinte » et « la rue
        est noyée », c'est la seconde qui décide de l'urgence de l'intervention."""
        lignes = self.co.execute(
            "SELECT latitude, longitude, source, date_observation, ampleur, quartier"
            " FROM signalements WHERE fuite_id = ? AND statut <> 'rejete'", (id_fuite,)).fetchall()
        if not lignes:
            self.co.execute("DELETE FROM fuites WHERE id = ?", (id_fuite,))
            return
        milieu = lambda valeurs: sorted(valeurs)[len(valeurs) // 2]
        sources = {l["source"] for l in lignes}
        dates = [l["date_observation"] for l in lignes if l["date_observation"]]
        ampleurs = [l["ampleur"] for l in lignes if l["ampleur"] in URGENCE]
        ampleur = max(ampleurs, key=lambda a: URGENCE[a]) if ampleurs else None
        quartiers = [l["quartier"] for l in lignes if l["quartier"]]
        quartier = max(set(quartiers), key=quartiers.count) if quartiers else None
        self.co.execute(
            "UPDATE fuites SET latitude = ?, longitude = ?, nb_signalements = ?, nb_sources = ?,"
            " premier_vu = ?, dernier_vu = ?, ampleur = ?, quartier = ? WHERE id = ?",
            (milieu([l["latitude"] for l in lignes]), milieu([l["longitude"] for l in lignes]),
             len(lignes), len(sources), min(dates) if dates else None,
             max(dates) if dates else None, ampleur, quartier, id_fuite))
        # Deux appareils différents qui voient la même fuite : la confirmation vaut vérification.
        if len(sources) >= 2:
            self.co.execute("UPDATE signalements SET statut = 'verifie'"
                            " WHERE fuite_id = ? AND statut = 'recevable'", (id_fuite,))

    # ------------------------------------------------------------------ lecture
    def liste(self, etape: str = None, poste: str = None, limite: int = 300) -> list:
        requete = "SELECT * FROM fuites"
        valeurs, conditions = [], []
        if etape:
            conditions.append("etape = ?")
            valeurs.append(etape)
        elif poste:
            attendues = [cle for cle, e in CHAINE_EAU.items() if e["poste"] == poste]
            if not attendues:
                return []
            conditions.append("etape IN (%s)" % ",".join("?" * len(attendues)))
            valeurs.extend(attendues)
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        # Les plus graves d'abord : une rue noyée n'attend pas derrière un suintement.
        requete += (" ORDER BY CASE ampleur WHEN 'inondation' THEN 3 WHEN 'jet' THEN 2"
                    " WHEN 'suintement' THEN 1 ELSE 0 END DESC, dernier_vu DESC LIMIT ?")
        valeurs.append(limite)
        return [self._enrichir(dict(l)) for l in self.co.execute(requete, valeurs)]

    def detail(self, id_fuite: int, avec_declarants: bool = False) -> dict:
        ligne = self.co.execute("SELECT * FROM fuites WHERE id = ?", (id_fuite,)).fetchone()
        if ligne is None:
            raise ErreurFuite("Fuite inconnue.")
        fuite = self._enrichir(dict(ligne))
        fuite["journal"] = [dict(l) for l in self.co.execute(
            "SELECT date, poste, auteur, etape, detail FROM journal_fuite"
            " WHERE fuite_id = ? ORDER BY id", (id_fuite,))]
        colonnes = ("id, date_observation, date_reception, ampleur, quartier, commentaire,"
                    " photo, message_vocal, source, statut, motifs,"
                    " precision_m, source_position, lieu_nom")
        if avec_declarants:
            # Identité facultative : réservée aux agents connectés, jamais servie au public.
            colonnes += ", declarant_nom, declarant_telephone, photo_cnib, photo_visage"
        signalements = [dict(l) for l in self.co.execute(
            f"SELECT {colonnes} FROM signalements WHERE fuite_id = ? ORDER BY id", (id_fuite,))]
        for s in signalements:
            s["motifs"] = json.loads(s.get("motifs") or "[]")
        fuite["signalements"] = signalements
        return fuite

    @staticmethod
    def _enrichir(fuite: dict) -> dict:
        etape = CHAINE_EAU.get(fuite.get("etape") or "signale", CHAINE_EAU["signale"])
        fuite["etape_nom"] = etape["nom"]
        fuite["poste_attendu"] = etape["poste"]
        fuite["action_attendue"] = etape["action"]
        fuite["explication_etape"] = etape["explication"]
        fuite["ampleur_nom"] = AMPLEUR_NOMS.get(fuite.get("ampleur"), "Ampleur non précisée")
        return fuite

    def comptes_par_etape(self) -> dict:
        comptes = {cle: 0 for cle in CHAINE_EAU}
        for ligne in self.co.execute("SELECT etape, COUNT(*) n FROM fuites GROUP BY etape"):
            comptes[ligne["etape"]] = ligne["n"]
        return comptes

    def carte(self) -> list:
        """Les fuites non réparées, pour la carte de décision."""
        return [self._enrichir(dict(l)) for l in self.co.execute(
            "SELECT * FROM fuites WHERE etat = 'active' AND etape <> 'classe'")]

    # ------------------------------------------------------------------ chaîne
    def avancer(self, id_fuite: int, poste: str, auteur: str, detail: str = "") -> dict:
        """Fait passer la fuite à l'étape suivante. Seul le poste attendu en a le droit."""
        fuite = self.detail(id_fuite)
        etape = CHAINE_EAU.get(fuite["etape"], CHAINE_EAU["signale"])
        if etape["suivante"] is None:
            raise ErreurFuite("Ce dossier est déjà clos (%s)." % etape["nom"].lower())
        if etape["poste"] != poste:
            raise ErreurFuite(
                "C'est au poste « %s » d'agir à cette étape, pas à « %s »."
                % (etape["poste"], poste))
        suivante = etape["suivante"]
        self.co.execute("UPDATE fuites SET etape = ? WHERE id = ?", (suivante, id_fuite))
        if suivante == "transmis" and detail:
            # La mairie note le numéro que l'ONEA lui rend : les deux services parlent du
            # même dossier quand ils se téléphonent.
            self.co.execute("UPDATE fuites SET reference_onea = ? WHERE id = ?",
                            (detail[:60], id_fuite))
        if suivante == "repare":
            self.co.execute("UPDATE fuites SET etat = 'reparee' WHERE id = ?", (id_fuite,))
        self._noter(id_fuite, poste, auteur, suivante, detail)
        self.co.commit()
        return self.detail(id_fuite)

    def classer(self, id_fuite: int, poste: str, auteur: str, motif: str) -> dict:
        """Classe la fuite sans suite. Réservé à la mairie."""
        if poste != "mairie":
            raise ErreurFuite("Seule la mairie peut classer un dossier sans suite.")
        fuite = self.detail(id_fuite)
        if fuite["etape"] in ("repare", "classe"):
            raise ErreurFuite("Ce dossier est déjà clos.")
        self.co.execute("UPDATE fuites SET etape = 'classe', etat = 'reparee' WHERE id = ?",
                        (id_fuite,))
        self._noter(id_fuite, poste, auteur, "classe", motif or "sans motif précisé")
        self.co.commit()
        return self.detail(id_fuite)

    def _noter(self, id_fuite: int, poste: str, auteur: str, etape: str, detail: str) -> None:
        self.co.execute(
            "INSERT INTO journal_fuite (fuite_id, date, poste, auteur, etape, detail)"
            " VALUES (?,?,?,?,?,?)",
            (id_fuite, maintenant(), poste, auteur, etape, (detail or "")[:500]))

    def comptes(self) -> dict:
        (actives,) = self.co.execute(
            "SELECT COUNT(*) FROM fuites WHERE etat = 'active' AND etape <> 'classe'").fetchone()
        (a_transmettre,) = self.co.execute(
            "SELECT COUNT(*) FROM fuites WHERE etape = 'signale'").fetchone()
        (chez_onea,) = self.co.execute(
            "SELECT COUNT(*) FROM fuites WHERE etape = 'transmis'").fetchone()
        (reparees,) = self.co.execute(
            "SELECT COUNT(*) FROM fuites WHERE etape = 'repare'").fetchone()
        return {"fuites": actives, "a_transmettre": a_transmettre,
                "chez_onea": chez_onea, "reparees": reparees}
