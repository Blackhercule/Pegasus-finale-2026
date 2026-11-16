"""Vérifie donnees/preparer.py sur une petite commune inventée (aucun téléchargement).

La commune d'essai est un rectangle d'environ 16 km × 13 km placé à Ouagadougou. Elle contient
un quadrillage de rues, un îlot de rues isolé, des bâtiments, un barrage, une mare trop petite,
un canal, une école, un marché et une décharge.
"""

import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
OUEST, SUD, EST, NORD = -1.60, 12.30, -1.45, 12.42


class Carte:
    """Petit générateur de fichier OpenStreetMap (XML)."""

    def __init__(self):
        self.noeuds, self.voies, self.relations, self.n = [], [], [], 0

    def noeud(self, lon, lat, **etiquettes):
        self.n += 1
        self.noeuds.append((self.n, lon, lat, etiquettes))
        return self.n

    def voie(self, refs, **etiquettes):
        self.n += 1
        self.voies.append((self.n, refs, etiquettes))
        return self.n

    def rectangle(self, ouest, sud, est, nord, **etiquettes):
        coins = [self.noeud(ouest, sud), self.noeud(est, sud), self.noeud(est, nord), self.noeud(ouest, nord)]
        return self.voie(coins + [coins[0]], **etiquettes)

    def limite(self, ouest, sud, est, nord, nom, niveau):
        contour = self.rectangle(ouest, sud, est, nord)
        self.n += 1
        self.relations.append((self.n, contour, {"type": "boundary", "boundary": "administrative",
                                                 "name": nom, "admin_level": str(niveau)}))

    def xml(self):
        def balises(e):
            return "".join(f'<tag k="{k}" v="{v}"/>' for k, v in e.items())
        lignes = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6" generator="essai">']
        for i, lon, lat, e in self.noeuds:
            lignes.append(f'<node id="{i}" version="1" lon="{lon}" lat="{lat}">{balises(e)}</node>')
        for i, refs, e in self.voies:
            nd = "".join(f'<nd ref="{r}"/>' for r in refs)
            lignes.append(f'<way id="{i}" version="1">{nd}{balises(e)}</way>')
        for i, contour, e in self.relations:
            lignes.append(f'<relation id="{i}" version="1"><member type="way" ref="{contour}" role="outer"/>'
                          f'{balises(e)}</relation>')
        return "\n".join(lignes + ["</osm>"])


@pytest.fixture(scope="module")
def sortie(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("commune")
    c = Carte()
    # Un département plus grand et la commune portent le même nom : la commune doit être choisie.
    c.limite(OUEST - 0.3, SUD - 0.3, EST + 0.3, NORD + 0.3, "Ouagadougou", 6)
    c.limite(OUEST, SUD, EST, NORD, "Ouagadougou", 8)
    c.limite(OUEST, SUD, -1.525, NORD, "Arrondissement 1", 9)
    c.limite(OUEST, SUD, -1.56, 12.36, "Secteur 1", 10)
    # Quadrillage de rues : 4 colonnes × 4 lignes, croisées à des nœuds communs.
    colonnes = [OUEST + 0.01 + i * 0.04 for i in range(4)]
    rangees = [SUD + 0.01 + j * 0.03 for j in range(4)]
    grille = [[c.noeud(x, y) for x in colonnes] for y in rangees]
    for j in range(4):
        c.voie(grille[j], highway="residential", surface="dirt")
    for i in range(4):
        c.voie([grille[j][i] for j in range(4)], highway="primary", surface="asphalt")
    c.voie([grille[0][0], grille[1][1]], highway="tertiary", oneway="-1")      # sens unique à rebours
    c.voie([c.noeud(-1.47, 12.31), c.noeud(-1.465, 12.31)], highway="residential")  # îlot isolé
    c.voie([grille[0][3], c.noeud(-1.46, 12.305)], highway="footway")          # sentier : ignoré
    # Bâtiments : trois dans le secteur 1, un hors de la commune.
    for k in range(3):
        c.rectangle(-1.59 + k * 0.0005, 12.32, -1.5899 + k * 0.0005, 12.3201, building="yes")
    c.rectangle(-1.30, 12.35, -1.2999, 12.3501, building="yes")
    # Eau : un barrage, et une mare trop petite pour être gardée.
    c.rectangle(-1.52, 12.38, -1.515, 12.385, natural="water", name="Barrage d'essai")
    c.rectangle(-1.50, 12.33, -1.49995, 12.33005, natural="water")
    c.voie([c.noeud(-1.55, 12.31), c.noeud(-1.50, 12.35)], waterway="canal", name="Canal d'essai")
    # Lieux.
    c.noeud(-1.57, 12.34, amenity="school", name="École d'essai")
    c.noeud(-1.53, 12.36, amenity="marketplace")
    c.rectangle(-1.48, 12.40, -1.475, 12.405, landuse="landfill", name="Décharge d'essai")
    extrait = dossier / "essai.osm"
    extrait.write_text(c.xml(), encoding="utf-8")
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "donnees" / "preparer.py"), "--extrait", str(extrait),
         "--commune", "ouagadougou", "--sortie", str(dossier / "sortie"), "--marge-km", "2"],
        capture_output=True, text=True, encoding="utf-8")
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    return dossier / "sortie"


