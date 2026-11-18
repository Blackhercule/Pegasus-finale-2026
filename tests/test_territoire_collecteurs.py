"""C14 : zones (carte thermique, quartiers, récurrents, curage), collecteurs et côté habitant."""

import datetime

from application.territoire import jours_avant_les_pluies, quartier_de
from conftest import MOT_DE_PASSE


def signaler(client, la=12.3714, lo=-1.5197, n=0, **champs):
    return client.post("/api/signalements", json={
        "latitude": la, "longitude": lo, "taille": "grand", "source": "tel-%d" % n,
        "id_client": "c-%s-%s-%d" % (la, lo, n), **champs}).get_json()


# ------------------------------------------------------------------ quartiers et carte thermique

def test_un_point_va_dans_le_quartier_le_plus_proche():
    quartiers = [("Tampouy", 12.38987, -1.57692), ("Ouaga 2000", 12.30606, -1.50285)]
    assert quartier_de(quartiers, 12.39, -1.57) == "Tampouy"
    assert quartier_de(quartiers, 12.30, -1.50) == "Ouaga 2000"
    assert quartier_de(quartiers, None, None) == "Non localisé"


def test_la_saison_des_pluies_commence_en_juin():
    assert jours_avant_les_pluies(datetime.date(2026, 11, 18)) == 195
    assert jours_avant_les_pluies(datetime.date(2027, 5, 31)) == 1
    assert jours_avant_les_pluies(datetime.date(2027, 7, 15)) == 0


def test_carte_thermique_et_quartiers_touches(agent):
    r = signaler(agent)
    agent.post("/api/signalements/%d/verifier" % r["id"])
    signaler(agent, 12.3896, -1.5765, 1)
    points = agent.get("/api/territoire/points").get_json()["points"]
    assert {p["poids"] for p in points} <= {0.5, 1.0} and len(points) == 2
    quartiers = agent.get("/api/territoire/quartiers").get_json()["quartiers"]
    assert quartiers[0]["indice"] >= quartiers[-1]["indice"]
    assert sum(q["signalements"] for q in quartiers) == 2
    # Filtre par type de problème : aucune fuite signalée.
    assert agent.get("/api/territoire/points?nature=fuite_eau").get_json()["points"] == []
    historique = agent.get("/api/territoire/historique?quartier=" + points[0]["quartier"]).get_json()
    assert historique["historique"]


def test_les_signalements_ecartes_ne_chauffent_pas_la_carte(agent):
    r = signaler(agent)
    agent.post("/api/signalements/%d/rejeter" % r["id"])
    assert agent.get("/api/territoire/points").get_json()["points"] == []


def test_un_tas_revenu_apres_ramassage_est_recurrent(agent, application):
    from application.base import connexion
    for n, la in enumerate((12.37140, 12.37150)):          # deux dossiers à 11 m l'un de l'autre
        r = signaler(agent, la, -1.5197, n)
        agent.post("/api/signalements/%d/verifier" % r["id"])
    co = connexion(application.extensions["reglages"].base)
    with co:
        ids = [l["id"] for l in co.execute("SELECT id FROM depotoirs")]
        if len(ids) == 1:                                   # regroupés : on simule un retour
            co.execute("INSERT INTO depotoirs (latitude, longitude) VALUES (12.3716, -1.5197)")
    recurrents = agent.get("/api/territoire/recurrents").get_json()["recurrents"]
    assert recurrents and len(recurrents[0]["dossiers"]) >= 2


def test_curage_un_caniveau_bouche_entre_dans_la_liste(agent):
    signaler(agent, nature="caniveau_bouche", gravite="grave")
    curage = agent.get("/api/territoire/curage").get_json()
    assert "jours_avant_les_pluies" in curage
    assert curage["a_curer"] and curage["a_curer"][0]["genre"] == "Caniveau bouché"


def test_les_zones_sont_reservees_aux_agents(client):
    for adresse in ("points", "quartiers", "historique", "recurrents", "curage"):
        assert client.get("/api/territoire/" + adresse).status_code == 401


# ------------------------------------------------------------------ collecteurs

COLLECTEUR = {"nom": "Association Laafi Propreté", "genre": "association",
              "telephone_service": "25 00 00 00", "quartiers": ["Tampouy", "Inconnu"],
              "jours": ["mardi", "vendredi", "jourdesfous"]}


