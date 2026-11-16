"""Outil d'aide à la décision pour l'assainissement — application Flask.

Un seul service : il sert l'interface (page de signalement, carte de décision), les fichiers de
données de la commune, et l'API. Aucune requête ne sort de la machine (exigence E14).
"""

import csv
import functools
import hashlib
import io
import json
import os
import secrets

from flask import (Blueprint, Flask, abort, jsonify, request, send_file,
                   send_from_directory, session)
from werkzeug.security import check_password_hash, generate_password_hash

from .base import connexion, creer
from .export_osm import en_osm, note_d_export
from .geo import Geographie
from .plan import repartir_la_demande
from .plan.calcul import calculer_le_plan, charger_geojson
from .simulation import simuler
from .reglages import Reglages
from .reseau import Reseau
from .signalements import Controleur, Depotoirs

vues = Blueprint("api", __name__)


def creer_application(reglages: Reglages = None) -> Flask:
    reglages = reglages or Reglages()
    creer(reglages.base)
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=reglages.secret_session or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=reglages.parametres["controles"]["photo_max_octets"] + 2_000_000,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        JSON_SORT_KEYS=False,
    )
    app.extensions["reglages"] = reglages
    app.extensions["geographie"] = Geographie(reglages.fichier("commune.geojson"),
                                              reglages.fichier("eau.geojson"))
    app.extensions["controleur"] = Controleur(app.extensions["geographie"], reglages.parametres)
    app.register_blueprint(vues)

    @app.after_request
    def entetes(reponse):
        # La page ne charge que ses propres fichiers : ni script, ni police, ni carte d'ailleurs.
        reponse.headers.setdefault("Content-Security-Policy",
                                   "default-src 'self'; img-src 'self' data: blob:; worker-src 'self' blob:; "
                                   "style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none'")
        reponse.headers.setdefault("X-Content-Type-Options", "nosniff")
        reponse.headers.setdefault("Referrer-Policy", "no-referrer")
        return reponse

    @app.errorhandler(413)
    def trop_gros(_):
        return jsonify({"erreur": "Envoi trop volumineux."}), 413

    @app.errorhandler(500)
    def panne(_):
        return jsonify({"erreur": "Erreur interne."}), 500

    return app


# ------------------------------------------------------------------ accès aux objets de l'application
def reglages() -> Reglages:
    from flask import current_app
    return current_app.extensions["reglages"]


def reseau() -> Reseau:
    """Le réseau routier est lu une seule fois : 111 000 carrefours, c'est long à relire."""
    from flask import current_app
    if "reseau" not in current_app.extensions:
        current_app.extensions["reseau"] = Reseau(current_app.extensions["reglages"].dossier_donnees)
    return current_app.extensions["reseau"]


def parametres_du_scenario(remplacements: dict = None) -> dict:
    """Les paramètres de départ, avec les changements demandés par-dessus.

    C'est par là que passent les modifications du jury : rien n'est écrit en dur, un paramètre
    change et tout le plan est recalculé (exigence E11)."""
    parametres = json.loads(json.dumps(reglages().parametres))     # copie, pour ne rien abîmer
    for cle, valeur in (remplacements or {}).items():
        if cle in parametres and isinstance(parametres[cle], dict) and isinstance(valeur, dict):
            parametres[cle].update(valeur)
        else:
            parametres[cle] = valeur
    return parametres


def controleur() -> Controleur:
    from flask import current_app
    return current_app.extensions["controleur"]


def depotoirs() -> Depotoirs:
    """Une connexion SQLite par requête : SQLite n'aime pas qu'on partage la même entre fils d'exécution."""
    from flask import current_app, g
    if "depotoirs" not in g:
        g.co = connexion(current_app.extensions["reglages"].base)
        g.depotoirs = Depotoirs(g.co, current_app.extensions["reglages"].parametres)
    return g.depotoirs


@vues.teardown_request
def fermer(_):
    from flask import g
    co = g.pop("co", None)
    if co is not None:
        co.close()


def agent_requis(vue):
    """Seul un agent connecté décide du sort d'un signalement."""
    @functools.wraps(vue)
    def emballage(*args, **kwargs):
        if not session.get("agent"):
            return jsonify({"erreur": "Connexion requise."}), 401
        if request.method != "GET" and not secrets.compare_digest(
                request.headers.get("X-Jeton", ""), session.get("jeton", "")):
            return jsonify({"erreur": "Jeton de session absent ou invalide."}), 403
        return vue(*args, **kwargs)
    return emballage


# ------------------------------------------------------------------ interface et données
@vues.route("/")
def accueil():
    return send_from_directory(os.path.join(reglages().dossier_interface, "decision"), "index.html")


