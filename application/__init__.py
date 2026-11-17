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
import threading
import time

from flask import (Blueprint, Flask, abort, jsonify, request, send_file,
                   send_from_directory, session)
from werkzeug.security import check_password_hash, generate_password_hash

from .base import connexion, creer
from .dossiers import CHAINE, POSTES, Dossiers, ErreurDossier
from .export_osm import en_osm, note_d_export
from .export_geojson import en_geojson
from .fuites import AMPLEUR_NOMS, CHAINE_EAU, ErreurFuite, Fuites
from .anonymiser import disponible as masquage_disponible, masquer
from .inspection import base_du_service, tournees_d_inspection
from .priorite import Priorite
from .nuisances import (CHAINE_NUISANCE, GRAVITE_NOMS, NATURES as NATURES_NUISANCE,
                        ErreurNuisance, Nuisances)
from .geo import Geographie
from .lieux import charger_lieux
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
    # Les lieux connus (marchés, écoles, santé), lus une fois : T16.
    app.extensions["lieux"] = charger_lieux(reglages.fichier("lieux.geojson"))
    app.extensions["controleur"] = Controleur(app.extensions["geographie"], reglages.parametres,
                                              app.extensions["lieux"])
    # La file priorisée : les lieux sensibles et la densité sont chargés une fois, au
    # démarrage, pour que le classement d'une file de plusieurs milliers de dossiers reste
    # instantané quand le jury en injecte un lot.
    app.extensions["priorite"] = Priorite(
        fichier_lieux=reglages.fichier("lieux.geojson"),
        fichier_zones=reglages.fichier("zones.geojson"),
        geo=app.extensions["geographie"],
        poids=reglages.parametres.get("priorite"))
    app.register_blueprint(vues)

    @app.before_request
    def porte_d_entree():
        """Tout est fermé, sauf ce qui est ouvert au public (liste blanche, voir OUVERT_A_TOUS)."""
        return filtrer_l_acces()

    @app.after_request
    def entetes(reponse):
        # La page ne charge que ses propres fichiers : ni script, ni police, ni carte d'ailleurs.
        reponse.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; worker-src 'self' blob:; "
            # blob: est nécessaire pour réécouter un message vocal avant de l'envoyer.
            "media-src 'self' blob:; "
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


def dossiers() -> Dossiers:
    from flask import g
    depotoirs()                       # ouvre la connexion si besoin
    if "dossiers" not in g:
        g.dossiers = Dossiers(g.co)
    return g.dossiers


def fuites() -> Fuites:
    from flask import current_app, g
    depotoirs()                       # ouvre la connexion si besoin
    if "fuites" not in g:
        g.fuites = Fuites(g.co, current_app.extensions["reglages"].parametres)
    return g.fuites


def nuisances() -> Nuisances:
    from flask import current_app, g
    depotoirs()                       # ouvre la connexion si besoin
    if "nuisances" not in g:
        g.nuisances = Nuisances(g.co, current_app.extensions["reglages"].parametres)
    return g.nuisances


def agent_requis(vue=None, postes=None):
    """Seul un agent connecté agit, et seulement depuis le poste qui en a le droit."""
    def decorateur(vue):
        @functools.wraps(vue)
        def emballage(*args, **kwargs):
            if not session.get("agent"):
                return jsonify({"erreur": "Connexion requise."}), 401
            if request.method != "GET" and not secrets.compare_digest(
                    request.headers.get("X-Jeton", ""), session.get("jeton", "")):
                return jsonify({"erreur": "Jeton de session absent ou invalide."}), 403
            if postes and session.get("poste") not in postes:
                return jsonify({"erreur": "Ce poste n'a pas le droit de faire cela."}), 403
            return vue(*args, **kwargs)
        return emballage
    return decorateur(vue) if vue else decorateur


# ------------------------------------------------------------------ essais de mot de passe
# Maintenant que toute la partie décision est derrière un mot de passe, il faut empêcher qu'on
# les essaie tous. Pas de bibliothèque ni de cryptographie ici : un simple compteur en mémoire,
# que n'importe quel membre de l'équipe peut expliquer au jury.
#
# Les seuils sont volontairement indulgents. Un agent qui se trompe deux ou trois fois le jour
# de la démonstration ne doit pas se retrouver bloqué devant le jury ; une machine qui essaie
# des milliers de mots de passe, elle, est arrêtée dès le dixième.
ESSAIS_MAX = 10                 # échecs tolérés…
FENETRE_ESSAIS_S = 300          # …sur cinq minutes
BLOCAGE_S = 120                 # puis deux minutes de refus

