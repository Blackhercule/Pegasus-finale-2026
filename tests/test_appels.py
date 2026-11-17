"""T23 : appeler la mairie depuis la page Signaler — les règles du standard téléphonique.

L'horloge des appels est remplacée par une horloge qu'on avance à la main : les délais
(90 s de sonnerie, 30 min d'appel, 60 s avant l'oubli) se vérifient sans attendre.
"""

import pytest

from application.appels import (APPELS_PAR_ADRESSE_MAX, DESCRIPTION_MAX, DUREE_MAX_S, OUBLI_S,
                                SONNERIE_MAX_S, Appels)
from conftest import MOT_DE_PASSE

OFFRE = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
REPONSE = OFFRE.replace("o=- 1 2", "o=- 3 4")
POSITION = {"latitude": 12.3714, "longitude": -1.5197, "precision_m": 12}


@pytest.fixture
def horloge(application):
    """Une horloge à avancer à la main, branchée sur le standard de l'application."""
    temps = [1000.0]
    application.extensions["appels"] = Appels(horloge=lambda: temps[0])
    return temps


def appeler(client, adresse="10.0.0.5", **champs):
    corps = {"offre": OFFRE, **POSITION, **champs}
    return client.post("/api/appels", json=corps, headers={"X-Forwarded-For": adresse})


def avec_jeton(jeton):
    return {"X-Appel-Jeton": jeton}


def connecte(application, nom, mot_de_passe):
    client = application.test_client()
    reponse = client.post("/api/connexion", json={"nom": nom, "mot_de_passe": mot_de_passe})
    assert reponse.status_code == 200
    client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    return client


# ------------------------------------------------------------------ côté habitant
def test_un_habitant_appelle_sans_compte(client, horloge):
    reponse = appeler(client)
    assert reponse.status_code == 201
    corps = reponse.get_json()
    assert set(corps) == {"id", "jeton"} and len(corps["jeton"]) >= 40
    etat = client.get(f"/api/appels/{corps['id']}", headers=avec_jeton(corps["jeton"]))
    assert etat.get_json() == {"id": corps["id"], "etat": "sonne"}


def test_la_position_est_facultative(client, horloge, agent):
    reponse = client.post("/api/appels", json={"offre": OFFRE})
    assert reponse.status_code == 201
    assert agent.get("/api/appels").get_json()[0]["position"] is None


@pytest.mark.parametrize("jeton", [None, "", "faux", "x" * 43])
def test_sans_le_bon_jeton_l_appel_est_inconnu(client, horloge, jeton):
    corps = appeler(client).get_json()
    entetes = {} if jeton is None else avec_jeton(jeton)
    for methode, adresse, envoi in [("get", f"/api/appels/{corps['id']}", None),
                                    ("post", f"/api/appels/{corps['id']}/position", POSITION),
                                    ("post", f"/api/appels/{corps['id']}/raccrocher", None)]:
        reponse = getattr(client, methode)(adresse, json=envoi, headers=entetes)
        assert reponse.status_code == 404, adresse
    # Le jeton d'un appel n'ouvre pas un autre appel.
    autre = appeler(client).get_json()
    assert client.get(f"/api/appels/{autre['id']}", headers=avec_jeton(corps["jeton"])).status_code == 404


@pytest.mark.parametrize("offre", [None, "", 42, ["v=0"], "bonjour", "v=0" + "a" * DESCRIPTION_MAX])
def test_une_offre_invalide_est_refusee(client, horloge, offre):
    assert client.post("/api/appels", json={"offre": offre}).status_code == 400


@pytest.mark.parametrize("position", [
    {"latitude": 91, "longitude": -1.5}, {"latitude": "douze", "longitude": -1.5},
    {"latitude": 0, "longitude": 0}, {"latitude": 12.37, "longitude": None},
    {"latitude": 1e999, "longitude": -1.5}, {"latitude": True, "longitude": -1.5},
])
def test_une_position_invalide_est_refusee(client, horloge, position):
    assert client.post("/api/appels", json={"offre": OFFRE, **position}).status_code == 400
    corps = appeler(client).get_json()
    reponse = client.post(f"/api/appels/{corps['id']}/position", json=position,
                          headers=avec_jeton(corps["jeton"]))
    assert reponse.status_code == 400


def test_un_envoi_qui_n_est_pas_du_json_est_refuse(client, horloge):
    assert client.post("/api/appels", data="n'importe quoi").status_code == 400


