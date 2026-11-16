"""T12 : la page d'accueil publique et ses trois chiffres."""

from conftest import MOT_DE_PASSE

BON = {"latitude": 12.3714, "longitude": -1.5197, "taille": "grand", "source": "essai"}


def test_l_accueil_s_ouvre_sans_connexion(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert b'href="/signaler/"' in reponse.data and b'href="/decision/"' in reponse.data
    for fichier in ("accueil.css", "accueil.js"):
        assert client.get("/accueil/" + fichier).status_code == 200


def test_api_publics_ne_renvoie_que_trois_nombres(client):
    client.post("/api/signalements", json={**BON, "id_client": "a"})
    assert client.post("/api/signalements", json={**BON, "id_client": "b", "latitude": 12.3732}).get_json()["statut"] == "recevable"
    client.post("/api/signalements", json={**BON, "id_client": "c", "latitude": 48.85, "longitude": 2.35})
    chiffres = client.get("/api/publics").get_json()
    assert set(chiffres) == {"signalements", "depotoirs", "dossiers_traites"}
    assert all(type(v) is int for v in chiffres.values())     # que des nombres : ni position, ni détail
    assert chiffres == {"signalements": 3, "depotoirs": 2, "dossiers_traites": 0}


def test_un_dossier_classe_compte_comme_traite(client):
    client.post("/api/signalements", json={**BON, "id_client": "a"})
    reponse = client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    assert client.post("/api/dossiers/1/classer", json={"detail": "Doublon"}).status_code == 200
    assert client.get("/api/publics").get_json()["dossiers_traites"] == 1
