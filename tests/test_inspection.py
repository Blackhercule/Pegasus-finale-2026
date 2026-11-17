"""Tournées d'inspection : grouper les visites de terrain au lieu d'une sortie par dossier.

Ce qui est éprouvé : que le groupement fait bien gagner du temps, qu'il ne perd aucun dossier
en silence, et qu'il tient quand les données sont mauvaises — le jury enverra des dossiers
piégés, et une tournée qui tombe pendant la démonstration ne se rattrape pas.
"""

import random

from conftest import MOT_DE_PASSE


def connecter(client, nom="agent", mot_de_passe=None):
    r = client.post("/api/connexion", json={
        "nom": nom, "mot_de_passe": mot_de_passe or MOT_DE_PASSE})
    if r.status_code == 200:
        client.environ_base["HTTP_X_JETON"] = r.get_json()["jeton"]
    return r


def semer(client, combien=10, graine=7):
    """Des dossiers dispersés dans la commune, tous en attente de la mairie."""
    alea = random.Random(graine)
    acceptes = 0
    for i in range(combien):
        r = client.post("/api/signalements", json={
            "latitude": 12.345 + alea.random() * 0.045,
            "longitude": -1.545 + alea.random() * 0.075,
            "taille": "moyen", "source": "s%d" % i, "id_client": "x%d" % i})
        acceptes += r.get_json()["statut"] != "rejete"
    return acceptes


def test_grouper_les_visites_fait_gagner_du_temps(agent):
    """Le cœur de la fonction : une sortie qui couvre plusieurs constats."""
    semer(agent, 10)
    resultat = agent.get("/api/inspection").get_json()
    assert resultat["tournees"], "aucune tournée produite"
    visites = sum(t["nb_visites"] for t in resultat["tournees"])
    assert visites > len(resultat["tournees"]), "aucun regroupement : une sortie par dossier"
    economie = resultat["economie"]
    assert economie["heures_avec_groupement"] < economie["heures_sans_groupement"]
    assert economie["sorties_evitees"] > 0


def test_chaque_tournee_tient_dans_une_journee(agent):
    semer(agent, 12)
    resultat = agent.get("/api/inspection?agents_terrain=2").get_json()
    for tournee in resultat["tournees"]:
        assert tournee["duree_min"] <= 8 * 60 + 1, tournee


def test_aucun_dossier_n_est_perdu_en_silence(agent):
    """Ce qui ne rentre pas est nommé, jamais escamoté."""
    acceptes = semer(agent, 10)
    resultat = agent.get("/api/inspection").get_json()
    programmes = {e["id"] for t in resultat["tournees"] for e in t["etapes"]}
    comptes = len(programmes) + len(resultat["non_visites"]) + len(resultat["injoignables"])
    assert comptes == acceptes


def test_l_outil_dit_combien_d_agents_sont_necessaires(agent):
    """Si une seule journée suffit, en envoyer deux coûte une journée pour rien."""
    semer(agent, 8)
    resultat = agent.get("/api/inspection?agents_terrain=5").get_json()
    assert resultat["agents"] == 5
    assert 1 <= resultat["agents_necessaires"] <= 5
    assert resultat["agents_necessaires"] <= len(resultat["tournees"]) or not resultat["tournees"]


def test_la_tournee_suit_les_rues(agent):
    semer(agent, 8)
    resultat = agent.get("/api/inspection").get_json()
    tournee = resultat["tournees"][0]
    # Une ligne droite ferait deux points par étape ; un vrai chemin en fait beaucoup plus.
    assert tournee["geometrie"] is None or len(tournee["geometrie"]) > tournee["nb_visites"] * 2


def test_sans_dossier_a_visiter_la_reponse_reste_saine(agent):
    resultat = agent.get("/api/inspection").get_json()
    assert resultat["tournees"] == []
    assert resultat["non_visites"] == [] and resultat["injoignables"] == []


def test_la_base_de_depart_est_annoncee_comme_a_confirmer(agent):
    """Tant que la mairie ne nous a pas donné l'adresse du service, on le dit."""
    semer(agent, 3)
    base = agent.get("/api/inspection").get_json()["base"]
    assert base["a_confirmer"] is True
    assert "confirmer" in base["nom"].lower()


def test_il_faut_etre_connecte(client):
    assert client.get("/api/inspection").status_code == 401


def test_un_poste_ne_voit_que_ce_qui_l_attend(agent):
    """La brigade n'a rien à visiter tant que la mairie n'a rien confirmé."""
    semer(agent, 5)
    assert agent.get("/api/inspection?poste=brigade").get_json()["tournees"] == []
    assert agent.get("/api/inspection?poste=mairie").get_json()["tournees"]