def test_la_mairie_enregistre_un_collecteur_ses_vehicules_et_ses_collectes(agent):
    c = agent.post("/api/collecteurs", json=COLLECTEUR).get_json()
    assert c["quartiers"] == ["Tampouy"] and c["jours"] == ["mardi", "vendredi"]
    c = agent.post("/api/collecteurs/%d/vehicules" % c["id"], json={"genre": "tricycle", "capacite_m3": 2}).get_json()
    assert c["vehicules"][0]["genre"] == "tricycle"
    centre = agent.post("/api/centres", json={"nom": "Centre de Tampouy", "latitude": 12.39,
                                              "longitude": -1.57}).get_json()
    assert centre["longitude"] == -1.57
    bilan = agent.post("/api/collectes", json={"collecteur_id": c["id"], "date": "2026-11-18",
                                               "quartier": "Tampouy", "quantite_kg": 850,
                                               "centre_id": centre["id"]}).get_json()
    assert bilan["total_kg"] == 850
    tout = agent.get("/api/collecteurs").get_json()
    assert tout["calendrier"]["Tampouy"]["mardi"] == ["Association Laafi Propreté"]
    assert tout["centres"][0]["recu_kg"] == 850


def test_saisies_invalides_refusees_avec_un_message(agent):
    assert agent.post("/api/collecteurs", json={"nom": "", "genre": "association"}).status_code == 400
    assert agent.post("/api/collecteurs", json={"nom": "X", "genre": "pirate"}).status_code == 400
    c = agent.post("/api/collecteurs", json=COLLECTEUR).get_json()
    r = agent.post("/api/collectes", json={"collecteur_id": c["id"], "date": "hier", "quantite_kg": 1})
    assert r.status_code == 400 and "AAAA-MM-JJ" in r.get_json()["erreur"]
    r = agent.post("/api/collectes", json={"collecteur_id": c["id"], "date": "2026-11-18", "quantite_kg": -5})
    assert r.status_code == 400


def test_seule_la_mairie_enregistre_un_collecteur(application):
    brigade = application.test_client()
    r = brigade.post("/api/connexion", json={"nom": "brigade", "mot_de_passe": "essai-brigade"})
    brigade.environ_base["HTTP_X_JETON"] = r.get_json()["jeton"]
    assert brigade.post("/api/collecteurs", json=COLLECTEUR).status_code == 403


# ------------------------------------------------------------------ côté habitant

def test_l_habitant_trouve_les_collecteurs_de_son_quartier_et_porte_plainte(agent, application):
    c = agent.post("/api/collecteurs", json=COLLECTEUR).get_json()
    public = application.test_client()
    trouves = public.get("/api/public/collecteurs?quartier=Tampouy").get_json()["collecteurs"]
    assert trouves == [{"id": c["id"], "nom": "Association Laafi Propreté", "genre": "Association",
                        "jours": ["mardi", "vendredi"], "telephone_service": "25 00 00 00"}]
    assert public.get("/api/public/collecteurs?quartier=Saaba").get_json()["collecteurs"] == []
    plainte = {"collecteur_id": c["id"], "quartier": "Tampouy", "motif": "pas_passe", "source": "appareil-1234abcd"}
    for _ in range(3):
        assert public.post("/api/public/plaintes", json=plainte).status_code == 200
    assert public.post("/api/public/plaintes", json=plainte).status_code == 400   # 4e le même jour
    assert agent.get("/api/collecteurs").get_json()["plaintes"][0]["motif_nom"].startswith("N'est pas")


def test_points_et_classement_des_quartiers_propres(agent, application):
    r = agent.post("/api/signalements", json={"latitude": 12.3714, "longitude": -1.5197, "taille": "grand",
                                               "source": "appareil-00112233", "id_client": "p1"}).get_json()
    agent.post("/api/signalements/%d/verifier" % r["id"])
    public = application.test_client()
    assert public.get("/api/public/points?source=appareil-00112233").get_json() == {"verifies": 1, "points": 10}
    assert public.get("/api/public/points?source=x").get_json()["points"] == 0
    classement = public.get("/api/public/quartiers").get_json()["classement"]
    assert classement[0]["ouverts"] <= classement[-1]["ouverts"]
    assert set(classement[0]) == {"quartier", "ouverts", "signalements"}      # aucune position


def test_campagnes_publiees(agent, application):
    agent.post("/api/campagnes", json={"titre": "Opération Ouaga propre", "date": "2026-11-14",
                                        "quartier": "Tampouy", "organisateur": "Lycée de Tampouy",
                                        "participants": 120, "quantite_kg": 3400})
    campagnes = application.test_client().get("/api/public/campagnes").get_json()["campagnes"]
    assert campagnes[0]["organisateur"] == "Lycée de Tampouy" and campagnes[0]["participants"] == 120
