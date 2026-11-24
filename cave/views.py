"""
Les pages de l'application.

Chaque vue lit la requête, appelle une fonction de services.py (où sont les
règles de gestion) et affiche le résultat. Les droits :
- @login_required : il faut être connecté (patron ou gérant) ;
- @patron_requis  : réservé au patron.
Un gérant ne voit que ses propres ventes, reçus et comptes ; le patron voit tout.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from . import services
from .droits import patron_requis
from .forms import (
    AnnulationForm, ClientForm, GerantCreationForm, GerantModificationForm, ParametresForm, PerteForm,
    ProduitForm, ReglementForm,
)
from .formats import fcfa
from .models import (
    Arrivage, Client, JournalActivite, ModePaiement, ParametresCave, Perte, Produit, Reglement, TypeVente,
    Utilisateur, Vente,
)
from .services import ErreurOperation, journaliser


def _verifier_proprietaire(request, utilisateur_operation):
    """Un gérant ne peut ouvrir que ses propres opérations ; le patron peut tout ouvrir."""
    if not request.user.est_patron and utilisateur_operation != request.user:
        raise PermissionDenied


def lire_quantites(donnees, ids_produits):
    """Lit les champs « q_<id du produit> » du formulaire : {id: caisses}."""
    quantites = {}
    for pid in ids_produits:
        texte = (donnees.get(f"q_{pid}") or "").strip()
        if not texte:
            continue
        try:
            valeur = int(texte)
        except ValueError:
            raise ErreurOperation("Les quantités doivent être des nombres entiers de caisses.")
        if valeur < 0:
            raise ErreurOperation("Une quantité ne peut pas être négative.")
        if valeur:
            quantites[pid] = valeur
    return quantites


def _identifiant(texte):
    """Un identifiant de la base lu dans l'adresse ou le formulaire, ou None s'il est invalide."""
    texte = (texte or "").strip()
    return int(texte) if texte.isdigit() else None


def _lire_entier(texte, message):
    try:
        return int((texte or "0").strip() or 0)
    except ValueError:
        raise ErreurOperation(message)


# --------------------------------------------------------------------------
# Accueil : tableau de bord du patron, espace du gérant
# --------------------------------------------------------------------------

@login_required
def accueil(request):
    jour = services.aujourd_hui()
    if request.user.est_patron:
        debut, fin = services.bornes_mois(jour.year, jour.month)
        gerants = Utilisateur.objects.filter(is_active=True).order_by("role", "first_name", "username")
        par_personne = []
        for personne in gerants:
            resume = services.resume_jour(jour, vendeur=personne)
            if resume["nombre_ventes"] or resume["remboursements"] or personne.role == Utilisateur.Role.GERANT:
                par_personne.append({"utilisateur": personne, **resume})
        contexte = {
            "jour": jour,
            "resume": services.resume_jour(jour),
            "resume_hier": services.resume_jour(jour - timedelta(days=1)),
            "ca_mois": services._somme(
                Vente.objects.filter(annulee=False, date__gte=debut, date__lt=fin), "montant_total"
            ),
            "nom_mois": services.nom_mois(jour.year, jour.month),
            "par_personne": par_personne,
            "alertes": [p for p in services.produits_avec_stock() if p.en_alerte],
            "total_dettes": services.total_dettes_clients(),
            "journal": JournalActivite.objects.select_related("utilisateur")[:15],
        }
        return render(request, "cave/tableau_de_bord.html", contexte)

    contexte = {
        "jour": jour,
        "resume": services.resume_jour(jour, vendeur=request.user),
        "alertes": [p for p in services.produits_avec_stock() if p.en_alerte],
        "dernieres_ventes": Vente.objects.filter(vendeur=request.user, date__date=jour)
        .select_related("client")[:8],
    }
    return render(request, "cave/espace_gerant.html", contexte)


# --------------------------------------------------------------------------
# Ventes
# --------------------------------------------------------------------------

@login_required
def nouvelle_vente(request):
    produits = services.produits_avec_stock()
    soldes = services.soldes_clients()
    clients = list(Client.objects.all())
    for client in clients:
        client.solde = soldes.get(client.id, 0)

    valeurs = {"type_vente": TypeVente.DETAIL, "paiement": "comptant", "mode_paiement": ModePaiement.ESPECES}
    if request.method == "POST":
        valeurs = request.POST
        try:
            quantites = lire_quantites(request.POST, [p.id for p in produits])
            comptant = request.POST.get("paiement", "comptant") != "credit"
            montant_verse = _lire_entier(request.POST.get("montant_verse"), "Le montant versé doit être un nombre.")
            with transaction.atomic():
                # Le client : choisi dans la liste, ou créé à la volée
                client = None
                nom_nouveau = request.POST.get("nouveau_client_nom", "").strip()
                if nom_nouveau:
                    client = Client.objects.create(
                        nom=nom_nouveau[:100], telephone=request.POST.get("nouveau_client_tel", "").strip()[:30]
                    )
                    journaliser(request.user, "client", f"Nouveau client : {client}", lien=f"/clients/{client.pk}/")
                elif _identifiant(request.POST.get("client")):
                    client = Client.objects.filter(pk=_identifiant(request.POST["client"])).first()
                vente = services.enregistrer_vente(
                    vendeur=request.user,
                    type_vente=request.POST.get("type_vente", ""),
                    quantites=quantites,
                    client=client,
                    comptant=comptant,
                    montant_verse=montant_verse,
                    mode_paiement=request.POST.get("mode_paiement", ModePaiement.ESPECES),
                    note=request.POST.get("note", "").strip()[:200],
                )
        except ErreurOperation as erreur:
            messages.error(request, str(erreur))
        else:
            messages.success(request, f"Vente {vente.numero} enregistrée : {fcfa(vente.montant_total)}.")
            return redirect("recu_vente", pk=vente.pk)

    for produit in produits:
        produit.quantite_saisie = valeurs.get(f"q_{produit.id}", "") if request.method == "POST" else ""
    return render(request, "cave/vente_form.html", {
        "produits": produits,
        "clients": clients,
        "valeurs": valeurs,
        "modes": ModePaiement.choices,
    })


@login_required
def recu_vente(request, pk):
    vente = get_object_or_404(
        Vente.objects.select_related("client", "vendeur", "annulee_par").prefetch_related("lignes__produit"), pk=pk
    )
    _verifier_proprietaire(request, vente.vendeur)
    solde = services.solde_client(vente.client) if vente.client else None
    return render(request, "cave/recu_vente.html", {"vente": vente, "solde_client": solde})


@login_required
def liste_ventes(request):
    jour = services.lire_date(request.GET.get("date"))
    debut, fin = services.bornes_jour(jour)
    ventes = Vente.objects.filter(date__gte=debut, date__lt=fin).select_related("client", "vendeur")
    vendeur_choisi = None
    if request.user.est_patron:
        if _identifiant(request.GET.get("vendeur")):
            vendeur_choisi = Utilisateur.objects.filter(pk=_identifiant(request.GET["vendeur"])).first()
            if vendeur_choisi:
                ventes = ventes.filter(vendeur=vendeur_choisi)
    else:
        ventes = ventes.filter(vendeur=request.user)
    if request.GET.get("type") in TypeVente.values:
        ventes = ventes.filter(type_vente=request.GET["type"])
    return render(request, "cave/ventes_liste.html", {
        "jour": jour,
        "veille": jour - timedelta(days=1),
        "lendemain": jour + timedelta(days=1),
        "ventes": ventes.prefetch_related("lignes__produit"),
        "vendeurs": Utilisateur.objects.order_by("first_name", "username") if request.user.est_patron else [],
        "vendeur_choisi": vendeur_choisi,
        "type_choisi": request.GET.get("type", ""),
    })


# --------------------------------------------------------------------------
# Arrivages et pertes
# --------------------------------------------------------------------------

@login_required
def arrivages(request):
    produits = services.produits_avec_stock()
    if request.method == "POST":
        try:
            arrivage = services.enregistrer_arrivage(
                utilisateur=request.user,
                quantites=lire_quantites(request.POST, [p.id for p in produits]),
                fournisseur=request.POST.get("fournisseur", "").strip()[:100],
                note=request.POST.get("note", "").strip()[:200],
            )
        except ErreurOperation as erreur:
            messages.error(request, str(erreur))
            for produit in produits:
                produit.quantite_saisie = request.POST.get(f"q_{produit.id}", "")
        else:
            nb = sum(ligne.quantite_caisses for ligne in arrivage.lignes.all())
            messages.success(request, f"Arrivage {arrivage.numero} enregistré : {nb} caisse(s) ajoutée(s) au stock.")
            return redirect("arrivages")
    return render(request, "cave/arrivages.html", {
        "produits": produits,
        "valeurs": request.POST if request.method == "POST" else {},
        "historique": Arrivage.objects.select_related("enregistre_par").prefetch_related("lignes__produit")[:30],
    })


@login_required
def pertes(request):
    form = PerteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            perte = services.enregistrer_perte(
                utilisateur=request.user,
                produit=form.cleaned_data["produit"],
                type_perte=form.cleaned_data["type_perte"],
                bouteilles=form.total_bouteilles(),
                note=form.cleaned_data["note"],
            )
        except ErreurOperation as erreur:
            messages.error(request, str(erreur))
        else:
            messages.success(request, f"Perte {perte.numero} enregistrée et retirée du stock.")
            return redirect("pertes")
    return render(request, "cave/pertes.html", {
        "form": form,
        "historique": Perte.objects.select_related("produit", "enregistre_par")[:30],
    })


# --------------------------------------------------------------------------
# Clients et crédits
# --------------------------------------------------------------------------

@login_required
def clients(request):
    soldes = services.soldes_clients()
    liste = Client.objects.all()
    recherche = request.GET.get("q", "").strip()
    if recherche:
        liste = liste.filter(Q(nom__icontains=recherche) | Q(telephone__icontains=recherche))
    liste = list(liste)
    for client in liste:
        client.solde = soldes.get(client.id, 0)
    if request.GET.get("filtre") != "tous":
        # Par défaut on montre d'abord ceux qui doivent de l'argent
        liste.sort(key=lambda c: (-max(c.solde, 0), c.nom.lower()))
    return render(request, "cave/clients.html", {
        "clients": liste,
        "recherche": recherche,
        "total_dettes": sum(s for s in soldes.values() if s > 0),
        "nb_debiteurs": sum(1 for s in soldes.values() if s > 0),
    })


@login_required
def client_form(request, pk=None):
    client = get_object_or_404(Client, pk=pk) if pk else None
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        journaliser(request.user, "client", f"Fiche client {'modifiée' if pk else 'créée'} : {client}",
                    lien=f"/clients/{client.pk}/")
        messages.success(request, "Fiche client enregistrée.")
        return redirect("client_detail", pk=client.pk)
    return render(request, "cave/client_form.html", {"form": form, "client": client})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "cave/client_detail.html", {
        "client": client,
        "solde": services.solde_client(client),
        "ventes": client.ventes.select_related("vendeur").prefetch_related("lignes__produit")[:100],
        "reglements": client.reglements.select_related("recu_par")[:100],
    })


@login_required
def nouveau_reglement(request, pk):
    client = get_object_or_404(Client, pk=pk)
    solde = services.solde_client(client)
    form = ReglementForm(request.POST or None, initial={"montant": solde if solde > 0 else None})
    if request.method == "POST" and form.is_valid():
        try:
            reglement = services.enregistrer_reglement(
                utilisateur=request.user,
                client=client,
                montant=form.cleaned_data["montant"],
                mode_paiement=form.cleaned_data["mode_paiement"],
                note=form.cleaned_data["note"],
            )
        except ErreurOperation as erreur:
            messages.error(request, str(erreur))
        else:
            messages.success(request, f"Remboursement de {fcfa(reglement.montant)} enregistré.")
            return redirect("recu_reglement", pk=reglement.pk)
    return render(request, "cave/reglement_form.html", {"client": client, "solde": solde, "form": form})


@login_required
def recu_reglement(request, pk):
    reglement = get_object_or_404(Reglement.objects.select_related("client", "recu_par"), pk=pk)
    _verifier_proprietaire(request, reglement.recu_par)
    return render(request, "cave/recu_reglement.html", {
        "reglement": reglement,
        "solde_client": services.solde_client(reglement.client),
    })


# --------------------------------------------------------------------------
# Stock, comptes du jour, statistiques, journal
# --------------------------------------------------------------------------

@login_required
def stock(request):
    produits = services.produits_avec_stock()
    contexte = {
        "produits": produits,
        "nb_alertes": sum(1 for p in produits if p.en_alerte),
    }
    if request.user.est_patron:
        contexte["valeur_stock"] = sum(p.valeur_stock for p in produits)
        contexte["besoins"] = services.besoins_reapprovisionnement()
    return render(request, "cave/stock.html", contexte)


@login_required
def point_du_jour(request):
    jour = services.lire_date(request.GET.get("date"))
    vendeur = None
    if request.user.est_patron:
        if _identifiant(request.GET.get("vendeur")):
            vendeur = Utilisateur.objects.filter(pk=_identifiant(request.GET["vendeur"])).first()
    else:
        vendeur = request.user  # un gérant fait les comptes de sa propre caisse
    rapport = services.rapport_journee(jour, vendeur=vendeur)
    return render(request, "cave/point_du_jour.html", {
        "r": rapport,
        "jour": jour,
        "veille": jour - timedelta(days=1),
        "lendemain": jour + timedelta(days=1),
        "est_aujourdhui": jour == services.aujourd_hui(),
        "vendeur": vendeur,
        "vendeurs": Utilisateur.objects.order_by("first_name", "username") if request.user.est_patron else [],
        "imprime_le": timezone.localtime(),
    })


def echelle(maximum):
    """Haut d'un graphique arrondi à un nombre rond (1, 2, 2,5 ou 5 × 10ⁿ) pour des graduations lisibles."""
    if maximum <= 0:
        return 1
    puissance = 10 ** (len(str(int(maximum))) - 1)
    for facteur in (1, 2, 2.5, 5, 10):
        if maximum <= facteur * puissance:
            return int(facteur * puissance)


