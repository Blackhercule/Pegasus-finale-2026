"""La file priorisée : classer par urgence réelle plutôt que par ordre d'arrivée.

Ce qui est éprouvé ici, c'est que le classement fait ce qu'on raconte au jury. Un score dont
personne ne peut prédire le comportement ne vaut pas mieux qu'une boîte noire.
"""

from conftest import MOT_DE_PASSE

# Un point à quelques dizaines de mètres de l'Université Joseph Ki-Zerbo, et un autre loin de
# tout lieu sensible. Les deux sont dans la commune et sur la terre ferme.
PRES_ECOLE = (12.3650, -1.5100)
LOIN = (12.3500, -1.4800)


def signaler(client, position, taille="grand", source="tel-a", id_client="a", **champs):
    lat, lon = position
    return client.post("/api/signalements", json={
        "latitude": lat, "longitude": lon, "taille": taille,
        "source": source, "id_client": id_client, **champs})


def connecter(client):
    r = client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    client.environ_base["HTTP_X_JETON"] = r.get_json()["jeton"]


def test_un_petit_tas_pres_d_une_ecole_passe_devant_un_grand_tas_isole(agent):
    """C'est tout l'intérêt du classement : la gravité ne décide pas seule."""
    signaler(agent, LOIN, taille="grand", id_client="loin")
    signaler(agent, PRES_ECOLE, taille="petit", id_client="ecole")
    liste = agent.get("/api/dossiers").get_json()
    assert len(liste) == 2
    premier = liste[0]
    assert premier["latitude"] == PRES_ECOLE[0], (
        "le tas près de l'école devrait passer en premier : %s"
        % [(d["latitude"], d["priorite"]) for d in liste])
    assert any("scolaire" in r for r in premier["priorite"]["raisons"])


def test_chaque_dossier_dit_pourquoi_il_est_la(agent):
    """Un agent doit pouvoir contester le classement, donc le comprendre. Et un membre de
    l'équipe doit pouvoir l'expliquer au jury sans ouvrir le code."""
    signaler(agent, PRES_ECOLE, source="tel-a", id_client="a")
    signaler(agent, PRES_ECOLE, source="tel-b", id_client="b")
    dossier = agent.get("/api/dossiers").get_json()[0]
    assert dossier["priorite"]["note"] > 0
    raisons = " · ".join(dossier["priorite"]["raisons"])
    assert "témoins" in raisons
    assert "scolaire" in raisons or "soins" in raisons or "marché" in raisons


def test_deux_temoins_pesent_plus_qu_un_seul(agent):
    """La certitude compte autant que la gravité : un signalement confirmé passe devant."""
    signaler(agent, PRES_ECOLE, source="tel-a", id_client="seul")
    seul = agent.get("/api/dossiers").get_json()[0]["priorite"]["note"]
    signaler(agent, PRES_ECOLE, source="tel-b", id_client="confirme")
    confirme = agent.get("/api/dossiers").get_json()[0]["priorite"]["note"]
    assert confirme > seul


def test_l_ordre_d_arrivee_reste_accessible(agent):
    """On ne retire rien : qui veut l'ordre historique le demande."""
    signaler(agent, LOIN, id_client="un")
    signaler(agent, PRES_ECOLE, id_client="deux")
    par_arrivee = [d["id"] for d in agent.get("/api/dossiers?ordre=arrivee").get_json()]
    assert par_arrivee == sorted(par_arrivee)
    # et dans ce mode, aucune note n'est calculée : on ne paie pas ce qu'on ne demande pas
    assert "priorite" not in agent.get("/api/dossiers?ordre=arrivee").get_json()[0]


def test_les_fuites_et_les_nuisances_sont_classees_aussi(agent):
    lat, lon = PRES_ECOLE
    agent.post("/api/signalements", json={
        "nature": "fuite_eau", "latitude": lat, "longitude": lon, "ampleur": "inondation",
        "source": "a", "id_client": "f1"})
    agent.post("/api/signalements", json={
        "nature": "caniveau_bouche", "latitude": lat, "longitude": lon, "gravite": "grave",
        "source": "b", "id_client": "n1"})
    assert agent.get("/api/fuites").get_json()[0]["priorite"]["note"] > 0
    assert agent.get("/api/nuisances").get_json()[0]["priorite"]["note"] > 0


def test_une_position_manquante_ne_fait_pas_tomber_le_classement(application):
    """Le jury enverra des dossiers mal formés : le classement doit tenir."""
    priorite = application.extensions["priorite"]
    assert priorite.noter(None, None)["note"] == 0
    assert priorite.noter(12.37, -1.52, gravite="inconnue")["note"] >= 0
    liste = priorite.classer([{"latitude": None, "longitude": None},
                              {"latitude": 12.37, "longitude": -1.52}])
    assert len(liste) == 2
    assert liste[0]["priorite"]["note"] >= liste[1]["priorite"]["note"]


def test_le_classement_tient_la_charge(application):
    """Le classement sert justement quand la file devient ingérable : il doit rester instantané
    sur plusieurs milliers de dossiers, sinon il ne résout rien."""
    import time

    priorite = application.extensions["priorite"]
    dossiers = [{"latitude": 12.33 + (i % 100) * 0.0008,
                 "longitude": -1.56 + (i % 97) * 0.0009,
                 "nb_sources": 1 + i % 3, "premier_vu": "2026-11-10T08:00:00+00:00"}
                for i in range(5000)]
    debut = time.monotonic()
    classes = priorite.classer(dossiers)
    duree = time.monotonic() - debut
    assert len(classes) == 5000
    assert duree < 5.0, "classement de 5 000 dossiers en %.1f s" % duree
    notes = [d["priorite"]["note"] for d in classes]
    assert notes == sorted(notes, reverse=True)
