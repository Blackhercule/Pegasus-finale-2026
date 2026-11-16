"""Prépare les fichiers d'une commune à partir d'un extrait OpenStreetMap (.osm.pbf).

    python donnees/preparer.py --extrait burkina-faso-latest.osm.pbf --commune Ouagadougou

Le script lit l'extrait deux fois :
  1. les SURFACES : limites administratives (pour trouver la commune et ses secteurs) et plans d'eau ;
  2. les OBJETS situés dans l'emprise de la commune : voies, bâtiments, lieux utiles, cours d'eau.

Il écrit dans donnees/<commune>/ les fichiers décrits dans docs/conception.md. Rien n'est propre
à Ouagadougou : une autre commune se prépare avec la même commande et un autre nom (exigence E13).

Données © les contributeurs d'OpenStreetMap, licence ODbL.
Bibliothèques : pyosmium (lecture), Shapely (géométrie), pyproj (projection), SciPy (graphe).
"""

import argparse
import csv
import gzip
import json
import math
import os
import sys
import time
import unicodedata
from collections import Counter

import numpy as np
import osmium
import shapely
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from shapely import wkb
from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.prepared import prep

# Voies où un camion ou une charrette peut passer (valeurs de l'étiquette « highway »).
VOIES_CARROSSABLES = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
    "living_street", "service", "track", "road",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}
# Valeurs de l'étiquette « surface » : voie revêtue ou non. Toute autre valeur : inconnu.
REVETUES = {"paved", "asphalt", "concrete", "concrete:plates", "concrete:lanes", "paving_stones",
            "sett", "cobblestone", "unhewn_cobblestone", "metal", "wood", "bricks"}
NON_REVETUES = {"unpaved", "dirt", "ground", "earth", "sand", "gravel", "fine_gravel", "compacted",
                "laterite", "mud", "grass", "pebblestone", "clay", "rock"}
# Lieux utiles au plan : étiquette OpenStreetMap -> type simplifié.
TYPES_DE_LIEUX = {
    "school": "ecole", "kindergarten": "ecole", "college": "ecole", "university": "ecole",
    "hospital": "sante", "clinic": "sante", "doctors": "sante", "health_post": "sante",
    "marketplace": "marche",
    "waste_transfer_station": "dechets", "waste_disposal": "dechets", "recycling": "dechets",
    "waste_dump_site": "dechets",
}
COURS_D_EAU = {"river", "stream", "canal", "drain", "ditch"}
SURFACE_MIN_EAU_M2 = 200          # en dessous, une mare n'est pas gardée
SURFACE_MIN_COMMUNE_KM2 = 20      # une « commune » plus petite est en réalité un quartier


def sans_accents(texte: str) -> str:
    """« Ouagadougou », « OUAGADOUGOU » et « Ouagadougou » accentué se comparent de la même façon."""
    decompose = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold().strip()


def nom_de_dossier(nom: str) -> str:
    """« Bobo-Dioulasso » -> « bobo-dioulasso » : le dossier de la commune."""
    return "".join(c if c.isalnum() else "-" for c in sans_accents(nom)).strip("-")


def distance_m(lon1, lat1, lon2, lat2) -> float:
    """Distance à vol d'oiseau entre deux points (formule de haversine), en mètres."""
    rayon_terre = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * rayon_terre * math.asin(math.sqrt(a))


def surface_m2(points) -> float:
    """Surface d'un petit polygone (lon, lat), par la formule du lacet sur un plan local en mètres."""
    lat0 = math.radians(points[0][1])
    kx, ky = 111320.0 * math.cos(lat0), 110540.0   # mètres par degré de longitude et de latitude
    somme = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        somme += (x1 * kx) * (y2 * ky) - (x2 * kx) * (y1 * ky)
    return abs(somme) / 2


def projection_metrique(lon: float, lat: float) -> int:
    """Code EPSG de la zone UTM qui contient le point (Ouagadougou : 32630)."""
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


