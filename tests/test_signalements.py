"""Les signalements : contrôles, pièges du jury, regroupement en dépotoirs, décisions de l'agent."""

import json
import os

import pytest

from conftest import MOT_DE_PASSE

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


def test_un_commentaire_hostile_est_garde_comme_texte(client, agent):
    resultat = envoyer(client, commentaire="<script>alert(1)</script>", id_client="hostile").get_json()
    assert resultat["statut"] == "recevable"
    lignes = client.get("/api/signalements").get_json()
    assert lignes[0]["commentaire"] == "<script>alert(1)</script>"   # gardé tel quel, échappé à l'affichage


# ------------------------------------------------------------------ dépotoirs
def test_deux_sources_confirment_le_meme_depotoir(client, agent):
    envoyer(client, source="telephone-a", id_client="a")
    deuxieme = envoyer(client, latitude=12.37145, longitude=-1.51975,
                       source="telephone-b", id_client="b").get_json()
    assert deuxieme["statut"] == "verifie"
    depotoirs = client.get("/api/depotoirs").get_json()["features"]
    assert len(depotoirs) == 1
    assert depotoirs[0]["properties"]["nb_sources"] == 2


def test_deux_dépotoirs_eloignes_restent_distincts(client, agent):
    envoyer(client, id_client="un")
    envoyer(client, latitude=12.40, longitude=-1.48, id_client="deux")
    assert len(client.get("/api/depotoirs").get_json()["features"]) == 2


def test_le_meme_envoi_repete_ne_compte_quune_fois(client):
    premier = envoyer(client, id_client="unique")
    second = envoyer(client, id_client="unique")
    assert premier.status_code == 201 and second.status_code == 200
    assert second.get_json()["nouveau"] is False
    assert len(client.get("/api/signalements").get_json()) == 1


def test_un_signalement_rejete_n_entre_pas_dans_la_carte(client, agent):
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


# ------------------------------------------------------------------ plan de gestion
def test_le_plan_se_calcule_et_se_verifie(client, agent):
    plan = client.get("/api/plan").get_json()
    assert plan["points"], "aucun point de regroupement"
    assert plan["tournees"], "aucune tournée"
    assert {c["nom"] for c in plan["controles"]}, "aucun contrôle de cohérence"
    graves = [c for c in plan["controles"] if c["etat"] == "probleme"]
    assert not graves, graves


def test_des_camions_en_panne_degradent_le_plan_sans_le_casser(client, agent):
    reference = client.get("/api/plan").get_json()
    degrade = client.post("/api/plan", json={"camions_en_panne": 20}).get_json()
    assert len(degrade["tournees"]) < len(reference["tournees"])
    assert len(degrade["non_desservis"]) > len(reference["non_desservis"])
    assert not [c for c in degrade["controles"] if c["etat"] == "probleme"]


def test_la_saison_des_pluies_ralentit_les_tournees(client, agent):
    seche = client.get("/api/plan").get_json()
    pluies = client.post("/api/plan", json={"saison": "pluies"}).get_json()
    assert len(pluies["tournees"]) < len(seche["tournees"])


def test_un_nouveau_quartier_augmente_la_demande(client, agent):
    reference = client.get("/api/plan").get_json()
    agrandi = client.post("/api/plan", json={"nouveaux_quartiers": [
        {"longitude": -1.47, "latitude": 12.42, "rayon_m": 3000, "population": 150000}]}).get_json()
    assert agrandi["demande"]["m3_par_jour"] > reference["demande"]["m3_par_jour"]


@pytest.mark.parametrize("parametres", [
    {"nb_camions": 0}, {"nb_camions": -5}, {"capacite_camion_m3": 0},
    {"population": 0}, {"frequence_collecte_jours": 0}, {"saison": "neige"},
    {"heures_travail": 0}, {"distance_max_precollecte_m": 0}, {"camions_en_panne": 9999},
])
def test_des_parametres_absurdes_ne_cassent_pas_le_serveur(client, parametres, agent):
    reponse = client.post("/api/plan", json=parametres)
    assert reponse.status_code in (200, 400), reponse.get_data(as_text=True)[:200]


# ------------------------------------------------------------------ simulation et scénarios
def test_la_simulation_fait_vivre_les_quatre_acteurs(client, agent):
    resultat = client.post("/api/scenario", json={"jours": 10}).get_json()
    agents = resultat["simulation"]["agents"]
    assert agents["menages"] > 100 and agents["precollecteurs"] > 0
    assert agents["brigade"] == 1 and agents["mairie"] == 1
    journal = resultat["simulation"]["journal"]
    assert len(journal) == 10
    assert all(j["produit_m3"] > 0 for j in journal)


