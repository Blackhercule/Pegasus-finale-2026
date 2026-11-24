"""
Charge des données de démonstration pour essayer l'application :
des boissons, deux gérants, des clients et environ trois mois d'activité
(ventes au détail et en gros, crédits, remboursements, arrivages, casses).

- Les noms de clients et de gérants sont fictifs.
- Les prix sont des EXEMPLES : le patron les remplace par les siens (Produits et prix).
- La commande ne fait rien si des produits existent déjà : elle ne peut pas
  mélanger des données fictives avec de vraies données.
"""
import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cave import services
from cave.models import Client, Perte, Produit, TypeVente, Utilisateur, Vente

# nom, format, catégorie, bouteilles/caisse, achat, détail, gros (prix d'une caisse, en F CFA, fictifs),
# popularité (poids dans le tirage au sort des ventes)
PRODUITS = [
    ("Brakina", "65 cl", "biere", 12, 7000, 7800, 7500, 10),
    ("Beaufort", "65 cl", "biere", 12, 7400, 8300, 8000, 7),
    ("Castel", "65 cl", "biere", 12, 7400, 8300, 8000, 6),
    ("Flag Spéciale", "65 cl", "biere", 12, 7400, 8300, 8000, 5),
    ("So.b.bra", "65 cl", "biere", 12, 7000, 7800, 7500, 4),
    ("Guinness", "33 cl", "biere", 24, 14500, 16000, 15500, 3),
    ("Coca-Cola", "30 cl", "sucrerie", 24, 6500, 7400, 7100, 4),
    ("Fanta", "30 cl", "sucrerie", 24, 6500, 7400, 7100, 3),
    ("Sprite", "30 cl", "sucrerie", 24, 6500, 7400, 7100, 2),
    ("Eau minérale", "1,5 L", "eau", 6, 1800, 2200, 2000, 3),
]

CLIENTS = [
    ("Maquis Le Baobab", "70 00 00 01", "Revendeur, prend en gros"),
    ("Bar Chez Tanti", "70 00 00 02", "Revendeur"),
    ("Kiosque Wend-Kuuni", "70 00 00 03", ""),
    ("Restaurant La Paillote", "70 00 00 04", "Paie souvent en fin de mois"),
    ("Buvette du marché", "70 00 00 05", ""),
    ("M. Traoré (fêtes)", "70 00 00 06", "Client de détail"),
]

GERANTS = [("awa", "Awa", "Ouédraogo"), ("issa", "Issa", "Sawadogo")]