# --------------------------------------------------------------------------- 1. surfaces
def lire_surfaces(extrait: str):
    """Première lecture : limites administratives nommées et plans d'eau, sous forme de polygones."""
    # Seules ces étiquettes nous intéressent : le filtre évite d'assembler toutes les surfaces du pays.
    utiles = osmium.filter.TagFilter(("boundary", "administrative"), ("natural", "water"),
                                     ("landuse", "reservoir"), ("landuse", "basin"),
                                     ("waterway", "riverbank"), ("waterway", "dock"))
    lecteur = (osmium.FileProcessor(extrait)
               .with_areas(utiles)
               .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA))
               .with_filter(utiles))
    fabrique = osmium.geom.WKBFactory()
    limites, eaux = [], []
    for surface in lecteur:
        e = surface.tags
        est_limite = e.get("boundary") == "administrative" and e.get("name")
        est_eau = (e.get("natural") == "water" or e.get("landuse") in ("reservoir", "basin")
                   or e.get("waterway") in ("riverbank", "dock"))
        if not (est_limite or est_eau):
            continue
        try:
            geometrie = wkb.loads(fabrique.create_multipolygon(surface), hex=True)
        except Exception:      # contour ouvert ou cassé dans OpenStreetMap : on l'ignore
            continue
        if est_limite:
            try:
                niveau = int(e.get("admin_level", ""))
            except ValueError:
                niveau = 0
            limites.append({"nom": e.get("name"), "niveau": niveau, "geometrie": geometrie,
                            "id_osm": surface.orig_id(), "relation": not surface.from_way()})
        else:
            eaux.append({"nom": e.get("name", ""), "geometrie": geometrie,
                         "intermittent": e.get("intermittent") == "yes" or e.get("seasonal") == "yes"})
    return limites, eaux


def choisir_commune(limites, nom, relation=None, niveau=None):
    """Trouve la limite de la commune parmi les limites administratives portant son nom."""
    cible = sans_accents(nom)
    prefixes = ("commune de ", "commune urbaine de ", "commune rurale de ", "ville de ", "")
    candidates = []
    for l in limites:
        n = sans_accents(l["nom"])
        if any(n == p + cible for p in prefixes):
            l["km2"] = surface_km2(l["geometrie"])
            candidates.append(l)
    if relation is not None:
        candidates = [l for l in limites if l["id_osm"] == relation]
        for l in candidates:
            l["km2"] = surface_km2(l["geometrie"])
    if not candidates:
        proches = sorted({l["nom"] for l in limites if cible[:5] in sans_accents(l["nom"])})[:15]
        sys.exit(f"Aucune limite administrative nommée « {nom} » dans l'extrait.\n"
                 f"Noms approchants : {', '.join(proches) or 'aucun'}.\n"
                 "Essayez --relation <identifiant OpenStreetMap> ou --bbox ouest,sud,est,nord.")
    print(f"Limites nommées « {nom} » trouvées :")
    for l in sorted(candidates, key=lambda l: l["niveau"]):
        print(f"   niveau {l['niveau']:>2} · {l['km2']:>9.1f} km² · identifiant {l['id_osm']}")
    if niveau is not None:
        candidates = [l for l in candidates if l["niveau"] == niveau] or sys.exit(
            f"Aucune limite de niveau {niveau} pour « {nom} ».")
    # La commune est l'entité la plus locale qui porte ce nom, sans être un simple quartier.
    assez_grandes = [l for l in candidates if l["km2"] >= SURFACE_MIN_COMMUNE_KM2] or candidates
    choisie = max(assez_grandes, key=lambda l: (l["niveau"], -l["km2"]))
    print(f"-> retenue : niveau {choisie['niveau']}, {choisie['km2']:.1f} km² "
          "(pour en choisir une autre : --niveau ou --relation)")
    return choisie


def surface_km2(geometrie) -> float:
    """Surface réelle d'un polygone en km², calculée après projection en mètres."""
    centre = geometrie.representative_point()
    vers_m = Transformer.from_crs(4326, projection_metrique(centre.x, centre.y), always_xy=True)

    def projeter(points):                  # tableau de (lon, lat) -> tableau de (x, y) en mètres
        x, y = vers_m.transform(points[:, 0], points[:, 1])
        return np.column_stack([x, y])

    return shapely.transform(geometrie, projeter).area / 1e6