@patron_requis
def statistiques(request):
    jour = services.aujourd_hui()
    annee, mois = jour.year, jour.month
    texte = request.GET.get("mois", "")
    try:
        a, m = (int(x) for x in texte.split("-"))
        if 2000 <= a <= 2100 and 1 <= m <= 12:
            annee, mois = a, m
    except ValueError:
        pass
    stats = services.statistiques_mois(annee, mois)
    evolution = services.evolution_mensuelle(annee, mois)
    precedent = services.mois_precedent(annee, mois)
    suivant = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    echelle_evolution = echelle(max(e["total"] for e in evolution))
    echelle_jour = echelle(max(j["total"] for j in stats["par_jour"]))
    return render(request, "cave/statistiques.html", {
        "s": stats,
        "evolution": evolution,
        "echelle_evolution": echelle_evolution,
        "demi_evolution": echelle_evolution // 2,
        "echelle_jour": echelle_jour,
        "demi_jour": echelle_jour // 2,
        "max_caisses_produit": max([p["caisses"] for p in stats["par_produit"]] + [1]),
        "produits_par_caisses": sorted(stats["par_produit"], key=lambda p: -p["caisses"]),
        "mois_precedent": f"{precedent[0]}-{precedent[1]:02d}",
        "mois_suivant": f"{suivant[0]}-{suivant[1]:02d}" if suivant <= (jour.year, jour.month) else None,
    })


