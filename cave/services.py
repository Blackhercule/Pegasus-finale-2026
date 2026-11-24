"""
Les règles de gestion de la cave, regroupées ici et non dans les pages.

Chaque opération (vente, arrivage, perte, règlement, annulation) passe par une
fonction de ce fichier qui :
1. vérifie les règles (stock suffisant, client obligatoire pour un crédit…) ;
2. enregistre tout dans une seule transaction (tout ou rien) ;
3. écrit une ligne dans le journal d'activité lu par le patron.

Les calculs des comptes du soir et des statistiques sont aussi ici.
"""
import math
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from .formats import fcfa, texte_stock
from .models import (
    Arrivage,
    Client,
    JournalActivite,
    LigneArrivage,
    LigneVente,
    ModePaiement,
    Perte,
    Produit,
    Reglement,
    TypeVente,
    Utilisateur,
    Vente,
)

NOMS_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


class ErreurOperation(Exception):
    """Une règle de gestion n'est pas respectée. Le message est montré tel quel à l'utilisateur."""


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------

def journaliser(utilisateur, action, description, lien="", date=None):
    JournalActivite.objects.create(
        utilisateur=utilisateur, action=action, description=description[:300], lien=lien,
        date=date or timezone.now(),
    )


def bornes_jour(jour):
    """Début et fin (exclue) d'une journée, à l'heure de Ouagadougou."""
    debut = timezone.make_aware(datetime.combine(jour, time.min))
    return debut, debut + timedelta(days=1)


def bornes_mois(annee, mois):
    debut = timezone.make_aware(datetime(annee, mois, 1))
    suivant = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    return debut, timezone.make_aware(datetime(*suivant, 1))


def mois_precedent(annee, mois):
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def nom_mois(annee, mois):
    return f"{NOMS_MOIS[mois - 1]} {annee}"


def _somme(queryset, champ):
    return queryset.aggregate(s=Sum(champ))["s"] or 0


def _par_cle(queryset, cle, champ):
    """Somme de `champ` regroupée par `cle`, renvoyée sous forme de dictionnaire."""
    lignes = queryset.order_by().values(cle).annotate(s=Sum(champ))
    return {ligne[cle]: ligne["s"] or 0 for ligne in lignes}


# --------------------------------------------------------------------------
# Stock et soldes
# --------------------------------------------------------------------------

def stock_par_produit(produit_ids=None):
    """
    Stock de chaque produit, en bouteilles :
    arrivages − ventes − pertes (les opérations annulées ne comptent pas).
    """
    arrivees = LigneArrivage.objects.filter(arrivage__annulee=False)
    vendues = LigneVente.objects.filter(vente__annulee=False)
    perdues = Perte.objects.filter(annulee=False)
    if produit_ids is not None:
        arrivees = arrivees.filter(produit_id__in=produit_ids)
        vendues = vendues.filter(produit_id__in=produit_ids)
        perdues = perdues.filter(produit_id__in=produit_ids)

    entrees = _par_cle(arrivees, "produit", "bouteilles")
    sorties_ventes = _par_cle(vendues, "produit", "bouteilles")
    sorties_pertes = _par_cle(perdues, "produit", "bouteilles")

    ids = produit_ids if produit_ids is not None else Produit.objects.values_list("id", flat=True)
    return {
        pid: entrees.get(pid, 0) - sorties_ventes.get(pid, 0) - sorties_pertes.get(pid, 0)
        for pid in ids
    }


def produits_avec_stock(actifs_seulement=True):
    """Liste des produits, chacun avec son stock (attributs ajoutés : stock_bouteilles, en_alerte…)."""
    produits = list(Produit.objects.filter(actif=True) if actifs_seulement else Produit.objects.all())
    stocks = stock_par_produit([p.id for p in produits])
    for produit in produits:
        produit.stock_bouteilles = stocks.get(produit.id, 0)
        produit.stock_caisses = produit.stock_bouteilles // produit.bouteilles_par_caisse
        produit.stock_texte = texte_stock(produit.stock_bouteilles, produit.bouteilles_par_caisse)
        produit.en_alerte = produit.stock_caisses < produit.seuil_alerte_caisses
        produit.valeur_stock = produit.stock_bouteilles * produit.prix_achat_caisse // produit.bouteilles_par_caisse
    return produits


