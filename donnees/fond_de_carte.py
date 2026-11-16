"""Télécharge le fond de carte d'une commune : un seul fichier PMTiles, servi ensuite par notre machine.

    python donnees/fond_de_carte.py                 (commune par défaut : donnees/ouagadougou)

Le fond vient des constructions quotidiennes de Protomaps, fabriquées à partir d'OpenStreetMap.
L'outil « pmtiles » ne télécharge que les morceaux qui couvrent l'emprise de la commune. Il faut
Internet une seule fois, ici ; ensuite la carte s'affiche sans aucune connexion (exigence E14).

Données © les contributeurs d'OpenStreetMap, licence ODbL. Outil pmtiles : licence BSD-3.
N'utilise que la bibliothèque standard de Python.
"""

import argparse
import datetime
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ICI = os.path.dirname(os.path.abspath(__file__))
OUTILS = os.path.join(ICI, "outils")            # hors dépôt (voir .gitignore)
VERSIONS = "https://api.github.com/repos/protomaps/go-pmtiles/releases/latest"
CONSTRUCTIONS = "https://build.protomaps.com/{jour}.pmtiles"


def ouvrir(adresse, entetes=None, delai=60):
    requete = urllib.request.Request(adresse, headers={"User-Agent": "pegasus-finale-2026", **(entetes or {})})
    return urllib.request.urlopen(requete, timeout=delai)


def outil_pmtiles() -> str:
    """Chemin de l'outil pmtiles : déjà présent, ou téléchargé depuis sa page de versions GitHub."""
    nom = "pmtiles.exe" if platform.system() == "Windows" else "pmtiles"
    local = os.path.join(OUTILS, nom)
    if os.path.isfile(local):
        return local
    if shutil.which("pmtiles"):
        return shutil.which("pmtiles")
    systeme = {"Windows": "windows", "Linux": "linux", "Darwin": "darwin"}[platform.system()]
    processeur = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    print("Recherche de l'outil pmtiles…", flush=True)
    version = json.load(ouvrir(VERSIONS))
    fichiers = [f for f in version["assets"]
                if systeme in f["name"].lower() and processeur in f["name"].lower()]
    if not fichiers:
        sys.exit(f"Aucun outil pmtiles pour {systeme} {processeur} dans la version {version['tag_name']}.")
    print(f"Téléchargement de {fichiers[0]['name']} ({version['tag_name']})…", flush=True)
    archive = ouvrir(fichiers[0]["browser_download_url"], delai=300).read()
    os.makedirs(OUTILS, exist_ok=True)
    if fichiers[0]["name"].endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            membre = next(m for m in z.namelist() if os.path.basename(m) == nom)
            with open(local, "wb") as f:
                f.write(z.read(membre))
    else:
        with tarfile.open(fileobj=io.BytesIO(archive)) as t:
            membre = next(m for m in t.getmembers() if os.path.basename(m.name) == nom)
            with open(local, "wb") as f:
                f.write(t.extractfile(membre).read())
        os.chmod(local, 0o755)
    return local


def construction_recente(jour_voulu=None) -> str:
    """Adresse de la construction la plus récente qui répond (on remonte jusqu'à dix jours)."""
    jours = [jour_voulu] if jour_voulu else [
        (datetime.date.today() - datetime.timedelta(days=n)).strftime("%Y%m%d") for n in range(10)]
    for jour in jours:
        adresse = CONSTRUCTIONS.format(jour=jour)
        try:
            # Un fichier PMTiles commence par les lettres « PMTiles » : on ne lit que cela.
            if ouvrir(adresse, {"Range": "bytes=0-6"}, delai=30).read(7) == b"PMTiles":
                return adresse
        except Exception:
            continue
    sys.exit("Aucune construction Protomaps accessible (réseau coupé, ou adresse changée).\n"
             "La liste des constructions est sur https://maps.protomaps.com/builds : relancez avec --jour AAAAMMJJ.")


def principal():
    sys.stdout.reconfigure(errors="replace")
    p = argparse.ArgumentParser(add_help=False, description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-h", "--aide", "--help", action="help", help="affiche cette aide")
    p.add_argument("--dossier", default=os.path.join(ICI, "ouagadougou"), help="dossier de la commune (défaut : donnees/ouagadougou)")
    p.add_argument("--zoom-max", type=int, default=15, help="zoom le plus détaillé (défaut : 15, le maximum)")
    p.add_argument("--jour", help="construction à utiliser, AAAAMMJJ (défaut : la plus récente)")
    a = p.parse_args()

    resume = os.path.join(a.dossier, "commune.json")
    if not os.path.isfile(resume):
        sys.exit(f"{resume} introuvable : lancez d'abord donnees/preparer.py.")
    with open(resume, encoding="utf-8") as f:
        emprise = json.load(f)["emprise_avec_marge"]
    try:
        outil = outil_pmtiles()
    except Exception as erreur:            # pas de réseau, GitHub injoignable…
        sys.exit(f"Outil pmtiles introuvable et téléchargement impossible : {erreur}")
    source = construction_recente(a.jour)
    sortie = os.path.join(a.dossier, "fond.pmtiles")
    commande = [outil, "extract", source, sortie,
                "--bbox=" + ",".join(str(v) for v in emprise),
                f"--maxzoom={a.zoom_max}", "--download-threads=4"]
    print("Lancement : " + " ".join(commande), flush=True)
    if subprocess.run(commande).returncode != 0 or not os.path.isfile(sortie):
        sys.exit("L'extraction du fond de carte a échoué.")
    print(f"Fond de carte écrit : {sortie} ({os.path.getsize(sortie) / 1e6:.1f} Mo), source {source}")


if __name__ == "__main__":
    principal()
