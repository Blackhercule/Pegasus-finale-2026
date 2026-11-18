"""Un espace de travail pour les acteurs de la collecte (C14).

À Ouagadougou, les ordures des ménages passent d'abord par des pré-collecteurs : entreprises
et associations, souvent en tricycle, payées par abonnement, qui vident les cours vers les
centres de collecte. La mairie les enregistre ici :

- le collecteur (entreprise ou association), les quartiers qu'il dessert et ses jours de passage ;
- ses véhicules (tricycles, camions, charrettes) ;
- les centres de collecte où il dépose ;
- les collectes effectuées, déclarées avec leur quantité : c'est le suivi des quantités évacuées ;
- les plaintes des habitants (« il n'est pas passé »), sans texte libre.

L'habitant, lui, cherche les collecteurs de son quartier et leurs jours de passage
(collecteurs_du_quartier), sans compte. Tout ce qui est écrit ici est saisi par un agent ;
les erreurs de saisie reviennent en messages clairs (ErreurCollecte).
"""

import datetime
import json

GENRES = {"entreprise": "Entreprise", "association": "Association"}
VEHICULES = {"tricycle": "Tricycle", "camion": "Camion", "charrette": "Charrette"}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOTIFS = {"pas_passe": "N'est pas passé le jour prévu",
          "hors_circuit": "Ne suit pas son circuit",
          "deverse": "A déversé les ordures dans la rue ou un caniveau"}
# Au-delà, une plainte du même téléphone le même jour est refusée : pas d'acharnement possible.
PLAINTES_PAR_JOUR = 3


class ErreurCollecte(ValueError):
    pass


def _maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _texte(envoi: dict, cle: str, longueur: int = 120, requis: bool = True) -> str:
    valeur = str(envoi.get(cle) or "").strip()[:longueur]
    if requis and not valeur:
        raise ErreurCollecte(f"Le champ « {cle} » est obligatoire.")
    return valeur


def _nombre(envoi: dict, cle: str, requis: bool = False, maximum: float = 1e7):
    valeur = envoi.get(cle)
    if valeur in (None, ""):
        if requis:
            raise ErreurCollecte(f"Le champ « {cle} » est obligatoire.")
        return None
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        raise ErreurCollecte(f"« {cle} » doit être un nombre.")
    if not 0 <= valeur <= maximum:
        raise ErreurCollecte(f"« {cle} » doit être compris entre 0 et {maximum:g}.")
    return valeur


def _coordonnee(envoi: dict, cle: str, borne: float):
    """Latitude ou longitude facultative (négative à l'ouest de Greenwich, comme à Ouaga)."""
    valeur = envoi.get(cle)
    if valeur in (None, ""):
        return None
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        raise ErreurCollecte(f"« {cle} » doit être un nombre.")
    if not -borne <= valeur <= borne:
        raise ErreurCollecte(f"« {cle} » hors limites.")
    return valeur