# --------------------------------------------------------------------------- 2. objets
def lire_objets(extrait: str, emprise):
    """Seconde lecture : voies, bâtiments, lieux et cours d'eau situés dans l'emprise (ouest, sud, est, nord)."""
    ouest, sud, est, nord = emprise

    def dedans(lon, lat):
        return ouest <= lon <= est and sud <= lat <= nord

    lecteur = (osmium.FileProcessor(extrait)
               .with_locations()
               .with_filter(osmium.filter.KeyFilter("highway", "building", "amenity", "landuse",
                                                    "healthcare", "waterway")))
    voies, batiments, lieux, cours_eau = [], [], [], []
    for o in lecteur:
        e = o.tags
        if o.is_node():
            genre = type_de_lieu(e)
            if genre and o.location.valid() and dedans(o.lon, o.lat):
                lieux.append(lieu(genre, e, o.lon, o.lat, f"node/{o.id}"))
            continue
        if not o.is_way() or len(o.nodes) < 2:
            continue
        voie = e.get("highway") in VOIES_CARROSSABLES
        cours = e.get("waterway") in COURS_D_EAU
        premier = o.nodes[0].location
        if not premier.valid():
            continue
        if not (voie or cours) and not dedans(premier.lon, premier.lat):
            continue                      # le pays compte des millions de bâtiments : on écarte vite ceux d'ailleurs
        points = [(n.lon, n.lat) for n in o.nodes if n.location.valid()]
        if len(points) != len(o.nodes):
            continue                      # voie dont un point manque dans l'extrait
        if "building" in e:
            if dedans(*points[0]) and len(points) >= 4:
                contour = points[:-1] if points[0] == points[-1] else points
                lon = sum(p[0] for p in contour) / len(contour)
                lat = sum(p[1] for p in contour) / len(contour)
                batiments.append((lon, lat, surface_m2(contour)))
        if voie and any(dedans(*p) for p in points) \
                and e.get("access") not in ("no", "private") and e.get("area") != "yes":
            refs = [n.ref for n in o.nodes]
            sens = e.get("oneway")
            if sens in ("-1", "reverse"):                 # sens unique à rebours du tracé
                refs, points, sens = refs[::-1], points[::-1], "yes"
            unique = sens in ("yes", "1", "true") or e.get("junction") == "roundabout" \
                or e.get("highway") == "motorway"
            surface = e.get("surface", "")
            revetu = 1 if surface in REVETUES else 0 if surface in NON_REVETUES else ""
            voies.append({"refs": refs, "points": points, "classe": e["highway"],
                          "revetu": revetu, "sens_unique": 1 if unique else 0})
        if cours and any(dedans(*p) for p in points):
            cours_eau.append({"type": e["waterway"], "nom": e.get("name", ""), "points": points})
        genre = type_de_lieu(e)
        if genre and dedans(*points[0]):
            lon = sum(p[0] for p in points) / len(points)
            lat = sum(p[1] for p in points) / len(points)
            lieux.append(lieu(genre, e, lon, lat, f"way/{o.id}"))
    return voies, batiments, lieux, cours_eau


def type_de_lieu(etiquettes):
    """« ecole », « sante », « marche », « dechets », « decharge », ou None."""
    if etiquettes.get("landuse") == "landfill":
        return "decharge"
    return TYPES_DE_LIEUX.get(etiquettes.get("amenity")) or (
        "sante" if etiquettes.get("healthcare") in ("hospital", "clinic", "centre", "doctor") else None)


def lieu(genre, etiquettes, lon, lat, identifiant):
    sous_type = etiquettes.get("amenity") or etiquettes.get("landuse") or etiquettes.get("healthcare", "")
    return {"type": genre, "sous_type": sous_type, "nom": etiquettes.get("name", ""),
            "osm": identifiant, "lon": lon, "lat": lat}


# --------------------------------------------------------------------------- 3. réseau
def construire_reseau(voies):
    """Transforme les voies en graphe : nœuds = carrefours et extrémités, tronçons entre deux nœuds.

    Seule la plus grande partie d'un seul tenant est gardée : un trajet existe alors toujours
    entre deux points du réseau."""
    usage = Counter()
    for v in voies:
        usage.update(v["refs"])
        usage[v["refs"][0]] += 1          # une extrémité est toujours un nœud du graphe
        usage[v["refs"][-1]] += 1
    position, troncons = {}, []
    for v in voies:
        debut, longueur = 0, 0.0
        for i in range(1, len(v["refs"])):
            longueur += distance_m(*v["points"][i - 1], *v["points"][i])
            if usage[v["refs"][i]] > 1:   # carrefour ou extrémité : on ferme le tronçon
                a, b = v["refs"][debut], v["refs"][i]
                if a != b and longueur > 0:
                    position[a], position[b] = v["points"][debut], v["points"][i]
                    troncons.append((a, b, longueur, v["classe"], v["revetu"], v["sens_unique"]))
                debut, longueur = i, 0.0
    if not troncons:
        sys.exit("Aucune voie carrossable trouvée dans l'emprise de la commune.")
    # Numérotation compacte 0..n-1, puis recherche de la plus grande partie connexe.
    numero = {ref: i for i, ref in enumerate(position)}
    departs = np.array([numero[t[0]] for t in troncons])
    arrivees = np.array([numero[t[1]] for t in troncons])
    n = len(numero)
    graphe = coo_matrix((np.ones(len(troncons)), (departs, arrivees)), shape=(n, n))
    _, etiquette = connected_components(graphe, directed=False)
    principale = np.bincount(etiquette).argmax()
    garde = etiquette == principale
    nouveau = np.cumsum(garde) - 1        # ancien numéro -> nouveau numéro parmi les nœuds gardés
    coordonnees = list(position.values())
    noeuds = [(int(nouveau[i]), coordonnees[i][0], coordonnees[i][1]) for i in range(n) if garde[i]]
    aretes = [(int(nouveau[d]), int(nouveau[a]), t[2], t[3], t[4], t[5])
              for d, a, t in zip(departs, arrivees, troncons) if garde[d]]
    return noeuds, aretes, n - len(noeuds)