_essais = {}                    # identifiant -> [nombre d'échecs, date du premier, fin du blocage]
_verrou_essais = threading.Lock()


def _bloque_encore(nom: str) -> int:
    """Secondes de blocage restantes pour cet identifiant, 0 s'il peut essayer."""
    with _verrou_essais:
        etat = _essais.get(nom)
        if not etat:
            return 0
        reste = etat[2] - time.monotonic()
        return int(reste) + 1 if reste > 0 else 0


def _noter_echec(nom: str) -> None:
    with _verrou_essais:
        maintenant = time.monotonic()
        etat = _essais.get(nom)
        # Au-delà de la fenêtre, on repart de zéro : des erreurs espacées ne s'additionnent pas.
        if not etat or maintenant - etat[1] > FENETRE_ESSAIS_S:
            etat = [0, maintenant, 0.0]
        etat[0] += 1
        if etat[0] >= ESSAIS_MAX:
            etat = [0, maintenant, maintenant + BLOCAGE_S]
        _essais[nom] = etat


def _oublier_les_echecs(nom: str) -> None:
    with _verrou_essais:
        _essais.pop(nom, None)


def entier_demande(nom: str, defaut: int, maximum: int) -> int:
    """Lit un entier dans l'adresse (?limite=…), sans jamais tomber.

    Un paramètre illisible vaut le défaut : on ne renvoie pas d'erreur pour cela, parce que
    la valeur n'est qu'un confort d'affichage. Mais on ne laisse pas non plus Python lever
    une exception, qui donnerait une erreur 500 — et une erreur 500 est exactement ce qu'un
    jury de cybersécurité cherche à provoquer."""
    try:
        valeur = int(request.args.get(nom, defaut))
    except (TypeError, ValueError):
        return defaut
    return max(1, min(valeur, maximum))


# ------------------------------------------------------------------ qui a le droit d'entrer
# LISTE BLANCHE : seules ces routes répondent sans connexion. Tout le reste (pages /decision/,
# API de la carte, du plan, des scénarios, des dossiers, des exports…) demande une session.
# Une route qu'on ajoute plus tard est donc FERMÉE par défaut : l'oubli ne peut pas ouvrir une
# porte. Le test tests/test_acces.py échoue si une route n'est ni ici ni protégée.
# Chaque nom est celui de la fonction Flask (« endpoint »), qui fixe aussi la méthode :
# « recevoir » est POST /api/signalements, alors que la liste (GET) s'appelle « lister ».
OUVERT_A_TOUS = {
    "api.accueil",             # / : la page d'accueil publique (T12)
    "api.page_accueil",        # /accueil/… : son style et son script
    # GET /api/publics : trois nombres, rien d'autre. C'est AUSSI le test de
    # disponibilité de installer.sh : la fermer ferait échouer toute installation,
    # alors même que l'application tourne. Un test le rappelle (tests/test_acces.py).
    "api.chiffres_publics",
    "api.lieux_connus",        # GET /api/lieux : marchés, écoles… pour signaler sans GPS (T16)
    "api.page_signaler",       # /signaler/… : la page de l'habitant, ses sons, son service worker
    "api.bibliotheques",       # /vendor/… : polices et bibliothèques (la page de signalement en charge)
    "api.recevoir",            # POST /api/signalements : un signalement (habitants et jury)
    "api.recevoir_lot",        # POST /api/signalements/lot : un lot (le jury, pièges compris)
    "api.fichier_joint",       # /api/fichiers/public/… ; les fichiers prive/ exigent déjà une session
    "api.connecter",           # POST /api/connexion
    "api.session_en_cours",    # GET /api/session : « suis-je connecté ? »
    "api.deconnecter",         # POST /api/deconnexion
}
# La page de connexion elle-même doit pouvoir s'afficher sans être connecté.
PAGE_DE_CONNEXION = {"connexion.html", "connexion.js", "connexion.css"}


