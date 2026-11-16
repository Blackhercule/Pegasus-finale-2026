"""Les signalements : contrôles, pièges du jury, regroupement en dépotoirs, décisions de l'agent."""

import json
import os

import pytest

ICI = os.path.dirname(os.path.abspath(__file__))
BON = {"latitude": 12.3714, "longitude": -1.5197, "taille": "grand", "source": "essai"}


def envoyer(client, **champs):
    return client.post("/api/signalements", json={**BON, **champs})


# ------------------------------------------------------------------ contrôles un par un
@pytest.mark.parametrize("motif,champs", [
    ("coordonnees_invalides", {"latitude": 0, "longitude": 0}),
    ("coordonnees_invalides", {"latitude": 91.5}),
    ("coordonnees_inversees", {"latitude": -1.5197, "longitude": 12.3714}),
    ("hors_commune", {"latitude": 48.8566, "longitude": 2.3522}),
    ("date_future", {"date_observation": "2030-01-01T10:00:00Z"}),
    ("date_trop_ancienne", {"date_observation": "2001-09-11T08:46:00Z"}),
    ("volume_invraisemblable", {"volume_m3": -5}),
    ("volume_invraisemblable", {"volume_m3": 1e9}),
    ("precision_insuffisante", {"precision_m": 5000}),
    ("format_invalide", {"latitude": "douze"}),
    ("format_invalide", {"latitude": float("inf")}),
    ("format_invalide", {"taille": None, "volume_m3": None}),
])
def test_chaque_controle_donne_son_motif(client, motif, champs):
    resultat = envoyer(client, **champs).get_json()
    assert motif in resultat["motifs"], resultat
    assert resultat["statut"] in ("rejete", "a_verifier")


def test_un_signalement_valide_est_accepte(client):
    reponse = envoyer(client)
    assert reponse.status_code == 201
    assert reponse.get_json()["statut"] == "recevable"
    assert reponse.get_json()["motifs"] == []


def test_un_point_dans_un_barrage_est_refuse(client, application):
    """Un dépotoir au milieu de l'eau n'existe pas : le point est pris dans un vrai plan d'eau."""
    geo = application.extensions["geographie"]
    dedans = [e for e in geo.eaux if geo.commune.contains(e.representative_point())]
    centre = max(dedans, key=lambda e: e.area).representative_point()
    resultat = envoyer(client, latitude=centre.y, longitude=centre.x).get_json()
    assert resultat["motifs"] == ["dans_l_eau"]


# ------------------------------------------------------------------ le lot piégé du jury
def test_le_lot_piege_du_jury(client):
    """Le fichier de pièges passe en un seul envoi : aucun ne doit entrer dans le plan,
    chacun reçoit le motif attendu, et le serveur ne répond jamais par une erreur."""
    with open(os.path.join(ICI, "pieges.json"), encoding="utf-8") as f:
        pieges = json.load(f)
    reponse = client.post("/api/signalements/lot",
                          json=[p["signalement"] for p in pieges])
    assert reponse.status_code == 200
    resultats = reponse.get_json()["resultats"]
    assert len(resultats) == len(pieges)
    erreurs = []
    for piege, resultat in zip(pieges, resultats):
        attendu = piege["motif_attendu"]
        if attendu == "aucun":
            if resultat["statut"] not in ("recevable", "verifie"):
                erreurs.append((piege["signalement"], attendu, resultat))
        elif attendu not in resultat["motifs"]:
            erreurs.append((piege["signalement"], attendu, resultat))
    assert not erreurs, erreurs[:5]


def test_un_lot_illisible_ne_fait_pas_tomber_le_serveur(client):
    for contenu in (b"", b"pas du json {{{", b"[1, 2, 3]", b'{"type":"FeatureCollection"}',
                    b'[{"latitude":[[[1]]]}]', b"\xff\xfe\x00"):
        reponse = client.post("/api/signalements/lot", data=contenu,
                              content_type="application/json")
        assert reponse.status_code in (200, 400), contenu


def test_un_commentaire_hostile_est_garde_comme_texte(client):
    resultat = envoyer(client, commentaire="<script>alert(1)</script>", id_client="hostile").get_json()
    assert resultat["statut"] == "recevable"
    lignes = client.get("/api/signalements").get_json()
    assert lignes[0]["commentaire"] == "<script>alert(1)</script>"   # gardé tel quel, échappé à l'affichage


# ------------------------------------------------------------------ dépotoirs
def test_deux_sources_confirment_le_meme_depotoir(client):
    envoyer(client, source="telephone-a", id_client="a")
    deuxieme = envoyer(client, latitude=12.37145, longitude=-1.51975,
                       source="telephone-b", id_client="b").get_json()
    assert deuxieme["statut"] == "verifie"
    depotoirs = client.get("/api/depotoirs").get_json()["features"]
    assert len(depotoirs) == 1
    assert depotoirs[0]["properties"]["nb_sources"] == 2


def test_deux_dépotoirs_eloignes_restent_distincts(client):
    envoyer(client, id_client="un")
    envoyer(client, latitude=12.40, longitude=-1.48, id_client="deux")
    assert len(client.get("/api/depotoirs").get_json()["features"]) == 2


def test_le_meme_envoi_repete_ne_compte_quune_fois(client):
    premier = envoyer(client, id_client="unique")
    second = envoyer(client, id_client="unique")
    assert premier.status_code == 201 and second.status_code == 200
    assert second.get_json()["nouveau"] is False
    assert len(client.get("/api/signalements").get_json()) == 1


def test_un_signalement_rejete_n_entre_pas_dans_la_carte(client):
    envoyer(client, latitude=48.8566, longitude=2.3522, id_client="paris")
    assert client.get("/api/depotoirs").get_json()["features"] == []


# ------------------------------------------------------------------ décisions de l'agent
def test_un_lot_de_l_agent_n_est_pas_pris_pour_une_rafale(client):
    """Le jury charge d'un coup des dizaines de signalements : c'est normal pour un lot, et
    cela ne doit pas les faire tous passer en « à vérifier »."""
    lot = [{**BON, "id_client": f"lot-{i}", "latitude": 12.37 + i / 1000} for i in range(40)]
    resultats = client.post("/api/signalements/lot", json=lot).get_json()["resultats"]
    assert all("rafale_meme_source" not in r["motifs"] for r in resultats)


def test_un_telephone_qui_envoie_en_rafale_est_signale(client):
    """La même chose depuis l'adresse publique, elle, est signalée à un agent."""
    statuts = [envoyer(client, id_client=f"rafale-{i}", latitude=12.37 + i / 1000).get_json()["statut"]
               for i in range(25)]
    assert "a_verifier" in statuts


def test_les_decisions_exigent_un_agent_connecte(client):
    envoyer(client, id_client="x")
    assert client.post("/api/signalements/1/verifier").status_code == 401


def test_un_agent_connecte_verifie_et_ecarte(agent):
    envoyer(agent, precision_m=5000, id_client="douteux")     # arrive « à vérifier »
    assert agent.post("/api/signalements/1/verifier").status_code == 200
    assert agent.get("/api/signalements?statut=verifie").get_json()[0]["id"] == 1
    assert agent.post("/api/signalements/1/rejeter").status_code == 200
    assert agent.get("/api/depotoirs").get_json()["features"] == []


def test_un_formulaire_sans_jeton_est_refuse(agent):
    envoyer(agent, id_client="y")
    del agent.environ_base["HTTP_X_JETON"]
    assert agent.post("/api/signalements/1/verifier").status_code == 403


def test_mot_de_passe_faux(client):
    assert client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": "faux"}).status_code == 401