@vues.route("/signaler/")
@vues.route("/signaler/<path:fichier>")
def page_signaler(fichier="index.html"):
    return send_from_directory(os.path.join(reglages().dossier_interface, "signaler"), fichier)


@vues.route("/decision/")
@vues.route("/decision/<path:fichier>")
def page_decision(fichier="index.html"):
    return send_from_directory(os.path.join(reglages().dossier_interface, "decision"), fichier)


@vues.route("/vendor/<path:fichier>")
def bibliotheques(fichier):
    return send_from_directory(os.path.join(reglages().dossier_interface, "vendor"), fichier,
                               max_age=604800)


@vues.route("/donnees/<path:fichier>")
def donnees(fichier):
    """Fichiers de la commune. `conditional` autorise les requêtes partielles, dont le fond de
    carte a besoin : il ne télécharge que les tuiles visibles à l'écran."""
    chemin = os.path.join(reglages().dossier_donnees, fichier)
    if not os.path.isfile(chemin) or not os.path.realpath(chemin).startswith(
            os.path.realpath(reglages().dossier_donnees)):
        abort(404)
    return send_file(chemin, conditional=True, max_age=3600)


# ------------------------------------------------------------------ API des signalements
@vues.route("/api/parametres")
def parametres():
    r = reglages()
    with open(r.fichier("commune.json"), encoding="utf-8") as f:
        commune = json.load(f)
    return jsonify({"commune": commune, "parametres": r.parametres})


@vues.route("/api/signalements", methods=["POST"])
def recevoir():
    """Un signalement : JSON du téléphone, ou formulaire avec photo."""
    if request.files or request.form:
        brut = {k: v for k, v in request.form.items()}
        photo = request.files.get("photo")
        if photo is not None:
            contenu = photo.read()
            if not controleur().controler_photo(contenu):
                resultat = depotoirs().enregistrer(
                    Controleur.resultat(controleur().examiner(brut), ["photo_invalide"]))
                return jsonify(resultat), 201
            brut["photo"] = enregistrer_photo(contenu)
    else:
        brut = request.get_json(silent=True)
    examine = controleur().examiner(brut)
    if isinstance(brut, dict) and brut.get("photo") and examine["statut"] != "rejete":
        examine["photo"] = brut["photo"]
    resultat = depotoirs().enregistrer(examine)
    return jsonify(resultat), 201 if resultat["nouveau"] else 200


def enregistrer_photo(contenu: bytes) -> str:
    """Photo rangée sous l'empreinte de son contenu : deux envois identiques ne font qu'un fichier."""
    dossier = reglages().dossier_photos
    os.makedirs(dossier, exist_ok=True)
    nom = hashlib.sha256(contenu).hexdigest()[:32] + ".img"
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        with open(chemin, "wb") as f:
            f.write(contenu)
    return nom


@vues.route("/api/signalements/lot", methods=["POST"])
def recevoir_lot():
    """Un lot : tableau JSON, GeoJSON, ou CSV. Répond ligne par ligne, jamais par une erreur globale."""
    try:
        lignes = lire_lot()
    except Exception as erreur:
        return jsonify({"erreur": f"Lot illisible : {erreur}"}), 400
    resultats = []
    for brut in lignes[:5000]:
        try:
            resultats.append(depotoirs().enregistrer(controleur().examiner(brut),
                                                     verifier_rafale=False))
        except Exception as erreur:        # une ligne piégée n'interrompt pas le lot
            resultats.append({"statut": "rejete", "motifs": ["format_invalide"], "detail": str(erreur)[:200]})
    comptes = {}
    for r in resultats:
        comptes[r["statut"]] = comptes.get(r["statut"], 0) + 1
    return jsonify({"recus": len(resultats), "comptes": comptes, "resultats": resultats}), 200


def lire_lot() -> list:
    """Accepte les trois formes que le jury peut nous donner."""
    fichier = next(iter(request.files.values()), None)
    contenu = fichier.read().decode("utf-8", "replace") if fichier else request.get_data(as_text=True)
    contenu = contenu.strip()
    if not contenu:
        return []
    if contenu[0] in "[{":
        donnees_lot = json.loads(contenu)
        if isinstance(donnees_lot, dict):
            if donnees_lot.get("type") == "FeatureCollection":       # GeoJSON
                return [depuis_geojson(e) for e in donnees_lot.get("features", [])]
            donnees_lot = donnees_lot.get("signalements", [donnees_lot])
        return donnees_lot if isinstance(donnees_lot, list) else [donnees_lot]
    return list(csv.DictReader(io.StringIO(contenu)))                 # CSV


