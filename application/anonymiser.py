"""Masquer les visages et les plaques d'immatriculation sur les photos de signalement.

Exigence E18, premier livrable du challenge : « application de signalement hors connexion, qui
masque automatiquement les visages et les plaques d'immatriculation sur les photos ».

**Le point essentiel : l'image d'origine ne touche jamais le disque.** Le masquage se fait en
mémoire, à la réception, avant le moindre enregistrement — pas de fichier temporaire, pas de
copie « au cas où ». C'est toute la différence entre « nous floutons les visages » et « nous
gardons les visages mais nous les cachons ». Un jury de cybersécurité ira vérifier le fichier
sur le disque, pas ce que montre l'écran.

Quelqu'un qui passe derrière un tas d'ordures n'a rien demandé à personne. Sa photo ne doit pas
finir dans une base municipale parce qu'il passait là.

Tout fonctionne **hors ligne** : les détecteurs sont livrés dans le paquet `opencv-python-
headless` (version 4.10 ; OpenCV 5 ne les livre plus), rien n'est téléchargé à l'exécution.

Pour les visages, deux méthodes s'ajoutent : les cascades d'OpenCV, et **YuNet**, un petit
réseau de neurones (230 Ko, licence MIT, rangé dans `application/modeles/`). Les cascades
ratent les visages petits, au fond d'une photo prise de loin, qui sont justement ceux qu'on
trouve devant un dépotoir ; YuNet les voit. Un visage vu par l'une OU l'autre est masqué.

Ce qui reste raté, et nous le disons plutôt que de le laisser découvrir : un visage vu
complètement de dos ou de côté, une plaque burkinabè dont le format diffère de celui sur lequel
la cascade a été entraînée. D'où le comptage renvoyé avec chaque photo, et le masquage à la main
offert aux agents sur leur poste de travail.
"""

import pathlib

import numpy as np

try:
    import cv2
except ImportError:                                   # pragma: no cover
    cv2 = None

# Les détecteurs, chargés une fois. Deux pour les visages : de face et de profil, parce qu'une
# photo prise de loin attrape souvent des gens de côté. Deux pour les plaques, qui ne couvrent
# pas les mêmes formats.
_CASCADES = {
    "visage": ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml"),
    "plaque": ("haarcascade_russian_plate_number.xml",
               "haarcascade_license_plate_rus_16stages.xml"),
}
_detecteurs = None

# Une cascade cadre au plus juste et laisse souvent le menton, les cheveux ou le bord de la
# plaque dehors. On élargit chaque zone avant de la masquer.
MARGE = 0.20
# Au-delà de cette largeur, l'image est réduite pour la détection : une photo de téléphone fait
# 4000 pixels de large, et y chercher des visages prendrait plusieurs secondes pour rien.
LARGEUR_DETECTION = 1280

# Ce qui distingue une vraie zone d'une fausse. Les cascades à plaques se déclenchent sur
# n'importe quel rectangle contrasté — une planche, une banderole, un panneau — et sur une
# photo de dépotoir il y en a partout. Masquer au hasard effacerait le tas d'ordures lui-même,
# c'est-à-dire la preuve que le signalement apporte. On filtre donc sur trois critères simples.
#
# Les seuils sont volontairement sévères pour les plaques et larges pour les visages : rater
# une plaque est regrettable, rater un visage ne l'est pas moins, mais noyer la moitié de la
# photo rend le signalement inutilisable. L'agent garde le masquage à la main pour le reste.
FORMES = {
    # (rapport largeur/hauteur minimum, maximum, part maximale de l'image, voisins exigés)
    "visage": (0.6, 1.8, 0.40, 5),
    "plaque": (1.8, 6.0, 0.06, 12),
}


def disponible() -> bool:
    """Le masquage peut-il se faire ? Si non, on refuse la photo plutôt que de la garder nue."""
    return cv2 is not None


def _charger():
    global _detecteurs
    if _detecteurs is None:
        _detecteurs = {}
        for genre, fichiers in _CASCADES.items():
            chargees = []
            for nom in fichiers:
                cascade = cv2.CascadeClassifier(cv2.data.haarcascades + nom)
                if not cascade.empty():
                    chargees.append(cascade)
            _detecteurs[genre] = chargees
    return _detecteurs


def _zones(image_grise, cascades, genre) -> list:
    """Les zones trouvées pour ce genre, une fois écartées les invraisemblables."""
    rapport_mini, rapport_maxi, part_maxi, voisins = FORMES[genre]
    hauteur, largeur = image_grise.shape[:2]
    aire_image = float(largeur * hauteur) or 1.0
    taille_mini = 24 if genre == "visage" else 20
    trouvees = []
    for cascade in cascades:
        for (x, y, l, h) in cascade.detectMultiScale(
                image_grise, scaleFactor=1.1, minNeighbors=voisins,
                minSize=(taille_mini, taille_mini)):
            if h <= 0:
                continue
            rapport = l / h
            if not rapport_mini <= rapport <= rapport_maxi:
                continue                       # ni un visage ni une plaque n'a cette forme
            if (l * h) / aire_image > part_maxi:
                continue                       # trop grand pour être ce qu'on cherche
            trouvees.append((int(x), int(y), int(l), int(h)))
    return trouvees


MODELE_YUNET = (pathlib.Path(__file__).resolve().parent / "modeles"
                / "face_detection_yunet_2023mar.onnx")
# Note de confiance de 0 à 1 au-dessus de laquelle YuNet annonce un visage. Plus bas que la
# valeur des exemples d'OpenCV (0,9) : ici, rater un visage coûte plus cher que flouter une
# zone de trop.
SEUIL_YUNET = 0.6


