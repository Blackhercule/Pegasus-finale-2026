"""Caniveaux bouchés, abattage clandestin, toilettes en plein air, eaux usées animales.

Ce qui est vérifié ici avant tout : chaque nature arrive au bon service, et aucune n'entre
dans les tournées des camions ni dans les fuites d'eau.
"""

from conftest import MOT_DE_PASSE

BASE = {"latitude": 12.3714, "longitude": -1.5197, "gravite": "moyen",
        "quartier": "Tanghin", "source": "tel-a", "id_client": "n1"}

# Quatre points sur la terre ferme et loin les uns des autres : un point choisi au hasard
# risque de tomber dans un barrage, et le contrôle « dans l'eau » l'écarterait à juste titre.
AILLEURS = [(12.3714, -1.5197), (12.3600, -1.5000), (12.3500, -1.4800), (12.3800, -1.4700)]

MOTS_DE_PASSE = {"agent": MOT_DE_PASSE, "brigade": "essai-brigade",
                 "collecte": "essai-collecte", "onea": "essai-onea"}


def signaler(client, nature="caniveau_bouche", **champs):
    return client.post("/api/signalements", json={**BASE, "nature": nature, **champs})


def connecter(client, nom):
    reponse = client.post("/api/connexion", json={"nom": nom, "mot_de_passe": MOTS_DE_PASSE[nom]})
    if reponse.status_code == 200:
        client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    return reponse


def test_chaque_nature_va_au_bon_service(client, agent):
    """C'est la décision centrale du module : la nature désigne le service."""
    attendus = {
        "caniveau_bouche": "collecte",
        "abattoir_clandestin": "brigade",
        "toilettes_plein_air": "onea",
        "eaux_usees_animales": "brigade",
    }
    for (nature, service), (lat, lon) in zip(attendus.items(), AILLEURS):
        # Chaque nature à un endroit différent, pour qu'elles ne se regroupent pas entre elles.
        signaler(client, nature, latitude=lat, longitude=lon, id_client="n-" + nature)
    for n in client.get("/api/nuisances").get_json():
        assert n["service"] == attendus[n["nature"]]


def test_deux_natures_au_meme_endroit_font_deux_dossiers(client, agent):
    """Un caniveau bouché et un abattage clandestin au même carrefour sont deux problèmes,
    deux services, donc deux dossiers — même si les points se touchent."""
    signaler(client, "caniveau_bouche", id_client="a")
    signaler(client, "abattoir_clandestin", id_client="b", source="tel-b")
    liste = client.get("/api/nuisances").get_json()
    assert len(liste) == 2
    assert {n["nature"] for n in liste} == {"caniveau_bouche", "abattoir_clandestin"}


def test_deux_appareils_confirment_la_meme_nuisance(client, agent):
    signaler(client, id_client="a", source="tel-a", gravite="leger")
    deuxieme = signaler(client, id_client="b", source="tel-b", latitude=12.37145, gravite="grave")
    assert deuxieme.get_json()["nuisance_id"] == 1
    assert deuxieme.get_json()["statut"] == "verifie"
    n = client.get("/api/nuisances").get_json()[0]
    # La gravité retenue est la plus forte signalée : c'est l'ordre de passage du service.
    assert n["gravite"] == "grave"
    assert n["nb_sources"] == 2


def test_gravite_absente_ou_inventee_est_rejetee(client, agent):
    for mauvaise in (None, "catastrophique", 7, ""):
        corps = signaler(client, gravite=mauvaise, id_client="x%s" % mauvaise).get_json()
        assert corps["statut"] == "rejete"
        assert "gravite_invalide" in corps["motifs"]
    assert client.get("/api/nuisances").get_json() == []


def test_une_nature_inconnue_est_rejetee_sans_tomber(client, agent):
    """Le jury peut inventer une nature : elle est écartée avec son motif, pas une erreur 500."""
    reponse = signaler(client, "depotoir_de_mars", id_client="z")
    assert reponse.status_code == 201
    assert reponse.get_json()["motifs"] == ["nature_inconnue"]
    assert client.get("/api/nuisances").get_json() == []
    assert client.get("/api/depotoirs").get_json()["features"] == []


def test_les_memes_controles_de_position_s_appliquent(client, agent):
    pieges = [
        ({"latitude": 0, "longitude": 0}, "coordonnees_invalides"),
        ({"latitude": "abc"}, "format_invalide"),
        ({"latitude": 48.85, "longitude": 2.35}, "hors_commune"),
        ({"date_observation": "2030-01-01T00:00:00Z"}, "date_future"),
    ]
    for rang, (champs, motif) in enumerate(pieges):
        corps = signaler(client, id_client="p%d" % rang, **champs).get_json()
        assert motif in corps["motifs"], (champs, corps)
    assert client.get("/api/nuisances").get_json() == []


