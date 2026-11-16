"""Remplit la base avec un jeu de démonstration, pour la vidéo et les répétitions.

    python outils/donnees_demonstration.py [adresse]

Tous les signalements sont fictifs et placés dans Ouagadougou. Le but est d'avoir, en une
commande, des dossiers à toutes les étapes de la chaîne : c'est ce qu'il faut pour montrer
l'outil sans tout refaire en direct devant le jury.
"""

import json
import random
import sys
import urllib.error
import urllib.request

ADRESSE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
COMPTES = {"mairie": ("agent", "essai"), "brigade": ("brigade", "essai-b"),
           "collecte": ("collecte", "essai-c")}

# Lieux fictifs répartis dans la commune, avec leur allure.
LIEUX = [
    (-1.5197, 12.3714, "grand", "caniveau", (9, 4)),
    (-1.4700, 12.3300, "tres_grand", "plein_air", (14, 7)),
    (-1.5600, 12.4000, "moyen", "bac", (4, 3)),
    (-1.5300, 12.3050, "grand", "plein_air", (11, 5)),
    (-1.5900, 12.3600, "tres_grand", "berge", (18, 9)),
    (-1.4850, 12.3900, "moyen", "fosse", (5, 4)),
    (-1.5450, 12.4150, "grand", "caniveau", (8, 3)),
    (-1.4950, 12.3450, "petit", "bac", (2, 2)),
    (-1.5700, 12.3350, "grand", "plein_air", (10, 6)),
    (-1.5050, 12.4050, "moyen", "caniveau", (6, 3)),
]


def appeler(chemin, donnees=None, methode=None, cookies=None, entetes=None):
    corps = json.dumps(donnees).encode() if donnees is not None else None
    tetes = {"Content-Type": "application/json", **(entetes or {})}
    if cookies:
        tetes["Cookie"] = cookies
    requete = urllib.request.Request(ADRESSE + chemin, corps, tetes, method=methode)
    try:
        reponse = urllib.request.urlopen(requete, timeout=60)
        return json.loads(reponse.read() or b"{}"), reponse.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as erreur:
        return json.loads(erreur.read() or b"{}"), ""


def connecter(poste):
    nom, mot_de_passe = COMPTES[poste]
    resultat, cookie = appeler("/api/connexion", {"nom": nom, "mot_de_passe": mot_de_passe})
    if "jeton" not in resultat:
        sys.exit(f"Connexion « {nom} » impossible : {resultat}. Vérifiez les mots de passe du .env.")
    return (cookie.split(";")[0] if cookie else ""), resultat["jeton"]


def principal():
    hasard = random.Random(2026)
    print(f"Remplissage de {ADRESSE}…")
    for numero, (lon, lat, taille, depot, (longueur, largeur)) in enumerate(LIEUX):
        for source in ("telephone-nord", "telephone-sud"):
            appeler("/api/signalements", {
                "latitude": lat + hasard.uniform(-8e-5, 8e-5),
                "longitude": lon + hasard.uniform(-8e-5, 8e-5),
                "taille": taille, "depot": depot,
                "longueur_m": longueur, "largeur_m": largeur,
                "type": hasard.choice(["menager", "gravats", "mixte"]),
                "precision_m": hasard.randint(5, 25),
                "commentaire": hasard.choice([
                    "Au bord du caniveau, depuis deux semaines",
                    "Devant l'école, les enfants passent à côté",
                    "Le bac déborde depuis le dernier passage", ""]),
                "source": source, "id_client": f"demo-{numero}-{source}",
            })
    print(f"{len(LIEUX)} dépotoirs créés, chacun confirmé par deux appareils.")

    # On fait avancer quelques dossiers, pour avoir des dossiers à chaque étape.
    avancees = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2}
    for identifiant, pas in avancees.items():
        for numero in range(pas):
            poste = ["mairie", "brigade", "mairie", "collecte"][numero]
            cookie, jeton = connecter(poste)
            detail = ["Confirmé sur place avec le chef de quartier",
                      "Riverains sensibilisés, un récidiviste verbalisé",
                      "Inscrit dans la tournée de jeudi",
                      "Enlevé : deux rotations"][numero]
            appeler(f"/api/dossiers/{identifiant}/avancer", {"detail": detail},
                    cookies=cookie, entetes={"X-Jeton": jeton})
    resultat, _ = appeler("/api/chaine")
    print("Dossiers par étape :", resultat.get("comptes"))


if __name__ == "__main__":
    principal()
