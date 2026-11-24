#!/usr/bin/env bash
# Construction de l'application, lancée par Render à chaque déploiement.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
# Crée le compte patron au premier déploiement (ne touche jamais un compte existant)
python manage.py initialiser_cave
# Données fictives pour essayer l'application (seulement si la base n'a aucun produit)
if [ "${DONNEES_DEMO:-non}" = "oui" ]; then
  python manage.py charger_demo
fi
