"""
Les tables de l'application.

Principe central : on n'enregistre jamais « le stock » directement. On enregistre
chaque mouvement (arrivage, vente, perte) et le stock se calcule toujours par :

    stock = bouteilles arrivées − bouteilles vendues − bouteilles perdues

Ainsi le stock ne peut pas « dériver » : il est toujours la somme exacte des
opérations, et une opération annulée cesse simplement d'être comptée.

Tous les montants sont en francs CFA, sans centimes : des entiers suffisent.
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class UtilisateurManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Un super-utilisateur (python manage.py createsuperuser) est toujours le patron.
        extra_fields.setdefault("role", "patron")
        return super().create_superuser(username, email, password, **extra_fields)


class Utilisateur(AbstractUser):
    """Un compte : soit le patron (voit et gère tout), soit un gérant."""

    objects = UtilisateurManager()

    class Role(models.TextChoices):
        PATRON = "patron", "Patron"
        GERANT = "gerant", "Gérant"

    role = models.CharField("Rôle", max_length=10, choices=Role.choices, default=Role.GERANT)

    @property
    def est_patron(self):
        return self.role == self.Role.PATRON

    def __str__(self):
        return self.get_full_name() or self.username


class ParametresCave(models.Model):
    """Informations de la cave imprimées sur les reçus (une seule ligne dans la table)."""

    nom = models.CharField("Nom de la cave", max_length=100, default="Ma cave")
    adresse = models.CharField("Adresse", max_length=200, blank=True)
    telephone = models.CharField("Téléphone", max_length=50, blank=True)
    message_recu = models.CharField(
        "Message en bas du reçu", max_length=200, blank=True, default="Merci pour votre confiance !"
    )

    class Meta:
        verbose_name = "paramètres de la cave"
        verbose_name_plural = "paramètres de la cave"

    @classmethod
    def charger(cls):
        parametres, _ = cls.objects.get_or_create(pk=1)
        return parametres

    def __str__(self):
        return self.nom


class TypeVente(models.TextChoices):
    DETAIL = "detail", "Détail"
    GROS = "gros", "Gros"


class ModePaiement(models.TextChoices):
    ESPECES = "especes", "Espèces"
    ORANGE = "orange", "Orange Money"
    MOOV = "moov", "Moov Money"
    AUTRE = "autre", "Autre"


class Produit(models.Model):
    """Une boisson vendue par la cave (ex. : Brakina 65 cl, caisse de 12)."""

    class Categorie(models.TextChoices):
        BIERE = "biere", "Bière"
        SUCRERIE = "sucrerie", "Sucrerie"
        EAU = "eau", "Eau"
        VIN = "vin", "Vin et liqueur"
        AUTRE = "autre", "Autre"

    nom = models.CharField("Nom", max_length=80)
    format = models.CharField("Format", max_length=30, blank=True, help_text="Ex. : 65 cl, 33 cl, 1,5 L")
    categorie = models.CharField("Catégorie", max_length=10, choices=Categorie.choices, default=Categorie.BIERE)
    bouteilles_par_caisse = models.PositiveIntegerField(
        "Bouteilles par caisse", default=12, validators=[MinValueValidator(1)]
    )
    prix_achat_caisse = models.PositiveIntegerField("Prix d'achat d'une caisse (F CFA)", default=0)
    prix_detail_caisse = models.PositiveIntegerField("Prix de vente au détail d'une caisse (F CFA)")
    prix_gros_caisse = models.PositiveIntegerField("Prix de vente en gros d'une caisse (F CFA)")
    seuil_alerte_caisses = models.PositiveIntegerField(
        "Alerte quand il reste moins de (caisses)", default=5
    )
    actif = models.BooleanField("En vente", default=True, help_text="Décochez pour retirer le produit des ventes.")

    class Meta:
        ordering = ["categorie", "nom", "format"]
        constraints = [models.UniqueConstraint(fields=["nom", "format"], name="produit_unique")]

    def __str__(self):
        return f"{self.nom} {self.format}".strip()

    def prix_caisse(self, type_vente):
        """Prix d'une caisse selon que la vente est en gros ou au détail."""
        if type_vente == TypeVente.GROS:
            return self.prix_gros_caisse
        return self.prix_detail_caisse


class Annulable(models.Model):
    """
    Champs communs aux opérations qu'on peut annuler.

    Une opération n'est jamais effacée : elle est marquée « annulée », avec qui,
    quand et pourquoi. Le patron garde ainsi la trace de toutes les corrections.
    """

    annulee = models.BooleanField("Annulée", default=False)
    annulee_le = models.DateTimeField(null=True, blank=True)
    annulee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    motif_annulation = models.CharField("Motif de l'annulation", max_length=200, blank=True)

    class Meta:
        abstract = True


