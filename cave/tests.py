"""
Tests automatiques. Lancer : python manage.py test

Ils vérifient les règles de gestion (stock, crédit, comptes du soir,
statistiques) et les droits (un gérant ne voit pas les pages du patron).
"""
import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import Client, JournalActivite, Perte, Produit, TypeVente, Utilisateur, Vente
from .services import ErreurOperation


class Base(TestCase):
    def setUp(self):
        self.patron = Utilisateur.objects.create_user("patron", password="Mot-de-passe-1", role="patron")
        self.awa = Utilisateur.objects.create_user("awa", password="Mot-de-passe-2", role="gerant", first_name="Awa")
        self.issa = Utilisateur.objects.create_user("issa", password="Mot-de-passe-3", role="gerant", first_name="Issa")
        self.brakina = Produit.objects.create(
            nom="Brakina", format="65 cl", bouteilles_par_caisse=12,
            prix_achat_caisse=7000, prix_detail_caisse=8000, prix_gros_caisse=7500,
        )
        self.coca = Produit.objects.create(
            nom="Coca-Cola", format="30 cl", categorie="sucrerie", bouteilles_par_caisse=24,
            prix_achat_caisse=6000, prix_detail_caisse=7000, prix_gros_caisse=6800,
        )
        services.enregistrer_arrivage(
            utilisateur=self.patron, quantites={self.brakina.id: 10, self.coca.id: 5}, fournisseur="Stock initial"
        )
        self.client_credit = Client.objects.create(nom="Maquis Test")

    def stock(self, produit):
        return services.stock_par_produit([produit.id])[produit.id]


class StockTests(Base):
    def test_le_stock_suit_arrivages_ventes_pertes_et_annulations(self):
        self.assertEqual(self.stock(self.brakina), 120)
        vente = services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 2})
        self.assertEqual(self.stock(self.brakina), 96)
        services.enregistrer_perte(utilisateur=self.awa, produit=self.brakina, type_perte="casse", bouteilles=3)
        self.assertEqual(self.stock(self.brakina), 93)
        services.annuler_operation(vente, self.patron, "erreur de saisie")
        self.assertEqual(self.stock(self.brakina), 117)

    def test_vente_refusee_si_stock_insuffisant(self):
        with self.assertRaisesMessage(ErreurOperation, "Stock insuffisant"):
            services.enregistrer_vente(vendeur=self.awa, type_vente="gros", quantites={self.brakina.id: 11})
        self.assertEqual(Vente.objects.count(), 0)

    def test_perte_refusee_au_dela_du_stock(self):
        with self.assertRaises(ErreurOperation):
            services.enregistrer_perte(utilisateur=self.awa, produit=self.coca, type_perte="casse", bouteilles=121)

    def test_annulation_arrivage_refusee_si_deja_vendu(self):
        arrivage = services.enregistrer_arrivage(utilisateur=self.awa, quantites={self.coca.id: 2})
        services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.coca.id: 6})
        with self.assertRaisesMessage(ErreurOperation, "déjà sortie du stock"):
            services.annuler_operation(arrivage, self.patron, "erreur")

    def test_texte_du_stock_en_caisses_et_bouteilles(self):
        services.enregistrer_perte(utilisateur=self.awa, produit=self.brakina, type_perte="casse", bouteilles=2)
        produit = next(p for p in services.produits_avec_stock() if p.id == self.brakina.id)
        self.assertEqual(produit.stock_texte, "9 caisses + 10 bt")


