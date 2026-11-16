#!/usr/bin/env bash
# Installation de l'outil d'assainissement en une commande.
#
#   ./installer.sh                     sur cet ordinateur seulement (https://localhost:8443)
#   ./installer.sh 192.168.1.20        accessible aux téléphones du réseau (adresse IP du PC)
#   ./installer.sh --changer-adresse 10.0.0.5
#                                      nouveau réseau : garde les signalements déjà collectés
#   ./installer.sh --reinitialiser     efface tout et recommence
#
# Sous Windows : lancer depuis « Git Bash », avec Docker Desktop démarré.
set -euo pipefail
# Git Bash (Windows) : ne pas transformer les chemins destinés aux conteneurs.
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")"

adresse_valide() {
  case "$1" in
    ""|*[!A-Za-z0-9.-]*) echo "Adresse invalide : « $1 » (exemple : 192.168.1.20)."; exit 1 ;;
  esac
}

CHANGEMENT_ADRESSE=""
if [ "${1:-}" = "--changer-adresse" ]; then
  [ -f .env ] || { echo "Aucune installation ici : lancez d'abord ./installer.sh ${2:-<adresse>}"; exit 1; }
  CHANGEMENT_ADRESSE="${2:-}"
  adresse_valide "$CHANGEMENT_ADRESSE"
  shift 2
fi

if [ "${1:-}" = "--reinitialiser" ]; then
  shift
  read -r -p "Tous les signalements collectés seront effacés. Continuer ? (oui/non) " reponse
  [ "$reponse" = "oui" ] || exit 1
  docker compose down -v || true
  rm -f .env ca-assainissement.crt
fi

