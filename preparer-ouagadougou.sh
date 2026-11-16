#!/usr/bin/env bash
# Prépare les données de Ouagadougou sur le PC de l'équipe, puis les envoie dans le dépôt.
#
#   ./preparer-ouagadougou.sh
#
# 1. trouve (ou télécharge) l'extrait OpenStreetMap du Burkina Faso ;
# 2. lance donnees/preparer.py ;
# 3. télécharge le fond de carte (si cela échoue, on continue : il se refait plus tard) ;
# 4. enregistre le résultat dans Git et le pousse.
#
# Sous Windows : à lancer depuis « Git Bash ». Internet est nécessaire.
set -uo pipefail
cd "$(dirname "$0")"

SOURCE="https://download.geofabrik.de/africa/burkina-faso-latest.osm.pbf"
COMMUNE="Ouagadougou"
DOSSIER="donnees/ouagadougou"
JOURNAL="comptes-rendus/T3-preparation.txt"

# Python de l'environnement .venv s'il existe, sinon celui du système.
if   [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ];         then PY=.venv/bin/python
elif command -v python  >/dev/null;   then PY=python
else PY=python3; fi
if ! "$PY" -c "import osmium, shapely, pyproj, scipy, numpy" 2>/dev/null; then
  echo "Installation des bibliothèques Python…"
  "$PY" -m pip install -r donnees/requirements.txt || { echo "Installation impossible."; exit 1; }
fi

# L'extrait : celui déjà téléchargé près du dépôt, sinon ../telechargements/.
EXTRAIT="${EXTRAIT:-$(find .. -maxdepth 3 -name 'burkina-faso*.osm.pbf' 2>/dev/null | head -1)}"
EXTRAIT="${EXTRAIT:-../telechargements/burkina-faso-latest.osm.pbf}"
mkdir -p "$(dirname "$EXTRAIT")"
# Un téléchargement interrompu laisse un fichier incomplet : on vérifie qu'il se lit jusqu'au bout.
extrait_lisible() {
  "$PY" -c "
import sys, osmium
for _ in osmium.FileProcessor(sys.argv[1], osmium.osm.RELATION):
    pass
" "$1" 2>/dev/null
}
if [ -f "$EXTRAIT" ] && extrait_lisible "$EXTRAIT"; then
  echo "Extrait déjà présent et complet."
else
  if [ -f "$EXTRAIT" ]; then
    echo "Extrait incomplet : reprise du téléchargement…"
    curl -L --fail -C - -o "$EXTRAIT" "$SOURCE"
  fi
  if ! { [ -f "$EXTRAIT" ] && extrait_lisible "$EXTRAIT"; }; then
    echo "Téléchargement complet de l'extrait (une centaine de Mo)…"
    curl -L --fail -o "$EXTRAIT" "$SOURCE" || { echo "Téléchargement impossible : vérifiez la connexion."; exit 1; }
    extrait_lisible "$EXTRAIT" || { echo "Extrait illisible après téléchargement."; exit 1; }
  fi
fi
echo "Extrait utilisé : $EXTRAIT ($(wc -c < "$EXTRAIT" | tr -d ' ') octets)"

{ echo "Préparation lancée le $(date '+%d/%m/%Y à %H:%M') sur $(uname -s)"; echo; } > "$JOURNAL"
"$PY" donnees/preparer.py --extrait "$EXTRAIT" --commune "$COMMUNE" 2>&1 | tee -a "$JOURNAL"
resultat=${PIPESTATUS[0]}
if [ "$resultat" -ne 0 ] && grep -q "Aucune limite administrative" "$JOURNAL"; then
  # La limite de la commune manque ou est cassée dans l'extrait : on prend un rectangle autour de la ville.
  echo "Limite de la commune introuvable : nouvel essai avec un rectangle autour de Ouagadougou." | tee -a "$JOURNAL"
  "$PY" donnees/preparer.py --extrait "$EXTRAIT" --commune "$COMMUNE" --bbox=-1.72,12.22,-1.36,12.52 2>&1 | tee -a "$JOURNAL"
  resultat=${PIPESTATUS[0]}
fi
if [ "$resultat" -ne 0 ]; then
  echo "La préparation a échoué : envoyez une capture d'écran au coordinateur." | tee -a "$JOURNAL"
  ECHEC=1
fi

if [ -z "${ECHEC:-}" ]; then
  { echo; echo "--- Fond de carte"; } >> "$JOURNAL"
  "$PY" donnees/fond_de_carte.py 2>&1 | tee -a "$JOURNAL"
  [ "${PIPESTATUS[0]}" -eq 0 ] || echo "Fond de carte non téléchargé : on continue sans lui pour l'instant." | tee -a "$JOURNAL"
fi

[ -n "${SANS_GIT:-}" ] && exit "${ECHEC:-0}"
# GitHub refuse les fichiers de plus de 100 Mo : on laisse de côté ce qui dépasse 90 Mo.
git add "$JOURNAL" .gitignore
[ -z "${ECHEC:-}" ] && for f in "$DOSSIER"/*; do
  if [ "$(wc -c < "$f" | tr -d ' ')" -lt 90000000 ]; then git add "$f"
  else echo "Trop gros pour le dépôt, laissé sur ce PC : $f" | tee -a "$JOURNAL"; git add "$JOURNAL"; fi
done
git commit -q -m "T3 : données de $COMMUNE préparées sur le PC" && git pull -q --rebase && git push -q \
  && echo "Envoyé dans le dépôt. Dites au coordinateur : « les données sont poussées »." \
  || echo "Rien de nouveau à envoyer, ou envoi impossible : faites une capture d'écran pour le coordinateur."
