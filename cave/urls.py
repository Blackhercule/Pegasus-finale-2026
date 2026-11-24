from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import ConnexionForm

urlpatterns = [
    path("connexion/", auth_views.LoginView.as_view(
        template_name="registration/connexion.html", authentication_form=ConnexionForm,
        redirect_authenticated_user=True), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("mon-mot-de-passe/", views.mon_mot_de_passe, name="mon_mot_de_passe"),

    path("", views.accueil, name="accueil"),

    path("ventes/", views.liste_ventes, name="ventes"),
    path("ventes/nouvelle/", views.nouvelle_vente, name="nouvelle_vente"),
    path("ventes/<int:pk>/", views.recu_vente, name="recu_vente"),

    path("arrivages/", views.arrivages, name="arrivages"),
    path("pertes/", views.pertes, name="pertes"),

    path("clients/", views.clients, name="clients"),
    path("clients/nouveau/", views.client_form, name="client_nouveau"),
    path("clients/<int:pk>/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/modifier/", views.client_form, name="client_modifier"),
    path("clients/<int:pk>/remboursement/", views.nouveau_reglement, name="nouveau_reglement"),
    path("remboursements/<int:pk>/", views.recu_reglement, name="recu_reglement"),

    path("stock/", views.stock, name="stock"),
    path("point-du-jour/", views.point_du_jour, name="point_du_jour"),
    path("statistiques/", views.statistiques, name="statistiques"),
    path("journal/", views.journal, name="journal"),
    path("annuler/<str:type_operation>/<int:pk>/", views.annuler, name="annuler"),

    path("produits/", views.produits, name="produits"),
    path("produits/nouveau/", views.produit_form, name="produit_nouveau"),
    path("produits/<int:pk>/", views.produit_form, name="produit_modifier"),
    path("gerants/", views.gerants, name="gerants"),
    path("gerants/nouveau/", views.gerant_nouveau, name="gerant_nouveau"),
    path("gerants/<int:pk>/", views.gerant_modifier, name="gerant_modifier"),
    path("gerants/<int:pk>/mot-de-passe/", views.gerant_mot_de_passe, name="gerant_mot_de_passe"),
    path("parametres/", views.parametres, name="parametres"),
]
