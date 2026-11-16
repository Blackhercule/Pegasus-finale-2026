"""Assemble le plan complet, puis le vérifie.

Le plan sert à décider : il doit donc dire aussi ce qu'il N'ARRIVE PAS à faire. Les contrôles
de cohérence, en bas de ce fichier, sont calculés à chaque recalcul et affichés avec le plan.
C'est ce que le jury regarde quand il met des camions en panne ou annonce la saison des pluies :
le plan change, et il reste honnête sur ses limites.
"""

import json
import math
import time

import numpy as np

from ..geo import distance_m
from . import calculer_les_tournees, placer_les_points, repartir_la_demande


def charger_geojson(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)["features"]


def choisir_la_decharge(lieux: list, parametres: dict) -> dict:
    """La décharge où les camions vident leur benne.

    Si la mairie nous donne sa position, on la prend. Sinon on la déduit d'OpenStreetMap :
    là où les sites de décharge sont les plus nombreux et les plus groupés."""
    donnee = parametres.get("decharge")
    if donnee:
        return {"longitude": float(donnee["longitude"]), "latitude": float(donnee["latitude"]),
                "nom": donnee.get("nom", "Décharge"), "origine": "paramètre de la mairie"}
    decharges = [f for f in lieux if f["properties"].get("type") in ("decharge", "dechets")]
    if not decharges:
        raise ValueError("Aucune décharge dans les données : donnez-la dans parametres.json.")
    points = np.array([f["geometry"]["coordinates"] for f in decharges])
    # On compte les sites par carré d'environ 1 km et on garde le carré le plus fourni.
    cases = np.floor(points / 0.01).astype(int)
    uniques, comptes = np.unique(cases, axis=0, return_counts=True)
    meilleure = uniques[int(np.argmax(comptes))]
    dedans = points[(cases == meilleure).all(axis=1)]
    return {"longitude": float(dedans[:, 0].mean()), "latitude": float(dedans[:, 1].mean()),
            "nom": "Décharge principale", "origine": f"OpenStreetMap, groupe de {len(dedans)} sites",
            "a_confirmer": True}


def calculer_le_plan(reglages, reseau, geographie, parametres: dict, depotoirs: list) -> dict:
    """Le plan complet : demande, points de regroupement, tournées, coûts et contrôles."""
    debut = time.monotonic()
    zones = charger_geojson(reglages.fichier("zones.geojson"))
    lieux = charger_geojson(reglages.fichier("lieux.geojson"))

    demande = repartir_la_demande(zones, parametres)
    decharge = choisir_la_decharge(lieux, parametres)
    decharge["noeud"] = reseau.noeud_le_plus_proche(decharge["longitude"], decharge["latitude"])

    resultat_points = placer_les_points(demande, reseau, parametres, lieux, geographie,
                                        parametres.get("points_existants"))
    points = resultat_points["points"]

    # Ce que les camions doivent faire AUJOURD'HUI : vider les points dont c'est le jour de
    # passage, et nettoyer les dépotoirs signalés. Un point n'est pas vidé tous les jours :
    # avec une fréquence de 3 jours, un tiers des points est desservi chaque jour.
    frequence = max(1, int(parametres["frequence_collecte_jours"]))
    jour = (int(parametres.get("jour_du_cycle", 1)) - 1) % frequence + 1
    du_jour = [p for p in points if p["jour_du_cycle"] == jour]
    arrets = [{"id": f"point-{p['id']}", "noeud": p["noeud"], "longitude": p["longitude"],
               "latitude": p["latitude"], "m3": p["m3_par_passage"], "genre": "point"}
              for p in du_jour if p["m3_par_passage"] > 0.1]
    noeuds_depotoirs = reseau.noeuds_les_plus_proches(
        [(d["longitude"], d["latitude"]) for d in depotoirs]) if depotoirs else []
    for d, noeud in zip(depotoirs, noeuds_depotoirs):
        arrets.append({"id": f"depotoir-{d['id']}", "noeud": int(noeud),
                       "longitude": d["longitude"], "latitude": d["latitude"],
                       "m3": float(d["volume_m3"] or 1), "genre": "depotoir"})

    tournees = calculer_les_tournees(arrets, decharge, reseau, parametres)
    couts = calculer_les_couts(tournees["tournees"], parametres)
    verifications = controles_de_coherence(demande, resultat_points, arrets, tournees, parametres, couts)

    return {
        "saison": parametres["saison"],
        "decharge": decharge,
        "demande": {
            "population": float(parametres["population"]),
            "m3_par_jour": round(float(demande["m3_par_jour"].sum()), 1),
            "tonnes_par_jour": round(float(demande["m3_par_jour"].sum())
                                     * float(parametres.get("densite_dechets_t_m3", 0.35)), 1),
            "carreaux": len(zones),
        },
        "jour_du_cycle": jour,
        "frequence_collecte_jours": frequence,
        "points": points,
        "points_resume": {
            "nombre": len(points),
            "a_vider_aujourd_hui": len(du_jour),
            "satures": sum(1 for p in points if p["sature"]),
            "distance_moyenne_m": round(resultat_points["distance_moyenne_m"]),
            "habitants_non_couverts": round(resultat_points["habitants_non_couverts"]),
            "m3_non_couverts": round(resultat_points["m3_non_couverts"], 1),
        },
        "tournees": tournees["tournees"],
        "non_desservis": tournees["non_desservis"],
        "camions_disponibles": tournees["camions_disponibles"],
        "couts": couts,
        "controles": verifications,
        "calcule_en_s": round(time.monotonic() - debut, 1),
    }


