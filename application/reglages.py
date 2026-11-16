"""Réglages de l'application : chemins, paramètres de la commune, compte de l'agent."""

import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Reglages:
    def __init__(self, commune=None, dossier_donnees=None, base=None):
        self.commune = commune or os.environ.get("COMMUNE", "ouagadougou")
        self.dossier_donnees = dossier_donnees or os.environ.get(
            "DOSSIER_DONNEES", os.path.join(RACINE, "donnees", self.commune))
        self.dossier_interface = os.path.join(RACINE, "interface")
        self.base = base or os.environ.get("BASE_DONNEES", os.path.join(self.dossier_donnees, "signalements.sqlite"))
        self.dossier_photos = os.environ.get("DOSSIER_PHOTOS", os.path.join(os.path.dirname(self.base), "photos"))
        # Compte de l'agent qui vérifie les signalements. Le mot de passe n'est jamais dans le dépôt.
        self.agent_nom = os.environ.get("AGENT_NOM", "agent")
        self.agent_mot_de_passe = os.environ.get("AGENT_MOT_DE_PASSE", "")
        self.secret_session = os.environ.get("SECRET_SESSION", "")
        self.parametres = self.lire_parametres()

    def fichier(self, nom: str) -> str:
        return os.path.join(self.dossier_donnees, nom)

    def lire_parametres(self) -> dict:
        """Les paramètres du scénario de départ (donnees/<commune>/parametres.json)."""
        with open(self.fichier("parametres.json"), encoding="utf-8") as f:
            return json.load(f)
