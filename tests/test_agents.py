"""Comptes individuels des agents, créés par la mairie.

Code d'authentification, la veille d'un jury de cybersécurité : chaque promesse faite dans
application/agents.py a ici son test. Un défaut d'authentification ne se rattrape pas en
démonstration.
"""

import time

from conftest import MOT_DE_PASSE

AWA = {"identifiant": "awa.ouedraogo", "nom": "Awa Ouédraogo", "poste": "brigade",
       "mot_de_passe": "constat-2026-laabal"}


def jeton(client, reponse):
    client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    return reponse


def connecter(client, nom, mot_de_passe):
    r = client.post("/api/connexion", json={"nom": nom, "mot_de_passe": mot_de_passe})
    if r.status_code == 200:
        jeton(client, r)
    return r


def creer(agent, **champs):
    return agent.post("/api/agents", json={**AWA, **champs})


# ------------------------------------------------------------------ créer, se connecter

def test_la_mairie_cree_un_agent_qui_peut_se_connecter(agent, application):
    assert creer(agent).status_code == 201
    autre = application.test_client()
    r = connecter(autre, "awa.ouedraogo", AWA["mot_de_passe"])
    assert r.status_code == 200
    assert r.get_json()["poste"] == "brigade"
    assert r.get_json()["nom"] == "Awa Ouédraogo"


def test_le_journal_signe_avec_le_vrai_nom(agent, application):
    """Tout l'intérêt : « qui a fait quoi » désigne enfin une personne, pas un service."""
    creer(agent)
    agent.post("/api/signalements", json={
        "latitude": 12.3714, "longitude": -1.5197, "taille": "grand",
        "source": "tel", "id_client": "x"})
    agent.post("/api/dossiers/1/avancer", json={})          # la mairie confirme
    brigade = application.test_client()
    connecter(brigade, "awa.ouedraogo", AWA["mot_de_passe"])
    dossier = brigade.post("/api/dossiers/1/avancer", json={"detail": "vu"}).get_json()
    assert dossier["journal"][-1]["auteur"] == "awa.ouedraogo"


def test_un_agent_n_a_que_les_droits_de_son_service(agent, application):
    creer(agent)
    brigade = application.test_client()
    connecter(brigade, "awa.ouedraogo", AWA["mot_de_passe"])
    # la brigade ne crée pas de comptes : c'est la mairie
    assert brigade.post("/api/agents", json={**AWA, "identifiant": "intrus"}).status_code == 403
    assert brigade.get("/api/agents").status_code == 403


# ------------------------------------------------------------------ désactiver

def test_un_compte_desactive_ne_peut_plus_se_connecter(agent, application):
    identifiant = creer(agent).get_json()["id"]
    agent.post("/api/agents/%d/desactiver" % identifiant, json={})
    autre = application.test_client()
    assert connecter(autre, "awa.ouedraogo", AWA["mot_de_passe"]).status_code == 401


def test_desactiver_coupe_aussi_une_session_deja_ouverte(agent, application):
    """Le test qui compte. Sans lui, « désactiver » n'empêcherait que la PROCHAINE connexion,
    et un agent parti garderait la main tant que son navigateur reste ouvert."""
    identifiant = creer(agent).get_json()["id"]
    awa = application.test_client()
    connecter(awa, "awa.ouedraogo", AWA["mot_de_passe"])
    assert awa.get("/api/dossiers").status_code == 200        # elle travaille…

    agent.post("/api/agents/%d/desactiver" % identifiant, json={})   # …la mairie la coupe…

    assert awa.get("/api/dossiers").status_code == 401         # …et dès la requête suivante
    assert awa.get("/api/session").status_code == 401


def test_reactiver_rend_l_acces(agent, application):
    identifiant = creer(agent).get_json()["id"]
    agent.post("/api/agents/%d/desactiver" % identifiant, json={})
    agent.post("/api/agents/%d/activer" % identifiant, json={})
    assert connecter(application.test_client(), "awa.ouedraogo",
                     AWA["mot_de_passe"]).status_code == 200


