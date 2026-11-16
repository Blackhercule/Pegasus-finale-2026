"""Fixtures communes : une application de test, avec une base vide à chaque fois."""

import os
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from application import creer_application          # noqa: E402
from application.reglages import Reglages          # noqa: E402

MOT_DE_PASSE = "essai-agent"


@pytest.fixture
def application(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MOT_DE_PASSE", MOT_DE_PASSE)
    monkeypatch.setenv("BRIGADE_MOT_DE_PASSE", "essai-brigade")
    monkeypatch.setenv("COLLECTE_MOT_DE_PASSE", "essai-collecte")
    monkeypatch.setenv("SECRET_SESSION", "secret-de-test")
    reglages = Reglages(base=str(tmp_path / "essai.sqlite"))
    app = creer_application(reglages)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(application):
    return application.test_client()


@pytest.fixture
def agent(client):
    """Un client déjà connecté comme agent, avec son jeton de session."""
    reponse = client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    assert reponse.status_code == 200, reponse.get_json()
    client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    return client
