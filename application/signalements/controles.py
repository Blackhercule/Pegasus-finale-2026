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
    "dimensions_invraisemblables": (A_VERIFIER, "Longueur ou largeur hors de proportion"),
    "ampleur_invalide":       (REJET, "Ampleur de la fuite absente ou inconnue"),
    "gravite_invalide":       (REJET, "Gravité absente ou inconnue"),
    "nature_inconnue":        (REJET, "Nature du signalement inconnue"),
    "photo_non_masquable":    (A_VERIFIER, "Photo écartée : le masquage des visages "
                                           "n'est pas disponible sur ce serveur"),
}

# Ce qui est signalé. Un tas d'ordures part dans les tournées des camions ; une fuite d'eau
# part à l'ONEA, qui seul intervient sur ses conduites.
# « ordures » part dans les tournées des camions, « fuite_eau » à l'ONEA, et les quatre
# dernières au service que leur nature désigne (voir application/nuisances.py).
NATURES = ("ordures", "fuite_eau", "caniveau_bouche", "abattoir_clandestin",
           "toilettes_plein_air", "eaux_usees_animales")
NATURES_NUISANCE = NATURES[2:]
# Ampleur d'une fuite, telle qu'un habitant peut la décrire sans rien mesurer.
AMPLEURS = ("suintement", "jet", "inondation")
# Gravité d'une nuisance : trois niveaux, formulés au téléphone dans les mots de chaque nature.
GRAVITES = ("leger", "moyen", "grave")

TAILLES = ("petit", "moyen", "grand", "tres_grand")
TYPES = ("menager", "gravats", "mixte", "autre")
# Où le tas se trouve : à même le sol, dans un bac, dans un caniveau… Cela change ce qu'il
# faut envoyer sur place et l'urgence (un caniveau bouché inonde le quartier aux pluies).
DEPOTS = ("plein_air", "bac", "caniveau", "fosse", "berge", "autre")
DIMENSION_MAX_M = 200
# Précision donnée à une position tirée d'un lieu connu (T16) : l'ordre de grandeur d'un marché
# ou d'un campus, pas celle d'un GPS.
PRECISION_LIEU_M = 150
# Premiers octets des formats d'image acceptés : on lit le contenu, jamais le nom du fichier.
SIGNATURES_IMAGE = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF", b"GIF87a", b"GIF89a")
# Sons acceptés pour un message vocal : WebM/Matroska (ce qu'enregistre un navigateur), OGG, MP4, MP3.
SIGNATURES_SON = (b"\x1aE\xdf\xa3", b"OggS", b"ID3", b"\xff\xfb", b"\xff\xf3", b"RIFF")