class VenteTests(Base):
    def test_prix_de_gros_et_de_detail(self):
        detail = services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 2})
        gros = services.enregistrer_vente(vendeur=self.awa, type_vente="gros", quantites={self.brakina.id: 2})
        self.assertEqual(detail.montant_total, 16000)
        self.assertEqual(gros.montant_total, 15000)

    def test_le_prix_est_fige_sur_le_recu(self):
        vente = services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 1})
        self.brakina.prix_detail_caisse = 9000
        self.brakina.save()
        vente.refresh_from_db()
        self.assertEqual(vente.montant_total, 8000)
        self.assertEqual(vente.lignes.get().prix_caisse, 8000)

    def test_credit_sans_client_refuse(self):
        with self.assertRaisesMessage(ErreurOperation, "choisissez le client"):
            services.enregistrer_vente(vendeur=self.awa, type_vente="gros",
                                       quantites={self.brakina.id: 4}, comptant=False, montant_verse=0)

    def test_credit_puis_remboursements(self):
        vente = services.enregistrer_vente(
            vendeur=self.awa, type_vente="gros", quantites={self.brakina.id: 4},
            client=self.client_credit, comptant=False, montant_verse=10000,
        )
        self.assertEqual(vente.reste_a_payer, 20000)
        self.assertEqual(services.solde_client(self.client_credit), 20000)
        services.enregistrer_reglement(utilisateur=self.issa, client=self.client_credit, montant=15000)
        self.assertEqual(services.solde_client(self.client_credit), 5000)
        with self.assertRaisesMessage(ErreurOperation, "ne doit que"):
            services.enregistrer_reglement(utilisateur=self.issa, client=self.client_credit, montant=6000)

    def test_rien_a_vendre(self):
        with self.assertRaises(ErreurOperation):
            services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 0})

    def test_chaque_vente_est_journalisee(self):
        services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 1})
        self.assertTrue(JournalActivite.objects.filter(action="vente", utilisateur=self.awa).exists())


class ComptesDuJourTests(Base):
    def test_rapport_de_la_journee(self):
        services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 2})  # 16 000
        services.enregistrer_vente(vendeur=self.issa, type_vente="gros", quantites={self.brakina.id: 4},
                                   client=self.client_credit, comptant=False, montant_verse=10000,
                                   mode_paiement="orange")  # 30 000 dont 10 000 versés
        annulee = services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.coca.id: 1})
        services.annuler_operation(annulee, self.patron, "client parti")
        services.enregistrer_reglement(utilisateur=self.awa, client=self.client_credit, montant=5000)
        services.enregistrer_perte(utilisateur=self.awa, produit=self.brakina, type_perte="casse", bouteilles=12)

        r = services.rapport_journee(services.aujourd_hui())
        self.assertEqual(r["nombre_ventes"], 2)
        self.assertEqual(r["chiffre_affaires"], 46000)
        self.assertEqual(r["par_type"]["detail"]["montant"], 16000)
        self.assertEqual(r["par_type"]["gros"]["montant"], 30000)
        self.assertEqual(r["par_type"]["gros"]["caisses"], 4)
        self.assertEqual(r["credit_accorde"], 20000)
        self.assertEqual(r["total_reglements"], 5000)
        self.assertEqual(r["total_encaisse"], 16000 + 10000 + 5000)
        self.assertEqual(r["especes_attendues"], 16000 + 5000)
        self.assertEqual(r["pertes_valeur"], 7000)
        self.assertEqual(r["montant_annule"], 7000)

        # La caisse d'Awa seule
        r_awa = services.rapport_journee(services.aujourd_hui(), vendeur=self.awa)
        self.assertEqual(r_awa["chiffre_affaires"], 16000)
        self.assertEqual(r_awa["total_encaisse"], 21000)

    def test_les_ventes_d_hier_ne_comptent_pas(self):
        hier = timezone.now() - timedelta(days=1)
        services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 1}, date=hier)
        self.assertEqual(services.rapport_journee(services.aujourd_hui())["nombre_ventes"], 0)


class StatistiquesTests(Base):
    def test_statistiques_du_mois(self):
        services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 2})
        services.enregistrer_vente(vendeur=self.awa, type_vente="gros", quantites={self.coca.id: 2})
        jour = services.aujourd_hui()
        s = services.statistiques_mois(jour.year, jour.month)
        self.assertEqual(s["chiffre_affaires"], 16000 + 13600)
        self.assertEqual(s["marge"], (16000 - 14000) + (13600 - 12000))
        self.assertEqual(s["par_produit"][0]["produit"], self.brakina)
        self.assertEqual(sum(j["total"] for j in s["par_jour"]), 29600)
        evolution = services.evolution_mensuelle(jour.year, jour.month)
        self.assertEqual(len(evolution), 12)
        self.assertEqual(evolution[-1]["total"], 29600)

    def test_besoins_de_reapprovisionnement(self):
        services.enregistrer_vente(vendeur=self.awa, type_vente="gros", quantites={self.brakina.id: 7})
        besoins = services.besoins_reapprovisionnement()
        ligne = next(b for b in besoins["lignes"] if b["produit"].id == self.brakina.id)
        self.assertGreater(ligne["a_commander"], 0)


