"""
Crée le compte du patron au premier démarrage, s'il n'existe pas encore.

L'identifiant et le mot de passe sont lus dans les variables d'environnement
PATRON_IDENTIFIANT (par défaut « patron ») et PATRON_MOT_DE_PASSE. Sur Render,
le mot de passe est demandé lors de la création du service (voir render.yaml).

Lancée à chaque déploiement, la commande ne touche jamais à un compte patron
existant : un mot de passe changé depuis l'application n'est pas écrasé.
Seule exception, pour un patron qui a oublié son mot de passe sur un hébergement
sans console : REINITIALISER_MOT_DE_PASSE_PATRON=oui remplace son mot de passe
par PATRON_MOT_DE_PASSE au déploiement suivant (remettre ensuite « non »).
"""
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from cave.models import ParametresCave, Utilisateur
from cave.services import journaliser


class Command(BaseCommand):
    help = "Crée le compte du patron s'il n'existe pas (variables PATRON_IDENTIFIANT et PATRON_MOT_DE_PASSE)."

    def handle(self, *args, **options):
        parametres = ParametresCave.charger()
        nom_cave = os.environ.get("NOM_CAVE", "").strip()
        if nom_cave and parametres.nom == "Ma cave":
            parametres.nom = nom_cave[:100]
            parametres.save()

        identifiant = os.environ.get("PATRON_IDENTIFIANT", "").strip() or "patron"
        mot_de_passe = os.environ.get("PATRON_MOT_DE_PASSE", "")

        patron = Utilisateur.objects.filter(role=Utilisateur.Role.PATRON).order_by("id").first()
        if patron is not None:
            if os.environ.get("REINITIALISER_MOT_DE_PASSE_PATRON", "").strip().lower() == "oui" and mot_de_passe:
                self._verifier(mot_de_passe)
                patron.set_password(mot_de_passe)
                patron.is_active = True
                patron.save()
                journaliser(None, "compte", f"Mot de passe du patron « {patron.username} » réinitialisé au déploiement")
                self.stdout.write(self.style.WARNING(
                    f"Mot de passe du patron « {patron.username} » réinitialisé. "
                    "Remettez REINITIALISER_MOT_DE_PASSE_PATRON à « non »."
                ))
            else:
                self.stdout.write("Le compte patron existe déjà : rien à faire.")
            return

        if not mot_de_passe:
            self.stdout.write(self.style.WARNING(
                "PATRON_MOT_DE_PASSE n'est pas défini : le compte patron n'est pas créé. "
                "Définissez cette variable puis relancez, ou utilisez « python manage.py createsuperuser »."
            ))
            return
        self._verifier(mot_de_passe)

        patron = Utilisateur.objects.create_superuser(
            username=identifiant, password=mot_de_passe, first_name="Patron", role=Utilisateur.Role.PATRON
        )
        journaliser(patron, "compte", f"Compte patron créé (identifiant « {identifiant} »)")
        self.stdout.write(self.style.SUCCESS(f"Compte patron créé : identifiant « {identifiant} »."))

    def _verifier(self, mot_de_passe):
        try:
            validate_password(mot_de_passe)
        except ValidationError as erreur:
            raise CommandError("Mot de passe du patron refusé : " + " ".join(erreur.messages))
