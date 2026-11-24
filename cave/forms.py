"""
Les formulaires. Django vérifie les champs (nombres, longueurs…) et protège
chaque envoi contre la falsification de requête (jeton CSRF).

La vente et l'arrivage n'ont pas de classe ici : leur page affiche une ligne
par produit, lue directement dans la vue (voir lire_quantites dans views.py).
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Client, ModePaiement, ParametresCave, Perte, Produit, Utilisateur


class ConnexionForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Identifiant ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé. Adressez-vous au patron.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Identifiant"
        self.fields["password"].label = "Mot de passe"


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = [
            "nom", "format", "categorie", "bouteilles_par_caisse",
            "prix_detail_caisse", "prix_gros_caisse", "prix_achat_caisse",
            "seuil_alerte_caisses", "actif",
        ]
        widgets = {
            "prix_detail_caisse": forms.NumberInput(attrs={"inputmode": "numeric", "min": 0}),
            "prix_gros_caisse": forms.NumberInput(attrs={"inputmode": "numeric", "min": 0}),
            "prix_achat_caisse": forms.NumberInput(attrs={"inputmode": "numeric", "min": 0}),
        }


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["nom", "telephone", "note"]
        widgets = {"telephone": forms.TextInput(attrs={"inputmode": "tel"})}


class PerteForm(forms.Form):
    produit = forms.ModelChoiceField(queryset=Produit.objects.filter(actif=True), label="Produit")
    type_perte = forms.ChoiceField(choices=Perte.TypePerte.choices, label="Type de perte")
    caisses = forms.IntegerField(label="Caisses entières", min_value=0, initial=0, required=False)
    bouteilles = forms.IntegerField(label="Bouteilles en plus", min_value=0, initial=0, required=False)
    note = forms.CharField(label="Explication", max_length=200, required=False,
                           widget=forms.TextInput(attrs={"placeholder": "Ex. : caisse tombée au déchargement"}))

    def total_bouteilles(self):
        produit = self.cleaned_data["produit"]
        caisses = self.cleaned_data.get("caisses") or 0
        bouteilles = self.cleaned_data.get("bouteilles") or 0
        return caisses * produit.bouteilles_par_caisse + bouteilles


class ReglementForm(forms.Form):
    montant = forms.IntegerField(label="Montant versé (F CFA)", min_value=1,
                                 widget=forms.NumberInput(attrs={"inputmode": "numeric"}))
    mode_paiement = forms.ChoiceField(choices=ModePaiement.choices, label="Mode de paiement")
    note = forms.CharField(label="Note", max_length=200, required=False)


class AnnulationForm(forms.Form):
    motif = forms.CharField(label="Motif de l'annulation", max_length=200,
                            widget=forms.TextInput(attrs={"placeholder": "Ex. : erreur de quantité, client parti sans payer…"}))


class GerantCreationForm(UserCreationForm):
    """Création d'un compte gérant par le patron (identifiant + mot de passe)."""

    class Meta:
        model = Utilisateur
        fields = ["username", "first_name", "last_name"]
        labels = {"username": "Identifiant de connexion", "first_name": "Prénom", "last_name": "Nom"}
        help_texts = {"username": "Ex. : awa, issa.k — sans espace."}

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.role = Utilisateur.Role.GERANT
        if commit:
            utilisateur.save()
        return utilisateur


class GerantModificationForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "is_active"]
        labels = {"first_name": "Prénom", "last_name": "Nom", "is_active": "Compte actif (peut se connecter)"}
        help_texts = {"is_active": "Décochez pour bloquer l'accès d'un gérant qui ne travaille plus à la cave."}


class ParametresForm(forms.ModelForm):
    class Meta:
        model = ParametresCave
        fields = ["nom", "adresse", "telephone", "message_recu"]