class PagesEtDroitsTests(Base):
    PAGES_PATRON = ["statistiques", "journal", "produits", "gerants", "parametres", "produit_nouveau", "gerant_nouveau"]
    PAGES_TOUS = ["accueil", "nouvelle_vente", "ventes", "point_du_jour", "clients", "stock", "arrivages", "pertes",
                  "client_nouveau", "mon_mot_de_passe"]

    def test_il_faut_se_connecter(self):
        reponse = self.client.get(reverse("accueil"))
        self.assertRedirects(reponse, reverse("connexion") + "?next=/")

    def test_le_gerant_ne_voit_pas_les_pages_du_patron(self):
        self.client.force_login(self.awa)
        for nom in self.PAGES_PATRON:
            self.assertEqual(self.client.get(reverse(nom)).status_code, 403, nom)
        for nom in self.PAGES_TOUS:
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200, nom)

    def test_le_patron_voit_tout(self):
        services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 1})
        self.client.force_login(self.patron)
        for nom in self.PAGES_PATRON + self.PAGES_TOUS:
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200, nom)
        self.assertEqual(self.client.get(reverse("statistiques") + "?mois=2020-01").status_code, 200)

    def test_vendre_depuis_le_formulaire_puis_imprimer_le_recu(self):
        self.client.force_login(self.awa)
        reponse = self.client.post(reverse("nouvelle_vente"), {
            "type_vente": "detail", f"q_{self.brakina.id}": "3", "paiement": "comptant", "mode_paiement": "especes",
        })
        vente = Vente.objects.get()
        self.assertRedirects(reponse, reverse("recu_vente", args=[vente.pk]))
        recu = self.client.get(reverse("recu_vente", args=[vente.pk]))
        self.assertContains(recu, "24 000 F")
        self.assertContains(recu, vente.numero)

    def test_vente_a_credit_avec_nouveau_client(self):
        self.client.force_login(self.awa)
        self.client.post(reverse("nouvelle_vente"), {
            "type_vente": "gros", f"q_{self.brakina.id}": "2", "paiement": "credit", "montant_verse": "5000",
            "nouveau_client_nom": "Bar Nouveau", "mode_paiement": "especes",
        })
        client = Client.objects.get(nom="Bar Nouveau")
        self.assertEqual(services.solde_client(client), 10000)

    def test_erreur_de_vente_affichee_sans_rien_enregistrer(self):
        self.client.force_login(self.awa)
        reponse = self.client.post(reverse("nouvelle_vente"), {
            "type_vente": "detail", f"q_{self.brakina.id}": "50", "paiement": "comptant",
            "nouveau_client_nom": "Client fantôme", "mode_paiement": "especes",
        })
        self.assertContains(reponse, "Stock insuffisant")
        self.assertFalse(Client.objects.filter(nom="Client fantôme").exists())

    def test_un_gerant_ne_voit_pas_les_recus_des_autres(self):
        vente = services.enregistrer_vente(vendeur=self.issa, type_vente="detail", quantites={self.brakina.id: 1})
        self.client.force_login(self.awa)
        self.assertEqual(self.client.get(reverse("recu_vente", args=[vente.pk])).status_code, 403)
        self.client.force_login(self.patron)
        self.assertEqual(self.client.get(reverse("recu_vente", args=[vente.pk])).status_code, 200)

    def test_seul_le_patron_annule(self):
        vente = services.enregistrer_vente(vendeur=self.awa, type_vente="detail", quantites={self.brakina.id: 1})
        url = reverse("annuler", args=["vente", vente.pk])
        self.client.force_login(self.awa)
        self.assertEqual(self.client.post(url, {"motif": "test"}).status_code, 403)
        self.client.force_login(self.patron)
        self.client.post(url, {"motif": "erreur de quantité", "suite": "/ventes/"})
        vente.refresh_from_db()
        self.assertTrue(vente.annulee)
        self.assertEqual(vente.annulee_par, self.patron)

    def test_le_patron_cree_un_gerant_qui_peut_se_connecter(self):
        self.client.force_login(self.patron)
        self.client.post(reverse("gerant_nouveau"), {
            "username": "moussa", "first_name": "Moussa", "last_name": "K",
            "password1": "Cave-Moussa-2026", "password2": "Cave-Moussa-2026",
        })
        moussa = Utilisateur.objects.get(username="moussa")
        self.assertEqual(moussa.role, "gerant")
        self.client.logout()
        reponse = self.client.post(reverse("connexion"), {"username": "moussa", "password": "Cave-Moussa-2026"})
        self.assertRedirects(reponse, reverse("accueil"))

    def test_connexion_refusee_journalisee(self):
        reponse = self.client.post(reverse("connexion"), {"username": "awa", "password": "faux"})
        self.assertContains(reponse, "Identifiant ou mot de passe incorrect")
        self.assertTrue(JournalActivite.objects.filter(action="echec_connexion").exists())

    def test_gerant_desactive_ne_peut_plus_se_connecter(self):
        self.awa.is_active = False
        self.awa.save()
        self.assertFalse(self.client.login(username="awa", password="Mot-de-passe-2"))


