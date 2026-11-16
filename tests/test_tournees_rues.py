"""T15 : les tournées suivent les rues.

D'abord un petit réseau fabriqué à la main, où l'on connaît la réponse ; puis le vrai plan de
Ouagadougou, où l'on vérifie que chaque tracé part de la décharge, y revient, et passe par
tous les arrêts dans l'ordre.
"""

import csv
import gzip

import numpy as np

from application.plan import geometrie_tournee
from application.reseau import Reseau

VITESSES = {"seche": {"defaut": 36}}          # 36 km/h = 10 m/s : durées faciles à lire


def petit_reseau(tmp_path):
    """   0 ── 1 ── 2          Un carré : de 0 à 3, le chemin passe par 1 et 2.
          │         │          Le nœud 4 est isolé : aucun chemin n'y mène.
          5 ─────── 3   (le tronçon 0-5-3 est bien plus long : il ne doit pas être pris)  """
    noeuds = [(0, 0.0, 0.0), (1, 0.001, 0.0), (2, 0.002, 0.0), (3, 0.002, -0.001),
              (4, 0.01, 0.01), (5, 0.0, -0.001)]
    troncons = [(0, 1, 100), (1, 2, 100), (2, 3, 100), (0, 5, 500), (5, 3, 500)]
    with gzip.open(tmp_path / "reseau_noeuds.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "lon", "lat"]); w.writerows(noeuds)
    with gzip.open(tmp_path / "reseau_troncons.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["depart", "arrivee", "longueur_m", "classe", "revetu", "sens_unique"])
        w.writerows([(a, b, l, "residential", "1", "0") for a, b, l in troncons])
    return Reseau(str(tmp_path))


def test_le_chemin_suit_le_reseau(tmp_path):
    reseau = petit_reseau(tmp_path)
    durees, preds = reseau.durees_et_chemins([0, 3, 4], VITESSES, "seche")
    assert durees[0, 1] == 30                              # 300 m à 10 m/s, par 1 et 2
    assert reseau.chemin(preds[0], 0, 3) == [0, 1, 2, 3]
    assert reseau.chemin(preds[1], 3, 0) == [3, 2, 1, 0]   # double sens
    assert reseau.chemin(preds[0], 0, 4) is None           # nœud isolé : pas de chemin
    assert reseau.chemin(preds[0], 0, 0) == [0]
    # Mêmes durées que l'ancien calcul : seul le tracé s'ajoute.
    assert np.array_equal(durees, reseau.durees([0, 3, 4], [0, 3, 4], VITESSES, "seche"))


def test_sans_chemin_pas_de_trace_et_la_carte_garde_le_trait_droit(tmp_path):
    reseau = petit_reseau(tmp_path)
    noeuds = [0, 3, 4]                                     # décharge, arrêt joignable, arrêt isolé
    _, preds = reseau.durees_et_chemins(noeuds, VITESSES, "seche")
    depot = {"longitude": 0.0, "latitude": 0.0}
    passages = [{"longitude": 0.002, "latitude": -0.001}, {"longitude": 0.01, "latitude": 0.01}]
    trace = geometrie_tournee([1], noeuds, preds, passages, depot, reseau)
    assert trace[0] == trace[-1] == [0.0, 0.0]
    # Par la rue du haut (coin 0.002, 0) et non par le détour du nœud 5 (0, -0.001). Le point du
    # milieu de la rue droite (0.001, 0) est retiré par la simplification : c'est voulu.
    assert [0.002, -0.001] in trace and [0.002, 0.0] in trace and [0.0, -0.001] not in trace
    assert geometrie_tournee([2], noeuds, preds, passages, depot, reseau) is None


def test_le_vrai_plan_suit_les_rues_de_la_decharge_a_la_decharge(agent):
    plan = agent.post("/api/plan", json={}).get_json()
    decharge = [plan["decharge"]["longitude"], plan["decharge"]["latitude"]]
    assert plan["tournees"]
    sommets_en_plus = 0
    for tournee in plan["tournees"]:
        trace = tournee["geometrie"]
        assert trace is not None, tournee["camion"]
        assert trace[0] == trace[-1] == [round(x, 6) for x in decharge]
        # Chaque arrêt est un sommet du tracé, et ils viennent dans l'ordre de la tournée.
        rang = 0
        for etape in tournee["etapes"]:
            cible = [round(etape["longitude"], 6), round(etape["latitude"], 6)]
            rang = trace.index(cible, rang)                # lève une erreur si absent ou en désordre
        sommets_en_plus += len(trace) - (len(tournee["etapes"]) + 2)
    # Le tracé épouse les rues : bien plus de sommets que les seuls arrêts.
    assert sommets_en_plus > 10 * len(plan["tournees"])