def test_la_simulation_est_reproductible(client, agent):
    premier = client.post("/api/scenario", json={"jours": 10}).get_json()["simulation"]["resume"]
    second = client.post("/api/scenario", json={"jours": 10}).get_json()["simulation"]["resume"]
    assert premier == second


def test_passer_tous_les_jours_ameliore_la_collecte(client, agent):
    reference = client.post("/api/scenario", json={"jours": 20}).get_json()
    ameliore = client.post("/api/scenario", json={
        "jours": 20, "parametres": {"frequence_collecte_jours": 1, "nb_camions": 45}}).get_json()
    assert (ameliore["simulation"]["resume"]["taux_collecte"]
            > reference["simulation"]["resume"]["taux_collecte"])


def test_comparer_deux_scenarios(client, agent):
    reponse = client.post("/api/comparer", json={"jours": 10, "scenarios": [
        {"nom": "Aujourd'hui", "parametres": {}},
        {"nom": "Plus de camions", "parametres": {"nb_camions": 45, "frequence_collecte_jours": 1}},
    ]})
    assert reponse.status_code == 200
    scenarios = reponse.get_json()["scenarios"]
    assert len(scenarios) == 2
    assert scenarios[1]["taux_collecte"] > scenarios[0]["taux_collecte"]


def test_une_comparaison_mal_formee_est_refusee(client, agent):
    for envoi in ({}, {"scenarios": []}, {"scenarios": [{}]}, {"scenarios": "deux"},
                  {"scenarios": [{}, {}, {}, {}, {}]}):
        assert client.post("/api/comparer", json=envoi).status_code == 400


# ------------------------------------------------------------------ bien commun
def test_l_export_osm_ne_contient_que_les_depotoirs_verifies(client, agent):
    envoyer(client, source="telephone-a", id_client="a")               # recevable seulement
    reponse = client.get("/api/export/osm")
    assert reponse.status_code == 200
    assert b"<node" not in reponse.data, "un dépotoir non vérifié est sorti dans l'export"

    envoyer(client, latitude=12.37145, source="telephone-b", id_client="b")   # deuxième source
    reponse = client.get("/api/export/osm")
    contenu = reponse.data.decode("utf-8")
    assert contenu.count("<node") == 1
    assert 'k="amenity" v="waste_dump_site"' in contenu
    assert "RELIRE" in contenu, "l'export doit rappeler qu'une relecture humaine est obligatoire"


def test_l_export_osm_echappe_les_valeurs(client):
    """Un commentaire hostile ne doit pas pouvoir casser le fichier XML."""
    from application.export_osm import en_osm
    contenu = en_osm([{"latitude": 12.37, "longitude": -1.51, "type": '"><script>',
                       "dernier_vu": "2026-11-16"}])
    assert "<script>" not in contenu.replace("&lt;script&gt;", "")
    import xml.etree.ElementTree as ET
    ET.fromstring(contenu)              # doit rester un XML valide


# ------------------------------------------------------------------ chaîne de traitement
def connecter(client, nom, mot_de_passe):
    reponse = client.post("/api/connexion", json={"nom": nom, "mot_de_passe": mot_de_passe})
    if reponse.status_code == 200:
        client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    return reponse


def test_chaque_poste_a_son_compte(client, monkeypatch):
    assert connecter(client, "agent", MOT_DE_PASSE).get_json()["poste"] == "mairie"
    assert connecter(client, "brigade", "essai-brigade").get_json()["poste"] == "brigade"
    assert connecter(client, "collecte", "essai-collecte").get_json()["poste"] == "collecte"
    assert connecter(client, "inconnu", "x").status_code == 401


def test_le_dossier_avance_de_poste_en_poste(client, agent):
    envoyer(client, source="a", id_client="a")
    envoyer(client, latitude=12.37145, source="b", id_client="b")
    assert client.get("/api/dossiers").get_json()[0]["etape"] == "signale"

    connecter(client, "agent", MOT_DE_PASSE)
    dossier = client.post("/api/dossiers/1/avancer", json={"detail": "Vu sur place"}).get_json()
    assert dossier["etape"] == "confirme"

    connecter(client, "brigade", "essai-brigade")
    dossier = client.post("/api/dossiers/1/avancer",
                          json={"detail": "Riverains sensibilisés, un récidiviste verbalisé"}).get_json()
    assert dossier["etape"] == "constat"

    connecter(client, "agent", MOT_DE_PASSE)
    assert client.post("/api/dossiers/1/avancer", json={}).get_json()["etape"] == "a_collecter"

    connecter(client, "collecte", "essai-collecte")
    dossier = client.post("/api/dossiers/1/avancer", json={"detail": "Deux camions"}).get_json()
    assert dossier["etape"] == "collecte"
    assert dossier["etat"] == "nettoye"
    assert [e["poste"] for e in dossier["journal"]] == ["mairie", "brigade", "mairie", "collecte"]
    # Un dépotoir ramassé sort du plan de gestion.
    assert client.get("/api/depotoirs").get_json()["features"] == []