def geojson(dossier, nom):
    return json.loads((dossier / nom).read_text(encoding="utf-8"))["features"]


def lignes_csv(dossier, nom):
    with gzip.open(dossier / nom, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_la_commune_est_choisie_parmi_les_limites_du_meme_nom(sortie):
    resume = json.loads((sortie / "commune.json").read_text(encoding="utf-8"))
    assert resume["niveau_administratif"] == 8
    assert 190 < resume["surface_km2"] < 240          # environ 16 km × 13 km
    assert resume["epsg_metrique"] == 32630
    assert resume["bbox"] == [OUEST, SUD, EST, NORD]


def test_secteurs_et_arrondissements(sortie):
    noms = {(s["properties"]["nom"], s["properties"]["niveau"]) for s in geojson(sortie, "secteurs.geojson")}
    assert noms == {("Arrondissement 1", 9), ("Secteur 1", 10)}


def test_reseau_d_un_seul_tenant(sortie):
    noeuds = lignes_csv(sortie, "reseau_noeuds.csv.gz")
    troncons = lignes_csv(sortie, "reseau_troncons.csv.gz")
    assert len(noeuds) == 16                           # les 16 carrefours ; ni l'îlot ni le sentier
    assert [n["id"] for n in noeuds] == [str(i) for i in range(16)]
    assert len(troncons) == 12 + 12 + 1                # 12 tronçons de rue, 12 d'avenue, la diagonale
    assert {t["classe"] for t in troncons} == {"residential", "primary", "tertiary"}
    assert {t["revetu"] for t in troncons} == {"0", "1", ""}
    # Tous les tronçons relient des nœuds gardés.
    assert all(0 <= int(t["depart"]) < 16 and 0 <= int(t["arrivee"]) < 16 for t in troncons)
    resume = json.loads((sortie / "commune.json").read_text(encoding="utf-8"))
    assert resume["comptes"]["noeuds_isoles_ecartes"] == 2
    assert 15 < resume["trajet_de_controle_km"] < 30


def test_sens_unique_a_rebours_est_retourne(sortie):
    noeuds = {n["id"]: (float(n["lon"]), float(n["lat"])) for n in lignes_csv(sortie, "reseau_noeuds.csv.gz")}
    diagonale = [t for t in lignes_csv(sortie, "reseau_troncons.csv.gz") if t["classe"] == "tertiary"][0]
    assert diagonale["sens_unique"] == "1"
    # Tracée du coin sud-ouest vers le nord-est avec oneway=-1 : elle se parcourt du nord-est au sud-ouest.
    assert noeuds[diagonale["depart"]][1] > noeuds[diagonale["arrivee"]][1]


def test_longueur_d_un_troncon(sortie):
    rue = [t for t in lignes_csv(sortie, "reseau_troncons.csv.gz") if t["classe"] == "residential"][0]
    assert 4200 < float(rue["longueur_m"]) < 4500      # 0,04° de longitude à cette latitude : environ 4,35 km


def test_batiments_comptes_par_carreau(sortie):
    zones = geojson(sortie, "zones.geojson")
    assert sum(z["properties"]["nb_batiments"] for z in zones) == 3     # celui hors commune est écarté
    assert {z["properties"]["secteur"] for z in zones} == {"Secteur 1"}
    assert all(z["properties"]["surface_batie_m2"] > 0 for z in zones)


def test_eau_et_cours_d_eau(sortie):
    eau = geojson(sortie, "eau.geojson")
    assert [e["properties"]["nom"] for e in eau] == ["Barrage d'essai"]  # la mare de 30 m² est écartée
    assert geojson(sortie, "cours_eau.geojson")[0]["properties"]["type"] == "canal"


def test_lieux(sortie):
    types = sorted(l["properties"]["type"] for l in geojson(sortie, "lieux.geojson"))
    assert types == ["decharge", "ecole", "marche"]
