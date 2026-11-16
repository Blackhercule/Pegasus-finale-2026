"""Contrôles d'un signalement reçu : recevable, à vérifier, ou rejeté avec son motif.

Le jury injecte des signalements piégés (exigence E10). Règle de base : un piège ne doit ni
faire tomber le serveur, ni entrer dans le plan de gestion. Chaque contrôle est une petite
fonction qui renvoie un code de motif, ou rien. Les motifs sont gardés et affichés : un
signalement écarté reste visible, avec la raison.
"""

import datetime
import math

# Un motif bloque le signalement (rejete) ou demande un contrôle humain (a_verifier).
REJET = "rejete"
A_VERIFIER = "a_verifier"

MOTIFS = {
    "format_invalide":        (REJET, "Champ obligatoire absent, mauvais type ou texte trop long"),
    "coordonnees_invalides":  (REJET, "Latitude ou longitude absurde, hors bornes, ou point (0, 0)"),
    "coordonnees_inversees":  (REJET, "Latitude et longitude semblent échangées"),
    "hors_commune":           (REJET, "Point hors de la commune"),
    "dans_l_eau":             (REJET, "Point au milieu d'un plan d'eau"),
    "date_future":            (REJET, "Date d'observation dans le futur"),
    "volume_invraisemblable": (REJET, "Volume négatif, nul ou démesuré"),
    "photo_invalide":         (REJET, "Le fichier envoyé n'est pas une image, ou dépasse la taille permise"),
    "date_trop_ancienne":     (A_VERIFIER, "Observation trop ancienne pour être encore d'actualité"),
    "precision_insuffisante": (A_VERIFIER, "Position trop imprécise"),
    "rafale_meme_source":     (A_VERIFIER, "Beaucoup de signalements d'un même appareil en très peu de temps"),
}

TAILLES = ("petit", "moyen", "grand", "tres_grand")
TYPES = ("menager", "gravats", "mixte", "autre")
# Premiers octets des formats d'image acceptés : on lit le contenu, jamais le nom du fichier.
SIGNATURES_IMAGE = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF87a", b"GIF89a")


def nombre(valeur):
    """Convertit en nombre fini, ou renvoie None. Refuse les textes, les listes, NaN et l'infini."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, str)):
        return None
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def texte(valeur, maximum: int):
    """Texte propre : les caractères de contrôle sont retirés, la longueur est bornée."""
    if valeur is None:
        return ""
    if not isinstance(valeur, str):
        return None
    propre = "".join(c for c in valeur if c == "\n" or c >= " ")
    return propre.strip()[:maximum]


def maintenant() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def lire_date(valeur):
    """Date ISO 8601, avec ou sans fuseau (sans fuseau : lue comme UTC). None si illisible."""
    if not isinstance(valeur, str) or not valeur.strip():
        return None
    try:
        d = datetime.datetime.fromisoformat(valeur.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def est_une_image(contenu: bytes) -> bool:
    return any(contenu.startswith(s) for s in SIGNATURES_IMAGE)


class Controleur:
    """Applique tous les contrôles. `geo` répond « dans la commune ? dans l'eau ? »."""

    def __init__(self, geographie, parametres: dict):
        self.geo = geographie
        self.seuils = parametres["controles"]
        self.volumes = parametres["volumes_par_taille_m3"]

    def examiner(self, brut: dict) -> dict:
        """Renvoie un signalement propre : champs normalisés, statut et motifs.

        `brut` vient du téléphone ou d'un lot du jury : rien n'y est tenu pour vrai."""
        motifs = []
        maxi_texte = self.seuils["texte_max_caracteres"]
        if not isinstance(brut, dict):
            return self.resultat({}, ["format_invalide"])

        lon, lat = nombre(brut.get("longitude")), nombre(brut.get("latitude"))
        if lon is None or lat is None:
            motifs.append("format_invalide")
        elif not (-180 <= lon <= 180 and -90 <= lat <= 90) or (lon == 0 and lat == 0):
            motifs.append("coordonnees_invalides")
        elif not self.geo.dans_la_commune(lon, lat):
            # Confusion fréquente : latitude et longitude saisies à l'envers.
            if abs(lat) <= 180 and abs(lon) <= 90 and self.geo.dans_la_commune(lat, lon):
                motifs.append("coordonnees_inversees")
            else:
                motifs.append("hors_commune")
        elif self.geo.dans_l_eau(lon, lat):
            motifs.append("dans_l_eau")

        taille = brut.get("taille")
        taille = taille if taille in TAILLES else None
        volume = nombre(brut.get("volume_m3"))
        if volume is None and taille:
            volume = self.volumes[taille]                 # pas de volume donné : celui de la taille
        if taille is None and volume is None:
            motifs.append("format_invalide")
        elif volume is not None and not (0 < volume <= self.seuils["volume_max_m3"]):
            motifs.append("volume_invraisemblable")

        date = lire_date(brut.get("date_observation"))
        if date is None:
            date = maintenant()                            # non précisée : on prend l'heure de réception
        elif date > maintenant() + datetime.timedelta(minutes=10):
            motifs.append("date_future")
        elif (maintenant() - date).days > self.seuils["anciennete_max_jours"]:
            motifs.append("date_trop_ancienne")

        precision = nombre(brut.get("precision_m"))
        if precision is not None and (precision < 0 or precision > self.seuils["precision_max_m"]):
            motifs.append("precision_insuffisante")

        commentaire = texte(brut.get("commentaire"), maxi_texte)
        genre = brut.get("type") if brut.get("type") in TYPES else "autre"
        source = texte(brut.get("source"), 64)
        id_client = texte(brut.get("id_client"), 64)
        if commentaire is None or source is None or id_client is None:
            motifs.append("format_invalide")

        propre = {
            "id_client": id_client or None, "latitude": lat, "longitude": lon,
            "precision_m": precision, "date_observation": date.isoformat(timespec="seconds"),
            "taille": taille, "volume_m3": volume, "type": genre,
            "commentaire": commentaire or "", "source": source or "inconnue",
        }
        return self.resultat(propre, motifs)

    @staticmethod
    def resultat(propre: dict, motifs: list) -> dict:
        """Le motif le plus grave décide du statut : un rejet l'emporte sur une vérification."""
        gravites = [MOTIFS[m][0] for m in motifs if m in MOTIFS]
        statut = REJET if REJET in gravites else A_VERIFIER if A_VERIFIER in gravites else "recevable"
        propre = dict(propre)
        propre["statut"] = statut
        propre["motifs"] = motifs
        return propre

    def controler_photo(self, contenu: bytes) -> bool:
        return bool(contenu) and len(contenu) <= self.seuils["photo_max_octets"] and est_une_image(contenu)