def trajet_de_controle(noeuds, aretes, emprise):
    """Distance par le réseau entre les nœuds les plus proches de deux coins opposés (en km)."""
    lon = np.array([p[1] for p in noeuds])
    lat = np.array([p[2] for p in noeuds])
    ouest, sud, est, nord = emprise
    depart = int(np.argmin((lon - ouest) ** 2 + (lat - sud) ** 2))
    arrivee = int(np.argmin((lon - est) ** 2 + (lat - nord) ** 2))
    n = len(noeuds)
    # Pour ce contrôle, toutes les voies sont prises dans les deux sens.
    d = [a[0] for a in aretes] + [a[1] for a in aretes]
    a = [a[1] for a in aretes] + [a[0] for a in aretes]
    poids = [x[2] for x in aretes] * 2
    graphe = coo_matrix((poids, (d, a)), shape=(n, n)).tocsr()
    return float(dijkstra(graphe, indices=depart)[arrivee]) / 1000


# --------------------------------------------------------------------------- 4. carreaux
def construire_zones(batiments, commune, secteurs, epsg, cote_m):
    """Grille de carreaux : nombre de bâtiments et surface bâtie par carreau, dans la commune."""
    vers_m = Transformer.from_crs(4326, epsg, always_xy=True)
    vers_deg = Transformer.from_crs(epsg, 4326, always_xy=True)
    cumul = {}
    if batiments:
        xs, ys = vers_m.transform([b[0] for b in batiments], [b[1] for b in batiments])
        for x, y, (_, _, surface) in zip(xs, ys, batiments):
            cle = (int(x // cote_m), int(y // cote_m))
            carreau = cumul.setdefault(cle, [0, 0.0])
            carreau[0] += 1
            carreau[1] += surface
    dans_commune = prep(commune)
    # Du plus fin au plus large : un carreau porte le nom de son secteur avant celui de son arrondissement.
    decoupages = [(s["nom"], prep(s["geometrie"]))
                  for s in sorted(secteurs, key=lambda s: -s["niveau"])]
    zones = []
    for (ix, iy), (nombre, surface) in sorted(cumul.items()):
        x0, y0 = ix * cote_m, iy * cote_m
        lon_c, lat_c = vers_deg.transform(x0 + cote_m / 2, y0 + cote_m / 2)
        centre = Point(lon_c, lat_c)
        if not dans_commune.contains(centre):
            continue
        coins = [vers_deg.transform(x, y) for x, y in
                 ((x0, y0), (x0 + cote_m, y0), (x0 + cote_m, y0 + cote_m), (x0, y0 + cote_m))]
        secteur = next((nom for nom, zone in decoupages if zone.contains(centre)), "")
        zones.append({"id": f"{ix}_{iy}", "nb_batiments": nombre, "surface_batie_m2": round(surface),
                      "secteur": secteur, "geometrie": Polygon(coins)})
    return zones


# --------------------------------------------------------------------------- 5. écriture
def arrondi(valeur, chiffres=6):
    """Arrondit toutes les coordonnées d'une géométrie GeoJSON (6 décimales : environ 10 cm)."""
    if isinstance(valeur, (list, tuple)):
        return [arrondi(v, chiffres) for v in valeur]
    return round(valeur, chiffres) if isinstance(valeur, float) else valeur


def ecrire_geojson(chemin, entites):
    """entites : liste de (géométrie Shapely, propriétés)."""
    collection = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": proprietes,
         "geometry": {"type": mapping(g)["type"], "coordinates": arrondi(mapping(g)["coordinates"])}}
        for g, proprietes in entites]}
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, separators=(",", ":"))