class Command(BaseCommand):
    help = "Charge des données de démonstration (seulement si aucun produit n'existe)."

    def add_arguments(self, parser):
        parser.add_argument("--jours", type=int, default=90, help="Nombre de jours d'historique (90 par défaut).")

    def handle(self, *args, **options):
        if Produit.objects.exists():
            self.stdout.write("Des produits existent déjà : les données de démonstration ne sont pas chargées.")
            return
        patron = Utilisateur.objects.filter(role=Utilisateur.Role.PATRON).first()
        if patron is None:
            raise CommandError("Créez d'abord le compte patron (commande initialiser_cave).")

        with transaction.atomic():
            self._charger(patron, options["jours"])
        self.stdout.write(self.style.SUCCESS(
            f"Données de démonstration chargées : {Vente.objects.count()} ventes, {Client.objects.count()} clients."
        ))

    def _charger(self, patron, nb_jours):
        alea = random.Random(2026)  # toujours le même tirage : la démonstration est reproductible
        produits = [
            Produit.objects.create(
                nom=nom, format=fmt, categorie=cat, bouteilles_par_caisse=bpc,
                prix_achat_caisse=achat, prix_detail_caisse=detail, prix_gros_caisse=gros,
                seuil_alerte_caisses=10 if pop >= 5 else 6,
            )
            for nom, fmt, cat, bpc, achat, detail, gros, pop in PRODUITS
        ]
        popularite = [ligne[-1] for ligne in PRODUITS]
        gerants = []
        for identifiant, prenom, nom in GERANTS:
            # Pas de mot de passe : le patron en donne un depuis la page « Gérants »
            gerant = Utilisateur.objects.create_user(
                username=identifiant, first_name=prenom, last_name=nom, password=None, role=Utilisateur.Role.GERANT
            )
            gerants.append(gerant)
        clients = [Client.objects.create(nom=n, telephone=t, note=note) for n, t, note in CLIENTS]
        revendeurs = clients[:5]

        maintenant = timezone.now()
        aujourdhui = timezone.localdate()
        premier_jour = aujourdhui - timedelta(days=nb_jours)

        def a(jour, heure, minute=0):
            return timezone.make_aware(datetime.combine(jour, time(heure, minute)))

        # Stock de départ
        services.enregistrer_arrivage(
            utilisateur=patron, quantites={p.id: 40 + 8 * pop for p, pop in zip(produits, popularite)},
            fournisseur="Stock initial", date=a(premier_jour, 7),
        )

        for n in range(nb_jours + 1):
            jour = premier_jour + timedelta(days=n)
            # Réapprovisionnement le lundi et le jeudi
            if jour.weekday() in (0, 3) and n > 0:
                stocks = services.stock_par_produit()
                quantites = {}
                for p, pop in zip(produits, popularite):
                    if p.nom == "Sprite" and (aujourdhui - jour).days < 25:
                        continue  # rupture chez le fournisseur : montre l'alerte de stock bas
                    cible = 30 + 10 * pop
                    caisses = stocks[p.id] // p.bouteilles_par_caisse
                    if caisses < cible:
                        quantites[p.id] = cible - caisses
                if quantites and a(jour, 8) < maintenant:
                    services.enregistrer_arrivage(
                        utilisateur=alea.choice(gerants), quantites=quantites,
                        fournisseur=alea.choice(["Brakina", "Dépôt SODIBO", "Grossiste"]), date=a(jour, 8),
                    )

            # Plus de monde le vendredi et le samedi
            nb_ventes = alea.randint(3, 6) + (4 if jour.weekday() in (4, 5) else 0)
            heures = sorted(alea.randint(9 * 60, 22 * 60) for _ in range(nb_ventes))
            for minutes in heures:
                date = a(jour, minutes // 60, minutes % 60)
                if date >= maintenant:
                    break
                self._vente_au_hasard(alea, date, produits, popularite, gerants, patron, clients, revendeurs)

            # Quelques remboursements de crédit
            if alea.random() < 0.35 and a(jour, 12) < maintenant:
                soldes = services.soldes_clients()
                debiteurs = [c for c in clients if soldes.get(c.id, 0) > 0]
                if debiteurs:
                    client = alea.choice(debiteurs)
                    dette = soldes[client.id]
                    montant = max(1000, min(dette, round(dette * alea.choice([0.3, 0.5, 1]), -3)))
                    services.enregistrer_reglement(
                        utilisateur=alea.choice(gerants), client=client, montant=min(montant, dette),
                        mode_paiement=alea.choice(["especes", "especes", "orange", "moov"]), date=a(jour, 12, 30),
                    )

            # Une casse de temps en temps
            if alea.random() < 0.2 and a(jour, 23) < maintenant:
                produit = alea.choices(produits, weights=popularite)[0]
                try:
                    services.enregistrer_perte(
                        utilisateur=alea.choice(gerants), produit=produit,
                        type_perte=alea.choice([Perte.TypePerte.CASSE] * 4 + [Perte.TypePerte.DISPARUE]),
                        bouteilles=alea.randint(1, 6), note="Démonstration", date=a(jour, 23),
                    )
                except services.ErreurOperation:
                    pass

        services.journaliser(patron, "demo", "Données de démonstration chargées (noms et prix fictifs)")

    def _vente_au_hasard(self, alea, date, produits, popularite, gerants, patron, clients, revendeurs):
        en_gros = alea.random() < 0.22
        quantites = {}
        for produit in set(alea.choices(produits, weights=popularite, k=alea.randint(1, 4 if en_gros else 2))):
            quantites[produit.id] = alea.randint(8, 30) if en_gros else alea.randint(1, 3)

        client, comptant, verse = None, True, 0
        if en_gros:
            client = alea.choice(revendeurs)
            if alea.random() < 0.35:
                comptant = False
                verse = alea.choice([0, 0.5])
        elif alea.random() < 0.06:
            client = alea.choice(clients)
            comptant = False

        vendeur = alea.choice(gerants + gerants + [patron])
        try:
            total = sum(
                q * p.prix_caisse(TypeVente.GROS if en_gros else TypeVente.DETAIL)
                for p in produits for pid, q in quantites.items() if p.id == pid
            )
            services.enregistrer_vente(
                vendeur=vendeur,
                type_vente=TypeVente.GROS if en_gros else TypeVente.DETAIL,
                quantites=quantites,
                client=client,
                comptant=comptant,
                montant_verse=int(total * verse) // 1000 * 1000,
                mode_paiement=alea.choice(["especes"] * 6 + ["orange", "orange", "moov"]),
                date=date,
            )
        except services.ErreurOperation:
            pass  # stock insuffisant ce jour-là : on passe