class Collecteurs:
    def __init__(self, co, quartiers: list):
        self.co = co
        self.noms_quartiers = [q[0] for q in quartiers]

    def _quartiers(self, valeur) -> list:
        valeur = [str(q) for q in (valeur or []) if str(q) in self.noms_quartiers]
        return sorted(set(valeur))

    # ------------------------------------------------------------------ collecteurs
    def enregistrer(self, envoi: dict, auteur: str, identifiant: int = None) -> dict:
        nom = _texte(envoi, "nom")
        genre = envoi.get("genre")
        if genre not in GENRES:
            raise ErreurCollecte("Choisissez « entreprise » ou « association ».")
        jours = [j for j in JOURS if j in (envoi.get("jours") or [])]
        quartiers = self._quartiers(envoi.get("quartiers"))
        telephone = _texte(envoi, "telephone_service", 30, requis=False)
        with self.co:
            if identifiant:
                if not self.co.execute("UPDATE collecteurs SET nom = ?, genre = ?, telephone_service = ?,"
                                       " quartiers = ?, jours = ?, actif = ? WHERE id = ?",
                                       (nom, genre, telephone, json.dumps(quartiers, ensure_ascii=False),
                                        json.dumps(jours), 1 if envoi.get("actif", True) else 0,
                                        identifiant)).rowcount:
                    raise ErreurCollecte("Collecteur introuvable.")
            else:
                identifiant = self.co.execute(
                    "INSERT INTO collecteurs (nom, genre, telephone_service, quartiers, jours, cree_le,"
                    " cree_par) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (nom, genre, telephone, json.dumps(quartiers, ensure_ascii=False), json.dumps(jours),
                     _maintenant(), auteur)).lastrowid
        return self.fiche(identifiant)

    def fiche(self, identifiant: int) -> dict:
        l = self.co.execute("SELECT * FROM collecteurs WHERE id = ?", (identifiant,)).fetchone()
        if not l:
            raise ErreurCollecte("Collecteur introuvable.")
        c = dict(l)
        c["quartiers"] = json.loads(c["quartiers"])
        c["jours"] = json.loads(c["jours"])
        c["actif"] = bool(c["actif"])
        c["vehicules"] = [dict(v) for v in self.co.execute(
            "SELECT id, genre, immatriculation, capacite_m3 FROM vehicules WHERE collecteur_id = ?"
            " ORDER BY id", (identifiant,))]
        (c["plaintes"],) = self.co.execute("SELECT COUNT(*) FROM plaintes WHERE collecteur_id = ?",
                                           (identifiant,)).fetchone()
        (c["quantite_kg"],) = self.co.execute(
            "SELECT COALESCE(SUM(quantite_kg), 0) FROM collectes WHERE collecteur_id = ?",
            (identifiant,)).fetchone()
        return c

    def liste(self) -> list:
        return [self.fiche(l["id"]) for l in self.co.execute("SELECT id FROM collecteurs ORDER BY nom")]

    def ajouter_vehicule(self, identifiant: int, envoi: dict) -> dict:
        self.fiche(identifiant)
        genre = envoi.get("genre")
        if genre not in VEHICULES:
            raise ErreurCollecte("Choisissez tricycle, camion ou charrette.")
        with self.co:
            self.co.execute("INSERT INTO vehicules (collecteur_id, genre, immatriculation, capacite_m3)"
                            " VALUES (?, ?, ?, ?)",
                            (identifiant, genre, _texte(envoi, "immatriculation", 20, requis=False),
                             _nombre(envoi, "capacite_m3", maximum=100)))
        return self.fiche(identifiant)

    # ------------------------------------------------------------------ pour l'habitant
    def collecteurs_du_quartier(self, quartier: str) -> list:
        """Ce que l'habitant voit : nom, genre, jours, téléphone du service. Rien d'autre."""
        sortie = []
        for c in self.liste():
            if c["actif"] and quartier in c["quartiers"]:
                sortie.append({"id": c["id"], "nom": c["nom"], "genre": GENRES[c["genre"]],
                               "jours": c["jours"], "telephone_service": c["telephone_service"]})
        return sortie

    def calendrier(self) -> dict:
        """Quartier → jour → collecteurs qui y passent : le calendrier de passage."""
        grille = {}
        for c in self.liste():
            if not c["actif"]:
                continue
            for q in c["quartiers"]:
                for j in c["jours"]:
                    grille.setdefault(q, {}).setdefault(j, []).append(c["nom"])
        return grille

    # ------------------------------------------------------------------ centres et collectes
    def ajouter_centre(self, envoi: dict) -> dict:
        with self.co:
            identifiant = self.co.execute(
                "INSERT INTO centres (nom, latitude, longitude, capacite_t) VALUES (?, ?, ?, ?)",
                (_texte(envoi, "nom"), _coordonnee(envoi, "latitude", 90),
                 _coordonnee(envoi, "longitude", 180), _nombre(envoi, "capacite_t", maximum=1e6))).lastrowid
        return dict(self.co.execute("SELECT * FROM centres WHERE id = ?", (identifiant,)).fetchone())

    def centres(self) -> list:
        return [dict(l) for l in self.co.execute(
            "SELECT c.*, COALESCE(SUM(k.quantite_kg), 0) AS recu_kg FROM centres c"
            " LEFT JOIN collectes k ON k.centre_id = c.id GROUP BY c.id ORDER BY c.nom")]

    def declarer(self, envoi: dict, auteur: str) -> dict:
        identifiant = int(envoi.get("collecteur_id") or 0)
        self.fiche(identifiant)
        date = _texte(envoi, "date", 10)
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            raise ErreurCollecte("Date attendue au format AAAA-MM-JJ.")
        centre = envoi.get("centre_id") or None
        if centre and not self.co.execute("SELECT 1 FROM centres WHERE id = ?", (centre,)).fetchone():
            raise ErreurCollecte("Centre de collecte introuvable.")
        quartier = envoi.get("quartier") or None
        if quartier and quartier not in self.noms_quartiers:
            raise ErreurCollecte("Quartier inconnu.")
        with self.co:
            self.co.execute("INSERT INTO collectes (collecteur_id, date, quartier, quantite_kg, centre_id,"
                            " declare_par) VALUES (?, ?, ?, ?, ?, ?)",
                            (identifiant, date, quartier, _nombre(envoi, "quantite_kg", True, 100000),
                             centre, auteur))
        return self.bilan()

    def bilan(self) -> dict:
        """Les quantités évacuées, par collecteur et par mois, et les dernières déclarations."""
        par_collecteur = [dict(l) for l in self.co.execute(
            "SELECT c.nom, substr(k.date, 1, 7) AS mois, COUNT(*) AS collectes,"
            " SUM(k.quantite_kg) AS quantite_kg FROM collectes k JOIN collecteurs c ON c.id = k.collecteur_id"
            " GROUP BY c.id, mois ORDER BY mois DESC, quantite_kg DESC")]
        dernieres = [dict(l) for l in self.co.execute(
            "SELECT k.date, c.nom AS collecteur, k.quartier, k.quantite_kg, e.nom AS centre, k.declare_par"
            " FROM collectes k JOIN collecteurs c ON c.id = k.collecteur_id"
            " LEFT JOIN centres e ON e.id = k.centre_id ORDER BY k.date DESC, k.id DESC LIMIT 50")]
        (total,) = self.co.execute("SELECT COALESCE(SUM(quantite_kg), 0) FROM collectes").fetchone()
        return {"total_kg": total, "par_collecteur": par_collecteur, "dernieres": dernieres}

    # ------------------------------------------------------------------ plaintes
    def porter_plainte(self, envoi: dict, source: str) -> None:
        identifiant = int(envoi.get("collecteur_id") or 0)
        fiche = self.fiche(identifiant)
        motif = envoi.get("motif")
        if motif not in MOTIFS:
            raise ErreurCollecte("Motif inconnu.")
        quartier = envoi.get("quartier") if envoi.get("quartier") in fiche["quartiers"] else None
        source = str(source or "")[:64]
        aujourd_hui = _maintenant()[:10]
        if source:
            (deja,) = self.co.execute("SELECT COUNT(*) FROM plaintes WHERE source = ? AND date LIKE ?",
                                      (source, aujourd_hui + "%")).fetchone()
            if deja >= PLAINTES_PAR_JOUR:
                raise ErreurCollecte("Vous avez déjà envoyé plusieurs plaintes aujourd'hui.")
        with self.co:
            self.co.execute("INSERT INTO plaintes (collecteur_id, quartier, motif, date, source)"
                            " VALUES (?, ?, ?, ?, ?)", (identifiant, quartier, motif, _maintenant(), source))

    def plaintes(self) -> list:
        return [dict(l, motif_nom=MOTIFS.get(l["motif"], l["motif"])) for l in self.co.execute(
            "SELECT p.id, p.date, p.quartier, p.motif, c.nom AS collecteur FROM plaintes p"
            " JOIN collecteurs c ON c.id = p.collecteur_id ORDER BY p.date DESC LIMIT 100")]

    # ------------------------------------------------------------------ campagnes de salubrité
    def publier_campagne(self, envoi: dict, auteur: str) -> list:
        date = _texte(envoi, "date", 10)
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            raise ErreurCollecte("Date attendue au format AAAA-MM-JJ.")
        quartier = envoi.get("quartier") or None
        if quartier and quartier not in self.noms_quartiers:
            raise ErreurCollecte("Quartier inconnu.")
        participants = _nombre(envoi, "participants", maximum=100000)
        with self.co:
            self.co.execute("INSERT INTO campagnes (titre, date, quartier, organisateur, participants,"
                            " quantite_kg, publie_par) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (_texte(envoi, "titre"), date, quartier,
                             _texte(envoi, "organisateur", 120, requis=False),
                             int(participants) if participants is not None else None,
                             _nombre(envoi, "quantite_kg", maximum=1e7), auteur))
        return self.campagnes()

    def campagnes(self) -> list:
        """Publiques : pas de nom de personne, seulement l'organisateur (école, association…)."""
        return [dict(l) for l in self.co.execute(
            "SELECT id, titre, date, quartier, organisateur, participants, quantite_kg FROM campagnes"
            " ORDER BY date DESC LIMIT 30")]
