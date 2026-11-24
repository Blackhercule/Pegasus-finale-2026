"""Les connexions, déconnexions et échecs de connexion vont dans le journal du patron."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .services import journaliser


@receiver(user_logged_in)
def connexion(sender, request, user, **kwargs):
    journaliser(user, "connexion", f"{user} ({user.get_role_display().lower()}) s'est connecté")


@receiver(user_logged_out)
def deconnexion(sender, request, user, **kwargs):
    if user is not None:
        journaliser(user, "deconnexion", f"{user} s'est déconnecté")


@receiver(user_login_failed)
def echec_connexion(sender, credentials, request=None, **kwargs):
    identifiant = str(credentials.get("username", ""))[:50]
    journaliser(None, "echec_connexion", f"Mot de passe refusé pour l'identifiant « {identifiant} »")
