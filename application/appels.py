"""Le standard téléphonique de la mairie (T23) : un habitant appelle depuis la page Signaler.

Ce module NE TRANSPORTE PAS LA VOIX. La voix passe directement d'un navigateur à l'autre, par
WebRTC, chiffrée par les navigateurs eux-mêmes (DTLS-SRTP, obligatoire dans WebRTC) : aucune
cryptographie n'est écrite par l'équipe. Le serveur sert seulement de standard :

    téléphone ── offre ──►  serveur  ── offre ──►  agent de la mairie
    téléphone ◄─ réponse ── serveur  ◄─ réponse ── agent
    téléphone ── position toutes les 3 s ──► serveur ──► carte de l'agent
    puis la voix va directement : téléphone ◄══════ Wi-Fi ══════► PC de l'agent

« Offre » et « réponse » sont deux textes (des descriptions SDP) que chaque navigateur fabrique :
ils disent quelles adresses du réseau local essayer et comment chiffrer. Il n'y a ni serveur
STUN ni serveur TURN : seules les adresses du réseau local sont proposées, rien ne sort.

Rien n'est enregistré. Les appels vivent EN MÉMOIRE, dans un dictionnaire protégé par un verrou :
jamais sur le disque, jamais dans la base, jamais dans les journaux. La position d'un habitant
est une donnée personnelle : elle est effacée dès que l'appel se termine, et l'appel lui-même est
oublié une minute plus tard.
"""

import hmac
import secrets
import threading
import time
from collections import deque

SONNERIE_MAX_S = 90          # personne ne décroche : « sans réponse »
DUREE_MAX_S = 30 * 60        # un appel en cours est coupé au bout de 30 minutes
OUBLI_S = 60                 # un appel terminé est oublié une minute après (le temps que
                             # le téléphone et l'agent l'apprennent)
APPELS_SIMULTANES_MAX = 3    # qui sonnent ou sont en cours, en même temps
APPELS_PAR_ADRESSE_MAX = 5   # par adresse de téléphone…
FENETRE_ADRESSE_S = 10 * 60  # …sur dix minutes
DESCRIPTION_MAX = 20_000     # caractères d'une offre ou d'une réponse WebRTC
PRECISION_MAX_M = 100_000

ACTIFS = ("sonne", "en_cours")
FINIS = ("termine", "sans_reponse")