# ------------------------------------------------------------------ côté agent
def test_seule_la_mairie_voit_et_decroche(application, client, horloge):
    corps = appeler(client).get_json()
    assert client.get("/api/appels").status_code == 401
    assert client.get(f"/api/appels/{corps['id']}/offre").status_code == 401
    assert client.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE}).status_code == 401
    assert client.post(f"/api/appels/{corps['id']}/terminer").status_code == 401
    brigade = connecte(application, "brigade", "essai-brigade")
    assert brigade.get("/api/appels").status_code == 403
    assert brigade.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE}).status_code == 403
    assert brigade.post(f"/api/appels/{corps['id']}/terminer").status_code == 403


def test_decrocher_sans_le_jeton_de_session_est_refuse(application, client, horloge):
    corps = appeler(client).get_json()
    mairie = application.test_client()
    mairie.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    assert mairie.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE}).status_code == 403


def test_la_mairie_decroche_et_le_telephone_recoit_la_reponse(client, agent, horloge):
    corps = appeler(client).get_json()
    liste = agent.get("/api/appels").get_json()
    assert [a["etat"] for a in liste] == ["sonne"]
    assert "jeton" not in str(liste) and corps["jeton"] not in str(liste)
    assert liste[0]["position"]["latitude"] == POSITION["latitude"]
    assert agent.get(f"/api/appels/{corps['id']}/offre").get_json()["offre"] == OFFRE
    decroche = agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE})
    assert decroche.status_code == 200 and decroche.get_json()["agent"] == "agent"
    etat = client.get(f"/api/appels/{corps['id']}", headers=avec_jeton(corps["jeton"])).get_json()
    assert etat == {"id": corps["id"], "etat": "en_cours", "reponse": REPONSE}
    # Le journal de l'appel garde qui a décroché.
    assert agent.get("/api/appels").get_json()[0]["agent"] == "agent"


def test_on_ne_decroche_pas_deux_fois(application, client, agent, horloge):
    corps = appeler(client).get_json()
    assert agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE}).status_code == 200
    autre_agent = connecte(application, "agent", MOT_DE_PASSE)
    second = autre_agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE})
    assert second.status_code == 409 and "déjà décroché" in second.get_json()["erreur"]
    assert agent.get(f"/api/appels/{corps['id']}/offre").status_code == 409


@pytest.mark.parametrize("reponse", [None, "", "bonjour", "v=0" + "a" * DESCRIPTION_MAX])
def test_une_reponse_invalide_est_refusee(client, agent, horloge, reponse):
    corps = appeler(client).get_json()
    assert agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": reponse}).status_code == 400
    assert agent.get("/api/appels").get_json()[0]["etat"] == "sonne"


def test_un_appel_inconnu(agent, horloge):
    assert agent.get("/api/appels/999/offre").status_code == 404
    assert agent.post("/api/appels/999/decrocher", json={"reponse": REPONSE}).status_code == 404
    assert agent.post("/api/appels/999/terminer").status_code == 404


# ------------------------------------------------------------------ la position en direct
def test_la_position_suit_l_habitant_puis_s_efface(client, agent, horloge):
    corps = appeler(client).get_json()
    agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE})
    horloge[0] += 3
    nouvelle = {"latitude": 12.3720, "longitude": -1.5190, "precision_m": 8}
    assert client.post(f"/api/appels/{corps['id']}/position", json=nouvelle,
                       headers=avec_jeton(corps["jeton"])).status_code == 200
    horloge[0] += 4
    appel = agent.get("/api/appels").get_json()[0]
    assert (appel["position"]["latitude"], appel["position"]["age_s"]) == (12.3720, 4.0)
    assert appel["trajet"] == [[-1.5197, 12.3714], [-1.519, 12.372]]
    # L'habitant raccroche : la position disparaît tout de suite.
    assert client.post(f"/api/appels/{corps['id']}/raccrocher",
                       headers=avec_jeton(corps["jeton"])).get_json()["etat"] == "termine"
    appel = agent.get("/api/appels").get_json()[0]
    assert appel["etat"] == "termine" and appel["position"] is None and appel["trajet"] == []
    assert client.post(f"/api/appels/{corps['id']}/position", json=nouvelle,
                       headers=avec_jeton(corps["jeton"])).status_code == 409
    # Une minute plus tard, l'appel lui-même est oublié.
    horloge[0] += OUBLI_S + 1
    assert agent.get("/api/appels").get_json() == []
    assert client.get(f"/api/appels/{corps['id']}", headers=avec_jeton(corps["jeton"])).status_code == 404