@patron_requis
def journal(request):
    jour = services.lire_date(request.GET.get("date"))
    debut, fin = services.bornes_jour(jour)
    entrees = JournalActivite.objects.filter(date__gte=debut, date__lt=fin).select_related("utilisateur")
    if _identifiant(request.GET.get("qui")):
        entrees = entrees.filter(utilisateur_id=_identifiant(request.GET["qui"]))
    return render(request, "cave/journal.html", {
        "jour": jour,
        "veille": jour - timedelta(days=1),
        "lendemain": jour + timedelta(days=1),
        "entrees": entrees,
        "personnes": Utilisateur.objects.order_by("first_name", "username"),
        "qui": request.GET.get("qui", ""),
    })


@patron_requis
def annuler(request, type_operation, pk):
    modele = services.OPERATIONS_ANNULABLES.get(type_operation)
    if modele is None:
        raise Http404
    operation = get_object_or_404(modele, pk=pk)
    suite = request.POST.get("suite") or request.GET.get("suite") or "/"
    if not url_has_allowed_host_and_scheme(suite, allowed_hosts={request.get_host()}):
        suite = "/"
    form = AnnulationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.annuler_operation(operation, request.user, form.cleaned_data["motif"])
        except ErreurOperation as erreur:
            messages.error(request, str(erreur))
        else:
            messages.success(request, f"L'opération {operation.numero} est annulée.")
        return redirect(suite)
    return render(request, "cave/annuler.html", {
        "operation": operation, "type_operation": type_operation, "form": form, "suite": suite,
    })


