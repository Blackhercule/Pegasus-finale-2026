"""E18 : masquer les visages et les plaques sur les photos de signalement.

Ce qui est vérifié ici, c'est **notre** code : qu'une zone détectée est bien floutée, que c'est
l'image masquée et non l'originale qui est écrite sur le disque, que les comptes suivent, et
qu'une photo est refusée plutôt que gardée nue si le masquage est indisponible.

La qualité de détection d'OpenCV, elle, est à OpenCV. On ne peut pas l'éprouver avec une image
fabriquée : ces cascades sont entraînées sur de vraies photos et ne voient pas un visage
dessiné. Elle se vérifie avec une vraie photo, sur le PC, avant la démonstration — et le test
du bas le fait tout seul si on dépose une photo dans tests/photos/.
"""

import io
import pathlib

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from application import anonymiser


def image_bruitee(largeur=640, hauteur=480) -> bytes:
    """Une image bien bruitée : après floutage, sa variance s'effondre. C'est ce qui permet de
    prouver qu'on a flouté, et pas seulement dessiné par-dessus."""
    generateur = np.random.default_rng(1234)
    tableau = generateur.integers(0, 256, (hauteur, largeur, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", tableau)[1].tobytes()


def variance(contenu: bytes, x1, y1, x2, y2) -> float:
    image = cv2.imdecode(np.frombuffer(contenu, np.uint8), cv2.IMREAD_COLOR)
    return float(image[y1:y2, x1:x2].std())


def test_masquer_une_zone_floute_vraiment(   ):
    """Un flou léger se défait ; celui-ci doit effondrer le détail de la zone."""
    avant = image_bruitee()
    apres = anonymiser.masquer_une_zone(avant, 0.25, 0.25, 0.5, 0.5)
    centre = (200, 150, 440, 330)
    assert variance(apres, *centre) < variance(avant, *centre) / 3
    # et seulement la zone : le coin reste net
    assert variance(apres, 0, 0, 80, 60) > variance(avant, 0, 0, 80, 60) / 2


def test_une_zone_hors_image_ne_casse_rien():
    avant = image_bruitee()
    assert anonymiser.masquer_une_zone(avant, 2.0, 2.0, 0.5, 0.5) == avant
    assert anonymiser.masquer_une_zone(avant, 0.5, 0.5, 0, 0) == avant


def test_sans_rien_a_masquer_l_image_est_rendue_telle_quelle():
    """Une photo sans personne ni véhicule ne doit pas perdre en qualité pour rien."""
    avant = image_bruitee()
    apres, comptes = anonymiser.masquer(avant)
    assert apres == avant
    assert comptes == {"visages": 0, "plaques": 0}


def test_un_fichier_qui_n_est_pas_une_image_ressort_intact():
    contenu = b"ceci n'est pas une image" * 20
    apres, comptes = anonymiser.masquer(contenu)
    assert apres == contenu and comptes == {"visages": 0, "plaques": 0}


def test_une_zone_detectee_est_floutee_et_comptee(monkeypatch):
    """On force la détection pour éprouver NOTRE chaîne, sans dépendre d'une vraie photo."""
    zone = [(160, 120, 160, 120)]                    # x, y, largeur, hauteur
    monkeypatch.setattr(anonymiser, "_zones",
                        lambda grise, cascades, mini: zone if cascades else [])
    avant = image_bruitee()
    apres, comptes = anonymiser.masquer(avant)
    assert comptes["visages"] >= 1
    assert apres != avant
    assert variance(apres, 180, 140, 300, 220) < variance(avant, 180, 140, 300, 220) / 3


def test_la_marge_elargit_la_zone(monkeypatch):
    """Une cascade cadre au plus juste : sans marge, le menton ou le bord de la plaque restent."""
    monkeypatch.setattr(anonymiser, "_zones",
                        lambda grise, cascades, mini: [(200, 200, 100, 100)] if cascades else [])
    apres, _ = anonymiser.masquer(image_bruitee())
    avant = image_bruitee()
    # juste en dehors de la zone brute, mais dans la marge de 20 %
    assert variance(apres, 185, 185, 199, 199) < variance(avant, 185, 185, 199, 199)


# --------------------------------------------------------------------- bout en bout

PHOTO = {"latitude": "12.3714", "longitude": "-1.5197", "taille": "grand",
         "source": "tel-essai", "id_client": "p1"}


def envoyer_photo(client, contenu, champ="photo", **champs):
    return client.post("/api/signalements", data={
        **PHOTO, **champs, champ: (io.BytesIO(contenu), "photo.jpg")},
        content_type="multipart/form-data")


def test_c_est_l_image_masquee_qui_est_ecrite_sur_le_disque(client, agent, tmp_path, monkeypatch):
    """Le point que le jury viendra vérifier : l'originale ne doit jamais toucher le disque."""
    monkeypatch.setattr(anonymiser, "_zones",
                        lambda grise, cascades, mini: [(160, 120, 160, 120)] if cascades else [])
    original = image_bruitee()
    reponse = envoyer_photo(client, original)
    assert reponse.status_code == 201

    s = agent.get("/api/depotoirs").get_json()["features"][0]["properties"]
    detail = agent.get("/api/dossiers/%d" % s["id"]).get_json()
    chemin = detail["signalements"][0]["photo"]
    assert chemin, "la photo n'a pas été enregistrée"

    servi = agent.get("/api/fichiers/" + chemin).get_data()
    assert servi != original, "l'image d'origine a été enregistrée telle quelle"
    assert variance(servi, 180, 140, 300, 220) < variance(original, 180, 140, 300, 220) / 3


def test_les_comptes_sont_rendus_a_l_agent(client, agent, monkeypatch):
    """L'agent doit savoir combien ont été masqués, pour masquer à la main ce qui reste."""
    monkeypatch.setattr(anonymiser, "_zones",
                        lambda grise, cascades, mini: [(160, 120, 100, 100)] if cascades else [])
    envoyer_photo(client, image_bruitee())
    s = agent.get("/api/depotoirs").get_json()["features"][0]["properties"]
    signalement = agent.get("/api/dossiers/%d" % s["id"]).get_json()["signalements"][0]
    assert signalement["visages_masques"] >= 1


def test_sans_masquage_la_photo_est_ecartee_et_le_dit(client, monkeypatch):
    """Mieux vaut perdre la photo que garder un visage en clair. Et le dire, pas le taire."""
    monkeypatch.setattr("application.masquage_disponible", lambda: False)
    reponse = envoyer_photo(client, image_bruitee())
    corps = reponse.get_json()
    assert "photo_non_masquable" in corps["motifs"]


def test_la_cnib_et_le_portrait_ne_sont_pas_floutes(client, agent, monkeypatch):
    """Ce sont les pièces que le déclarant a CHOISI de donner pour être témoin : les flouter
    les viderait de leur sens. Elles restent privées et s'effacent à la clôture."""
    monkeypatch.setattr(anonymiser, "_zones",
                        lambda grise, cascades, mini: [(160, 120, 160, 120)] if cascades else [])
    portrait = image_bruitee()
    client.post("/api/signalements", data={
        **PHOTO, "declarant_nom": "Awa",
        "photo_visage": (io.BytesIO(portrait), "moi.jpg")},
        content_type="multipart/form-data")
    s = agent.get("/api/depotoirs").get_json()["features"][0]["properties"]
    signalement = agent.get("/api/dossiers/%d" % s["id"]).get_json()["signalements"][0]
    servi = agent.get("/api/fichiers/" + signalement["photo_visage"]).get_data()
    assert servi == portrait, "le portrait du déclarant a été flouté alors qu'il est consenti"


# ------------------------------------------------- détection réelle, si une photo est fournie

PHOTOS = pathlib.Path(__file__).resolve().parent / "photos"


@pytest.mark.skipif(not (PHOTOS.exists() and list(PHOTOS.glob("*.jpg"))),
                    reason="aucune photo dans tests/photos/ : déposez-y une vraie photo de "
                           "visage pour éprouver la détection d'OpenCV")
def test_la_detection_voit_un_vrai_visage():
    """Ne tourne que si l'équipe a déposé une vraie photo. À faire sur le PC avant la
    démonstration : c'est la seule façon d'éprouver la détection, qu'une image fabriquée ne
    déclenche pas. Le dossier tests/photos/ n'est pas publié (voir .gitignore)."""
    for photo in sorted(PHOTOS.glob("*.jpg")):
        _, comptes = anonymiser.masquer(photo.read_bytes())
        assert comptes["visages"] + comptes["plaques"] > 0, (
            f"rien de détecté sur {photo.name}")
