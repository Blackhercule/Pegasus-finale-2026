#!/usr/bin/env bash
# Lance l'application sur ce PC (Windows avec Git Bash, Linux ou macOS).
# Les téléphones connectés au même Wi-Fi peuvent l'ouvrir avec l'adresse IP du PC.
set -e
cd "$(dirname "$0")"

# Réglages facultatifs lus dans .env (voir .env.exemple). Le fichier est lu ligne à ligne,
# jamais exécuté : une valeur avec des espaces ou une fin de ligne Windows ne pose pas de problème.
if [ -f .env ]; then
  while IFS='=' read -r cle valeur || [ -n "$cle" ]; do
    case "$cle" in ''|\#*) continue ;; esac
    [[ "$cle" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    valeur="${valeur%$'\r'}"
    valeur="${valeur%\"}"; valeur="${valeur#\"}"
    export "$cle=$valeur"
  done < .env
fi

# Sous Windows, « python3 » ouvre parfois le Microsoft Store : on prend « python »
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PYTHON=python ;;
  *) PYTHON=python3 ;;
esac

if [ ! -d .venv ]; then "$PYTHON" -m venv .venv; fi
if [ -f .venv/Scripts/activate ]; then . .venv/Scripts/activate; else . .venv/bin/activate; fi
python -m pip install -q -r requirements.txt
python manage.py migrate --no-input

# Premier lancement : on demande le mot de passe du patron s'il n'est pas dans .env
if ! python manage.py shell -c "import sys; from cave.models import Utilisateur as U; sys.exit(0 if U.objects.filter(role='patron').exists() else 1)" >/dev/null 2>&1; then
  if [ -z "$PATRON_MOT_DE_PASSE" ]; then
    read -r -s -p "Choisissez le mot de passe du patron (8 caractères minimum) : " PATRON_MOT_DE_PASSE
    echo
    export PATRON_MOT_DE_PASSE
  fi
fi
python manage.py initialiser_cave
if [ "${DONNEES_DEMO:-non}" = "oui" ]; then python manage.py charger_demo; fi

echo
echo "L'application est prête : ouvrez http://localhost:8000"
echo "Identifiant du patron : ${PATRON_IDENTIFIANT:-patron}"
echo "Pour l'arrêter : Ctrl + C"
python manage.py runserver 0.0.0.0:8000