# --------------------------------------------------------------------------
# Réglages du patron : produits, gérants, informations de la cave
# --------------------------------------------------------------------------

@patron_requis
def produits(request):
    return render(request, "cave/produits.html", {"produits": services.produits_avec_stock(actifs_seulement=False)})


@patron_requis
def produit_form(request, pk=None):
    produit = get_object_or_404(Produit, pk=pk) if pk else None
    anciens = {}
    if produit:
        anciens = {champ: getattr(produit, champ) for champ in ProduitForm.Meta.fields}
    form = ProduitForm(request.POST or None, instance=produit)
    if request.method == "POST" and form.is_valid():
        produit = form.save()
        if pk:
            changements = [
                f"{form.fields[c].label} : {anciens[c]} → {getattr(produit, c)}" for c in form.changed_data
            ]
            journaliser(request.user, "produit", f"Produit {produit} modifié — " + "; ".join(changements))
        else:
            journaliser(request.user, "produit", f"Nouveau produit : {produit}")
        messages.success(request, f"Produit « {produit} » enregistré.")
        return redirect("produits")
    return render(request, "cave/produit_form.html", {"form": form, "produit": produit})


@patron_requis
def gerants(request):
    return render(request, "cave/gerants.html", {
        "comptes": Utilisateur.objects.order_by("role", "-is_active", "first_name", "username"),
    })


