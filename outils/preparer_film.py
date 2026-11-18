"""Prépare la base pour filmer la vidéo (outils/filmer.mjs), après outils/donnees_demonstration.py.

    python outils/preparer_film.py [adresse]      (défaut http://127.0.0.1:8099)

Ajoute deux comptes individuels FICTIFS (Awa Kaboré à la mairie, Issa Sawadogo à la brigade),
pour que le journal « qui a fait quoi » montre des noms, et un signalement avec une photo de
tas d'ordures dessinée par programme (aucune photo réelle, aucun visage). Affiche les numéros
du signalement et du dossier, à passer à filmer.mjs par SIGNALEMENT=… DOSSIER=…
"""

import datetime
import io
import random
import sys

import requests
from PIL import Image, ImageDraw, ImageFilter

ADRESSE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
COMPTES = [
    {"identifiant": "awa.kabore", "nom": "Awa Kaboré", "poste": "mairie",
     "mot_de_passe": "mairie-awa-2026"},
    {"identifiant": "issa.sawadogo", "nom": "Issa Sawadogo", "poste": "brigade",
     "mot_de_passe": "laabal-issa-2026"},
]


def photo_de_tas() -> bytes:
    """Un sol sableux couvert de déchets de couleur : assez pour la démonstration."""
    hasard = random.Random(7)
    image = Image.new("RGB", (1280, 960), (196, 160, 112))
    dessin = ImageDraw.Draw(image)
    couleurs = [(40, 40, 40), (200, 30, 40), (30, 90, 170), (240, 240, 235), (30, 140, 70),
                (230, 160, 30), (120, 60, 140), (20, 20, 60)]
    for _ in range(260):
        x, y = hasard.randint(80, 1200), hasard.randint(330, 900)
        dessin.ellipse((x, y, x + hasard.randint(18, 90), y + hasard.randint(10, 45)),
                       fill=hasard.choice(couleurs))
    tampon = io.BytesIO()
    image.filter(ImageFilter.GaussianBlur(1.2)).save(tampon, "JPEG", quality=88)
    return tampon.getvalue()


def principal():
    session = requests.Session()
    reponse = session.post(ADRESSE + "/api/connexion", json={"nom": "agent", "mot_de_passe": "essai"})
    reponse.raise_for_status()
    session.headers["X-Jeton"] = reponse.json()["jeton"]
    for compte in COMPTES:
        print(compte["identifiant"], session.post(ADRESSE + "/api/agents", json=compte).status_code)
    maintenant = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    reponse = requests.post(ADRESSE + "/api/signalements", data={
        "latitude": "12.3790", "longitude": "-1.5110", "precision_m": "8", "taille": "tres_grand",
        "nature": "ordures", "source": "tel-film", "id_client": "film-1",
        "date_observation": maintenant}, files={"photo": ("tas.jpg", photo_de_tas(), "image/jpeg")})
    reponse.raise_for_status()
    r = reponse.json()
    print(f"SIGNALEMENT={r['id']} DOSSIER={r['depotoir_id']}")


if __name__ == "__main__":
    principal()
