"""
Administration de secours (/admin/), réservée au compte patron.
Elle sert à corriger une donnée sans passer par la console du serveur.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Arrivage, Client, JournalActivite, LigneArrivage, LigneVente, ParametresCave, Perte, Produit, Reglement,
    Utilisateur, Vente,
)

admin.site.site_header = "Gestion de cave — administration"


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Rôle dans la cave", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_active")


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0


class LigneArrivageInline(admin.TabularInline):
    model = LigneArrivage
    extra = 0


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "type_vente", "vendeur", "client", "montant_total", "montant_paye", "annulee")
    list_filter = ("type_vente", "annulee", "mode_paiement")
    inlines = [LigneVenteInline]


@admin.register(Arrivage)
class ArrivageAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "fournisseur", "enregistre_par", "annulee")
    inlines = [LigneArrivageInline]


@admin.register(JournalActivite)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("date", "utilisateur", "action", "description")
    list_filter = ("action",)


admin.site.register([ParametresCave, Produit, Client, Perte, Reglement])