class ErreurAppel(Exception):
    """Une demande refusée : le code HTTP et le message à renvoyer."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def lire_description(valeur) -> str:
    """Une offre ou une réponse WebRTC : un texte SDP, borné, qui commence par « v=0 »."""
    if not isinstance(valeur, str) or not valeur.strip():
        raise ErreurAppel(400, "Description de l'appel absente.")
    if len(valeur) > DESCRIPTION_MAX:
        raise ErreurAppel(400, "Description de l'appel trop longue.")
    if not valeur.lstrip().startswith("v=0"):
        raise ErreurAppel(400, "Description de l'appel illisible.")
    return valeur


def lire_position(envoi: dict, nombre, geo=None):
    """La position envoyée par le téléphone, contrôlée comme celle d'un signalement.

    Renvoie None si le téléphone n'en envoie pas (position refusée : l'appel passe quand même).
    Une position présente mais fausse est refusée."""
    if not isinstance(envoi, dict) or (envoi.get("latitude") is None and envoi.get("longitude") is None):
        return None
    lat, lon = nombre(envoi.get("latitude")), nombre(envoi.get("longitude"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        raise ErreurAppel(400, "Position invalide.")
    precision = nombre(envoi.get("precision_m"))
    if precision is not None and not (0 <= precision <= PRECISION_MAX_M):
        precision = None
    position = {"latitude": round(lat, 6), "longitude": round(lon, 6),
                "precision_m": round(precision) if precision is not None else None}
    # Hors de la commune, l'appel passe : on le signale seulement à l'agent.
    position["hors_commune"] = bool(geo) and not geo.dans_la_commune(lon, lat)
    return position


class Appels:
    """Les appels en cours, en mémoire. `horloge` est remplaçable pour les tests."""

    def __init__(self, horloge=time.monotonic):
        self._horloge = horloge
        self._verrou = threading.Lock()
        self._appels = {}
        self._par_adresse = {}       # adresse -> dates des derniers appels (pour la limite)
        self._suivant = 1

    # ------------------------------------------------------------------ outils internes
    def _ranger(self, maintenant: float) -> None:
        """Applique les délais : sonnerie sans réponse, appel trop long, appel à oublier."""
        for identifiant in list(self._appels):
            a = self._appels[identifiant]
            if a["etat"] == "sonne" and maintenant - a["cree"] > SONNERIE_MAX_S:
                self._finir(a, "sans_reponse", maintenant)
            elif a["etat"] == "en_cours" and maintenant - a["decroche_a"] > DUREE_MAX_S:
                self._finir(a, "termine", maintenant)
            elif a["etat"] in FINIS and maintenant - a["fini_a"] > OUBLI_S:
                del self._appels[identifiant]
        for adresse in list(self._par_adresse):
            dates = self._par_adresse[adresse]
            while dates and maintenant - dates[0] > FENETRE_ADRESSE_S:
                dates.popleft()
            if not dates:
                del self._par_adresse[adresse]

    @staticmethod
    def _finir(a: dict, etat: str, maintenant: float) -> None:
        """Fin d'un appel : on efface la position et les descriptions, on garde l'état."""
        a["etat"] = etat
        a["fini_a"] = maintenant
        a["position"] = None
        a["trajet"] = []
        a["offre"] = None
        a["reponse"] = None

    def _du_telephone(self, identifiant: int, jeton: str) -> dict:
        """L'appel, si le jeton est le bon. Même réponse que l'appel existe ou non."""
        a = self._appels.get(identifiant)
        if a is None or not isinstance(jeton, str) or not hmac.compare_digest(
                a["jeton"].encode(), jeton.encode()):
            raise ErreurAppel(404, "Appel inconnu.")
        return a

    def _de_l_agent(self, identifiant: int) -> dict:
        a = self._appels.get(identifiant)
        if a is None:
            raise ErreurAppel(404, "Appel inconnu.")
        return a

    @staticmethod
    def _noter_position(a: dict, position, maintenant: float) -> None:
        if position is None:
            return
        position = dict(position, recue=maintenant)
        a["position"] = position
        # Le trajet déjà parcouru, pour la carte de l'agent : borné, et effacé à la fin.
        a["trajet"].append([position["longitude"], position["latitude"]])
        del a["trajet"][:-600]

    # ------------------------------------------------------------------ côté habitant
    def appeler(self, offre: str, position, adresse: str) -> dict:
        """Un habitant appelle. Renvoie {id, jeton} ; le jeton est son seul moyen d'agir ensuite."""
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            actifs = sum(1 for a in self._appels.values() if a["etat"] in ACTIFS)
            if actifs >= APPELS_SIMULTANES_MAX:
                raise ErreurAppel(503, "Tous les agents sont occupés. Réessayez dans un moment.")
            dates = self._par_adresse.setdefault(adresse, deque())
            if len(dates) >= APPELS_PAR_ADRESSE_MAX:
                raise ErreurAppel(429, "Trop d'appels depuis ce téléphone. Réessayez plus tard.")
            dates.append(maintenant)
            identifiant = self._suivant
            self._suivant += 1
            a = {"id": identifiant, "jeton": secrets.token_urlsafe(32), "etat": "sonne",
                 "offre": offre, "reponse": None, "cree": maintenant, "decroche_a": None,
                 "fini_a": None, "agent": None, "position": None, "trajet": []}
            self._noter_position(a, position, maintenant)
            self._appels[identifiant] = a
            return {"id": identifiant, "jeton": a["jeton"]}

    def etat_pour_le_telephone(self, identifiant: int, jeton: str) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            a = self._du_telephone(identifiant, jeton)
            reponse = {"id": a["id"], "etat": a["etat"]}
            if a["etat"] == "en_cours":
                reponse["reponse"] = a["reponse"]
            return reponse

    def nouvelle_position(self, identifiant: int, jeton: str, position) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            a = self._du_telephone(identifiant, jeton)
            if a["etat"] not in ACTIFS:
                raise ErreurAppel(409, "Cet appel est terminé.")
            self._noter_position(a, position, maintenant)
            return {"etat": a["etat"]}

    def raccrocher_telephone(self, identifiant: int, jeton: str) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            a = self._du_telephone(identifiant, jeton)
            if a["etat"] in ACTIFS:
                self._finir(a, "termine", maintenant)
            return {"etat": a["etat"]}

    # ------------------------------------------------------------------ côté agent
    def lister(self) -> list:
        """Les appels qui sonnent ou sont en cours, et ceux qui viennent de finir (pour que la
        page de l'agent l'apprenne). Jamais le jeton du téléphone."""
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            liste = []
            for a in sorted(self._appels.values(), key=lambda x: x["id"]):
                p = a["position"]
                liste.append({
                    "id": a["id"], "etat": a["etat"], "agent": a["agent"],
                    "sonne_depuis_s": round(maintenant - a["cree"]),
                    "en_cours_depuis_s": (round(maintenant - a["decroche_a"])
                                          if a["decroche_a"] is not None and a["etat"] == "en_cours" else None),
                    "position": None if p is None else {
                        "latitude": p["latitude"], "longitude": p["longitude"],
                        "precision_m": p["precision_m"], "hors_commune": p["hors_commune"],
                        "age_s": round(maintenant - p["recue"], 1)},
                    "trajet": list(a["trajet"]),
                })
            return liste

    def offre(self, identifiant: int) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            a = self._de_l_agent(identifiant)
            if a["etat"] != "sonne":
                raise ErreurAppel(409, "Cet appel ne sonne plus.")
            return {"id": a["id"], "offre": a["offre"]}

    def decrocher(self, identifiant: int, reponse: str, agent: str) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            a = self._de_l_agent(identifiant)
            if a["etat"] == "en_cours":
                raise ErreurAppel(409, "Un autre agent a déjà décroché (%s)." % a["agent"])
            if a["etat"] != "sonne":
                raise ErreurAppel(409, "Cet appel ne sonne plus.")
            a.update(etat="en_cours", reponse=reponse, agent=agent, decroche_a=maintenant,
                     offre=None)
            return {"id": a["id"], "etat": a["etat"], "agent": agent}

    def raccrocher_agent(self, identifiant: int) -> dict:
        maintenant = self._horloge()
        with self._verrou:
            self._ranger(maintenant)
            a = self._de_l_agent(identifiant)
            if a["etat"] in ACTIFS:
                self._finir(a, "termine", maintenant)
            return {"id": a["id"], "etat": a["etat"]}


def adresse_du_client(request) -> str:
    """L'adresse du téléphone, pour la limite d'appels par adresse.

    En production, seul Caddy joint l'application (elle n'a aucun port publié, réseau Docker
    interne). Caddy pose l'adresse réelle du téléphone dans X-Forwarded-For : on en prend la
    DERNIÈRE valeur, celle qu'a ajoutée le dernier relais, et jamais la première, qu'un client
    pourrait écrire lui-même. Sans cet en-tête, c'est l'adresse de la connexion."""
    entete = request.headers.get("X-Forwarded-For", "")
    morceaux = [m.strip() for m in entete.split(",") if m.strip()]
    return (morceaux[-1] if morceaux else request.remote_addr or "inconnue")[:64]