def filtrer_l_acces():
    """Appelée avant chaque requête. Ne renvoie rien si l'accès est permis, sinon un refus."""
    point = request.endpoint
    if point is None:
        return None                                   # adresse inconnue : Flask répondra 404
    if point in OUVERT_A_TOUS or session.get("agent"):
        return None
    if point == "api.page_decision" and (request.view_args or {}).get("fichier") in PAGE_DE_CONNEXION:
        return None
    if request.path.startswith("/api/"):
        # Les pages de décision savent traiter ce refus : elles affichent la connexion.
        return jsonify({"erreur": "Connexion requise."}), 401
    # Une page demandée sans session : on sert la page de connexion À LA MÊME ADRESSE. Une fois
    # le mot de passe accepté, elle recharge simplement l'adresse : on arrive sur la page voulue,
    # sans paramètre de redirection qu'un tiers pourrait détourner.
    reponse = send_from_directory(os.path.join(reglages().dossier_interface, "decision"),
                                  "connexion.html")
    reponse.status_code = 401
    reponse.headers["Cache-Control"] = "no-store"
    return reponse


# ------------------------------------------------------------------ interface et données
@vues.route("/")
def accueil():
    """La page d'accueil publique : deux portes, « Signaler » et « Espace des services » (T12)."""
    return send_from_directory(os.path.join(reglages().dossier_interface, "accueil"), "index.html")


@vues.route("/accueil/<path:fichier>")
def page_accueil(fichier):
    return send_from_directory(os.path.join(reglages().dossier_interface, "accueil"), fichier)


@vues.route("/api/lieux")
def lieux_connus():
    """Les lieux nommés de la commune, pour la page de signalement quand le GPS ne marche pas.
    Ce sont des données publiques d'OpenStreetMap : aucun signalement n'y figure."""
    from flask import current_app
    reponse = jsonify(current_app.extensions["lieux"])
    reponse.headers["Cache-Control"] = "public, max-age=86400"
    return reponse


@vues.route("/api/publics")
def chiffres_publics():
    """Trois nombres, et rien d'autre : jamais une position, jamais un détail.

    C'est la seule adresse de données ouverte sans connexion (T12) ; tout le reste est derrière
    le mot de passe (T13). Ne rien y ajouter sans se demander ce que cela révèle."""
    co = depotoirs().co
    (signalements,) = co.execute("SELECT COUNT(*) FROM signalements").fetchone()
    (recenses,) = co.execute("SELECT COUNT(*) FROM depotoirs").fetchone()
    # Un dossier traité est un dépotoir arrivé au bout de la chaîne : ramassé, ou classé.
    fins = [nom for nom, etape in CHAINE.items() if etape["suivante"] is None]
    (traites,) = co.execute("SELECT COUNT(*) FROM depotoirs WHERE etape IN (%s)"
                            % ",".join("?" * len(fins)), fins).fetchone()
    return jsonify({"signalements": signalements, "depotoirs": recenses, "dossiers_traites": traites})


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


# Fichiers joints possibles. Les trois derniers sont FACULTATIFS et réservés au cas où le
# déclarant accepte d'être témoin ; ils ne sont jamais servis au public.
# champ du formulaire : (colonne, genre de fichier, privé ?)
# Pour chaque pièce jointe : la colonne, son genre, si elle est privée, et si les visages et
# les plaques doivent y être masqués.
#
# Seule la photo du tas est masquée, et c'est voulu. Quelqu'un qui passe derrière un dépotoir
# n'a rien demandé à personne : son visage ne doit pas finir dans une base municipale. La CNIB
# et le portrait, eux, SONT l'identité que le déclarant a choisi de donner pour être témoin :
# les flouter les viderait de leur sens. Ils ne sont d'ailleurs jamais servis au public et
# s'effacent à la clôture du dossier.
FICHIERS_JOINTS = {
    "photo": ("photo", "image", False, True),         # photo du tas : visible de tous, masquée
    "photo_cnib": ("photo_cnib", "image", True, False),      # pièce d'identité, facultative
    "photo_visage": ("photo_visage", "image", True, False),  # portrait, facultatif
    "message_vocal": ("message_vocal", "audio", True, False),  # signalement parlé : une voix
}