def _visages_yunet(image_couleur) -> list:
    """Les visages que voit YuNet, en (x, y, largeur, hauteur). Liste vide si le modèle manque :
    les cascades travaillent alors seules, comme avant."""
    if not MODELE_YUNET.exists() or not hasattr(cv2, "FaceDetectorYN"):
        return []
    hauteur, largeur = image_couleur.shape[:2]
    try:
        # Un détecteur par photo : il se crée en quelques millisecondes, et les fils de gunicorn
        # ne se partagent ainsi rien.
        detecteur = cv2.FaceDetectorYN.create(str(MODELE_YUNET), "", (largeur, hauteur),
                                              SEUIL_YUNET, 0.3, 5000)
        _, visages = detecteur.detect(image_couleur)
    except cv2.error:
        return []
    zones = []
    for visage in (visages if visages is not None else []):
        x, y, l, h = (int(round(float(v))) for v in visage[:4])
        x, y = max(0, x), max(0, y)
        l, h = min(l, largeur - x), min(h, hauteur - y)
        if l > 0 and h > 0:
            zones.append((x, y, l, h))
    return zones


def _fusionner(zones: list) -> list:
    """Deux cascades voient souvent le même visage : on ne masque pas deux fois au même endroit.

    Une zone contenue à plus de moitié dans une autre est absorbée par elle."""
    gardees = []
    for zone in sorted(zones, key=lambda z: z[2] * z[3], reverse=True):
        x, y, l, h = zone
        doublon = False
        for (gx, gy, gl, gh) in gardees:
            recouvrement_l = max(0, min(x + l, gx + gl) - max(x, gx))
            recouvrement_h = max(0, min(y + h, gy + gh) - max(y, gy))
            if recouvrement_l * recouvrement_h > 0.5 * l * h:
                doublon = True
                break
        if not doublon:
            gardees.append(zone)
    return gardees


def masquer(contenu: bytes) -> tuple:
    """Renvoie (image masquée en JPEG, comptes). Tout se passe en mémoire.

    Si rien n'est détecté, l'image est renvoyée telle quelle, sans ré-encodage : une photo sans
    personne ni véhicule ne doit pas perdre en qualité pour rien."""
    comptes = {"visages": 0, "plaques": 0}
    if cv2 is None:
        return contenu, comptes

    image = cv2.imdecode(np.frombuffer(contenu, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return contenu, comptes                       # pas une image : le contrôle s'en charge

    hauteur, largeur = image.shape[:2]
    # On cherche sur une version réduite, puis on reporte les zones sur l'image d'origine.
    facteur = min(1.0, LARGEUR_DETECTION / largeur) if largeur else 1.0
    petite = (cv2.resize(image, None, fx=facteur, fy=facteur, interpolation=cv2.INTER_AREA)
              if facteur < 1.0 else image)
    grise = cv2.equalizeHist(cv2.cvtColor(petite, cv2.COLOR_BGR2GRAY))

    detecteurs = _charger()
    trouvees = {genre: _zones(grise, cascades, genre) for genre, cascades in detecteurs.items()}
    # YuNet s'ajoute aux cascades ; un même visage vu deux fois n'est compté qu'une.
    trouvees["visage"] = trouvees.get("visage", []) + _visages_yunet(petite)
    trouvees = {genre: _fusionner(zones) for genre, zones in trouvees.items()}

    for genre, zones in trouvees.items():
        for (x, y, l, h) in zones:
            # Retour à l'échelle de l'image d'origine, puis élargissement.
            x, y, l, h = (int(v / facteur) for v in (x, y, l, h))
            dx, dy = int(l * MARGE), int(h * MARGE)
            x1, y1 = max(0, x - dx), max(0, y - dy)
            x2, y2 = min(largeur, x + l + dx), min(hauteur, y + h + dy)
            if x2 <= x1 or y2 <= y1:
                continue
            morceau = image[y1:y2, x1:x2]
            # Un noyau large et proportionnel à la zone : un flou léger se défait, pas celui-ci.
            noyau = max(21, (min(x2 - x1, y2 - y1) // 2) | 1)
            image[y1:y2, x1:x2] = cv2.GaussianBlur(morceau, (noyau, noyau), 0)
            comptes["visages" if genre == "visage" else "plaques"] += 1

    if not comptes["visages"] and not comptes["plaques"]:
        return contenu, comptes

    ok, encodee = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:                                        # pragma: no cover
        return contenu, comptes
    return encodee.tobytes(), comptes


def masquer_une_zone(contenu: bytes, x: float, y: float, largeur: float,
                     hauteur: float) -> bytes:
    """Masque une zone désignée à la main, en proportions de l'image (0 à 1).

    Pour ce que la détection automatique a raté : un agent qui peut corriger vaut mieux qu'un
    détecteur dont on prétendrait qu'il voit tout."""
    if cv2 is None:
        return contenu
    image = cv2.imdecode(np.frombuffer(contenu, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return contenu
    h_img, l_img = image.shape[:2]
    x1, y1 = max(0, int(x * l_img)), max(0, int(y * h_img))
    x2, y2 = min(l_img, int((x + largeur) * l_img)), min(h_img, int((y + hauteur) * h_img))
    if x2 <= x1 or y2 <= y1:
        return contenu
    noyau = max(21, (min(x2 - x1, y2 - y1) // 2) | 1)
    image[y1:y2, x1:x2] = cv2.GaussianBlur(image[y1:y2, x1:x2], (noyau, noyau), 0)
    ok, encodee = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return encodee.tobytes() if ok else contenu