def depuis_geojson(entite) -> dict:
    if not isinstance(entite, dict):
        return {}
    proprietes = dict(entite.get("properties") or {})
    coordonnees = ((entite.get("geometry") or {}).get("coordinates") or [None, None])
    if isinstance(coordonnees, list) and len(coordonnees) >= 2:
        proprietes.setdefault("longitude", coordonnees[0])
        proprietes.setdefault("latitude", coordonnees[1])
    return proprietes


@vues.route("/api/signalements")
def lister():
    return jsonify(depotoirs().liste(request.args.get("statut"), min(int(request.args.get("limite", 500)), 2000)))


@vues.route("/api/depotoirs")
def carte_depotoirs():
    """Les dépotoirs retenus, au format GeoJSON : c'est ce qu'affiche la carte."""
    strict = request.args.get("strict", "").lower() in ("1", "oui", "true")
    retenus = depotoirs().retenus(strict or reglages().parametres.get("mode_strict", False))
    return jsonify({"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [d["longitude"], d["latitude"]]},
         "properties": {k: d[k] for k in ("id", "volume_m3", "nb_signalements", "nb_sources",
                                          "premier_vu", "dernier_vu", "etat")}}
        for d in retenus]})


@vues.route("/api/plan", methods=["GET", "POST"])
def plan():
    """Le plan de gestion, recalculé à chaque appel avec les paramètres donnés.

    En GET : le plan de référence. En POST : le plan d'un scénario, les paramètres modifiés
    étant envoyés dans le corps de la requête."""
    from flask import current_app
    remplacements = request.get_json(silent=True) if request.method == "POST" else None
    if remplacements is not None and not isinstance(remplacements, dict):
        return jsonify({"erreur": "Les paramètres doivent être un objet."}), 400
    parametres = parametres_du_scenario(remplacements)
    try:
        resultat = calculer_le_plan(reglages(), reseau(), current_app.extensions["geographie"],
                                    parametres, depotoirs().retenus(parametres.get("mode_strict", False)))
    except (ValueError, KeyError, TypeError) as erreur:
        # Un paramètre absurde envoyé par le jury ne doit pas faire tomber le serveur.
        return jsonify({"erreur": "Plan impossible avec ces paramètres : %s" % erreur}), 400
    resultat["parametres_utilises"] = {cle: parametres[cle] for cle in (
        "population", "taux_abonnement", "nb_camions", "camions_en_panne", "capacite_camion_m3",
        "heures_travail", "frequence_collecte_jours", "capacite_point_m3", "saison",
        "budget_mensuel", "distance_max_precollecte_m", "effectif_brigade")}
    return jsonify(resultat)


def plan_et_simulation(parametres: dict, jours: int = 0) -> dict:
    """Calcule le plan, puis — si on le demande — fait tourner la simulation dessus."""
    from flask import current_app
    resultat = calculer_le_plan(reglages(), reseau(), current_app.extensions["geographie"],
                                parametres, depotoirs().retenus(parametres.get("mode_strict", False)))
    if jours > 0:
        demande = repartir_la_demande(charger_geojson(reglages().fichier("zones.geojson")), parametres)
        resultat["simulation"] = simuler(demande, resultat, parametres, jours=jours)
    return resultat


@vues.route("/api/scenario", methods=["POST"])
def scenario():
    """Un scénario complet : les paramètres donnés, le plan qui en découle, et la simulation.

    C'est ce qu'appelle le jury quand il change un paramètre : rien n'est pré-calculé."""
    envoi = request.get_json(silent=True) or {}
    if not isinstance(envoi, dict):
        return jsonify({"erreur": "Envoi invalide."}), 400
    jours = max(0, min(int(envoi.get("jours", 30) or 0), 180))
    try:
        parametres = parametres_du_scenario(envoi.get("parametres"))
        resultat = plan_et_simulation(parametres, jours)
    except (ValueError, KeyError, TypeError) as erreur:
        return jsonify({"erreur": "Scénario impossible : %s" % erreur}), 400
    resultat["nom"] = str(envoi.get("nom", "Scénario"))[:80]
    resultat["parametres_utilises"] = {cle: parametres[cle] for cle in (
        "population", "taux_abonnement", "nb_camions", "camions_en_panne", "capacite_camion_m3",
        "heures_travail", "frequence_collecte_jours", "capacite_point_m3", "saison",
        "budget_mensuel", "distance_max_precollecte_m", "effectif_brigade")}
    return jsonify(resultat)