@vues.route("/api/signalements", methods=["POST"])
def recevoir():
    """Un signalement : JSON du téléphone, ou formulaire avec photo et message vocal."""
    motifs_fichiers = []
    if request.files or request.form:
        brut = {k: v for k, v in request.form.items()}
        for champ, (cle, genre, prive, a_masquer) in FICHIERS_JOINTS.items():
            fichier = request.files.get(champ)
            if fichier is None:
                continue
            contenu = fichier.read()
            if genre == "image" and not controleur().controler_photo(contenu):
                if champ == "photo":
                    motifs_fichiers.append("photo_invalide")
                continue                      # une pièce jointe facultative illisible est ignorée
            if genre == "audio" and not controleur().controler_audio(contenu):
                continue
            if a_masquer:
                # E18 : le masquage se fait ICI, avant le moindre enregistrement. L'image
                # d'origine ne touche jamais le disque.
                if not masquage_disponible():
                    # Sans détecteur, on préfère perdre la photo que garder un visage en clair.
                    motifs_fichiers.append("photo_non_masquable")
                    continue
                contenu, comptes = masquer(contenu)
                brut["visages_masques"] = comptes["visages"]
                brut["plaques_masquees"] = comptes["plaques"]
            brut[cle] = enregistrer_fichier(contenu, prive)
    else:
        brut = request.get_json(silent=True)
    examine = controleur().examiner(brut)
    if motifs_fichiers:
        examine = Controleur.resultat(examine, list(examine["motifs"]) + motifs_fichiers)
    if isinstance(brut, dict) and examine["statut"] != "rejete":
        for _, (cle, _genre, _prive, _masque) in FICHIERS_JOINTS.items():
            if brut.get(cle):
                examine[cle] = brut[cle]
        for compteur in ("visages_masques", "plaques_masquees"):
            if brut.get(compteur) is not None:
                examine[compteur] = brut[compteur]
    # Une fuite d'eau suit sa propre chaîne (mairie → ONEA) : elle n'entre pas dans les
    # tournées des camions, et ne devient donc jamais un dépotoir.
    nature = examine.get("nature")
    if nature == "fuite_eau":
        resultat = fuites().enregistrer(examine)
    elif nature in NATURES_NUISANCE:
        resultat = nuisances().enregistrer(examine)
    else:
        resultat = depotoirs().enregistrer(examine)
    return jsonify(resultat), 201 if resultat["nouveau"] else 200


def enregistrer_fichier(contenu: bytes, prive: bool = False) -> str:
    """Fichier rangé sous l'empreinte de son contenu : deux envois identiques n'en font qu'un.

    Les pièces d'identité et les voix vont dans un sous-dossier à part, servi seulement aux
    agents connectés."""
    dossier = os.path.join(reglages().dossier_photos, "prive" if prive else "public")
    os.makedirs(dossier, exist_ok=True)
    nom = hashlib.sha256(contenu).hexdigest()[:32]
    chemin = os.path.join(dossier, nom)
    if not os.path.exists(chemin):
        with open(chemin, "wb") as f:
            f.write(contenu)
    return ("prive/" if prive else "public/") + nom


@vues.route("/api/fichiers/<genre>/<nom>")
def fichier_joint(genre, nom):
    """Sert une pièce jointe. Les pièces privées exigent un agent connecté."""
    if genre not in ("public", "prive") or not nom.isalnum():
        abort(404)
    if genre == "prive" and not session.get("agent"):
        return jsonify({"erreur": "Connexion requise."}), 401
    chemin = os.path.join(reglages().dossier_photos, genre, nom)
    if not os.path.isfile(chemin):
        abort(404)
    # Le type est deviné du contenu, jamais du nom : un fichier envoyé ne choisit pas comment
    # le navigateur l'interprète.
    with open(chemin, "rb") as f:
        debut = f.read(16)
    from .signalements.controles import est_un_son, est_une_image
    if est_une_image(debut):
        genre_mime = "image/jpeg" if debut.startswith(b"\xff\xd8\xff") else "image/png"
    elif est_un_son(debut) or debut[4:8] == b"ftyp":
        genre_mime = "audio/webm"
    else:
        genre_mime = "application/octet-stream"
    return send_file(chemin, mimetype=genre_mime, conditional=True)


@vues.route("/api/signalements/lot", methods=["POST"])
def recevoir_lot():
    """Un lot : tableau JSON, GeoJSON, ou CSV. Répond ligne par ligne, jamais par une erreur globale."""
    try:
        lignes = lire_lot()
    except Exception as erreur:
        return jsonify({"erreur": f"Lot illisible : {erreur}"}), 400
    # Tous les signalements de CE fichier partagent une seule origine. Sans cela, un lot
    # contenant deux lignes au même endroit avec deux « source » différentes se confirmerait
    # tout seul, et entrerait dans le plan puis dans l'export OpenStreetMap sans qu'aucun
    # second témoin existe. Voir application/geo.py, fonction origines().
    lot = "lot-" + secrets.token_hex(8)
    resultats = []
    for brut in lignes[:5000]:
        try:
            examine = controleur().examiner(brut)
            examine["lot"] = lot
            resultats.append(depotoirs().enregistrer(examine, verifier_rafale=False))
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
    return jsonify(depotoirs().liste(request.args.get("statut"),
                                     entier_demande("limite", 500, 2000)))


