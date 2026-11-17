"""Mesure les chiffres du rapport (RAPPORT.md) : plan, simulation et temps de calcul.

    python outils/mesurer_scenarios.py

Rien n'est estimé : l'application est lancée en mémoire, avec une base vide dans un dossier
provisoire, sur les vraies données de Ouagadougou. On y dépose les dix dépotoirs fictifs du jeu
de démonstration (chacun vu par deux téléphones, donc vérifié), puis on demande chaque scénario
comme le ferait le tableau de bord (`POST /api/scenario`, 30 jours simulés), et on chronomètre.
Le résultat s'affiche en tableau Markdown, prêt à coller.
"""

import importlib.util
import os
import sys
import tempfile
import time

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ.setdefault("AGENT_MOT_DE_PASSE", "mesure")
os.environ.setdefault("SECRET_SESSION", "mesure")

from application import creer_application  # noqa: E402
from application.reglages import Reglages  # noqa: E402

# Les dix lieux fictifs du jeu de démonstration (outils/donnees_demonstration.py).
_spec = importlib.util.spec_from_file_location(
    "demonstration", os.path.join(RACINE, "outils", "donnees_demonstration.py"))
_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_demo)

SCENARIOS = [
    ("Référence (parametres.json)", {}),
    ("Saison des pluies", {"saison": "pluies"}),
    ("8 camions en panne sur 24", {"camions_en_panne": 8}),
    ("Nouveau quartier de 150 000 habitants", {"nouveaux_quartiers": [
        {"longitude": -1.50, "latitude": 12.31, "rayon_m": 2000, "population": 150000}]}),
    ("Abonnement à 60 %", {"taux_abonnement": 0.60}),
    ("Collecte tous les 2 jours", {"frequence_collecte_jours": 2}),
]


def milliers(n):
    return format(int(round(n)), ",d").replace(",", " ")


def main():
    base = os.path.join(tempfile.mkdtemp(), "mesure.sqlite")
    client = creer_application(Reglages(base=base)).test_client()
    for numero, (lon, lat, taille, depot, (longueur, largeur)) in enumerate(_demo.LIEUX):
        for source in ("tel-a", "tel-b"):
            client.post("/api/signalements", json={
                "latitude": lat, "longitude": lon, "taille": taille, "depot": depot,
                "longueur_m": longueur, "largeur_m": largeur, "source": source,
                "id_client": f"mesure-{numero}-{source}"})
    reponse = client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": os.environ["AGENT_MOT_DE_PASSE"]})
    if reponse.status_code != 200:
        sys.exit("Connexion impossible : " + reponse.get_data(as_text=True))
    depotoirs = client.get("/api/depotoirs").get_json()["features"]
    print(f"Dépotoirs vérifiés dans la base : {len(depotoirs)}\n")

    client.post("/api/scenario", json={"jours": 30})          # premier appel : lecture du réseau
    print("| Scénario | Points de regroupement | Tournées | Arrêts non desservis | km/jour "
          "| Coût mensuel (F CFA) | Solde mensuel (F CFA) | Taux de collecte (30 j) "
          "| Contrôles en défaut | Temps de calcul |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for nom, parametres in SCENARIOS:
        debut = time.perf_counter()
        reponse = client.post("/api/scenario", json={"nom": nom, "parametres": parametres, "jours": 30})
        duree = time.perf_counter() - debut
        r = reponse.get_json()
        if reponse.status_code != 200:
            print(f"| {nom} | erreur {reponse.status_code} : {r} |")
            continue
        resume = r.get("simulation", {}).get("resume", {})
        defauts = [c["nom"] for c in r["controles"] if c["etat"] != "ok"] or ["aucun"]
        print(f"| {nom} | {len(r['points'])} | {len(r['tournees'])} | {len(r['non_desservis'])} "
              f"| {r['couts']['km_par_jour']} | {milliers(r['couts']['cout_par_mois'])} "
              f"| {milliers(r['couts']['solde_mensuel'])} "
              f"| {round(100 * resume.get('taux_collecte', 0), 1)} % "
              f"| {', '.join(defauts)} | {duree:.1f} s |")


if __name__ == "__main__":
    main()