@vues.route("/api/comparer", methods=["POST"])
def comparer():
    """Deux scénarios côte à côte, avec leurs écarts (exigence E5)."""
    envoi = request.get_json(silent=True) or {}
    scenarios = envoi.get("scenarios") if isinstance(envoi, dict) else None
    if not isinstance(scenarios, list) or not 2 <= len(scenarios) <= 4:
        return jsonify({"erreur": "Donnez entre deux et quatre scénarios."}), 400
    jours = max(0, min(int(envoi.get("jours", 30) or 0), 180))
    resultats = []
    for numero, demande in enumerate(scenarios, start=1):
        if not isinstance(demande, dict):
            return jsonify({"erreur": "Scénario %d invalide." % numero}), 400
        try:
            parametres = parametres_du_scenario(demande.get("parametres"))
            resultat = plan_et_simulation(parametres, jours)
        except (ValueError, KeyError, TypeError) as erreur:
            return jsonify({"erreur": "Scénario %d impossible : %s" % (numero, erreur)}), 400
        resume = resultat.get("simulation", {}).get("resume", {})
        resultats.append({
            "nom": str(demande.get("nom", "Scénario %d" % numero))[:80],
            "parametres_utilises": {cle: parametres[cle] for cle in (
                "nb_camions", "camions_en_panne", "taux_abonnement",
                "frequence_collecte_jours", "capacite_point_m3", "saison")},
            "points": len(resultat["points"]),
            "tournees": len(resultat["tournees"]),
            "non_desservis": len(resultat["non_desservis"]),
            "km_par_jour": resultat["couts"]["km_par_jour"],
            "cout_par_mois": resultat["couts"]["cout_par_mois"],
            "solde_mensuel": resultat["couts"]["solde_mensuel"],
            "taux_collecte": resume.get("taux_collecte"),
            "volume_depotoirs_m3": resume.get("volume_depotoirs_m3"),
            "points_satures": resume.get("points_satures"),
            "controles_en_defaut": [c["nom"] for c in resultat["controles"] if c["etat"] != "ok"],
        })
    return jsonify({"jours": jours, "scenarios": resultats})


@vues.route("/api/export/osm")
def export_osm():
    """Les dépotoirs VÉRIFIÉS, au format d'OpenStreetMap, à relire avant tout versement (E12)."""
    verifies = [d for d in depotoirs().retenus(mode_strict=True)]
    for d in verifies:
        ligne = depotoirs().co.execute(
            "SELECT type, dernier_vu FROM signalements s JOIN depotoirs dd ON dd.id = s.depotoir_id"
            " WHERE dd.id = ? ORDER BY s.id DESC LIMIT 1", (d["id"],)).fetchone()
        d["type"] = ligne["type"] if ligne else "autre"
    fichier = en_osm(verifies, note_d_export(len(verifies)))
    return app_reponse_osm(fichier, len(verifies))


def app_reponse_osm(contenu: str, nombre: int):
    from flask import Response
    return Response(contenu, mimetype="application/xml", headers={
        "Content-Disposition": 'attachment; filename="depotoirs-verifies.osm"',
        "X-Depotoirs": str(nombre)})


@vues.route("/api/comptes")
def comptes():
    return jsonify(depotoirs().comptes())


@vues.route("/api/connexion", methods=["POST"])
def connecter():
    r = reglages()
    envoi = request.get_json(silent=True) or {}
    attendu = r.agent_mot_de_passe
    if not attendu:
        return jsonify({"erreur": "Aucun compte d'agent configuré (AGENT_MOT_DE_PASSE)."}), 503
    empreinte = attendu if attendu.startswith(("pbkdf2:", "scrypt:")) else generate_password_hash(attendu)
    if envoi.get("nom") != r.agent_nom or not check_password_hash(empreinte, envoi.get("mot_de_passe", "")):
        return jsonify({"erreur": "Identifiant ou mot de passe incorrect."}), 401
    session.clear()
    session["agent"] = r.agent_nom
    session["jeton"] = secrets.token_urlsafe(32)
    return jsonify({"agent": r.agent_nom, "jeton": session["jeton"]})


@vues.route("/api/session")
def session_en_cours():
    """La page de vérification demande si un agent est déjà connecté (la session dure 
    le temps du navigateur)."""
    if not session.get("agent"):
        return jsonify({"agent": None}), 401
    return jsonify({"agent": session["agent"], "jeton": session["jeton"]})


@vues.route("/api/deconnexion", methods=["POST"])
def deconnecter():
    session.clear()
    return jsonify({"ok": True})


@vues.route("/api/signalements/<int:identifiant>/verifier", methods=["POST"])
@agent_requis
def verifier(identifiant):
    return (jsonify({"ok": True}) if depotoirs().decider(identifiant, True)
            else (jsonify({"erreur": "Signalement inconnu."}), 404))


@vues.route("/api/signalements/<int:identifiant>/rejeter", methods=["POST"])
@agent_requis
def rejeter(identifiant):
    return (jsonify({"ok": True}) if depotoirs().decider(identifiant, False)
            else (jsonify({"erreur": "Signalement inconnu."}), 404))