class Client(models.Model):
    """Un client, surtout utile pour suivre ceux qui prennent à crédit."""

    nom = models.CharField("Nom", max_length=100)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    note = models.CharField("Note", max_length=200, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Vente(Annulable):
    """Une vente (un reçu). Les produits vendus sont dans LigneVente."""

    date = models.DateTimeField(default=timezone.now, db_index=True)
    type_vente = models.CharField("Type de vente", max_length=10, choices=TypeVente.choices)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT, related_name="ventes")
    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventes")
    montant_total = models.PositiveIntegerField(default=0)
    # Ce que le client a versé au moment de la vente. La différence est du crédit.
    montant_paye = models.PositiveIntegerField(default=0)
    mode_paiement = models.CharField(
        "Mode de paiement", max_length=10, choices=ModePaiement.choices, default=ModePaiement.ESPECES
    )
    note = models.CharField("Note", max_length=200, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant_paye__lte=models.F("montant_total")), name="vente_paye_inferieur_total"
            )
        ]

    @property
    def numero(self):
        return f"V{self.pk:06d}"

    @property
    def reste_a_payer(self):
        return self.montant_total - self.montant_paye

    @property
    def a_credit(self):
        return self.reste_a_payer > 0

    @property
    def nb_caisses(self):
        return sum(ligne.quantite_caisses for ligne in self.lignes.all())

    def __str__(self):
        return self.numero


class LigneVente(models.Model):
    """Un produit dans une vente. Prix et coût sont figés au moment de la vente."""

    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name="lignes_vente")
    quantite_caisses = models.PositiveIntegerField()
    bouteilles = models.PositiveIntegerField()  # quantité_caisses × bouteilles par caisse
    prix_caisse = models.PositiveIntegerField()
    montant = models.PositiveIntegerField()  # quantité × prix
    cout = models.PositiveIntegerField(default=0)  # quantité × prix d'achat, pour la marge

    class Meta:
        ordering = ["id"]


class Arrivage(Annulable):
    """Une livraison reçue (camion du fournisseur, stock de départ…)."""

    date = models.DateTimeField(default=timezone.now, db_index=True)
    fournisseur = models.CharField("Fournisseur", max_length=100, blank=True)
    note = models.CharField("Note", max_length=200, blank=True)
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date"]

    @property
    def numero(self):
        return f"A{self.pk:06d}"

    def __str__(self):
        return self.numero


class LigneArrivage(models.Model):
    arrivage = models.ForeignKey(Arrivage, on_delete=models.CASCADE, related_name="lignes")
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name="lignes_arrivage")
    quantite_caisses = models.PositiveIntegerField()
    bouteilles = models.PositiveIntegerField()
    cout = models.PositiveIntegerField(default=0)  # quantité × prix d'achat du moment

    class Meta:
        ordering = ["id"]


class Perte(Annulable):
    """Bouteilles cassées, caisses disparues, produits avariés…"""

    class TypePerte(models.TextChoices):
        CASSE = "casse", "Bouteilles cassées"
        DISPARUE = "disparue", "Caisses ou bouteilles disparues"
        AVARIEE = "avariee", "Produit avarié ou périmé"
        AUTRE = "autre", "Autre"

    date = models.DateTimeField(default=timezone.now, db_index=True)
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name="pertes")
    type_perte = models.CharField("Type de perte", max_length=10, choices=TypePerte.choices)
    bouteilles = models.PositiveIntegerField("Nombre de bouteilles perdues", validators=[MinValueValidator(1)])
    valeur = models.PositiveIntegerField(default=0)  # valeur au prix d'achat
    note = models.CharField("Note", max_length=200, blank=True)
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date"]

    @property
    def numero(self):
        return f"P{self.pk:06d}"

    def __str__(self):
        return self.numero


class Reglement(Annulable):
    """Un remboursement de crédit versé par un client."""

    date = models.DateTimeField(default=timezone.now, db_index=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="reglements")
    montant = models.PositiveIntegerField("Montant versé (F CFA)", validators=[MinValueValidator(1)])
    mode_paiement = models.CharField(
        "Mode de paiement", max_length=10, choices=ModePaiement.choices, default=ModePaiement.ESPECES
    )
    recu_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    note = models.CharField("Note", max_length=200, blank=True)

    class Meta:
        ordering = ["-date"]

    @property
    def numero(self):
        return f"R{self.pk:06d}"

    def __str__(self):
        return self.numero


class JournalActivite(models.Model):
    """
    Le fil de tout ce qui se passe dans la cave, lu par le patron :
    connexions, ventes, arrivages, pertes, règlements, annulations, réglages.
    """

    date = models.DateTimeField(default=timezone.now, db_index=True)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=30)
    description = models.CharField(max_length=300)
    lien = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date:%d/%m/%Y %H:%M} {self.action} {self.description}"
