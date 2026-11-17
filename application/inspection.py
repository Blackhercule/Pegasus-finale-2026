"""Grouper les visites de terrain en tournées d'inspection.

Le problème : la brigade Laabal se déplace dossier par dossier. Dix constats à faire, dix
sorties — et comme les dossiers arrivent dans le désordre, deux visites à cent mètres l'une de
l'autre se font souvent deux jours différents. C'est du carburant, des heures d'agent, et des
dossiers qui attendent. Embaucher coûte cher ; mieux grouper les sorties ne coûte rien.

Ce module répond donc à : « qu'est-ce que je vais voir ce matin, et dans quel ordre ? »

**Rien n'est réinventé.** C'est le même algorithme des économies (Clarke et Wright, 1964) que
les tournées des camions, le même réseau de rues, le même tracé. Seule la contrainte change :
un camion est limité par sa benne, un agent par sa journée. On réemploie donc les fonctions de
`application/plan`, sans en écrire une seconde version — un jury qui demande « expliquez cet
algorithme » reçoit la même réponse pour les deux, et l'équipe n'a qu'une chose à savoir
expliquer.
"""

import numpy as np

from .plan import (SECONDES_PAR_HEURE, ameliorer, distance_tournee, duree_totale, fusionner,
                   geometrie_tournee)

# Une visite de terrain n'est pas un ramassage : l'agent constate, photographie, parle aux
# riverains. Vingt minutes est une hypothèse de l'équipe, à confirmer avec la brigade.
MINUTES_PAR_VISITE = 20
AGENTS_TERRAIN = 2


def base_du_service(parametres: dict, geographie) -> dict:
    """D'où part l'agent le matin, et où il revient.

    À confirmer avec la mairie, comme la décharge : tant qu'on ne l'a pas, on prend le centre
    de la commune, qui est le point le moins mauvais par défaut. Se change dans
    `parametres.json` sous la clé `base_inspection`, sans toucher au code."""
    donnee = (parametres or {}).get("base_inspection")
    if donnee and donnee.get("latitude") is not None:
        return {"latitude": float(donnee["latitude"]), "longitude": float(donnee["longitude"]),
                "nom": donnee.get("nom", "Base du service"), "a_confirmer": False}
    centre = geographie.commune.centroid
    return {"latitude": centre.y, "longitude": centre.x,
            "nom": "Centre de la commune (à confirmer avec la mairie)", "a_confirmer": True}


