"""Plan de gestion : où poser les points de regroupement, et quelles tournées font les camions.

Trois étapes, dans cet ordre :

  1. la DEMANDE  — combien de déchets chaque carreau de la ville produit par jour ;
  2. les POINTS  — où placer les points de regroupement pour que chaque ménage en ait un près
                   de chez lui, sans dépasser la capacité d'un point ;
  3. les TOURNÉES — quels camions passent où, dans quel ordre, sans dépasser leur capacité ni
                    la durée de travail, et ce qu'on n'arrive pas à desservir.

Puis des CONTRÔLES DE COHÉRENCE : le plan se vérifie lui-même et affiche ses propres limites.
Quand le jury change un paramètre (camions en panne, saison des pluies, nouveau quartier), tout
est recalculé à partir des mêmes fonctions : rien n'est écrit en dur (exigence E11).

Les deux algorithmes utilisés sont classiques et se racontent en une phrase :
  - placement des points : « couverture gloutonne » — on ouvre à chaque tour le point qui sert
    le plus de déchets encore non couverts ;
  - tournées : « algorithme des économies » de Clarke et Wright (1964) — on part d'un aller-retour
    par point, puis on fusionne les deux tournées qui font gagner le plus de trajet.
"""

import json
import math

import numpy as np

from ..geo import distance_m

SECONDES_PAR_HEURE = 3600


# ------------------------------------------------------------------ 1. la demande
def repartir_la_demande(zones: list, parametres: dict) -> dict:
    """Population et déchets produits par carreau, à partir de la surface bâtie.

    On ne connaît pas la population carreau par carreau : on la répartit au prorata de la
    surface bâtie, de sorte que le total égale la population donnée en paramètre. Les nouveaux
    quartiers annoncés par le jury ajoutent leur propre population."""
    surfaces = np.array([z["properties"]["surface_batie_m2"] for z in zones], dtype=float)
    total = surfaces.sum()
    if total <= 0:
        raise ValueError("Aucune surface bâtie : les données de la commune sont incomplètes.")
    habitants = surfaces / total * float(parametres["population"])

    centres = np.array([centre_du_carreau(z) for z in zones])
    for quartier in parametres.get("nouveaux_quartiers", []):
        habitants = ajouter_un_quartier(habitants, centres, quartier)

    kg = habitants * float(parametres["kg_par_habitant_jour"])
    m3 = kg / 1000 / float(parametres.get("densite_dechets_t_m3", 0.35))
    return {"centres": centres, "habitants": habitants, "m3_par_jour": m3,
            "identifiants": [z["properties"]["id"] for z in zones],
            "secteurs": [z["properties"].get("secteur", "") for z in zones]}


def centre_du_carreau(zone: dict) -> tuple:
    contour = zone["geometry"]["coordinates"][0]
    points = contour[:-1] if contour[0] == contour[-1] else contour
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def ajouter_un_quartier(habitants: np.ndarray, centres: np.ndarray, quartier: dict) -> np.ndarray:
    """Un nouveau quartier : sa population s'ajoute aux carreaux situés dans son périmètre.

    Le jury peut en annoncer un en direct ; il suffit de donner son centre, son rayon et sa
    population, sans toucher au code."""
    habitants = habitants.copy()
    lon, lat = float(quartier["longitude"]), float(quartier["latitude"])
    rayon = float(quartier.get("rayon_m", 1500))
    nouveaux = float(quartier.get("population", 0))
    distances = np.array([distance_m(lon, lat, c[0], c[1]) for c in centres])
    dedans = distances <= rayon
    if not dedans.any():
        # Quartier encore sans bâtiments cartographiés : on le rattache au carreau le plus proche.
        dedans = np.zeros(len(centres), dtype=bool)
        dedans[int(np.argmin(distances))] = True
    poids = np.where(dedans, 1.0, 0.0)
    habitants += poids / poids.sum() * nouveaux
    return habitants


