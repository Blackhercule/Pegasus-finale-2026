"""Ajoute des collecteurs, centres et campagnes d'EXEMPLE, pour montrer les pages vides (C14).

    python outils/exemples_collecteurs.py [adresse] [mot de passe du compte « agent »]

Tout est marqué « (exemple) » : ce ne sont pas de vrais acteurs. La mairie les remplace par les
vrais depuis la page Collecteurs. Rien n'est envoyé ailleurs que sur notre propre serveur.
"""

import datetime
import http.cookiejar
import json
import ssl
import sys
import urllib.request

ADRESSE = sys.argv[1] if len(sys.argv) > 1 else "https://localhost:8444"
MOT_DE_PASSE = sys.argv[2] if len(sys.argv) > 2 else "essai"


class Session:
    """Le strict nécessaire, avec la bibliothèque standard : rien à installer sur le PC.
    Le certificat de notre autorité interne n'est pas vérifié ici : on ne parle qu'à NOTRE
    machine (localhost)."""
    def __init__(self):
        contexte = ssl.create_default_context()
        if ADRESSE.startswith("https://localhost"):
            contexte.check_hostname, contexte.verify_mode = False, ssl.CERT_NONE
        self.ouvreur = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=contexte))
        self.jeton = ""

    def post(self, chemin, envoi):
        requete = urllib.request.Request(ADRESSE + chemin, data=json.dumps(envoi).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "X-Jeton": self.jeton})
        with self.ouvreur.open(requete) as reponse:
            return json.loads(reponse.read())

COLLECTEURS = [
    {"nom": "Association Laafi Propreté (exemple)", "genre": "association",
     "quartiers": ["Tampouy", "Kouritinga", "Bilbalogho"], "jours": ["mardi", "vendredi"],
     "vehicules": [("tricycle", 2), ("tricycle", 2)]},
    {"nom": "Ouaga Net Services (exemple)", "genre": "entreprise",
     "quartiers": ["Ouaga 2000", "Patte d'Oie", "Karpalin"], "jours": ["lundi", "jeudi"],
     "vehicules": [("camion", 8), ("tricycle", 2)]},
    {"nom": "Groupement des femmes de Gounghin (exemple)", "genre": "association",
     "quartiers": ["Gounghin Nord", "Gounghin Sud", "Paglayiri", "Kalgodin"],
     "jours": ["mercredi", "samedi"], "vehicules": [("charrette", 1), ("tricycle", 2)]},
]


def principal():
    s = Session()
    s.jeton = s.post("/api/connexion", {"nom": "agent", "mot_de_passe": MOT_DE_PASSE})["jeton"]
    centre = s.post("/api/centres", {"nom": "Centre de collecte de Kossodo (exemple)",
                                                     "latitude": 12.4125, "longitude": -1.4695,
                                     "capacite_t": 400})
    jour = datetime.date.today()
    for c in COLLECTEURS:
        fiche = s.post("/api/collecteurs", {k: v for k, v in c.items() if k != "vehicules"})
        for genre, capacite in c["vehicules"]:
            s.post(f"/api/collecteurs/{fiche['id']}/vehicules", {"genre": genre, "capacite_m3": capacite})
        for n in range(4):
            s.post("/api/collectes", {
                "collecteur_id": fiche["id"], "date": (jour - datetime.timedelta(days=3 * n)).isoformat(),
                "quartier": c["quartiers"][n % len(c["quartiers"])], "quantite_kg": 600 + 150 * n,
                "centre_id": centre["id"]})
    s.post("/api/campagnes", {
        "titre": "Challenge « École propre » (exemple)", "date": (jour - datetime.timedelta(days=4)).isoformat(),
        "quartier": "Tampouy", "organisateur": "Écoles primaires de Tampouy", "participants": 240,
        "quantite_kg": 1800})
    print("Exemples ajoutés :", len(COLLECTEURS), "collecteurs, 1 centre, 1 campagne.")


if __name__ == "__main__":
    principal()