def tournees_d_inspection(dossiers: list, base: dict, reseau, parametres: dict) -> dict:
    """Groupe les dossiers à visiter en tournées, une par agent et par journée.

    `dossiers` : des dicts portant au moins id, latitude, longitude. L'ordre d'entrée n'a pas
    d'importance ; celui de sortie est l'ordre de passage conseillé."""
    agents = max(1, int(parametres.get("agents_terrain", AGENTS_TERRAIN)))
    duree_max = float(parametres.get("heures_travail", 8)) * SECONDES_PAR_HEURE
    service = float(parametres.get("minutes_par_visite", MINUTES_PAR_VISITE)) * 60
    vitesses, saison = parametres["vitesses_kmh"], parametres["saison"]

    visites = [d for d in dossiers
               if d.get("latitude") is not None and d.get("longitude") is not None]
    if not visites:
        return {"tournees": [], "non_visites": [], "injoignables": [],
                "agents": agents, "base": base}

    # Même structure d'arrêt que pour les camions, pour réemployer leurs fonctions telles
    # quelles. Le volume ne sert pas ici : une visite ne remplit aucune benne.
    arrets = [{"id": d["id"], "id_arret": d["id"], "m3": 0.0,
               "latitude": float(d["latitude"]), "longitude": float(d["longitude"]),
               "genre": d.get("nature") or "dossier",
               "noeud": None} for d in visites]
    positions = np.array([[a["longitude"], a["latitude"]] for a in arrets])
    noeuds_arrets = reseau.noeuds_les_plus_proches(positions)
    for arret, noeud in zip(arrets, noeuds_arrets):
        arret["noeud"] = int(noeud)
    base = {**base, "noeud": int(reseau.noeud_le_plus_proche(base["longitude"], base["latitude"]))}

    noeuds = [base["noeud"]] + [a["noeud"] for a in arrets]
    durees, predecesseurs = reseau.durees_et_chemins(noeuds, vitesses, saison)
    durees = np.nan_to_num(durees, posinf=1e7, nan=1e7)

    # Une tournée par visite au départ ; celles qu'on ne peut pas atteindre dans la journée
    # sont écartées tout de suite et NOMMÉES, jamais perdues en silence.
    tournees, injoignables = [], []
    for i, arret in enumerate(arrets, start=1):
        aller_retour = durees[0, i] + durees[i, 0] + service
        if durees[0, i] >= 1e6 or aller_retour > duree_max:
            injoignables.append(arret["id"])
        else:
            tournees.append({"arrets": [i], "volume": 0.0, "duree": aller_retour})

    indices = [t["arrets"][0] for t in tournees]
    economies = []
    for rang, i in enumerate(indices):
        for j in indices[rang + 1:]:
            gain = durees[0, i] + durees[0, j] - durees[i, j]
            if gain > 0:
                economies.append((gain, i, j))
    economies.sort(reverse=True)

    position = {t["arrets"][0]: t for t in tournees}
    for _, i, j in economies:
        ti, tj = position.get(i), position.get(j)
        if ti is None or tj is None or ti is tj:
            continue
        fusion = fusionner(ti, tj, i, j, durees, service)
        # Seule contrainte : la journée de l'agent. Pas de benne à remplir.
        if fusion is None or fusion["duree"] > duree_max:
            continue
        tournees.remove(ti)
        tournees.remove(tj)
        tournees.append(fusion)
        for arret in fusion["arrets"]:
            position[arret] = fusion

    for tournee in tournees:
        tournee["arrets"] = ameliorer(tournee["arrets"], durees)
        tournee["duree"] = duree_totale(tournee["arrets"], durees, service)

    # Répartition entre les agents : la tournée la plus longue d'abord, à l'agent le moins
    # chargé. Même règle que pour les camions.
    tournees.sort(key=lambda t: -t["duree"])
    journees = [[] for _ in range(agents)]
    charges = [0.0] * agents
    reportees = []
    for tournee in tournees:
        agent = int(np.argmin(charges))
        if charges[agent] + tournee["duree"] <= duree_max:
            journees[agent].append(tournee)
            charges[agent] += tournee["duree"]
        else:
            reportees.append(tournee)       # pas perdue : elle passe au jour suivant

    resultat = []
    for numero, journee in enumerate(journees, start=1):
        for rang, tournee in enumerate(journee, start=1):
            ordre = tournee["arrets"]
            resultat.append({
                "agent": numero, "sortie": rang,
                "etapes": [{"id": arrets[i - 1]["id"], "latitude": arrets[i - 1]["latitude"],
                            "longitude": arrets[i - 1]["longitude"],
                            "genre": arrets[i - 1]["genre"]} for i in ordre],
                "nb_visites": len(ordre),
                "duree_min": round(float(tournee["duree"]) / 60, 1),
                "distance_km": round(float(distance_tournee(ordre, arrets, base)) / 1000, 1),
                "geometrie": geometrie_tournee(ordre, noeuds, predecesseurs, arrets, base, reseau),
            })
    resultat.sort(key=lambda t: (t["agent"], t["sortie"]))

    programmes = {arrets[i - 1]["id"] for t in tournees if t not in reportees
                  for i in t["arrets"]}
    non_visites = sorted({a["id"] for a in arrets} - programmes - set(injoignables))

    # Ce qu'on économise, dit simplement : une sortie par dossier, c'était l'aller-retour pour
    # chacun. C'est le chiffre qui parle à une mairie.
    sans_groupement = float(sum((durees[0, i] + durees[i, 0] + service)
                                for i in range(1, len(arrets) + 1)
                                if durees[0, i] < 1e6))
    avec_groupement = float(sum(t["duree"] for t in tournees))
    gain = max(0.0, sans_groupement - avec_groupement)

    return {
        "tournees": resultat, "non_visites": non_visites, "injoignables": injoignables,
        "agents": agents, "base": base, "reportees": len(reportees),
        # Combien d'agents il faut VRAIMENT aujourd'hui. Si le groupement tient dans la
        # journée d'un seul, en envoyer deux coûte une journée pour rien : c'est exactement
        # la dépense que cet outil doit éviter.
        "agents_necessaires": sum(1 for c in charges if c > 0),
        "heures_par_agent": [round(float(c) / 3600, 1) for c in charges],
        "economie": {
            "sorties_evitees": max(0, len(arrets) - len(resultat)),
            "heures_sans_groupement": round(sans_groupement / 3600, 1),
            "heures_avec_groupement": round(avec_groupement / 3600, 1),
            "heures_gagnees": round(gain / 3600, 1),
        },
    }