# ------------------------------------------------------------------ 2. les points de regroupement
def placer_les_points(demande: dict, reseau, parametres: dict, lieux: list = None,
                      geographie=None, points_existants: list = None) -> dict:
    """Choisit l'emplacement des points de regroupement parmi les carrefours du réseau.

    Méthode : couverture gloutonne. À chaque tour, on ouvre le carrefour qui dessert le plus de
    déchets encore non couverts, à moins de `distance_max_precollecte_m` d'un carreau. On
    s'arrête quand tout est couvert ou que le nombre de points nécessaires est atteint."""
    portee = float(parametres["distance_max_precollecte_m"])
    capacite = float(parametres["capacite_point_m3"])
    frequence = max(1, int(parametres["frequence_collecte_jours"]))
    part_desservie = float(parametres["taux_abonnement"])

    # Ce qui transite par les points de regroupement : la part des ménages desservie par un
    # pré-collecteur. Le reste part directement en dépotoir ou en décharge.
    a_couvrir = demande["m3_par_jour"] * part_desservie
    # Une marge : sans elle, le point moyen serait pile à sa capacité, et la moitié des points
    # déborderaient dès que le quartier produit un peu plus que la moyenne.
    marge = float(parametres.get("marge_points", 1.4))
    nb_points_voulus = (int(math.ceil(a_couvrir.sum() * frequence / capacite * marge))
                        if capacite > 0 else 0)
    nb_points_voulus = max(1, min(nb_points_voulus, 400))

    candidats = choisir_les_candidats(demande, reseau, lieux, geographie, portee)
    distances = distances_carreaux_candidats(demande["centres"], reseau.noeuds[candidats], portee)

    ouverts = []
    for point in (points_existants or []):            # sites déjà en service, gardés par la mairie
        plus_proche = reseau.noeud_le_plus_proche(point["longitude"], point["latitude"])
        if plus_proche not in ouverts:
            ouverts.append(plus_proche)

    restant = a_couvrir.copy()
    indices_candidats = list(range(len(candidats)))
    for noeud in ouverts:
        if noeud in candidats:
            indices_candidats.remove(int(np.where(candidats == noeud)[0][0]))
    choisis = [int(np.where(candidats == n)[0][0]) for n in ouverts if n in candidats]

    while len(choisis) < nb_points_voulus and restant.sum() > 1e-9 and indices_candidats:
        gains = np.array([restant[distances[:, i] <= portee].sum() for i in indices_candidats])
        meilleur = int(np.argmax(gains))
        if gains[meilleur] <= 1e-9:
            break                                     # plus rien à gagner : des carreaux sont hors de portée
        indice = indices_candidats.pop(meilleur)
        choisis.append(indice)
        restant[distances[:, indice] <= portee] = 0

    if not choisis:
        raise ValueError("Aucun emplacement possible pour un point de regroupement.")

    # Chaque carreau va au point ouvert le plus proche, s'il est à portée.
    sous_matrice = distances[:, choisis]
    plus_proche = np.argmin(sous_matrice, axis=1)
    distance_au_point = sous_matrice[np.arange(len(plus_proche)), plus_proche]
    desservi = distance_au_point <= portee

    points = []
    for rang, indice in enumerate(choisis):
        carreaux = np.where(desservi & (plus_proche == rang))[0]
        noeud = int(candidats[indice])
        lon, lat = reseau.noeuds[noeud]
        points.append({
            "id": rang, "noeud": noeud, "longitude": float(lon), "latitude": float(lat),
            "m3_par_jour": float(a_couvrir[carreaux].sum()),
            "m3_par_passage": float(a_couvrir[carreaux].sum() * frequence),
            # Jour du cycle où ce point est vidé : la charge est ainsi répartie sur la semaine,
            # au lieu de devoir vider toute la ville le même jour.
            "jour_du_cycle": rang % frequence + 1,
            "habitants": float(demande["habitants"][carreaux].sum()),
            "nb_carreaux": int(len(carreaux)),
            "distance_moyenne_m": float(distance_au_point[carreaux].mean()) if len(carreaux) else 0.0,
            "sature": bool(a_couvrir[carreaux].sum() * frequence > capacite),
        })
    return {
        "points": points,
        "m3_non_couverts": float(a_couvrir[~desservi].sum()),
        "habitants_non_couverts": float(demande["habitants"][~desservi].sum()),
        "distance_moyenne_m": float(distance_au_point[desservi].mean()) if desservi.any() else 0.0,
        "nb_points_voulus": nb_points_voulus,
    }


def choisir_les_candidats(demande, reseau, lieux, geographie, portee, maximum=1200) -> np.ndarray:
    """Emplacements possibles : des carrefours proches des habitations, et pas n'importe où.

    Sont écartés : l'eau, et les abords immédiats des écoles et des centres de santé."""
    candidats = reseau.noeuds_les_plus_proches(demande["centres"])
    candidats = np.unique(candidats)
    if geographie is not None:
        candidats = np.array([n for n in candidats
                              if not geographie.dans_l_eau(*reseau.noeuds[n])], dtype=int)
    sensibles = [(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1])
                 for f in (lieux or []) if f["properties"].get("type") in ("ecole", "sante")]
    if sensibles:
        tableau = np.array(sensibles)
        gardes = []
        for n in candidats:
            lon, lat = reseau.noeuds[n]
            # Comparaison rapide en degrés : 100 m valent environ 0,0009°.
            proche = np.abs(tableau[:, 0] - lon) < 0.0009
            proche &= np.abs(tableau[:, 1] - lat) < 0.0009
            if not proche.any():
                gardes.append(n)
        candidats = np.array(gardes, dtype=int)
    if len(candidats) > maximum:                      # on garde un échantillon régulier
        candidats = candidats[np.linspace(0, len(candidats) - 1, maximum).astype(int)]
    return candidats