def test_l_agent_raccroche(client, agent, horloge):
    corps = appeler(client).get_json()
    agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE})
    assert agent.post(f"/api/appels/{corps['id']}/terminer").get_json()["etat"] == "termine"
    assert client.get(f"/api/appels/{corps['id']}",
                      headers=avec_jeton(corps["jeton"])).get_json()["etat"] == "termine"
    assert agent.get("/api/appels").get_json()[0]["position"] is None


def test_rien_n_est_ecrit_dans_la_base(application, client, agent, horloge):
    import sqlite3
    co = sqlite3.connect(application.extensions["reglages"].base)
    tables = [t for (t,) in co.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    avant = {t: co.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    corps = appeler(client).get_json()
    agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE})
    client.post(f"/api/appels/{corps['id']}/raccrocher", headers=avec_jeton(corps["jeton"]))
    apres = {t: co.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    assert apres == avant
    assert not any("appel" in t for t in tables)


# ------------------------------------------------------------------ les délais
def test_personne_ne_decroche_en_90_secondes(client, agent, horloge):
    corps = appeler(client).get_json()
    horloge[0] += SONNERIE_MAX_S - 1
    assert client.get(f"/api/appels/{corps['id']}", headers=avec_jeton(corps["jeton"])).get_json()["etat"] == "sonne"
    horloge[0] += 2
    assert client.get(f"/api/appels/{corps['id']}", headers=avec_jeton(corps["jeton"])).get_json()["etat"] == "sans_reponse"
    assert agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE}).status_code == 409
    assert agent.get("/api/appels").get_json()[0]["position"] is None


def test_un_appel_est_coupe_au_bout_de_30_minutes(client, agent, horloge):
    corps = appeler(client).get_json()
    agent.post(f"/api/appels/{corps['id']}/decrocher", json={"reponse": REPONSE})
    horloge[0] += DUREE_MAX_S - 1
    assert agent.get("/api/appels").get_json()[0]["etat"] == "en_cours"
    horloge[0] += 2
    assert agent.get("/api/appels").get_json()[0]["etat"] == "termine"


# ------------------------------------------------------------------ pas d'inondation
def test_au_plus_trois_appels_a_la_fois(client, horloge):
    for numero in range(3):
        assert appeler(client, adresse=f"10.0.0.{numero}").status_code == 201
    occupe = appeler(client, adresse="10.0.0.9")
    assert occupe.status_code == 503 and "occupés" in occupe.get_json()["erreur"]
    # Dès qu'un appel se libère, on peut rappeler.
    horloge[0] += SONNERIE_MAX_S + 1
    assert appeler(client, adresse="10.0.0.9").status_code == 201


def test_au_plus_cinq_appels_par_telephone_en_dix_minutes(client, horloge):
    for _ in range(APPELS_PAR_ADRESSE_MAX):
        corps = appeler(client, adresse="10.0.0.7").get_json()
        client.post(f"/api/appels/{corps['id']}/raccrocher", headers=avec_jeton(corps["jeton"]))
    assert appeler(client, adresse="10.0.0.7").status_code == 429
    assert appeler(client, adresse="10.0.0.8").status_code == 201     # un autre téléphone passe
    horloge[0] += 10 * 60 + 1
    assert appeler(client, adresse="10.0.0.7").status_code == 201


def test_une_fausse_adresse_ecrite_par_le_client_ne_contourne_pas_la_limite(client, horloge):
    """On compte la DERNIÈRE adresse de X-Forwarded-For, celle qu'ajoute le relais (Caddy) ; la
    première, qu'un client écrirait lui-même, ne compte pas. (Caddy 2.11.2 remplace d'ailleurs
    tout l'en-tête : voir comptes-rendus/T23.md.)"""
    for numero in range(APPELS_PAR_ADRESSE_MAX):
        corps = appeler(client, adresse=f"6.6.6.{numero}, 10.0.0.7").get_json()
        client.post(f"/api/appels/{corps['id']}/raccrocher", headers=avec_jeton(corps["jeton"]))
    assert appeler(client, adresse="9.9.9.9, 10.0.0.7").status_code == 429