def ecrire_csv_gz(chemin, entete, lignes):
    with gzip.open(chemin, "wt", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(entete)
        ecrivain.writerows(lignes)


def taille(chemin) -> str:
    octets = os.path.getsize(chemin)
    return f"{octets / 1e6:.1f} Mo" if octets >= 1e6 else f"{max(1, round(octets / 1e3))} ko"


# --------------------------------------------------------------------------- programme
def arguments():
    p = argparse.ArgumentParser(add_help=False, description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-h", "--aide", "--help", action="help", help="affiche cette aide")
    p.add_argument("--extrait", required=True, help="fichier OpenStreetMap .osm.pbf (ex. extrait Geofabrik du pays)")
    p.add_argument("--commune", required=True, help="nom de la commune, tel qu'écrit dans OpenStreetMap")
    p.add_argument("--sortie", help="dossier d'écriture (défaut : donnees/<commune>/)")
    p.add_argument("--niveau", type=int, help="niveau administratif (admin_level) de la commune, s'il faut choisir")
    p.add_argument("--relation", type=int, help="identifiant OpenStreetMap de la limite, s'il faut choisir")
    p.add_argument("--bbox", help="ouest,sud,est,nord : emprise à utiliser si la commune n'a pas de limite cartographiée")
    p.add_argument("--marge-km", type=float, default=5, help="marge autour de la commune pour les voies et les lieux (défaut : 5)")
    p.add_argument("--carreau-m", type=int, default=250, help="côté des carreaux de la grille (défaut : 250)")
    return p.parse_args()


def principal():
    sys.stdout.reconfigure(errors="replace")   # un caractère que la console ne sait pas afficher ne doit pas tout arrêter
    a = arguments()
    if not os.path.isfile(a.extrait):
        sys.exit(f"Extrait introuvable : {a.extrait}")
    sortie = a.sortie or os.path.join(os.path.dirname(os.path.abspath(__file__)), nom_de_dossier(a.commune))
    os.makedirs(sortie, exist_ok=True)
    debut = time.time()

    print("1/4  Lecture des limites administratives et des plans d'eau…", flush=True)
    limites, eaux = lire_surfaces(a.extrait)
    if a.bbox:
        ouest, sud, est, nord = (float(x) for x in a.bbox.split(","))
        commune = {"nom": a.commune, "niveau": 0, "geometrie": box(ouest, sud, est, nord), "id_osm": None}
        commune["km2"] = surface_km2(commune["geometrie"])
    else:
        commune = choisir_commune(limites, a.commune, a.relation, a.niveau)
    contour = commune["geometrie"]
    dans_commune = prep(contour)
    secteurs = [l for l in limites if l["niveau"] > commune["niveau"] and l is not commune
                and dans_commune.contains(l["geometrie"].representative_point())]
    ouest, sud, est, nord = contour.bounds
    centre_lat = (sud + nord) / 2
    marge_lat = a.marge_km / 110.54
    marge_lon = a.marge_km / (111.32 * math.cos(math.radians(centre_lat)))
    emprise = (ouest - marge_lon, sud - marge_lat, est + marge_lon, nord + marge_lat)
    cadre = box(*emprise)
    epsg = projection_metrique((ouest + est) / 2, centre_lat)
    eaux = [e for e in eaux if e["geometrie"].intersects(cadre)]
    for e in eaux:
        e["m2"] = surface_km2(e["geometrie"]) * 1e6
    eaux = [e for e in eaux if e["m2"] >= SURFACE_MIN_EAU_M2]

    print("2/4  Lecture des voies, des bâtiments et des lieux…", flush=True)
    voies, batiments, lieux, cours_eau = lire_objets(a.extrait, emprise)

    print("3/4  Construction du réseau et de la grille…", flush=True)
    noeuds, aretes, ecartes = construire_reseau(voies)
    zones = construire_zones(batiments, contour, secteurs, epsg, a.carreau_m)
    km = trajet_de_controle(noeuds, aretes, contour.bounds)
    if not math.isfinite(km):
        sys.exit("Le réseau n'est pas d'un seul tenant : aucun trajet entre deux coins de la commune.")

    print("4/4  Écriture des fichiers…", flush=True)
    f = lambda nom: os.path.join(sortie, nom)
    ecrire_geojson(f("commune.geojson"), [(contour, {"nom": commune["nom"], "niveau": commune["niveau"]})])
    ecrire_geojson(f("secteurs.geojson"),
                   [(s["geometrie"].simplify(0.00002), {"nom": s["nom"], "niveau": s["niveau"]}) for s in secteurs])
    ecrire_geojson(f("eau.geojson"),
                   [(e["geometrie"].simplify(0.00002),
                     {"nom": e["nom"], "intermittent": e["intermittent"], "surface_m2": round(e["m2"])}) for e in eaux])
    ecrire_geojson(f("cours_eau.geojson"),
                   [(LineString(c["points"]), {"type": c["type"], "nom": c["nom"]}) for c in cours_eau])
    ecrire_geojson(f("zones.geojson"),
                   [(z["geometrie"], {k: z[k] for k in ("id", "nb_batiments", "surface_batie_m2", "secteur")})
                    for z in zones])
    ecrire_geojson(f("lieux.geojson"),
                   [(Point(l["lon"], l["lat"]), {k: l[k] for k in ("type", "sous_type", "nom", "osm")}) for l in lieux])
    ecrire_csv_gz(f("reseau_noeuds.csv.gz"), ["id", "lon", "lat"],
                  [(i, f"{lon:.7f}", f"{lat:.7f}") for i, lon, lat in noeuds])
    ecrire_csv_gz(f("reseau_troncons.csv.gz"),
                  ["depart", "arrivee", "longueur_m", "classe", "revetu", "sens_unique"],
                  [(d, ar, f"{longueur:.1f}", classe, revetu, sens) for d, ar, longueur, classe, revetu, sens in aretes])
    revetement_connu = sum(1 for t in aretes if t[4] != "") / len(aretes)
    lecteur = osmium.io.Reader(a.extrait)
    entete = lecteur.header()
    lecteur.close()
    resume = {
        "nom": commune["nom"], "bbox": [round(v, 6) for v in contour.bounds],
        "emprise_avec_marge": [round(v, 6) for v in emprise],
        "epsg_metrique": epsg, "surface_km2": round(commune["km2"], 1),
        "niveau_administratif": commune["niveau"], "id_osm": commune["id_osm"],
        "carreau_m": a.carreau_m,
        "extrait": {"fichier": os.path.basename(a.extrait),
                    "octets": os.path.getsize(a.extrait),
                    "date_des_donnees": entete.get("osmosis_replication_timestamp", "") or entete.get("timestamp", "")},
        "source": "OpenStreetMap, extrait Geofabrik", "licence": "ODbL 1.0 — © les contributeurs d'OpenStreetMap",
        "comptes": {"noeuds": len(noeuds), "troncons": len(aretes), "noeuds_isoles_ecartes": ecartes,
                    "carreaux_batis": len(zones), "batiments": sum(z["nb_batiments"] for z in zones),
                    "secteurs": len(secteurs), "plans_d_eau": len(eaux), "cours_d_eau": len(cours_eau),
                    "lieux": dict(Counter(l["type"] for l in lieux)),
                    "part_revetement_connu": round(revetement_connu, 3)},
        "trajet_de_controle_km": round(km, 1),
    }
    with open(f("commune.json"), "w", encoding="utf-8") as fichier:
        json.dump(resume, fichier, ensure_ascii=False, indent=2)

    c = resume["comptes"]
    print(f"\nCommune : {commune['nom']} — {commune['km2']:.1f} km² (projection EPSG:{epsg})")
    print(f"Réseau : {c['noeuds']} nœuds, {c['troncons']} tronçons "
          f"({ecartes} nœuds isolés écartés ; revêtement connu pour {revetement_connu:.0%} des tronçons)")
    print(f"Trajet de contrôle entre deux coins opposés : {km:.1f} km par le réseau")
    print(f"Carreaux bâtis : {c['carreaux_batis']} ({c['batiments']} bâtiments) · "
          f"secteurs : {c['secteurs']} · plans d'eau : {c['plans_d_eau']} · cours d'eau : {c['cours_d_eau']}")
    niveaux = Counter(s["niveau"] for s in secteurs)
    print("Découpages trouvés : " + (", ".join(f"niveau {n} × {k}" for n, k in sorted(niveaux.items())) or "aucun"))
    print("Lieux : " + (", ".join(f"{k} × {v}" for k, v in sorted(c["lieux"].items())) or "aucun"))
    print(f"\nFichiers écrits dans {sortie} :")
    for nom in sorted(os.listdir(sortie)):
        print(f"   {nom:<28} {taille(f(nom))}")
    print(f"Terminé en {time.time() - debut:.0f} s.")


if __name__ == "__main__":
    principal()
