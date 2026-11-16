"""Réseau routier : durées de trajet entre points, par le vrai réseau de voies.

Les voies viennent d'OpenStreetMap (donnees/<commune>/reseau_*.csv.gz). La durée d'un tronçon
dépend de sa catégorie, de son revêtement et de la saison : en saison des pluies, une piste en
terre se parcourt bien plus lentement. C'est ce qui permet au plan de changer quand le jury
annonce la saison des pluies (exigence E11).

Aucune cartographie n'est recalculée ici : on lit un graphe déjà préparé et on applique
l'algorithme de Dijkstra (SciPy).
"""

import csv
import gzip
import os

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree


class Reseau:
    def __init__(self, dossier: str):
        self.noeuds = self._lire_noeuds(os.path.join(dossier, "reseau_noeuds.csv.gz"))
        (self.departs, self.arrivees, self.longueurs,
         self.classes, self.revetus, self.sens_uniques) = self._lire_troncons(
            os.path.join(dossier, "reseau_troncons.csv.gz"))
        # L'arbre permet de trouver en un instant le nœud le plus proche d'un point quelconque.
        self._arbre = cKDTree(self.noeuds)
        self._cache_graphe = {}

    @staticmethod
    def _lire_noeuds(chemin) -> np.ndarray:
        with gzip.open(chemin, "rt", encoding="utf-8") as f:
            lignes = list(csv.reader(f))[1:]
        return np.array([(float(l[1]), float(l[2])) for l in lignes], dtype=np.float64)

    @staticmethod
    def _lire_troncons(chemin):
        departs, arrivees, longueurs, classes, revetus, sens = [], [], [], [], [], []
        with gzip.open(chemin, "rt", encoding="utf-8") as f:
            for l in csv.DictReader(f):
                departs.append(int(l["depart"]))
                arrivees.append(int(l["arrivee"]))
                longueurs.append(float(l["longueur_m"]))
                classes.append(l["classe"])
                revetus.append(l["revetu"])
                sens.append(l["sens_unique"] == "1")
        return (np.array(departs), np.array(arrivees), np.array(longueurs, dtype=np.float64),
                np.array(classes), np.array(revetus), np.array(sens, dtype=bool))

    @property
    def nb_noeuds(self) -> int:
        return len(self.noeuds)

    def noeud_le_plus_proche(self, lon: float, lat: float) -> int:
        return int(self._arbre.query([lon, lat])[1])

    def noeuds_les_plus_proches(self, points) -> np.ndarray:
        if not len(points):
            return np.array([], dtype=int)
        return self._arbre.query(np.asarray(points, dtype=np.float64))[1].astype(int)

    # ------------------------------------------------------------------ graphe des durées
    def graphe(self, vitesses: dict, saison: str) -> csr_matrix:
        """Durée de parcours de chaque tronçon, en secondes, pour la saison donnée."""
        cle = (saison, tuple(sorted(vitesses.get(saison, {}).items(), key=lambda kv: str(kv[0]))))
        if cle in self._cache_graphe:
            return self._cache_graphe[cle]
        table = vitesses[saison]
        kmh = np.full(len(self.longueurs), float(table.get("defaut", 20)))
        for classe, valeur in table.items():
            if classe in ("defaut", "non_revetu"):
                continue
            kmh[self.classes == classe] = float(valeur)
        # Une voie non revêtue est plus lente ; la pénalité est plus forte en saison des pluies.
        kmh[self.revetus == "0"] *= float(table.get("non_revetu", 1))
        secondes = self.longueurs / (kmh * 1000 / 3600)
        # Les voies à double sens se parcourent dans les deux sens : on ajoute l'arête inverse.
        double = ~self.sens_uniques
        d = np.concatenate([self.departs, self.arrivees[double]])
        a = np.concatenate([self.arrivees, self.departs[double]])
        t = np.concatenate([secondes, secondes[double]])
        graphe = csr_matrix((t, (d, a)), shape=(self.nb_noeuds, self.nb_noeuds))
        self._cache_graphe[cle] = graphe
        return graphe

    def durees(self, sources, cibles, vitesses: dict, saison: str, par_paquet: int = 48):
        """Matrice des durées (secondes) entre des nœuds de départ et des nœuds d'arrivée.

        Le calcul se fait par paquets de sources : sur une ville entière, demander tout d'un
        coup remplirait la mémoire du PC."""
        sources, cibles = np.asarray(sources, dtype=int), np.asarray(cibles, dtype=int)
        graphe = self.graphe(vitesses, saison)
        resultat = np.empty((len(sources), len(cibles)), dtype=np.float32)
        for debut in range(0, len(sources), par_paquet):
            paquet = sources[debut:debut + par_paquet]
            distances = dijkstra(graphe, directed=True, indices=paquet)
            resultat[debut:debut + len(paquet)] = distances[:, cibles]
        return resultat
