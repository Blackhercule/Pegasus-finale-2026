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

Ce que ces détecteurs ratent, et nous le disons plutôt que de le laisser découvrir : un visage
vu très de côté, un visage minuscule au fond de l'image, une plaque burkinabè dont le format
diffère de celui sur lequel la cascade a été entraînée. D'où le comptage renvoyé avec chaque
photo, et le masquage à la main offert aux agents sur leur poste de travail.
"""

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


def _zones(image_grise, cascades, taille_mini) -> list:
    trouvees = []
    for cascade in cascades:
        for (x, y, l, h) in cascade.detectMultiScale(
                image_grise, scaleFactor=1.1, minNeighbors=5,
                minSize=(taille_mini, taille_mini)):
            trouvees.append((int(x), int(y), int(l), int(h)))
    return trouvees


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
    trouvees = {genre: _fusionner(_zones(grise, cascades, 24 if genre == "visage" else 20))
                for genre, cascades in detecteurs.items()}

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