command -v docker >/dev/null || { echo "Docker est requis (Docker Desktop sous Windows)."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 est requis."; exit 1; }
[ -f donnees/ouagadougou/commune.json ] || {
  echo "Les données de la commune sont absentes : lancez d'abord ./preparer-ouagadougou.sh"; exit 1; }

secret() { openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

if [ ! -f .env ]; then
  DOMAINE="${1:-localhost}"
  adresse_valide "$DOMAINE"
  PORT_HTTPS="${PORT_HTTPS:-8443}"
  umask 077
  cat > .env <<FIN
# Créé par installer.sh le $(date '+%d/%m/%Y %H:%M'). Ne jamais publier ce fichier.
COMMUNE=ouagadougou
DOMAINE=$DOMAINE
PORT_HTTPS=$PORT_HTTPS
# Un compte par poste : mairie, brigade Laabal, équipe de collecte, et l'ONEA pour
# les fuites d'eau.
AGENT_NOM=agent
AGENT_MOT_DE_PASSE=$(secret | cut -c1-16)
BRIGADE_NOM=brigade
BRIGADE_MOT_DE_PASSE=$(secret | cut -c1-16)
COLLECTE_NOM=collecte
COLLECTE_MOT_DE_PASSE=$(secret | cut -c1-16)
ONEA_NOM=onea
ONEA_MOT_DE_PASSE=$(secret | cut -c1-16)
SECRET_SESSION=$(secret)
FIN
  echo "Fichier .env créé, avec un mot de passe par poste, tiré au hasard."
elif [ -n "${1:-}" ]; then
  echo "Une installation existe déjà. Pour changer d'adresse : ./installer.sh --changer-adresse $1"
  exit 1
fi

if [ -n "$CHANGEMENT_ADRESSE" ]; then
  sed -i.precedent -e "s#^DOMAINE=.*#DOMAINE=$CHANGEMENT_ADRESSE#" .env
  rm -f .env.precedent
  echo "Nouvelle adresse : $CHANGEMENT_ADRESSE (signalements et certificat conservés)."
fi

# Une installation plus ancienne n'a pas tous les comptes : on ajoute ceux qui manquent
# sans rien effacer, pour ne pas perdre les signalements déjà reçus.
if [ -f .env ]; then
  for poste in BRIGADE COLLECTE ONEA; do
    if ! grep -q "^${poste}_MOT_DE_PASSE=" .env; then
      minuscule=$(echo "$poste" | tr "[:upper:]" "[:lower:]")
      printf '%s_NOM=%s\n%s_MOT_DE_PASSE=%s\n' "$poste" "$minuscule" "$poste" "$(secret | cut -c1-16)" >> .env
      echo "Compte « $minuscule » ajouté à .env."
    fi
  done
fi

port_voulu="${PORT_HTTPS:-}"
set -a; . ./.env; set +a
if [ -n "$port_voulu" ] && [ "$port_voulu" != "$PORT_HTTPS" ]; then
  sed -i.precedent -e "s#^PORT_HTTPS=.*#PORT_HTTPS=$port_voulu#" .env
  rm -f .env.precedent
  PORT_HTTPS="$port_voulu"
  echo "Nouveau port : $PORT_HTTPS."
fi
ADRESSE="https://$DOMAINE:$PORT_HTTPS"

# Un autre conteneur occupe-t-il déjà notre port ? (la messagerie du sprint utilisait le 8443)
occupant=$(docker ps --filter "publish=$PORT_HTTPS" --format "{{.Names}}" 2>/dev/null \
           | grep -v "^assainissement-ouaga" || true)
if [ -n "$occupant" ]; then
  echo "Le port $PORT_HTTPS est déjà pris par : $occupant"
  echo "Arrêtez-le (rien n'est effacé, il redémarre avec « docker compose start ») :"
  echo "    docker stop $occupant"
  echo "Ou choisissez un autre port :  PORT_HTTPS=8444 ./installer.sh"
  exit 1
fi

echo "Construction et démarrage (la première fois : quelques minutes)…"
if ! docker compose up -d --build; then
  # Deux causes possibles : pas d'Internet pour reconstruire, ou un port occupé. Dans le
  # second cas, repartir sans rien dire donnerait un démarrage à moitié fait.
  if docker compose up -d 2>&1 | tee /tmp/assainissement-demarrage.txt | grep -qi "already allocated\|port is already"; then
    echo "Le port $PORT_HTTPS est occupé. Voyez quel programme le tient :"
    echo "    docker ps --filter publish=$PORT_HTTPS"
    echo "Ou choisissez un autre port :  PORT_HTTPS=8444 ./installer.sh"
    exit 1
  fi
  echo "(Reconstruction impossible — pas d'Internet ? — démarrage avec les images existantes.)"
fi

# --ssl-no-revoke : sous Windows, curl veut vérifier la révocation auprès d'un service extérieur ;
# notre autorité est interne. Les sorties sont jetées par « >/dev/null » et non par « -o /dev/null »,
# que curl.exe ne sait pas écrire sous Git Bash.
echo -n "Attente du démarrage"
pret=""
for _ in $(seq 1 60); do
  if docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./ca-assainissement.crt >/dev/null 2>&1 \
     && curl -fsS --ssl-no-revoke --cacert ca-assainissement.crt "$ADRESSE/api/comptes" >/dev/null 2>&1; then
    pret="oui"; echo " : prêt."; break
  fi
  echo -n "."; sleep 4
done
if [ -z "$pret" ]; then
  # On dit ce qui bloque, au lieu d'un simple « échec ».
  echo " : pas prêt."
  if ! docker compose ps --status running --services 2>/dev/null | grep -q application; then
    echo "L'application ne tourne pas. Ses dernières lignes de journal :"
    docker compose logs --tail=25 application
  elif ! docker compose exec -T application python -c "import urllib.request;
urllib.request.urlopen('http://127.0.0.1:8000/api/comptes', timeout=10)" >/dev/null 2>&1; then
    echo "L'application tourne mais ne répond pas encore. Ses dernières lignes de journal :"
    docker compose logs --tail=25 application
  else
    echo "L'application répond, mais pas à travers le HTTPS : c'est Caddy ou le certificat."
    docker compose logs --tail=25 caddy
  fi
  echo
  echo "Relancez ./installer.sh après avoir corrigé, ou envoyez ces lignes au coordinateur."
  exit 1
fi

cat <<FIN

  Carte de décision      : $ADRESSE/decision/
  Vérifier les signalements : $ADRESSE/decision/verifier.html
  Signaler (téléphone)   : $ADRESSE/signaler/

  Postes de travail     : $ADRESSE/decision/dossiers.html
  Fuites d'eau (ONEA)   : $ADRESSE/decision/fuites.html
  Comparer des scénarios : $ADRESSE/decision/scenarios.html

  Un compte par poste (mots de passe dans .env) :
    Mairie            « $AGENT_NOM »     $AGENT_MOT_DE_PASSE
    Brigade Laabal    « $BRIGADE_NOM »   $BRIGADE_MOT_DE_PASSE
    Équipe de collecte « $COLLECTE_NOM » $COLLECTE_MOT_DE_PASSE
    ONEA (fuites d'eau) « $ONEA_NOM »  $ONEA_MOT_DE_PASSE

  Certificat : le HTTPS utilise une autorité INTERNE. Pour que les navigateurs et les
  téléphones lui fassent confiance, installez ca-assainissement.crt :
    Windows : certutil -user -addstore Root ca-assainissement.crt
    Téléphone : ouvrez $ADRESSE/ca-assainissement.crt et suivez l'installation.
  Sans ce certificat, le téléphone refusera de donner sa position et l'appareil photo.
FIN
openssl x509 -in ca-assainissement.crt -noout -fingerprint -sha256 2>/dev/null | sed 's/^/  Empreinte : /' || true