def soldes_clients():
    """
    Dette de chaque client = crédit accordé lors des ventes − règlements reçus.
    Un solde négatif veut dire que le client a une avance.
    """
    credits = {}
    lignes = (
        Vente.objects.filter(annulee=False, client__isnull=False)
        .order_by()
        .values("client")
        .annotate(s=Sum(F("montant_total") - F("montant_paye")))
    )
    for ligne in lignes:
        credits[ligne["client"]] = ligne["s"] or 0
    reglements = _par_cle(Reglement.objects.filter(annulee=False), "client", "montant")
    ids = set(credits) | set(reglements)
    return {cid: credits.get(cid, 0) - reglements.get(cid, 0) for cid in ids}


def solde_client(client):
    return soldes_clients().get(client.id, 0)


def total_dettes_clients():
    return sum(solde for solde in soldes_clients().values() if solde > 0)


# --------------------------------------------------------------------------
# Opérations
# --------------------------------------------------------------------------

def _verrouiller_produits(ids):
    """
    Verrouille les produits concernés le temps de la transaction (PostgreSQL) :
    deux ventes simultanées du même produit ne peuvent pas vendre le même stock.
    """
    return list(Produit.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def _resume_lignes(lignes):
    return ", ".join(f"{ligne.quantite_caisses} × {ligne.produit}" for ligne in lignes)


def enregistrer_vente(
    *,
    vendeur,
    type_vente,
    quantites,
    client=None,
    comptant=True,
    montant_verse=0,
    mode_paiement=ModePaiement.ESPECES,
    note="",
    date=None,
):
    """
    Enregistre une vente.

    quantites : {id du produit: nombre de caisses}
    comptant  : True si le client paie tout de suite la totalité ;
                sinon `montant_verse` est ce qu'il donne maintenant (0 = tout à crédit).
    """
    quantites = {int(pid): int(q) for pid, q in quantites.items() if int(q) > 0}
    if not quantites:
        raise ErreurOperation("Ajoutez au moins une caisse à la vente.")
    if type_vente not in TypeVente.values:
        raise ErreurOperation("Choisissez le type de vente : détail ou gros.")
    if mode_paiement not in ModePaiement.values:
        raise ErreurOperation("Mode de paiement inconnu.")

    with transaction.atomic():
        produits = [p for p in _verrouiller_produits(quantites) if p.actif]
        if len(produits) != len(quantites):
            raise ErreurOperation("Un des produits n'existe plus ou a été retiré de la vente.")

        stocks = stock_par_produit(list(quantites))
        manques = []
        for produit in produits:
            demande = quantites[produit.id] * produit.bouteilles_par_caisse
            if demande > stocks[produit.id]:
                reste = texte_stock(stocks[produit.id], produit.bouteilles_par_caisse)
                manques.append(f"{produit} (il reste {reste})")
        if manques:
            raise ErreurOperation("Stock insuffisant : " + " ; ".join(manques) + ".")

        lignes = []
        for produit in produits:
            q = quantites[produit.id]
            prix = produit.prix_caisse(type_vente)
            lignes.append(
                LigneVente(
                    produit=produit,
                    quantite_caisses=q,
                    bouteilles=q * produit.bouteilles_par_caisse,
                    prix_caisse=prix,
                    montant=q * prix,
                    cout=q * produit.prix_achat_caisse,
                )
            )
        total = sum(ligne.montant for ligne in lignes)

        if comptant:
            paye = total
        else:
            paye = int(montant_verse or 0)
            if paye < 0 or paye > total:
                raise ErreurOperation(f"Le montant versé doit être compris entre 0 et {fcfa(total)}.")
        if paye < total and client is None:
            raise ErreurOperation("Pour une vente à crédit, choisissez le client ou créez-le.")

        vente = Vente.objects.create(
            date=date or timezone.now(),
            type_vente=type_vente,
            client=client,
            vendeur=vendeur,
            montant_total=total,
            montant_paye=paye,
            mode_paiement=mode_paiement,
            note=note,
        )
        for ligne in lignes:
            ligne.vente = vente
        LigneVente.objects.bulk_create(lignes)

        if paye == total:
            paiement = f"payé comptant ({vente.get_mode_paiement_display()})"
        else:
            paiement = f"à crédit : versé {fcfa(paye)}, reste {fcfa(total - paye)}"
        qui = f" — client {client}" if client else ""
        journaliser(
            vendeur,
            "vente",
            f"Vente {vente.numero} ({vente.get_type_vente_display().lower()}) : "
            f"{_resume_lignes(lignes)} — {fcfa(total)}, {paiement}{qui}",
            lien=f"/ventes/{vente.pk}/",
            date=vente.date,
        )
    return vente


def enregistrer_arrivage(*, utilisateur, quantites, fournisseur="", note="", date=None):
    """Enregistre une livraison : quantites = {id du produit: nombre de caisses reçues}."""
    quantites = {int(pid): int(q) for pid, q in quantites.items() if int(q) > 0}
    if not quantites:
        raise ErreurOperation("Indiquez au moins une caisse reçue.")

    with transaction.atomic():
        produits = _verrouiller_produits(quantites)
        if len(produits) != len(quantites):
            raise ErreurOperation("Un des produits n'existe plus.")
        arrivage = Arrivage.objects.create(
            date=date or timezone.now(), fournisseur=fournisseur, note=note, enregistre_par=utilisateur
        )
        lignes = [
            LigneArrivage(
                arrivage=arrivage,
                produit=p,
                quantite_caisses=quantites[p.id],
                bouteilles=quantites[p.id] * p.bouteilles_par_caisse,
                cout=quantites[p.id] * p.prix_achat_caisse,
            )
            for p in produits
        ]
        LigneArrivage.objects.bulk_create(lignes)
        de = f" de {fournisseur}" if fournisseur else ""
        journaliser(
            utilisateur,
            "arrivage",
            f"Arrivage {arrivage.numero}{de} : {_resume_lignes(lignes)}",
            lien="/arrivages/",
            date=arrivage.date,
        )
    return arrivage


def enregistrer_perte(*, utilisateur, produit, type_perte, bouteilles, note="", date=None):
    bouteilles = int(bouteilles or 0)
    if bouteilles <= 0:
        raise ErreurOperation("Indiquez le nombre de caisses ou de bouteilles perdues.")
    if type_perte not in Perte.TypePerte.values:
        raise ErreurOperation("Choisissez le type de perte.")

    with transaction.atomic():
        produit = _verrouiller_produits([produit.id])[0]
        stock = stock_par_produit([produit.id])[produit.id]
        if bouteilles > stock:
            raise ErreurOperation(
                f"Impossible : il ne reste que {texte_stock(stock, produit.bouteilles_par_caisse)} de {produit}."
            )
        perte = Perte.objects.create(
            date=date or timezone.now(),
            produit=produit,
            type_perte=type_perte,
            bouteilles=bouteilles,
            valeur=bouteilles * produit.prix_achat_caisse // produit.bouteilles_par_caisse,
            note=note,
            enregistre_par=utilisateur,
        )
        journaliser(
            utilisateur,
            "perte",
            f"Perte {perte.numero} : {texte_stock(bouteilles, produit.bouteilles_par_caisse)} de {produit} "
            f"({perte.get_type_perte_display().lower()}){' — ' + note if note else ''}",
            lien="/pertes/",
            date=perte.date,
        )
    return perte


def enregistrer_reglement(*, utilisateur, client, montant, mode_paiement=ModePaiement.ESPECES, note="", date=None):
    montant = int(montant or 0)
    if montant <= 0:
        raise ErreurOperation("Le montant versé doit être supérieur à zéro.")
    if mode_paiement not in ModePaiement.values:
        raise ErreurOperation("Mode de paiement inconnu.")

    with transaction.atomic():
        # Verrou sur le client : deux règlements simultanés ne dépassent pas la dette.
        client = Client.objects.select_for_update().get(pk=client.pk)
        dette = solde_client(client)
        if dette <= 0:
            raise ErreurOperation(f"{client} ne doit rien à la cave.")
        if montant > dette:
            raise ErreurOperation(f"{client} ne doit que {fcfa(dette)}.")
        reglement = Reglement.objects.create(
            date=date or timezone.now(),
            client=client,
            montant=montant,
            mode_paiement=mode_paiement,
            recu_par=utilisateur,
            note=note,
        )
        journaliser(
            utilisateur,
            "reglement",
            f"Règlement {reglement.numero} : {client} rembourse {fcfa(montant)} "
            f"({reglement.get_mode_paiement_display()}), reste dû {fcfa(dette - montant)}",
            lien=f"/clients/{client.pk}/",
            date=reglement.date,
        )
    return reglement


OPERATIONS_ANNULABLES = {
    "vente": Vente,
    "arrivage": Arrivage,
    "perte": Perte,
    "reglement": Reglement,
}


def annuler_operation(objet, utilisateur, motif):
    """Marque une opération comme annulée (elle reste visible, barrée, avec le motif)."""
    motif = (motif or "").strip()
    if not motif:
        raise ErreurOperation("Indiquez le motif de l'annulation.")

    with transaction.atomic():
        objet = type(objet).objects.select_for_update().get(pk=objet.pk)
        if objet.annulee:
            raise ErreurOperation(f"L'opération {objet.numero} est déjà annulée.")

        if isinstance(objet, Arrivage):
            # On ne peut pas annuler une livraison dont les caisses sont déjà vendues.
            lignes = list(objet.lignes.select_related("produit"))
            _verrouiller_produits([ligne.produit_id for ligne in lignes])
            stocks = stock_par_produit([ligne.produit_id for ligne in lignes])
            for ligne in lignes:
                if stocks[ligne.produit_id] - ligne.bouteilles < 0:
                    raise ErreurOperation(
                        f"Impossible d'annuler : une partie de {ligne.produit} de cet arrivage est déjà sortie du stock."
                    )

        objet.annulee = True
        objet.annulee_le = timezone.now()
        objet.annulee_par = utilisateur
        objet.motif_annulation = motif[:200]
        objet.save(update_fields=["annulee", "annulee_le", "annulee_par", "motif_annulation"])
        journaliser(utilisateur, "annulation", f"Annulation de {objet.numero} — motif : {motif}")
    return objet


# --------------------------------------------------------------------------
# Comptes de la journée
# --------------------------------------------------------------------------

def _modes_paiement(ventes_par_mode, reglements_par_mode):
    modes = []
    for code, libelle in ModePaiement.choices:
        v = ventes_par_mode.get(code, 0)
        r = reglements_par_mode.get(code, 0)
        if v or r or code == ModePaiement.ESPECES:
            modes.append({"code": code, "libelle": libelle, "ventes": v, "reglements": r, "total": v + r})
    return modes


def rapport_journee(jour, vendeur=None):
    """
    Les comptes de fin de journée : tout ce qui a été vendu (détail et gros),
    encaissé, donné à crédit, remboursé, perdu et reçu.
    Si `vendeur` est donné, seulement ses opérations à lui (sa caisse).
    """
    debut, fin = bornes_jour(jour)
    ventes = Vente.objects.filter(date__gte=debut, date__lt=fin)
    reglements = Reglement.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    pertes = Perte.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    arrivages = Arrivage.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    if vendeur is not None:
        ventes = ventes.filter(vendeur=vendeur)
        reglements = reglements.filter(recu_par=vendeur)
        pertes = pertes.filter(enregistre_par=vendeur)
        arrivages = arrivages.filter(enregistre_par=vendeur)

    valides = ventes.filter(annulee=False)
    annulees = ventes.filter(annulee=True)
    lignes = LigneVente.objects.filter(vente__in=valides)

    # Détail et gros séparés
    par_type = {}
    nombres = dict(valides.order_by().values_list("type_vente").annotate(n=Count("id")))
    caisses = _par_cle(lignes, "vente__type_vente", "quantite_caisses")
    montants = _par_cle(lignes, "vente__type_vente", "montant")
    for code, libelle in TypeVente.choices:
        par_type[code] = {
            "libelle": libelle,
            "nombre": nombres.get(code, 0),
            "caisses": caisses.get(code, 0),
            "montant": montants.get(code, 0),
        }

    chiffre_affaires = _somme(valides, "montant_total")
    encaisse_ventes = _somme(valides, "montant_paye")
    credit_accorde = chiffre_affaires - encaisse_ventes
    total_reglements = _somme(reglements, "montant")
    modes = _modes_paiement(
        _par_cle(valides, "mode_paiement", "montant_paye"),
        _par_cle(reglements, "mode_paiement", "montant"),
    )

    # Détail par produit
    produits = {p.id: p for p in Produit.objects.all()}
    par_produit = []
    lignes_produit = (
        lignes.order_by()
        .values("produit")
        .annotate(
            caisses_detail=Sum("quantite_caisses", filter=Q(vente__type_vente=TypeVente.DETAIL)),
            caisses_gros=Sum("quantite_caisses", filter=Q(vente__type_vente=TypeVente.GROS)),
            montant=Sum("montant"),
        )
        .order_by("-montant")
    )
    for ligne in lignes_produit:
        par_produit.append(
            {
                "produit": produits[ligne["produit"]],
                "caisses_detail": ligne["caisses_detail"] or 0,
                "caisses_gros": ligne["caisses_gros"] or 0,
                "montant": ligne["montant"] or 0,
            }
        )

    # Chaque gérant et sa caisse (seulement pour la vue d'ensemble du patron)
    par_vendeur = []
    if vendeur is None:
        comptes = {}
        for ligne in valides.order_by().values("vendeur").annotate(
            n=Count("id"), total=Sum("montant_total"), paye=Sum("montant_paye")
        ):
            comptes[ligne["vendeur"]] = {
                "nombre": ligne["n"], "total": ligne["total"] or 0, "paye": ligne["paye"] or 0, "reglements": 0
            }
        for uid, montant in _par_cle(reglements, "recu_par", "montant").items():
            comptes.setdefault(uid, {"nombre": 0, "total": 0, "paye": 0, "reglements": 0})["reglements"] = montant
        utilisateurs = {u.id: u for u in Utilisateur.objects.filter(id__in=comptes)}
        for uid, compte in comptes.items():
            compte["utilisateur"] = utilisateurs[uid]
            compte["encaisse"] = compte["paye"] + compte["reglements"]
            par_vendeur.append(compte)
        par_vendeur.sort(key=lambda c: -c["encaisse"])

    return {
        "jour": jour,
        "nombre_ventes": valides.count(),
        "caisses_vendues": _somme(lignes, "quantite_caisses"),
        "par_type": par_type,
        "chiffre_affaires": chiffre_affaires,
        "encaisse_ventes": encaisse_ventes,
        "credit_accorde": credit_accorde,
        "ventes_a_credit": valides.filter(montant_paye__lt=F("montant_total")).select_related("client"),
        "reglements": reglements.select_related("client", "recu_par"),
        "total_reglements": total_reglements,
        "modes": modes,
        "total_encaisse": encaisse_ventes + total_reglements,
        "especes_attendues": next(m["total"] for m in modes if m["code"] == ModePaiement.ESPECES),
        "pertes": pertes.select_related("produit", "enregistre_par"),
        "pertes_bouteilles": _somme(pertes, "bouteilles"),
        "pertes_valeur": _somme(pertes, "valeur"),
        "arrivages": arrivages.prefetch_related("lignes__produit"),
        "caisses_recues": _somme(LigneArrivage.objects.filter(arrivage__in=arrivages), "quantite_caisses"),
        "annulees": annulees.select_related("annulee_par", "vendeur"),
        "montant_annule": _somme(annulees, "montant_total"),
        "par_produit": par_produit,
        "par_vendeur": par_vendeur,
        "ventes": valides.select_related("client", "vendeur").prefetch_related("lignes__produit"),
    }


def resume_jour(jour, vendeur=None):
    """Version courte des comptes pour les tableaux de bord."""
    debut, fin = bornes_jour(jour)
    ventes = Vente.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    reglements = Reglement.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    pertes = Perte.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    if vendeur is not None:
        ventes = ventes.filter(vendeur=vendeur)
        reglements = reglements.filter(recu_par=vendeur)
        pertes = pertes.filter(enregistre_par=vendeur)
    ca = _somme(ventes, "montant_total")
    paye = _somme(ventes, "montant_paye")
    rembourse = _somme(reglements, "montant")
    return {
        "nombre_ventes": ventes.count(),
        "caisses": _somme(LigneVente.objects.filter(vente__in=ventes), "quantite_caisses"),
        "chiffre_affaires": ca,
        "encaisse": paye + rembourse,
        "credit_accorde": ca - paye,
        "remboursements": rembourse,
        "pertes_valeur": _somme(pertes, "valeur"),
    }


# --------------------------------------------------------------------------
# Statistiques
# --------------------------------------------------------------------------

def statistiques_mois(annee, mois):
    """Les chiffres d'un mois, comparés au mois précédent."""
    debut, fin = bornes_mois(annee, mois)
    valides = Vente.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    lignes = LigneVente.objects.filter(vente__in=valides)
    chiffre_affaires = _somme(lignes, "montant")
    cout = _somme(lignes, "cout")
    pertes = Perte.objects.filter(date__gte=debut, date__lt=fin, annulee=False)
    reglements = Reglement.objects.filter(date__gte=debut, date__lt=fin, annulee=False)

    # Comparaison avec le mois précédent. Si le mois est en cours (ex. le 24),
    # on compare avec les mêmes jours du mois précédent (du 1er au 24) :
    # comparer 24 jours à un mois entier ferait croire à une baisse.
    a, m = mois_precedent(annee, mois)
    debut_prec, fin_prec = bornes_mois(a, m)
    periode_comparee = nom_mois(a, m)  # « octobre 2026 »
    jour = aujourd_hui()
    if (annee, mois) == (jour.year, jour.month):
        fin_prec = min(fin_prec, debut_prec + timedelta(days=jour.day))
        dernier = (fin_prec - timedelta(days=1)).day
        periode_comparee = f"1er–{dernier} {NOMS_MOIS[m - 1]}"  # « 1er–24 octobre »
    ca_prec = _somme(
        LigneVente.objects.filter(vente__annulee=False, vente__date__gte=debut_prec, vente__date__lt=fin_prec),
        "montant",
    )
    evolution = None
    if ca_prec:
        evolution = round((chiffre_affaires - ca_prec) * 100 / ca_prec)

    # Ventes de chaque jour du mois, détail et gros séparés
    jours = {}
    for ligne in (
        lignes.annotate(jour=TruncDate("vente__date"))
        .order_by()
        .values("jour", "vente__type_vente")
        .annotate(s=Sum("montant"))
    ):
        jours.setdefault(ligne["jour"], {TypeVente.DETAIL: 0, TypeVente.GROS: 0})[ligne["vente__type_vente"]] = ligne["s"]
    nb_jours = (fin - debut).days
    par_jour = []
    for i in range(nb_jours):
        j = (debut + timedelta(days=i)).date()
        valeurs = jours.get(j, {TypeVente.DETAIL: 0, TypeVente.GROS: 0})
        par_jour.append(
            {"jour": j, "detail": valeurs[TypeVente.DETAIL], "gros": valeurs[TypeVente.GROS],
             "total": valeurs[TypeVente.DETAIL] + valeurs[TypeVente.GROS]}
        )

    # Classement des produits
    produits = {p.id: p for p in Produit.objects.all()}
    par_produit = []
    for ligne in (
        lignes.order_by()
        .values("produit")
        .annotate(
            caisses=Sum("quantite_caisses"),
            caisses_gros=Sum("quantite_caisses", filter=Q(vente__type_vente=TypeVente.GROS)),
            ca=Sum("montant"),
            cout=Sum("cout"),
        )
        .order_by("-ca")
    ):
        par_produit.append(
            {
                "produit": produits[ligne["produit"]],
                "caisses": ligne["caisses"] or 0,
                "caisses_gros": ligne["caisses_gros"] or 0,
                "caisses_detail": (ligne["caisses"] or 0) - (ligne["caisses_gros"] or 0),
                "ca": ligne["ca"] or 0,
                "marge": (ligne["ca"] or 0) - (ligne["cout"] or 0),
            }
        )

    # Chaque gérant
    utilisateurs = {u.id: u for u in Utilisateur.objects.all()}
    par_vendeur = [
        {"utilisateur": utilisateurs[l["vendeur"]], "nombre": l["n"], "ca": l["ca"] or 0}
        for l in valides.order_by().values("vendeur").annotate(n=Count("id"), ca=Sum("montant_total")).order_by("-ca")
    ]

    par_type = {code: {"libelle": libelle, "ca": 0, "caisses": 0} for code, libelle in TypeVente.choices}
    for code, valeur in _par_cle(lignes, "vente__type_vente", "montant").items():
        par_type[code]["ca"] = valeur
    for code, valeur in _par_cle(lignes, "vente__type_vente", "quantite_caisses").items():
        par_type[code]["caisses"] = valeur

    return {
        "annee": annee,
        "mois": mois,
        "nom_mois": nom_mois(annee, mois),
        "chiffre_affaires": chiffre_affaires,
        "ca_mois_precedent": ca_prec,
        "nom_mois_precedent": nom_mois(a, m),
        "periode_comparee": periode_comparee,
        "evolution": evolution,
        "marge": chiffre_affaires - cout,
        "nombre_ventes": valides.count(),
        "caisses": _somme(lignes, "quantite_caisses"),
        "par_type": par_type,
        "credit_accorde": _somme(valides, "montant_total") - _somme(valides, "montant_paye"),
        "reglements": _somme(reglements, "montant"),
        "pertes_valeur": _somme(pertes, "valeur"),
        "pertes_bouteilles": _somme(pertes, "bouteilles"),
        "par_jour": par_jour,
        "par_produit": par_produit,
        "par_vendeur": par_vendeur,
    }


def evolution_mensuelle(annee, mois, nb_mois=12):
    """Chiffre d'affaires des `nb_mois` derniers mois (jusqu'au mois donné inclus)."""
    liste = [(annee, mois)]
    for _ in range(nb_mois - 1):
        liste.insert(0, mois_precedent(*liste[0]))
    debut, _ = bornes_mois(*liste[0])
    _, fin = bornes_mois(annee, mois)

    valeurs = {}
    for ligne in (
        LigneVente.objects.filter(vente__annulee=False, vente__date__gte=debut, vente__date__lt=fin)
        .annotate(m=TruncMonth("vente__date"))
        .order_by()
        .values("m", "vente__type_vente")
        .annotate(ca=Sum("montant"))
    ):
        cle = (ligne["m"].year, ligne["m"].month)
        valeurs.setdefault(cle, {})[ligne["vente__type_vente"]] = ligne["ca"] or 0

    resultat = []
    for a, m in liste:
        v = valeurs.get((a, m), {})
        detail, gros = v.get(TypeVente.DETAIL, 0), v.get(TypeVente.GROS, 0)
        resultat.append(
            {"annee": a, "mois": m, "etiquette": MOIS_COURTS[m - 1] + ("" if a == annee else f" {a % 100:02d}"),
             "nom": nom_mois(a, m), "detail": detail, "gros": gros, "total": detail + gros}
        )
    return resultat


def besoins_reapprovisionnement(maintenant=None):
    """
    Estimation de ce qu'il faut commander pour tenir 30 jours, d'après le rythme
    des ventes des 90 derniers jours (ou depuis la première vente si la cave est récente).
    """
    maintenant = maintenant or timezone.now()
    premiere = Vente.objects.filter(annulee=False).order_by("date").values_list("date", flat=True).first()
    if premiere is None:
        jours = 0
    else:
        jours = min(90, max(7, (maintenant - premiere).days + 1))
    depuis = maintenant - timedelta(days=jours)
    vendues = _par_cle(
        LigneVente.objects.filter(vente__annulee=False, vente__date__gte=depuis), "produit", "bouteilles"
    )

    resultat = []
    for produit in produits_avec_stock():
        par_jour = vendues.get(produit.id, 0) / jours if jours else 0  # en bouteilles
        besoin_30j = math.ceil(par_jour * 30 / produit.bouteilles_par_caisse) if par_jour else 0
        resultat.append(
            {
                "produit": produit,
                "ventes_30j": besoin_30j,
                "couverture_jours": int(produit.stock_bouteilles / par_jour) if par_jour else None,
                "a_commander": max(0, besoin_30j - produit.stock_caisses),
            }
        )
    resultat.sort(key=lambda b: (b["couverture_jours"] is None, b["couverture_jours"] or 0))
    return {"jours_observes": jours, "lignes": resultat}


def aujourd_hui():
    return timezone.localdate()


def lire_date(texte, defaut=None):
    """'2026-11-24' -> date ; texte invalide -> défaut."""
    try:
        return date.fromisoformat(texte)
    except (TypeError, ValueError):
        return defaut or aujourd_hui()