def test_desactiver_ne_supprime_rien(agent):
    """Le journal doit garder le nom de qui a fait quoi, même après le départ de l'agent."""
    identifiant = creer(agent).get_json()["id"]
    agent.post("/api/agents/%d/desactiver" % identifiant, json={})
    comptes = agent.get("/api/agents").get_json()["agents"]
    awa = [c for c in comptes if c["identifiant"] == "awa.ouedraogo"][0]
    assert awa["actif"] == 0 and awa["desactive_le"]


# ------------------------------------------------------------------ ce qui doit être refusé

def test_le_mot_de_passe_ne_sort_jamais(agent):
    creer(agent)
    texte = agent.get("/api/agents").get_data(as_text=True)
    assert "empreinte" not in texte
    assert AWA["mot_de_passe"] not in texte
    assert "pbkdf2" not in texte and "scrypt" not in texte


def test_mot_de_passe_trop_court_refuse(agent):
    r = creer(agent, mot_de_passe="court")
    assert r.status_code == 400 and "caractères" in r.get_json()["erreur"]


def test_mot_de_passe_egal_a_l_identifiant_refuse(agent):
    assert creer(agent, identifiant="awa.ouedraogo",
                 mot_de_passe="awa.ouedraogo").status_code == 400


def test_identifiant_en_double_refuse(agent):
    assert creer(agent).status_code == 201
    r = creer(agent, nom="Une autre Awa")
    assert r.status_code == 400 and "existe déjà" in r.get_json()["erreur"]


def test_identifiants_reserves_et_mal_formes_refuses(agent):
    for mauvais in ("agent", "brigade", "admin", "AW", "awa ouedraogo", "awa;drop table",
                    "<script>", "é" * 5, "", "a" * 60):
        assert creer(agent, identifiant=mauvais).status_code == 400, mauvais


def test_un_service_inconnu_est_refuse(agent):
    assert creer(agent, poste="dieu").status_code == 400


def test_sans_jeton_on_ne_cree_rien(agent):
    """La protection contre les requêtes forgées vaut aussi pour la création de comptes."""
    del agent.environ_base["HTTP_X_JETON"]
    assert creer(agent).status_code == 403


def test_les_essais_sont_freines_aussi_pour_les_comptes_individuels(agent, application):
    creer(agent)
    autre = application.test_client()
    for _ in range(11):
        autre.post("/api/connexion", json={"nom": "awa.ouedraogo", "mot_de_passe": "faux"})
    r = autre.post("/api/connexion", json={"nom": "awa.ouedraogo",
                                           "mot_de_passe": AWA["mot_de_passe"]})
    assert r.status_code == 429


def test_le_temps_de_reponse_ne_dit_pas_quels_comptes_existent(agent, application):
    """Un identifiant inconnu doit coûter le même calcul qu'un identifiant connu : sinon le
    chronomètre suffirait à dresser la liste des agents, c'est-à-dire de noms de personnes."""
    creer(agent)
    autre = application.test_client()

    def duree(nom):
        mesures = []
        for _ in range(3):
            debut = time.perf_counter()
            autre.post("/api/connexion", json={"nom": nom, "mot_de_passe": "mauvais-mot"})
            mesures.append(time.perf_counter() - debut)
        return sorted(mesures)[1]

    connu, inconnu = duree("awa.ouedraogo"), duree("personne.inconnue")
    # Les deux doivent faire au moins un calcul de hachage complet ; on tolère du bruit.
    assert inconnu > connu * 0.4, (connu, inconnu)


def test_les_comptes_de_demarrage_marchent_toujours(client):
    """Sans eux, personne ne pourrait créer le premier compte individuel."""
    assert connecter(client, "agent", MOT_DE_PASSE).status_code == 200