def test_la_chaine_passe_par_la_mairie_puis_le_service(client):
    signaler(client, "caniveau_bouche")
    connecter(client, "agent")
    n = client.post("/api/nuisances/1/avancer", json={"detail": "vu sur place"}).get_json()
    assert n["etape"] == "confirme"
    assert n["poste_attendu"] == "collecte"

    # La mairie ne cure pas le caniveau à la place de l'équipe de collecte.
    assert client.post("/api/nuisances/1/avancer", json={}).status_code == 400
    # Et la brigade non plus : ce n'est pas elle que cette nature désigne.
    client.post("/api/deconnexion")
    connecter(client, "brigade")
    assert client.post("/api/nuisances/1/avancer", json={}).status_code == 400

    client.post("/api/deconnexion")
    connecter(client, "collecte")
    n = client.post("/api/nuisances/1/avancer", json={"detail": "caniveau curé"}).get_json()
    assert n["etape"] == "traite" and n["etat"] == "traitee"
    assert [e["poste"] for e in n["journal"]] == ["mairie", "collecte"]
    assert client.get("/api/nuisances/carte").get_json()["features"] == []


def test_chaque_service_ne_voit_que_ce_qui_le_regarde(client):
    """Le filtre « qui m'attendent » doit tenir compte de la nature, pas seulement de l'étape."""
    for nature, (lat, lon) in zip(("caniveau_bouche", "abattoir_clandestin",
                                   "toilettes_plein_air"), AILLEURS):
        signaler(client, nature, latitude=lat, longitude=lon, id_client="n-" + nature)
    connecter(client, "agent")
    # À la mairie, les trois attendent d'être orientés.
    assert len(client.get("/api/nuisances?pour_moi=1").get_json()) == 3
    for identifiant in (1, 2, 3):
        client.post("/api/nuisances/%d/avancer" % identifiant, json={})
    # Une fois orientés, chacun n'apparaît que chez son service.
    assert client.get("/api/nuisances?pour_moi=1").get_json() == []
    attendus = {"collecte": ["caniveau_bouche"], "brigade": ["abattoir_clandestin"],
                "onea": ["toilettes_plein_air"]}
    for poste, natures in attendus.items():
        client.post("/api/deconnexion")
        connecter(client, poste)
        vus = [n["nature"] for n in client.get("/api/nuisances?pour_moi=1").get_json()]
        assert vus == natures, (poste, vus)


def test_sans_connexion_on_ne_fait_rien_avancer(client):
    signaler(client)
    assert client.post("/api/nuisances/1/avancer", json={}).status_code == 401
    assert client.post("/api/nuisances/1/classer", json={"motif": "x"}).status_code == 401


def test_seule_la_mairie_classe_sans_suite(client):
    signaler(client)
    connecter(client, "collecte")
    assert client.post("/api/nuisances/1/classer", json={"motif": "bof"}).status_code == 403
    client.post("/api/deconnexion")
    connecter(client, "agent")
    n = client.post("/api/nuisances/1/classer", json={"motif": "rien sur place"}).get_json()
    assert n["etape"] == "classe"


def test_le_bordereau_liste_les_dossiers_orientes(client):
    signaler(client, "caniveau_bouche", id_client="a")
    signaler(client, "toilettes_plein_air", latitude=12.36, longitude=-1.50, id_client="b")
    connecter(client, "agent")
    client.post("/api/nuisances/1/avancer", json={})
    reponse = client.get("/api/export/nuisances")
    assert reponse.status_code == 200
    assert reponse.headers["X-Nuisances"] == "1"      # seul le dossier orienté y est
    texte = reponse.get_data(as_text=True)
    assert texte.startswith("﻿")
    assert "NUIS-00001" in texte and "collecte" in texte


def test_une_nuisance_n_est_ni_un_depotoir_ni_une_fuite(client, agent):
    signaler(client, "caniveau_bouche")
    assert client.get("/api/depotoirs").get_json()["features"] == []
    assert client.get("/api/fuites").get_json() == []
    assert client.get("/api/comptes").get_json().get("depotoirs", 0) == 0


def test_l_identite_du_declarant_reste_cachee_du_public(client):
    signaler(client, declarant_nom="Awa", declarant_telephone="70000000")
    # Sans connexion, la fiche n'est pas servie du tout (T13) : l'identité encore moins.
    assert client.get("/api/nuisances/1").status_code == 401
    connecter(client, "agent")
    prive = client.get("/api/nuisances/1").get_json()["signalements"][0]
    assert prive["declarant_nom"] == "Awa"


def test_le_meme_envoi_deux_fois_ne_compte_qu_une_fois(client):
    assert signaler(client).status_code == 201
    repete = signaler(client)
    assert repete.status_code == 200 and repete.get_json()["nouveau"] is False
    assert len(client.get("/api/nuisances").get_json()) == 1