def nombre(valeur):
    """Convertit en nombre fini, ou renvoie None. Refuse les textes, les listes, NaN et l'infini."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float, str)):
        return None
    try:
        v = float(valeur)
    except (TypeError, ValueError):
        return None
    except OverflowError:
        # Un entier de plusieurs centaines de chiffres ne tient pas dans un flottant. Python
        # lève alors OverflowError et non ValueError : sans cette ligne, le serveur tombait.
        return None
    return v if math.isfinite(v) else None


def texte(valeur, maximum: int):
    """Texte propre : les caractères de contrôle sont retirés, la longueur est bornée."""
    if valeur is None:
        return ""
    if not isinstance(valeur, str):
        return None
    # Un « demi-caractère » Unicode (\ud800 à \udfff) traverse JSON mais ne peut pas être
    # écrit en UTF-8 : il faisait tomber le serveur au moment de l'enregistrement en base,
    # c'est-à-dire bien plus loin que les contrôles. On l'écarte ici, à l'entrée.
    propre = "".join(c for c in valeur
                     if (c == "\n" or c >= " ") and not 0xD800 <= ord(c) <= 0xDFFF)
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


def est_un_son(contenu: bytes) -> bool:
    """Le format se lit dans le contenu, jamais dans le nom du fichier."""
    return (any(contenu.startswith(s) for s in SIGNATURES_SON)
            or contenu[4:8] == b"ftyp")          # MP4 et M4A : la marque est au cinquième octet


class Controleur:
    """Applique tous les contrôles. `geo` répond « dans la commune ? dans l'eau ? »."""

    def __init__(self, geographie, parametres: dict, lieux: list = None):
        self.geo = geographie
        # Les lieux connus, par identifiant (T16) : c'est le serveur qui donne la position d'un
        # lieu choisi, pas le téléphone.
        self.lieux = {l["id"]: l for l in (lieux or [])}
        self.seuils = parametres["controles"]
        self.volumes = parametres["volumes_par_taille_m3"]

    # Les contrôles communs aux deux natures de signalement : où, quand, et par qui.
    # Ils sont à part pour qu'une fuite d'eau subisse exactement les mêmes que les ordures,
    # sans que le code soit écrit deux fois.
    def _position(self, brut: dict, motifs: list):
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
        return lon, lat

    def _depuis_un_lieu(self, brut: dict):
        """Le téléphone n'a pas pu se localiser et l'habitant a choisi un lieu connu (T16).

        Renvoie (brut, provenance, motifs). Si un lieu est choisi, sa position et son nom sont
        pris dans NOTRE liste, d'après son identifiant : un envoi forgé ne peut pas mettre un
        nom rassurant sur une position quelconque. La précision annoncée est celle d'un repère,
        150 m au moins, et non celle d'un GPS : l'agent doit savoir qu'il faudra chercher."""
        if brut.get("source_position") != "lieu":
            return brut, {"source_position": "gps", "lieu_nom": None}, []
        lieu = self.lieux.get(str(brut.get("lieu_id", ""))[:80])
        if lieu is None:
            return brut, {"source_position": "lieu", "lieu_nom": None}, ["format_invalide"]
        precision = max(nombre(brut.get("precision_m")) or 0, PRECISION_LIEU_M)
        corrige = dict(brut, latitude=lieu["latitude"], longitude=lieu["longitude"],
                       precision_m=precision)
        return corrige, {"source_position": "lieu", "lieu_nom": lieu["nom"]}, []

    def _date(self, brut: dict, motifs: list):
        date = lire_date(brut.get("date_observation"))
        if date is None:
            date = maintenant()                        # non précisée : on prend l'heure de réception
        elif date > maintenant() + datetime.timedelta(minutes=10):
            motifs.append("date_future")
        elif (maintenant() - date).days > self.seuils["anciennete_max_jours"]:
            motifs.append("date_trop_ancienne")
        return date

    def _precision(self, brut: dict, motifs: list):
        precision = nombre(brut.get("precision_m"))
        if precision is not None and (precision < 0 or precision > self.seuils["precision_max_m"]):
            motifs.append("precision_insuffisante")
        return precision

    def _declarant(self, brut: dict, motifs: list) -> dict:
        """Identité FACULTATIVE : seulement si le déclarant accepte d'être témoin.
        Elle n'est jamais servie au public (voir Dossiers.detail)."""
        maxi_texte = self.seuils["texte_max_caracteres"]
        commentaire = texte(brut.get("commentaire"), maxi_texte)
        source = texte(brut.get("source"), 64)
        id_client = texte(brut.get("id_client"), 64)
        if commentaire is None or source is None or id_client is None:
            motifs.append("format_invalide")
        return {
            "id_client": id_client or None,
            "commentaire": commentaire or "", "source": source or "inconnue",
            "declarant_nom": texte(brut.get("declarant_nom"), 80) or None,
            "declarant_telephone": texte(brut.get("declarant_telephone"), 30) or None,
        }

    def examiner_fuite(self, brut: dict) -> dict:
        """Une fuite sur une conduite d'eau : mêmes contrôles de position et de date qu'un tas
        d'ordures, mais ni taille ni volume. Ce qu'on demande en plus, c'est l'ampleur, que
        n'importe qui peut décrire sans rien mesurer, et le quartier."""
        if not isinstance(brut, dict):
            return self.resultat({"nature": "fuite_eau"}, ["format_invalide"])
        brut, provenance, motifs = self._depuis_un_lieu(brut)
        lon, lat = self._position(brut, motifs)
        date = self._date(brut, motifs)
        precision = self._precision(brut, motifs)

        ampleur = brut.get("ampleur")
        if ampleur not in AMPLEURS:
            motifs.append("ampleur_invalide")
            ampleur = None

        propre = {"nature": "fuite_eau", "latitude": lat, "longitude": lon,
                  "precision_m": precision, "date_observation": date.isoformat(timespec="seconds"),
                  "ampleur": ampleur,
                  "quartier": texte(brut.get("quartier"), 80) or None, **provenance}
        propre.update(self._declarant(brut, motifs))
        return self.resultat(propre, motifs)

    def examiner_nuisance(self, brut: dict) -> dict:
        """Caniveau bouché, abattoir clandestin, déversement de toilettes, eaux usées.

        Mêmes contrôles de position et de date que tout le reste. Ce qu'on demande en plus,
        c'est la gravité : trois niveaux qu'on peut juger à l'œil, sans rien mesurer."""
        if not isinstance(brut, dict):
            return self.resultat({}, ["format_invalide"])
        motifs = []
        nature = brut.get("nature")
        if nature not in NATURES_NUISANCE:
            return self.resultat({}, ["nature_inconnue"])
        brut, provenance, motifs = self._depuis_un_lieu(brut)
        lon, lat = self._position(brut, motifs)
        date = self._date(brut, motifs)
        precision = self._precision(brut, motifs)

        gravite = brut.get("gravite")
        if gravite not in GRAVITES:
            motifs.append("gravite_invalide")
            gravite = None

        propre = {"nature": nature, "latitude": lat, "longitude": lon,
                  "precision_m": precision, "date_observation": date.isoformat(timespec="seconds"),
                  "gravite": gravite,
                  "quartier": texte(brut.get("quartier"), 80) or None, **provenance}
        propre.update(self._declarant(brut, motifs))
        return self.resultat(propre, motifs)

    def examiner(self, brut: dict) -> dict:
        """Renvoie un signalement propre : champs normalisés, statut et motifs.

        `brut` vient du téléphone ou d'un lot du jury : rien n'y est tenu pour vrai.
        Un signalement sans nature est un tas d'ordures : c'est le cas de loin le plus
        fréquent, et c'était le seul avant que les autres natures existent."""
        motifs = []
        if not isinstance(brut, dict):
            return self.resultat({}, ["format_invalide"])
        nature = brut.get("nature")
        if nature == "fuite_eau":
            return self.examiner_fuite(brut)
        if nature in NATURES_NUISANCE:
            return self.examiner_nuisance(brut)
        if nature is not None and nature not in NATURES:
            return self.resultat({}, ["nature_inconnue"])

        brut, provenance, motifs = self._depuis_un_lieu(brut)
        lon, lat = self._position(brut, motifs)

        taille = brut.get("taille")
        taille = taille if taille in TAILLES else None
        volume = nombre(brut.get("volume_m3"))
        if volume is None and taille:
            volume = self.volumes[taille]                 # pas de volume donné : celui de la taille
        if taille is None and volume is None:
            motifs.append("format_invalide")
        elif volume is not None and not (0 < volume <= self.seuils["volume_max_m3"]):
            motifs.append("volume_invraisemblable")

        date = self._date(brut, motifs)

        # Dimensions au sol, facultatives : elles donnent une superficie estimée.
        longueur, largeur = nombre(brut.get("longueur_m")), nombre(brut.get("largeur_m"))
        for valeur in (longueur, largeur):
            if valeur is not None and not (0 < valeur <= DIMENSION_MAX_M):
                motifs.append("dimensions_invraisemblables")
                longueur = largeur = None
                break

        precision = self._precision(brut, motifs)
        genre = brut.get("type") if brut.get("type") in TYPES else "autre"

        propre = {
            "nature": "ordures", "latitude": lat, "longitude": lon,
            "precision_m": precision, "date_observation": date.isoformat(timespec="seconds"),
            "taille": taille, "volume_m3": volume, "type": genre,
            "depot": brut.get("depot") if brut.get("depot") in DEPOTS else None,
            "longueur_m": longueur, "largeur_m": largeur,
            "quartier": texte(brut.get("quartier"), 80) or None,
            **provenance,
        }
        propre.update(self._declarant(brut, motifs))
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

    def controler_audio(self, contenu: bytes) -> bool:
        maximum = self.seuils.get("audio_max_octets", 4_000_000)
        return bool(contenu) and len(contenu) <= maximum and est_un_son(contenu)
