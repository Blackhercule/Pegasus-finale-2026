"""Comptes individuels des agents, créés par la mairie.

Avant, il y avait quatre comptes partagés : un par service. Tous les agents de la brigade
entraient avec le même mot de passe. Trois défauts, qu'un jury de cybersécurité relève tout de
suite :

- le journal écrivait « brigade a fait le constat », jamais QUEL agent : le « qui a fait quoi »
  ne valait rien ;
- un agent qui quittait le service gardait l'accès tant qu'on n'avait pas changé le mot de passe
  de tout le service ;
- un mot de passe partagé circule, se note sur un papier, se prête à un collègue.

Maintenant, la mairie ajoute chaque agent un par un, avec son nom et son service, et peut le
désactiver. Le journal signe avec son identifiant.

**Aucune cryptographie écrite par l'équipe.** Les mots de passe sont hachés par Werkzeug — la
bibliothèque sur laquelle Flask repose — avec son algorithme par défaut, salé et lent exprès.
Le mot de passe lui-même n'est jamais enregistré, jamais renvoyé, jamais écrit au journal.

Les quatre comptes de `.env` restent, comme comptes de démarrage : sans eux, personne ne
pourrait créer le premier compte individuel. C'est le compte `agent` (la mairie) qui ouvre les
autres.
"""

import datetime
import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

POSTES_POSSIBLES = ("mairie", "brigade", "collecte", "onea")

# Un identifiant simple, qu'on peut taper sur un téléphone et lire dans un journal : lettres
# minuscules, chiffres, point, tiret. Pas d'espace, pas d'accent — pas de deux comptes qui ne
# diffèrent que par un « é » qu'on ne voit pas.
FORME_IDENTIFIANT = re.compile(r"^[a-z0-9][a-z0-9.\-]{2,39}$")
LONGUEUR_MINI = 10
# Les comptes de démarrage gardent leurs noms : on ne peut pas en créer un second du même nom.
RESERVES = ("agent", "brigade", "collecte", "onea", "admin", "root")

# Une empreinte calculée une fois, sur un mot de passe que personne ne connaît. Elle sert à
# faire autant de calcul pour un identifiant inconnu que pour un connu : sans cela, le temps de
# réponse dirait lesquels existent — et ici ce sont des noms de personnes.
_EMPREINTE_LEURRE = generate_password_hash("leurre-jamais-utilise-" + "x" * 24)


class ErreurAgent(Exception):
    pass


def maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class Agents:
    def __init__(self, connexion):
        self.co = connexion

    # ------------------------------------------------------------------ création
    def creer(self, identifiant: str, nom: str, poste: str, mot_de_passe: str,
              cree_par: str) -> dict:
        identifiant = (identifiant or "").strip().lower()
        nom = " ".join((nom or "").split())[:80]
        if not FORME_IDENTIFIANT.match(identifiant):
            raise ErreurAgent("Identifiant invalide : 3 à 40 caractères, lettres minuscules sans "
                              "accent, chiffres, point ou tiret, sans espace.")
        if identifiant in RESERVES:
            raise ErreurAgent("Cet identifiant est réservé.")
        if not nom:
            raise ErreurAgent("Le nom de l'agent est obligatoire : c'est lui qui signe le journal.")
        if poste not in POSTES_POSSIBLES:
            raise ErreurAgent("Service inconnu.")
        if not isinstance(mot_de_passe, str) or len(mot_de_passe) < LONGUEUR_MINI:
            raise ErreurAgent("Le mot de passe doit faire au moins %d caractères." % LONGUEUR_MINI)
        if mot_de_passe.lower() in (identifiant, nom.lower()):
            raise ErreurAgent("Le mot de passe ne doit pas être l'identifiant ni le nom.")
        try:
            curseur = self.co.execute(
                "INSERT INTO agents (identifiant, nom, poste, empreinte, actif, cree_le, cree_par)"
                " VALUES (?,?,?,?,1,?,?)",
                (identifiant, nom, poste, generate_password_hash(mot_de_passe), maintenant(),
                 cree_par))
        except sqlite3.IntegrityError:
            self.co.rollback()
            raise ErreurAgent("Cet identifiant existe déjà.")
        self.co.commit()
        return self.detail(curseur.lastrowid)

    # ------------------------------------------------------------------ lecture
    def detail(self, id_agent: int) -> dict:
        ligne = self.co.execute(
            "SELECT id, identifiant, nom, poste, actif, cree_le, cree_par, desactive_le"
            " FROM agents WHERE id = ?", (id_agent,)).fetchone()
        if ligne is None:
            raise ErreurAgent("Compte inconnu.")
        return dict(ligne)

    def liste(self) -> list:
        # Jamais l'empreinte : elle ne sert qu'à vérifier, elle ne sort pas de la base.
        return [dict(l) for l in self.co.execute(
            "SELECT id, identifiant, nom, poste, actif, cree_le, cree_par, desactive_le"
            " FROM agents ORDER BY actif DESC, poste, nom")]

    def est_actif(self, identifiant: str) -> bool:
        ligne = self.co.execute("SELECT actif FROM agents WHERE identifiant = ?",
                                (identifiant,)).fetchone()
        return bool(ligne and ligne["actif"])

    # ------------------------------------------------------------------ connexion
    def verifier(self, identifiant: str, mot_de_passe: str):
        """Le compte si l'identifiant et le mot de passe sont bons et le compte actif, sinon None.

        Le calcul est le même quand l'identifiant n'existe pas : le temps de réponse ne doit pas
        dire quels comptes existent."""
        identifiant = (identifiant or "").strip().lower()
        ligne = self.co.execute(
            "SELECT id, identifiant, nom, poste, empreinte, actif FROM agents"
            " WHERE identifiant = ?", (identifiant,)).fetchone()
        empreinte = ligne["empreinte"] if ligne else _EMPREINTE_LEURRE
        bon = check_password_hash(empreinte, str(mot_de_passe or ""))
        if ligne is None or not bon or not ligne["actif"]:
            return None
        return {"identifiant": ligne["identifiant"], "nom": ligne["nom"], "poste": ligne["poste"]}

    @staticmethod
    def verifier_a_blanc(mot_de_passe: str) -> None:
        """Le même calcul qu'une vraie vérification, pour un identifiant qui n'existe nulle part."""
        check_password_hash(_EMPREINTE_LEURRE, str(mot_de_passe or ""))

    # ------------------------------------------------------------------ désactivation
    def changer_etat(self, id_agent: int, actif: bool, par: str) -> dict:
        """Désactiver ne supprime rien : le journal garde le nom de qui a fait quoi, même après
        le départ de l'agent. C'est l'accès qu'on coupe, pas l'histoire."""
        self.detail(id_agent)                                  # lève si le compte n'existe pas
        self.co.execute(
            "UPDATE agents SET actif = ?, desactive_le = ?, desactive_par = ? WHERE id = ?",
            (1 if actif else 0, None if actif else maintenant(), None if actif else par, id_agent))
        self.co.commit()
        return self.detail(id_agent)
