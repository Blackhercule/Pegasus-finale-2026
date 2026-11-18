"""C12 : sur chaque dossier, on sait QUI a vérifié un signalement et QUI a fait chaque étape.

Le nom affiché est « Nom (identifiant) » pour un compte individuel ; ce qui est gardé en base
reste l'identifiant, que les tests d'agents vérifient déjà.
"""

from test_agents import AWA, connecter, creer

AWA_MAIRIE = {**AWA, "identifiant": "awa.mairie", "poste": "mairie"}


def signaler(client, id_client="x"):
    return client.post("/api/signalements", json={
        "latitude": 12.3714, "longitude": -1.5197, "taille": "grand",
        "source": "tel", "id_client": id_client}).get_json()


def test_la_page_verifier_dit_qui_a_verifie_et_quand(agent, application):
    creer(agent, **AWA_MAIRIE)
    awa = application.test_client()
    connecter(awa, "awa.mairie", AWA["mot_de_passe"])
    r = signaler(awa)
    assert awa.post("/api/signalements/%d/verifier" % r["id"]).status_code == 200
    ligne = [s for s in awa.get("/api/signalements").get_json() if s["id"] == r["id"]][0]
    assert ligne["decide_par"] == "awa.mairie"
    assert ligne["decide_par_nom"] == "Awa Ouédraogo (awa.mairie)"
    assert ligne["decide_le"]


def test_un_compte_de_demarrage_signe_avec_son_identifiant(agent):
    r = signaler(agent)
    agent.post("/api/signalements/%d/rejeter" % r["id"])
    ligne = [s for s in agent.get("/api/signalements").get_json() if s["id"] == r["id"]][0]
    assert ligne["decide_par_nom"] == "agent"


def test_le_dossier_raconte_la_verification_et_les_etapes_avec_les_noms(agent, application):
    creer(agent, **AWA_MAIRIE)
    awa = application.test_client()
    connecter(awa, "awa.mairie", AWA["mot_de_passe"])
    r = signaler(awa)
    awa.post("/api/signalements/%d/verifier" % r["id"])
    dossier = awa.post("/api/dossiers/1/avancer", json={"detail": "vu sur place"}).get_json()
    lignes = [(e["etape"], e["auteur_nom"]) for e in dossier["journal"]]
    assert ("Signalement n° %d vérifié" % r["id"], "Awa Ouédraogo (awa.mairie)") in lignes
    assert lignes[-1][1] == "Awa Ouédraogo (awa.mairie)"


def test_un_signalement_non_decide_ne_porte_aucun_nom(agent):
    r = signaler(agent)
    ligne = [s for s in agent.get("/api/signalements").get_json() if s["id"] == r["id"]][0]
    assert ligne.get("decide_par") is None and "decide_par_nom" not in ligne


def test_le_public_ne_voit_pas_les_noms(client, agent, application):
    r = signaler(agent)
    agent.post("/api/signalements/%d/verifier" % r["id"])
    public = application.test_client()
    assert public.get("/api/signalements").status_code == 401
    assert public.get("/api/dossiers/1").status_code == 401