class CommandesTests(TestCase):
    def test_initialiser_cave_cree_le_patron_une_seule_fois(self):
        with mock.patch.dict(os.environ, {"PATRON_MOT_DE_PASSE": "Un-Bon-Mot-2026", "NOM_CAVE": "Cave Essai"}):
            call_command("initialiser_cave", stdout=StringIO())
            patron = Utilisateur.objects.get(username="patron")
            self.assertTrue(patron.est_patron)
            self.assertTrue(patron.check_password("Un-Bon-Mot-2026"))
        # Second lancement avec un autre mot de passe : le compte existant n'est pas modifié
        with mock.patch.dict(os.environ, {"PATRON_MOT_DE_PASSE": "Autre-Mot-2026"}):
            call_command("initialiser_cave", stdout=StringIO())
        patron.refresh_from_db()
        self.assertTrue(patron.check_password("Un-Bon-Mot-2026"))
        self.assertEqual(Utilisateur.objects.count(), 1)

    def test_reinitialiser_le_mot_de_passe_oublie_du_patron(self):
        Utilisateur.objects.create_superuser("patron", password="Ancien-Mot-2026")
        with mock.patch.dict(os.environ, {"PATRON_MOT_DE_PASSE": "Nouveau-Mot-2026",
                                          "REINITIALISER_MOT_DE_PASSE_PATRON": "oui"}):
            call_command("initialiser_cave", stdout=StringIO())
        self.assertTrue(Utilisateur.objects.get(username="patron").check_password("Nouveau-Mot-2026"))

    def test_mot_de_passe_patron_trop_faible_refuse(self):
        from django.core.management.base import CommandError
        with mock.patch.dict(os.environ, {"PATRON_MOT_DE_PASSE": "1234"}):
            with self.assertRaises(CommandError):
                call_command("initialiser_cave", stdout=StringIO())
        self.assertFalse(Utilisateur.objects.exists())

    def test_charger_demo_garde_un_stock_positif(self):
        Utilisateur.objects.create_superuser("patron", password="Un-Bon-Mot-2026")
        call_command("charger_demo", jours=40, stdout=StringIO())
        self.assertGreater(Vente.objects.count(), 50)
        self.assertGreaterEqual(min(services.stock_par_produit().values()), 0)
        self.assertTrue(all(solde >= 0 for solde in services.soldes_clients().values()))
        # Une seconde fois : ne fait rien
        nb = Vente.objects.count()
        call_command("charger_demo", stdout=StringIO())
        self.assertEqual(Vente.objects.count(), nb)