def test_un_poste_ne_peut_pas_agir_a_la_place_d_un_autre(client):
    envoyer(client, source="a", id_client="a")
    connecter(client, "brigade", "essai-brigade")
    reponse = client.post("/api/dossiers/1/avancer", json={})
    assert reponse.status_code == 400
    assert "mairie" in reponse.get_json()["erreur"].lower()


def test_seule_la_mairie_classe_sans_suite(client):
    envoyer(client, source="a", id_client="a")
    connecter(client, "collecte", "essai-collecte")
    assert client.post("/api/dossiers/1/classer", json={"motif": "rien"}).status_code == 403
    connecter(client, "agent", MOT_DE_PASSE)
    dossier = client.post("/api/dossiers/1/classer", json={"motif": "Le tas n'existe plus"}).get_json()
    assert dossier["etape"] == "classe"


def test_l_identite_du_declarant_n_est_pas_publique(client):
    client.post("/api/signalements", json={**BON, "id_client": "temoin",
                                           "declarant_nom": "Témoin Fictif",
                                           "declarant_telephone": "+226 00 00 00 00"})
    # Sans connexion, le dossier n'est pas servi du tout (T13) : l'identité encore moins.
    assert client.get("/api/dossiers/1").status_code == 401
    connecter(client, "agent", MOT_DE_PASSE)
    prive = client.get("/api/dossiers/1").get_json()
    assert prive["signalements"][0]["declarant_nom"] == "Témoin Fictif"


def test_les_identites_s_effacent_a_la_cloture(client):
    client.post("/api/signalements", json={**BON, "id_client": "t",
                                           "declarant_telephone": "+226 00 00 00 00"})
    connecter(client, "agent", MOT_DE_PASSE)
    assert client.delete("/api/dossiers/1/identites").get_json()["signalements_nettoyes"] == 1
    assert client.get("/api/dossiers/1").get_json()["signalements"][0]["declarant_telephone"] is None


def test_superficie_et_mode_de_depot(client, agent):
    envoyer(client, depot="caniveau", longueur_m=6, largeur_m=3, source="a", id_client="a")
    envoyer(client, latitude=12.37145, depot="caniveau", longueur_m=5, largeur_m=4,
            source="b", id_client="b")
    proprietes = client.get("/api/depotoirs").get_json()["features"][0]["properties"]
    assert proprietes["depot"] == "caniveau"
    assert proprietes["surface_m2"] == 20.0          # médiane de 18 et 20


def test_les_pieces_privees_ne_sont_pas_publiques(client):
    """Un message vocal ou une CNIB ne se télécharge pas sans être connecté."""
    import io
    son = b"\x1aE\xdf\xa3" + b"0" * 200
    reponse = client.post("/api/signalements", data={
        "latitude": "12.3714", "longitude": "-1.5197", "taille": "grand", "source": "a",
        "id_client": "vocal", "message_vocal": (io.BytesIO(son), "voix.webm"),
    }, content_type="multipart/form-data")
    assert reponse.status_code == 201
    connecter(client, "agent", MOT_DE_PASSE)
    nom = client.get("/api/dossiers/1").get_json()["signalements"][0]["message_vocal"]
    assert nom.startswith("prive/")
    adresse = "/api/fichiers/" + nom
    assert client.get(adresse).status_code == 200
    client.post("/api/deconnexion")
    assert client.get(adresse).status_code == 401


def test_un_son_qui_n_en_est_pas_un_est_ignore(client):
    import io
    client.post("/api/signalements", data={
        "latitude": "12.3714", "longitude": "-1.5197", "taille": "grand", "source": "a",
        "id_client": "faux", "message_vocal": (io.BytesIO(b"<?php echo 1; ?>"), "voix.webm"),
    }, content_type="multipart/form-data")
    connecter(client, "agent", MOT_DE_PASSE)
    assert client.get("/api/dossiers/1").get_json()["signalements"][0]["message_vocal"] is None