def distances_carreaux_candidats(centres: np.ndarray, positions: np.ndarray, portee: float) -> np.ndarray:
    """Distance à vol d'oiseau entre chaque carreau et chaque emplacement possible, en mètres.

    À l'échelle d'un quartier (quelques centaines de mètres, à pied ou à charrette), la distance
    directe suffit ; le réseau sert pour les camions, qui parcourent toute la ville."""
    lat_moyenne = math.radians(float(centres[:, 1].mean()))
    metres_par_degre_lon = 111320 * math.cos(lat_moyenne)
    metres_par_degre_lat = 110540
    dx = (centres[:, 0][:, None] - positions[:, 0][None, :]) * metres_par_degre_lon
    dy = (centres[:, 1][:, None] - positions[:, 1][None, :]) * metres_par_degre_lat
    return np.sqrt(dx * dx + dy * dy)


# ------------------------------------------------------------------ 3. les tournées
def decouper_les_arrets(arrets: list, capacite: float) -> list:
    """Un point qui contient plus qu'une benne demande plusieurs passages.

    Un camion de 12 m³ ne vide pas d'un coup un point de 60 m³ : il y revient cinq fois. On
    découpe donc chaque arrêt en autant de passages que nécessaire, chacun d'au plus une benne."""
    passages = []
    for arret in arrets:
        volume = float(arret["m3"])
        nombre = max(1, math.ceil(volume / capacite)) if capacite > 0 else 1
        for numero in range(nombre):
            passage = dict(arret)
            passage["m3"] = volume / nombre
            passage["id_arret"] = arret["id"]
            passage["id"] = arret["id"] if nombre == 1 else f"{arret['id']}#{numero + 1}"
            passages.append(passage)
    return passages