@vues.route("/api/depotoirs")
def carte_depotoirs():
    """Les dépotoirs retenus, au format GeoJSON : c'est ce qu'affiche la carte."""
    strict = request.args.get("strict", "").lower() in ("1", "oui", "true")
    retenus = depotoirs().retenus(strict or reglages().parametres.get("mode_strict", False))
    return jsonify({"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [d["longitude"], d["latitude"]]},
         "properties": {k: d.get(k) for k in ("id", "volume_m3", "surface_m2", "depot", "etape",
                                              "nb_signalements", "nb_sources", "premier_vu",
                                              "dernier_vu", "etat")}}
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


# ------------------------------------------------------------------ chaîne de traitement
@vues.route("/api/chaine")
def chaine():
    """Les étapes de la chaîne, qui agit à chacune, et combien de dossiers y sont."""
    return jsonify({"etapes": CHAINE, "postes": POSTES,
                    "comptes": dossiers().comptes_par_etape()})


def priorite() -> Priorite:
    from flask import current_app
    return current_app.extensions["priorite"]


@vues.route("/api/dossiers")
def lister_dossiers():
    poste = session.get("poste")
    etape = request.args.get("etape")
    pour_moi = request.args.get("pour_moi") in ("1", "oui", "true")
    liste = dossiers().liste(etape=etape, poste=poste if pour_moi else None)
    # Les plus urgents en tête, et chacun porte ses raisons : un agent qui traite une file de
    # plusieurs milliers de dossiers ne peut pas suivre l'ordre d'arrivée.
    if request.args.get("ordre") == "arrivee":
        return jsonify(liste)
    return jsonify(priorite().classer(liste, gravite=lambda d: d.get("taille")))


@vues.route("/api/dossiers/<int:identifiant>")
def detail_dossier(identifiant):
    try:
        # L'identité facultative du déclarant n'est servie qu'aux agents connectés.
        return jsonify(dossiers().detail(identifiant, avec_declarants=bool(session.get("agent"))))
    except ErreurDossier as erreur:
        return jsonify({"erreur": str(erreur)}), 404


@vues.route("/api/dossiers/<int:identifiant>/avancer", methods=["POST"])
@agent_requis(postes=("mairie", "brigade", "collecte"))
def avancer_dossier(identifiant):
    envoi = request.get_json(silent=True) or {}
    try:
        return jsonify(dossiers().avancer(identifiant, session["poste"], session["agent"],
                                          str(envoi.get("detail", ""))))
    except ErreurDossier as erreur:
        return jsonify({"erreur": str(erreur)}), 400


@vues.route("/api/dossiers/<int:identifiant>/classer", methods=["POST"])
@agent_requis(postes=("mairie",))
def classer_dossier(identifiant):
    envoi = request.get_json(silent=True) or {}
    try:
        return jsonify(dossiers().classer(identifiant, session["poste"], session["agent"],
                                          str(envoi.get("motif", ""))))
    except ErreurDossier as erreur:
        return jsonify({"erreur": str(erreur)}), 400


@vues.route("/api/dossiers/<int:identifiant>/identites", methods=["DELETE"])
@agent_requis(postes=("mairie",))
def effacer_identites(identifiant):
    """Efface les pièces d'identité d'un dossier clos : elles n'ont plus de raison d'être là."""
    return jsonify({"signalements_nettoyes": dossiers().effacer_identites(identifiant)})


# --------------------------------------------------------------------- fuites d'eau (ONEA)

@vues.route("/api/fuites/chaine")
def chaine_eau():
    """Les étapes de la chaîne d'une fuite, et combien de dossiers y sont."""
    return jsonify({"etapes": CHAINE_EAU, "ampleurs": AMPLEUR_NOMS,
                    "comptes": fuites().comptes_par_etape(), "resume": fuites().comptes()})


@vues.route("/api/fuites")
def lister_fuites():
    poste = session.get("poste")
    etape = request.args.get("etape")
    pour_moi = request.args.get("pour_moi") in ("1", "oui", "true")
    liste = fuites().liste(etape=etape, poste=poste if pour_moi else None)
    if request.args.get("ordre") == "arrivee":
        return jsonify(liste)
    return jsonify(priorite().classer(liste, gravite=lambda f: f.get("ampleur")))


@vues.route("/api/fuites/carte")
def carte_fuites():
    """Les fuites non réparées, en GeoJSON, pour la carte de décision."""
    entites = [{"type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f["longitude"], f["latitude"]]},
                "properties": {"id": f["id"], "ampleur": f["ampleur"] or "inconnue",
                               "quartier": f["quartier"], "etape": f["etape"],
                               "etape_nom": f["etape_nom"],
                               "nb_signalements": f["nb_signalements"]}}
               for f in fuites().carte()]
    return jsonify({"type": "FeatureCollection", "features": entites})


@vues.route("/api/fuites/<int:identifiant>")
def detail_fuite(identifiant):
    try:
        # L'identité facultative du déclarant n'est servie qu'aux agents connectés.
        return jsonify(fuites().detail(identifiant, avec_declarants=bool(session.get("agent"))))
    except ErreurFuite as erreur:
        return jsonify({"erreur": str(erreur)}), 404


@vues.route("/api/fuites/<int:identifiant>/avancer", methods=["POST"])
@agent_requis(postes=("mairie", "onea"))
def avancer_fuite(identifiant):
    envoi = request.get_json(silent=True) or {}
    try:
        return jsonify(fuites().avancer(identifiant, session["poste"], session["agent"],
                                        str(envoi.get("detail", ""))))
    except ErreurFuite as erreur:
        return jsonify({"erreur": str(erreur)}), 400


@vues.route("/api/fuites/<int:identifiant>/classer", methods=["POST"])
@agent_requis(postes=("mairie",))
def classer_fuite(identifiant):
    envoi = request.get_json(silent=True) or {}
    try:
        return jsonify(fuites().classer(identifiant, session["poste"], session["agent"],
                                        str(envoi.get("motif", ""))))
    except ErreurFuite as erreur:
        return jsonify({"erreur": str(erreur)}), 400


# --------------------------------------------------------------- autres nuisances

@vues.route("/api/nuisances/chaine")
def chaine_nuisances():
    """Les étapes, les natures, et qui intervient pour chacune."""
    return jsonify({"etapes": CHAINE_NUISANCE, "natures": NATURES_NUISANCE,
                    "gravites": GRAVITE_NOMS,
                    "comptes": nuisances().comptes_par_etape(),
                    "par_nature": nuisances().comptes_par_nature()})


@vues.route("/api/nuisances")
def lister_nuisances():
    poste = session.get("poste")
    pour_moi = request.args.get("pour_moi") in ("1", "oui", "true")
    liste = nuisances().liste(etape=request.args.get("etape"),
                              nature=request.args.get("nature"),
                              poste=poste if pour_moi else None)
    if request.args.get("ordre") == "arrivee":
        return jsonify(liste)
    # « moyen » veut dire la même chose pour une nuisance et pour un tas, mais la table des
    # niveaux les distingue : on lève l'ambiguïté ici.
    return jsonify(priorite().classer(
        liste, gravite=lambda n: ("moyen_nuisance" if n.get("gravite") == "moyen"
                                  else n.get("gravite"))))


@vues.route("/api/nuisances/carte")
def carte_nuisances():
    """Les nuisances non traitées, en GeoJSON, pour la carte de décision."""
    entites = [{"type": "Feature",
                "geometry": {"type": "Point", "coordinates": [n["longitude"], n["latitude"]]},
                "properties": {"id": n["id"], "nature": n["nature"],
                               "nature_nom": n["nature_nom"], "gravite": n["gravite"] or "inconnue",
                               "quartier": n["quartier"], "etape_nom": n["etape_nom"],
                               "service": n["service"],
                               "nb_signalements": n["nb_signalements"]}}
               for n in nuisances().carte()]
    return jsonify({"type": "FeatureCollection", "features": entites})


@vues.route("/api/nuisances/<int:identifiant>")
def detail_nuisance(identifiant):
    try:
        return jsonify(nuisances().detail(identifiant,
                                          avec_declarants=bool(session.get("agent"))))
    except ErreurNuisance as erreur:
        return jsonify({"erreur": str(erreur)}), 404


@vues.route("/api/nuisances/<int:identifiant>/avancer", methods=["POST"])
@agent_requis(postes=("mairie", "brigade", "collecte", "onea"))
def avancer_nuisance(identifiant):
    envoi = request.get_json(silent=True) or {}
    try:
        return jsonify(nuisances().avancer(identifiant, session["poste"], session["agent"],
                                           str(envoi.get("detail", ""))))
    except ErreurNuisance as erreur:
        return jsonify({"erreur": str(erreur)}), 400


@vues.route("/api/nuisances/<int:identifiant>/classer", methods=["POST"])
@agent_requis(postes=("mairie",))
def classer_nuisance(identifiant):
    envoi = request.get_json(silent=True) or {}
    try:
        return jsonify(nuisances().classer(identifiant, session["poste"], session["agent"],
                                           str(envoi.get("motif", ""))))
    except ErreurNuisance as erreur:
        return jsonify({"erreur": str(erreur)}), 400


@vues.route("/api/inspection")
@agent_requis(postes=("mairie", "brigade", "collecte", "onea"))
def tournee_d_inspection():
    """Les visites de terrain qui attendent ce poste, groupées en tournées.

    Pourquoi : la brigade se déplaçait dossier par dossier. Dix constats, dix sorties — et deux
    dossiers voisins visités deux jours différents parce qu'ils sont arrivés dans le désordre.
    C'est le même algorithme que les tournées des camions, avec la journée de l'agent pour
    seule contrainte au lieu de la benne."""
    poste = request.args.get("poste") or session["poste"]
    a_visiter = []
    # Les trois familles de signalements qui attendent ce poste : un agent sort une fois pour
    # tout ce qu'il a à voir, sans distinguer un tas d'un caniveau.
    for dossier in dossiers().liste(poste=poste):
        a_visiter.append({"id": "D%d" % dossier["id"], "latitude": dossier["latitude"],
                          "longitude": dossier["longitude"], "nature": "depotoir"})
    for fuite in fuites().liste(poste=poste):
        a_visiter.append({"id": "F%d" % fuite["id"], "latitude": fuite["latitude"],
                          "longitude": fuite["longitude"], "nature": "fuite_eau"})
    for nuisance in nuisances().liste(poste=poste):
        a_visiter.append({"id": "N%d" % nuisance["id"], "latitude": nuisance["latitude"],
                          "longitude": nuisance["longitude"],
                          "nature": nuisance.get("nature") or "nuisance"})

    from flask import current_app
    parametres = dict(reglages().parametres)
    for cle in ("agents_terrain", "minutes_par_visite"):
        valeur = request.args.get(cle)
        if valeur is not None:
            try:
                parametres[cle] = float(valeur)
            except ValueError:
                pass
    base = base_du_service(parametres, current_app.extensions["geographie"])
    resultat = tournees_d_inspection(a_visiter, base, reseau(), parametres)
    resultat["poste"] = poste
    return jsonify(resultat)


@vues.route("/api/export/nuisances")
def export_nuisances():
    """Le bordereau des nuisances orientées, par service, en CSV.

    Même raison que pour l'ONEA : l'outil ne sort pas de la machine (E14). Un agent imprime
    ce bordereau ou l'envoie au service, qui n'a pas forcément accès à l'outil."""
    lignes = nuisances().liste(etape=request.args.get("etape", "confirme"),
                               nature=request.args.get("nature"), limite=1000)
    tampon = io.StringIO()
    plume = csv.writer(tampon, delimiter=";")
    plume.writerow(["Reference", "Nature", "Service", "Quartier", "Gravite", "Latitude",
                    "Longitude", "Premier signalement", "Dernier signalement",
                    "Nombre de signalements", "Appareils distincts", "Etape"])
    for n in lignes:
        plume.writerow([f"NUIS-{n['id']:05d}", n["nature_nom"], n["service"] or "",
                        n["quartier"] or "non précisé", n["gravite_nom"],
                        round(n["latitude"], 6), round(n["longitude"], 6),
                        n["premier_vu"] or "", n["dernier_vu"] or "",
                        n["nb_signalements"], n["nb_sources"], n["etape_nom"]])
    contenu = "\ufeff" + tampon.getvalue()
    return contenu, 200, {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="bordereau-nuisances.csv"',
        "X-Nuisances": str(len(lignes))}


@vues.route("/api/export/onea")
def export_onea():
    """Le bordereau des fuites à transmettre à l'ONEA, en CSV.

    Pourquoi un fichier et non un envoi automatique : l'outil ne sort pas de la machine
    (exigence E14), et l'ONEA n'a pas d'interface publique où déposer un signalement. Un agent
    de la mairie imprime ce bordereau ou l'envoie, et note en retour le numéro que l'ONEA lui
    donne. C'est exactement ce que font les deux services aujourd'hui, en plus traçable."""
    a_transmettre = request.args.get("tout") not in ("1", "oui", "true")
    lignes = fuites().liste(etape="signale" if a_transmettre else None, limite=1000)
    tampon = io.StringIO()
    # Point-virgule : c'est ce qu'attend un tableur configuré en français.
    plume = csv.writer(tampon, delimiter=";")
    plume.writerow(["Reference", "Quartier", "Ampleur", "Latitude", "Longitude",
                    "Premier signalement", "Dernier signalement", "Nombre de signalements",
                    "Appareils distincts", "Etape", "Reference ONEA"])
    for f in lignes:
        plume.writerow([f"FUITE-{f['id']:05d}", f["quartier"] or "non précisé",
                        f["ampleur"] or "non précisée",
                        round(f["latitude"], 6), round(f["longitude"], 6),
                        f["premier_vu"] or "", f["dernier_vu"] or "",
                        f["nb_signalements"], f["nb_sources"], f["etape_nom"],
                        f["reference_onea"] or ""])
    contenu = "﻿" + tampon.getvalue()          # BOM : les accents s'affichent dans Excel
    return contenu, 200, {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="bordereau-fuites-onea.csv"',
        "X-Fuites": str(len(lignes))}


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


@vues.route("/api/export/geojson")
def export_geojson():
    """Les dépotoirs VÉRIFIÉS en GeoJSON, sous licence ODbL, sans donnée personnelle (T19)."""
    collection = en_geojson(depotoirs().retenus(mode_strict=True), depotoirs().co)
    reponse = jsonify(collection)
    reponse.headers["Content-Disposition"] = 'attachment; filename="signalements-ouaga.geojson"'
    reponse.headers["X-Depotoirs"] = str(len(collection["features"]))
    return reponse


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
    nom = str(envoi.get("nom", ""))

    reste = _bloque_encore(nom)
    if reste:
        return jsonify({"erreur": "Trop d'essais. Réessayez dans %d secondes." % reste}), 429

    compte = r.comptes.get(nom)
    if compte is None or not compte["mot_de_passe"]:
        # Même réponse qu'un mot de passe faux : on ne dit pas quels comptes existent.
        _noter_echec(nom)
        return jsonify({"erreur": "Identifiant ou mot de passe incorrect."}), 401
    attendu = compte["mot_de_passe"]
    empreinte = attendu if attendu.startswith(("pbkdf2:", "scrypt:")) else generate_password_hash(attendu)
    if not check_password_hash(empreinte, str(envoi.get("mot_de_passe", ""))):
        _noter_echec(nom)
        return jsonify({"erreur": "Identifiant ou mot de passe incorrect."}), 401
    _oublier_les_echecs(nom)
    session.clear()
    session["agent"] = nom
    session["poste"] = compte["poste"]
    session["jeton"] = secrets.token_urlsafe(32)
    return jsonify({"agent": session["agent"], "poste": session["poste"],
                    "poste_nom": POSTES[session["poste"]], "jeton": session["jeton"]})


@vues.route("/api/session")
def session_en_cours():
    """La page de vérification demande si un agent est déjà connecté (la session dure 
    le temps du navigateur)."""
    if not session.get("agent"):
        return jsonify({"agent": None}), 401
    return jsonify({"agent": session["agent"], "poste": session.get("poste"),
                    "poste_nom": POSTES.get(session.get("poste"), ""), "jeton": session["jeton"]})


@vues.route("/api/deconnexion", methods=["POST"])
def deconnecter():
    session.clear()
    return jsonify({"ok": True})


@vues.route("/api/signalements/<int:identifiant>/verifier", methods=["POST"])
@agent_requis(postes=("mairie",))
def verifier(identifiant):
    return (jsonify({"ok": True}) if depotoirs().decider(identifiant, True)
            else (jsonify({"erreur": "Signalement inconnu."}), 404))


@vues.route("/api/signalements/<int:identifiant>/rejeter", methods=["POST"])
@agent_requis(postes=("mairie",))
def rejeter(identifiant):
    return (jsonify({"ok": True}) if depotoirs().decider(identifiant, False)
            else (jsonify({"erreur": "Signalement inconnu."}), 404))
