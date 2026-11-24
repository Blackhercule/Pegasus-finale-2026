"""Petites fonctions d'affichage partagées par les pages et le journal."""

ESPACE_INSECABLE = " "  # espace fine insécable : « 25 500 F » ne se coupe pas en fin de ligne


def fcfa(montant):
    """25500 -> « 25 500 F »."""
    montant = int(montant or 0)
    signe = "−" if montant < 0 else ""
    chiffres = f"{abs(montant):,}".replace(",", ESPACE_INSECABLE)
    return f"{signe}{chiffres}{ESPACE_INSECABLE}F"


def decomposer_stock(bouteilles, bouteilles_par_caisse):
    """130 bouteilles, caisses de 12 -> (10 caisses, 10 bouteilles)."""
    bouteilles = int(bouteilles or 0)
    if bouteilles < 0:
        caisses, reste = decomposer_stock(-bouteilles, bouteilles_par_caisse)
        return -caisses, -reste
    return divmod(bouteilles, bouteilles_par_caisse)


def texte_stock(bouteilles, bouteilles_par_caisse):
    """130 bouteilles, caisses de 12 -> « 10 caisses + 10 bt »."""
    caisses, reste = decomposer_stock(bouteilles, bouteilles_par_caisse)
    texte = f"{caisses} caisse{'s' if abs(caisses) > 1 else ''}"
    if reste:
        texte += f" + {reste} bt"
    return texte