def calculer_les_tournees(arrets: list, depot: dict, reseau, parametres: dict) -> dict:
    """Tournées des camions : algorithme des économies (Clarke et Wright, 1964).

    Une tournée, c'est un chargement : le camion part de la décharge, remplit sa benne, et y
    revient vider. Au départ, chaque passage est une tournée à lui seul ; on fusionne ensuite
    les tournées qui font gagner le plus de trajet, tant que la benne suit. Les tournées
    obtenues sont enfin réparties entre les camions, chacun dans sa journée de travail : un
    camion en fait plusieurs à la suite. Ce qui ne rentre pas est laissé de côté — et nommé."""
    camions = max(0, int(parametres["nb_camions"]) - int(parametres.get("camions_en_panne", 0)))
    capacite = float(parametres["capacite_camion_m3"])
    duree_max = float(parametres["heures_travail"]) * SECONDES_PAR_HEURE
    vitesses, saison = parametres["vitesses_kmh"], parametres["saison"]
    minutes_par_arret = float(parametres.get("minutes_par_arret", 8))
    minutes_vidage = float(parametres.get("minutes_vidage_benne", 15))

    if not arrets or camions == 0 or capacite <= 0:
        return {"tournees": [], "non_desservis": sorted({a["id"] for a in arrets}),
                "camions_disponibles": camions, "injoignables": [], "tournees_abandonnees": 0}

    passages = decouper_les_arrets(arrets, capacite)
    noeuds = [depot["noeud"]] + [p["noeud"] for p in passages]
    durees = reseau.durees(noeuds, noeuds, vitesses, saison)
    durees = np.nan_to_num(durees, posinf=1e7, nan=1e7)
    service = minutes_par_arret * 60
    vidage = minutes_vidage * 60

    # Une tournée par passage au départ ; les passages hors d'atteinte sont écartés tout de suite.
    tournees, injoignables = [], []
    for i, passage in enumerate(passages, start=1):
        aller_retour = durees[0, i] + durees[i, 0] + service + vidage
        if durees[0, i] >= 1e6 or aller_retour > duree_max:
            injoignables.append(passage["id"])
        else:
            tournees.append({"arrets": [i], "volume": passage["m3"], "duree": aller_retour})

    indices = [t["arrets"][0] for t in tournees]
    economies = []
    for rang_i, i in enumerate(indices):
        for j in indices[rang_i + 1:]:
            gain = durees[0, i] + durees[0, j] - durees[i, j]
            if gain > 0:
                economies.append((gain, i, j))
    economies.sort(reverse=True)

    position = {t["arrets"][0]: t for t in tournees}
    for _, i, j in economies:
        ti, tj = position.get(i), position.get(j)
        if ti is None or tj is None or ti is tj:
            continue
        if ti["volume"] + tj["volume"] > capacite:
            continue                                   # la benne serait pleine : on ne fusionne pas
        fusion = fusionner(ti, tj, i, j, durees, service)
        if fusion is None or fusion["duree"] + vidage > duree_max:
            continue
        fusion["duree"] += vidage
        tournees.remove(ti)
        tournees.remove(tj)
        tournees.append(fusion)
        for arret in fusion["arrets"]:
            position[arret] = fusion

    for tournee in tournees:
        tournee["arrets"] = ameliorer(tournee["arrets"], durees)
        tournee["duree"] = duree_totale(tournee["arrets"], durees, service) + vidage

    # Répartition entre les camions : la tournée la plus longue d'abord, confiée au camion le
    # moins chargé. C'est la règle classique « le plus long d'abord », simple et efficace.
    tournees.sort(key=lambda t: (-t["volume"] / max(t["duree"], 1), t["duree"]))
    journees = [[] for _ in range(camions)]
    charges = [0.0] * camions
    abandonnees = []
    for tournee in tournees:
        camion = int(np.argmin(charges))
        if charges[camion] + tournee["duree"] <= duree_max:
            journees[camion].append(tournee)
            charges[camion] += tournee["duree"]
        else:
            abandonnees.append(tournee)

    resultat = []
    for numero, journee in enumerate(journees, start=1):
        for rang, tournee in enumerate(journee, start=1):
            ordre = tournee["arrets"]
            resultat.append({
                "camion": numero, "rotation": rang,
                "arrets": [passages[i - 1]["id"] for i in ordre],
                "etapes": [{"id": passages[i - 1]["id"], "longitude": passages[i - 1]["longitude"],
                            "latitude": passages[i - 1]["latitude"], "m3": round(passages[i - 1]["m3"], 2),
                            "genre": passages[i - 1].get("genre", "point")} for i in ordre],
                "volume_m3": round(sum(passages[i - 1]["m3"] for i in ordre), 2),
                "duree_min": round(tournee["duree"] / 60, 1),
                "distance_km": round(distance_tournee(ordre, passages, depot) / 1000, 1),
            })
    resultat.sort(key=lambda t: (t["camion"], t["rotation"]))

    servis = {passages[i - 1]["id_arret"] for t in tournees if t not in abandonnees
              for i in t["arrets"]}
    non_desservis = sorted({a["id"] for a in arrets} - servis)
    return {"tournees": resultat, "non_desservis": non_desservis, "camions_disponibles": camions,
            "injoignables": injoignables, "tournees_abandonnees": len(abandonnees),
            "heures_par_camion": [round(c / 3600, 1) for c in charges]}


def fusionner(ti, tj, i, j, durees, service):
    """Fusionne deux tournées en reliant leurs extrémités, si elles s'y prêtent."""
    ai, aj = ti["arrets"], tj["arrets"]
    if ai[-1] == i and aj[0] == j:
        ordre = ai + aj
    elif ai[0] == i and aj[-1] == j:
        ordre = aj + ai
    elif ai[0] == i and aj[0] == j:
        ordre = ai[::-1] + aj
    elif ai[-1] == i and aj[-1] == j:
        ordre = ai + aj[::-1]
    else:
        return None
    return {"arrets": ordre, "volume": ti["volume"] + tj["volume"],
            "duree": duree_totale(ordre, durees, service)}


def duree_totale(ordre, durees, service) -> float:
    total = durees[0, ordre[0]] + durees[ordre[-1], 0] + service * len(ordre)
    for a, b in zip(ordre, ordre[1:]):
        total += durees[a, b]
    return float(total)


def ameliorer(ordre, durees, tours=40):
    """Dernier coup de polish : on retourne un morceau du parcours s'il raccourcit la tournée
    (méthode « 2-opt », classique en optimisation de tournées)."""
    meilleur = list(ordre)
    for _ in range(tours):
        gagne = False
        for a in range(len(meilleur) - 1):
            for b in range(a + 1, len(meilleur)):
                essai = meilleur[:a] + meilleur[a:b + 1][::-1] + meilleur[b + 1:]
                if duree_totale(essai, durees, 0) < duree_totale(meilleur, durees, 0) - 1:
                    meilleur, gagne = essai, True
        if not gagne:
            break
    return meilleur


def distance_tournee(ordre, arrets, depot) -> float:
    points = [(depot["longitude"], depot["latitude"])] + \
             [(arrets[i - 1]["longitude"], arrets[i - 1]["latitude"]) for i in ordre] + \
             [(depot["longitude"], depot["latitude"])]
    return sum(distance_m(*a, *b) for a, b in zip(points, points[1:]))