def calculer_les_couts(tournees: list, parametres: dict) -> dict:
    km = sum(t["distance_km"] for t in tournees)
    jours_camion = len(tournees)
    par_jour = km * float(parametres["cout_km"]) + jours_camion * float(parametres["cout_jour_camion"])
    par_mois = par_jour * 30
    budget = float(parametres["budget_mensuel"])
    recettes = (float(parametres["population"]) / float(parametres["taille_menage"])
                * float(parametres["taux_abonnement"]) * float(parametres["tarif_abonnement"]))
    return {"km_par_jour": round(km, 1), "cout_par_jour": round(par_jour),
            "cout_par_mois": round(par_mois), "budget_mensuel": round(budget),
            "recettes_abonnements_par_mois": round(recettes),
            "solde_mensuel": round(budget + recettes - par_mois)}


def controles_de_coherence(demande, resultat_points, arrets, tournees, parametres, couts) -> list:
    """Le plan se vérifie lui-même. Chaque contrôle dit « oui », « non » ou « attention »,
    avec le chiffre qui le justifie. Un contrôle qui échoue n'est pas caché."""
    controles = []

    def noter(nom, satisfait, detail, gravite="probleme"):
        controles.append({"nom": nom, "etat": "ok" if satisfait else gravite, "detail": detail})

    capacite = float(parametres["capacite_camion_m3"])
    duree_max = float(parametres["heures_travail"]) * 60
    liste = tournees["tournees"]

    depassent = [t["camion"] for t in liste if t["volume_m3"] > capacite + 1e-6]
    noter("Capacité des camions respectée", not depassent,
          "Aucune tournée ne dépasse les %.0f m³." % capacite if not depassent
          else "Tournées trop chargées : %s." % ", ".join(map(str, depassent)))

    heures = {}
    for t in liste:
        heures[t["camion"]] = heures.get(t["camion"], 0) + t["duree_min"]
    trop_longues = [c for c, m in heures.items() if m > duree_max + 1e-6]
    noter("Durée de travail respectée", not trop_longues,
          "Journée la plus chargée : %.1f h sur %.0f h autorisées."
          % ((max(heures.values()) if heures else 0) / 60, duree_max / 60) if not trop_longues
          else "Camions au-delà de la journée de travail : %s." % ", ".join(map(str, trop_longues)))

    vus = [a for t in liste for a in t["arrets"]]
    noter("Aucun passage en double", len(vus) == len(set(vus)),
          "%d passages répartis en %d tournée(s), aucun en double." % (len(vus), len(liste))
          if len(vus) == len(set(vus)) else "Des passages apparaissent dans deux tournées.")

    non_servis = tournees["non_desservis"]
    noter("Tous les arrêts sont desservis", not non_servis,
          "Les %d arrêts sont desservis." % len(arrets) if not non_servis
          else "%d arrêt(s) non desservi(s) faute de camions ou de temps : %s%s"
               % (len(non_servis), ", ".join(non_servis[:6]),
                  "…" if len(non_servis) > 6 else ""), gravite="attention")

    noter("Tous les habitants ont un point à portée", resultat_points["habitants_non_couverts"] < 1,
          "Chaque carreau bâti a un point de regroupement à portée."
          if resultat_points["habitants_non_couverts"] < 1
          else "%d habitants sont à plus de %.0f m d'un point."
               % (resultat_points["habitants_non_couverts"],
                  float(parametres["distance_max_precollecte_m"])), gravite="attention")

    satures = [p["id"] for p in resultat_points["points"] if p["sature"]]
    noter("Aucun point de regroupement saturé", not satures,
          "Aucun point ne dépasse %.0f m³ entre deux passages." % float(parametres["capacite_point_m3"])
          if not satures else "%d point(s) saturé(s) : il faut les vider plus souvent."
                              % len(satures), gravite="attention")

    noter("Budget tenu", couts["solde_mensuel"] >= 0,
          "Coût %s F CFA/mois, couvert." % format(couts["cout_par_mois"], ",d").replace(",", " ")
          if couts["solde_mensuel"] >= 0
          else "Dépassement de %s F CFA par mois."
               % format(-couts["solde_mensuel"], ",d").replace(",", " "), gravite="attention")

    collecte = sum(t["volume_m3"] for t in liste)
    produit = float(demande["m3_par_jour"].sum())
    part = collecte / produit if produit else 0
    noter("Déchets produits = collectés + non collectés", True,
          "%.0f m³ collectés aujourd'hui sur %.0f m³ produits par jour, soit %.0f %% ; "
          "le reste finit en dépotoir." % (collecte, produit, part * 100))

    return controles