@patron_requis
def gerant_nouveau(request):
    form = GerantCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        gerant = form.save()
        journaliser(request.user, "compte", f"Compte gérant créé : {gerant} (identifiant « {gerant.username} »)")
        messages.success(request, f"Compte de {gerant} créé. Donnez-lui son identifiant et son mot de passe.")
        return redirect("gerants")
    return render(request, "cave/gerant_form.html", {"form": form, "titre": "Nouveau gérant"})


def _gerant(pk):
    return get_object_or_404(Utilisateur, pk=pk, role=Utilisateur.Role.GERANT)


@patron_requis
def gerant_modifier(request, pk):
    gerant = _gerant(pk)
    form = GerantModificationForm(request.POST or None, instance=gerant)
    if request.method == "POST" and form.is_valid():
        form.save()
        etat = "actif" if gerant.is_active else "désactivé"
        journaliser(request.user, "compte", f"Compte de {gerant} modifié (compte {etat})")
        messages.success(request, f"Compte de {gerant} enregistré.")
        return redirect("gerants")
    return render(request, "cave/gerant_form.html", {"form": form, "titre": f"Modifier le compte de {gerant}",
                                                     "gerant": gerant})


@patron_requis
def gerant_mot_de_passe(request, pk):
    gerant = _gerant(pk)
    form = SetPasswordForm(gerant, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        journaliser(request.user, "compte", f"Nouveau mot de passe donné à {gerant}")
        messages.success(request, f"Le mot de passe de {gerant} a été changé.")
        return redirect("gerants")
    return render(request, "cave/gerant_form.html", {"form": form, "titre": f"Nouveau mot de passe pour {gerant}"})


@patron_requis
def parametres(request):
    form = ParametresForm(request.POST or None, instance=ParametresCave.charger())
    if request.method == "POST" and form.is_valid():
        form.save()
        journaliser(request.user, "parametres", "Informations de la cave modifiées")
        messages.success(request, "Informations de la cave enregistrées.")
        return redirect("parametres")
    return render(request, "cave/parametres.html", {"form": form})


@login_required
def mon_mot_de_passe(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = form.save()
        update_session_auth_hash(request, utilisateur)  # reste connecté après le changement
        journaliser(utilisateur, "compte", f"{utilisateur} a changé son mot de passe")
        messages.success(request, "Votre mot de passe a été changé.")
        return redirect("accueil")
    return render(request, "cave/mon_mot_de_passe.html", {"form": form})
