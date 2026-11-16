"""Simulation multi-agents de la filière déchets, jour après jour.

Quatre familles d'acteurs, comme le demande l'énoncé (exigence E4) :

  - les MÉNAGES produisent des déchets. Abonnés, ils les remettent à un pré-collecteur ; sinon
    ils les portent au point de regroupement si l'un est assez proche, et à défaut les jettent
    dans un dépotoir ;
  - les PRÉ-COLLECTEURS ramassent chez leurs abonnés et déposent aux points de regroupement.
    En saison des pluies, leurs charrettes avancent moins vite et en desservent moins ;
  - la BRIGADE LAABAL patrouille là où l'on jette le plus. Elle sensibilise d'abord, verbalise
    en cas de récidive : les dépôts sauvages reculent dans les carreaux visités, et les
    abonnements y progressent ;
  - la MAIRIE fait rouler les camions selon le plan, vide les points et nettoie des dépotoirs
    dans la limite de son budget. Elle subit les pannes.

La bibliothèque Mesa (Apache-2.0) fournit la mécanique des agents et du pas de temps ; les
règles de comportement, elles, sont écrites ici et chacune tient en quelques lignes, pour qu'un
membre de l'équipe puisse les expliquer au jury.

Le tirage aléatoire part d'une graine fixe : deux simulations du même scénario donnent
exactement le même résultat.
"""

import math

import mesa
import numpy as np


class Menages(mesa.Agent):
    """Les ménages d'un carreau de 250 m. Un agent en représente plusieurs milliers."""

    def __init__(self, modele, carreau: int, habitants: float, point: int, distance_point: float):
        super().__init__(modele)
        self.modele = modele               # Mesa l'appelle « model » ; ici tout est en français
        self.carreau = carreau
        self.habitants = habitants
        self.point = point                      # point de regroupement le plus proche, ou -1
        self.distance_point = distance_point
        self.abonnes = modele.taux_abonnement
        self.civisme = 0.0                      # monte avec le passage de la brigade

    @property
    def m3_par_jour(self) -> float:
        return (self.habitants * self.modele.kg_par_habitant_jour / 1000
                / self.modele.densite_t_m3)

    def step(self):
        produit = self.m3_par_jour
        m = self.modele
        remis = produit * self.abonnes                       # confié au pré-collecteur
        reste = produit - remis
        m.attente_precollecte[self.carreau] += remis

        # Les non-abonnés : au point de regroupement s'il est proche et pas débordé, sinon
        # au dépotoir. Le civisme gagné grâce à la brigade augmente la part qui fait l'effort.
        if self.point >= 0 and self.distance_point <= m.distance_max_m and not m.point_sature[self.point]:
            part_au_point = min(0.95, 0.45 + self.civisme)
        else:
            part_au_point = min(0.3, self.civisme)
        au_point = reste * part_au_point
        if self.point >= 0:
            m.depot_aux_points[self.point] += au_point
        else:
            au_point = 0
        m.jete_en_depotoir[self.carreau] += reste - au_point
        m.produit_du_jour += produit


class PreCollecteur(mesa.Agent):
    """Une association ou une PME de pré-collecte, qui dessert un groupe de carreaux."""

    def __init__(self, modele, carreaux: list, point: int, capacite_m3: float):
        super().__init__(modele)
        self.modele = modele
        self.carreaux = carreaux
        self.point = point
        self.capacite_m3 = capacite_m3

    def step(self):
        m = self.modele
        # En saison des pluies, les charrettes passent mal sur les pistes : la capacité baisse.
        capacite = self.capacite_m3 * (0.65 if m.saison == "pluies" else 1.0)
        a_ramasser = sum(m.attente_precollecte[c] for c in self.carreaux)
        ramasse = min(a_ramasser, capacite)
        if a_ramasser > 0:
            part = ramasse / a_ramasser
            for c in self.carreaux:
                garde = m.attente_precollecte[c] * (1 - part)
                m.attente_precollecte[c] = garde
            # Ce que le pré-collecteur n'a pas pu prendre finit souvent en dépotoir.
            for c in self.carreaux:
                perdu = m.attente_precollecte[c] * 0.5
                m.attente_precollecte[c] -= perdu
                m.jete_en_depotoir[c] += perdu
        if self.point >= 0:
            m.depot_aux_points[self.point] += ramasse
        m.precollecte_du_jour += ramasse


class BrigadeLaabal(mesa.Agent):
    """La brigade de lutte contre l'incivisme : sensibilisation d'abord, verbalisation ensuite.

    Elle se rend chaque jour dans les carreaux où l'on jette le plus. Son effet n'est pas
    immédiat : le civisme d'un carreau monte à chaque passage, et retombe lentement sans elle."""

    def __init__(self, modele, effectif: int):
        super().__init__(modele)
        self.modele = modele
        self.effectif = effectif
        self.visites = {}

    def step(self):
        m = self.modele
        if self.effectif <= 0:
            return
        # Une patrouille couvre environ un carreau par agent et par jour.
        classement = sorted(m.menages, key=lambda a: m.jete_en_depotoir[a.carreau], reverse=True)
        for agent in classement[:self.effectif]:
            deja_vu = self.visites.get(agent.carreau, 0)
            self.visites[agent.carreau] = deja_vu + 1
            # Première visite : sensibilisation. Ensuite : verbalisation, plus dissuasive.
            gain = 0.04 if deja_vu == 0 else 0.07
            agent.civisme = min(0.5, agent.civisme + gain)
            agent.abonnes = min(0.95, agent.abonnes + (0.004 if deja_vu else 0.002))
            m.verbalisations_du_jour += 1 if deja_vu else 0
        for agent in m.menages:                  # sans passage, l'effet s'estompe
            agent.civisme = max(0.0, agent.civisme - 0.002)


class Mairie(mesa.Agent):
    """La mairie : elle fait rouler les camions du plan, vide les points, nettoie des dépotoirs."""

    def __init__(self, modele, plan: dict):
        super().__init__(modele)
        self.modele = modele
        self.plan = plan
        self.tournees_par_jour = plan.get("tournees", [])
        self.cout_km = modele.parametres["cout_km"]
        self.cout_jour_camion = modele.parametres["cout_jour_camion"]

    def step(self):
        m = self.modele
        camions = max(0, int(m.parametres["nb_camions"]) - int(m.parametres.get("camions_en_panne", 0)))
        # Une panne imprévue peut immobiliser un camion de plus dans la journée.
        if camions and m.rng.random() < m.probabilite_panne:
            camions -= 1
            m.pannes_du_jour += 1
        if not self.tournees_par_jour or camions == 0:
            return
        actives = [t for t in self.tournees_par_jour if t["camion"] <= camions]
        collecte = 0.0
        for tournee in actives:
            for etape in tournee["etapes"]:
                if etape["genre"] != "point":
                    continue
                numero = int(str(etape["id"]).split("-")[1].split("#")[0])
                pris = min(m.stock_aux_points[numero], etape["m3"])
                m.stock_aux_points[numero] -= pris
                collecte += pris
        km = sum(t["distance_km"] for t in actives)
        m.collecte_du_jour += collecte
        m.depense_du_jour += km * self.cout_km + len(set(t["camion"] for t in actives)) * self.cout_jour_camion

        # Nettoyage des dépotoirs, dans la limite de ce qu'il reste de budget.
        reste = m.budget_du_jour - m.depense_du_jour
        cout_nettoyage = m.parametres.get("cout_nettoyage_m3", 2500)
        if reste > 0 and m.volume_depotoirs > 0:
            nettoye = min(m.volume_depotoirs, reste / cout_nettoyage)
            m.volume_depotoirs -= nettoye
            m.depense_du_jour += nettoye * cout_nettoyage
            m.nettoye_du_jour += nettoye


class Filiere(mesa.Model):
    """Le modèle : un pas de temps vaut un jour."""

    def __init__(self, demande: dict, plan: dict, parametres: dict, graine: int = 2026):
        super().__init__(rng=graine)
        self.parametres = parametres
        self.saison = parametres["saison"]
        self.kg_par_habitant_jour = float(parametres["kg_par_habitant_jour"])
        self.densite_t_m3 = float(parametres.get("densite_dechets_t_m3", 0.35))
        self.taux_abonnement = float(parametres["taux_abonnement"])
        self.distance_max_m = float(parametres["distance_max_precollecte_m"])
        self.probabilite_panne = float(parametres.get("probabilite_panne_jour", 0.15))
        self.budget_du_jour = float(parametres["budget_mensuel"]) / 30

        points = plan.get("points", [])
        self.nb_points = len(points)
        self.capacite_point = float(parametres["capacite_point_m3"])
        self.stock_aux_points = np.zeros(self.nb_points)
        self.point_sature = np.zeros(self.nb_points, dtype=bool)
        self.depot_aux_points = np.zeros(self.nb_points)

        nb_carreaux = len(demande["habitants"])
        self.attente_precollecte = np.zeros(nb_carreaux)
        self.jete_en_depotoir = np.zeros(nb_carreaux)
        self.volume_depotoirs = float(plan.get("volume_depotoirs_initial", 0))

        self.menages = self._creer_menages(demande, points)
        self._creer_precollecteurs()
        self.brigade = BrigadeLaabal(self, int(parametres.get("effectif_brigade", 0)))
        self.mairie = Mairie(self, plan)
        self.journal = []

    def _creer_menages(self, demande, points):
        """Un agent par carreau bâti, rattaché au point de regroupement le plus proche."""
        positions = np.array([[p["longitude"], p["latitude"]] for p in points]) if points else None
        centres = demande["centres"]
        agents = []
        if positions is not None and len(positions):
            lat_moyenne = math.radians(float(centres[:, 1].mean()))
            dx = (centres[:, 0][:, None] - positions[:, 0][None, :]) * 111320 * math.cos(lat_moyenne)
            dy = (centres[:, 1][:, None] - positions[:, 1][None, :]) * 110540
            distances = np.sqrt(dx * dx + dy * dy)
            plus_proche = distances.argmin(axis=1)
            distance_min = distances[np.arange(len(centres)), plus_proche]
        else:
            plus_proche = np.full(len(centres), -1)
            distance_min = np.full(len(centres), 1e9)
        for carreau, habitants in enumerate(demande["habitants"]):
            if habitants <= 0:
                continue
            agents.append(Menages(self, carreau, float(habitants),
                                  int(plus_proche[carreau]) if positions is not None else -1,
                                  float(distance_min[carreau])))
        return agents

    def _creer_precollecteurs(self):
        """Un pré-collecteur par point de regroupement : il dessert les carreaux rattachés."""
        groupes = {}
        for agent in self.menages:
            groupes.setdefault(agent.point, []).append(agent.carreau)
        capacite = float(self.parametres.get("capacite_precollecteur_m3", 9))
        self.precollecteurs = [PreCollecteur(self, carreaux, point, capacite)
                               for point, carreaux in groupes.items() if point >= 0]

    # ------------------------------------------------------------------ un jour
    def step(self):
        self.produit_du_jour = 0.0
        self.collecte_du_jour = 0.0
        self.precollecte_du_jour = 0.0
        self.nettoye_du_jour = 0.0
        self.depense_du_jour = 0.0
        self.pannes_du_jour = 0
        self.verbalisations_du_jour = 0
        self.depot_aux_points[:] = 0

        # Ordre de la journée : les ménages sortent leurs déchets, les pré-collecteurs passent,
        # les camions ramassent, la brigade patrouille.
        for agent in self.menages:
            agent.step()
        for agent in self.precollecteurs:
            agent.step()
        self.stock_aux_points += self.depot_aux_points
        self.mairie.step()
        self.brigade.step()

        # Ce qui déborde d'un point saturé finit par terre, à côté.
        trop_plein = np.maximum(0, self.stock_aux_points - self.capacite_point)
        self.stock_aux_points -= trop_plein
        self.volume_depotoirs += float(trop_plein.sum() * 0.5)
        self.point_sature = self.stock_aux_points >= self.capacite_point * 0.9
        self.volume_depotoirs += float(self.jete_en_depotoir.sum())
        self.jete_en_depotoir[:] = 0

        taux = self.collecte_du_jour / self.produit_du_jour if self.produit_du_jour else 0
        self.journal.append({
            "jour": len(self.journal) + 1,
            "produit_m3": round(self.produit_du_jour, 1),
            "collecte_m3": round(self.collecte_du_jour, 1),
            "precollecte_m3": round(self.precollecte_du_jour, 1),
            "nettoye_m3": round(self.nettoye_du_jour, 1),
            "volume_depotoirs_m3": round(self.volume_depotoirs, 1),
            "points_satures": int(self.point_sature.sum()),
            "taux_collecte": round(taux, 3),
            "depense_fcfa": round(self.depense_du_jour),
            "pannes": self.pannes_du_jour,
            "verbalisations": self.verbalisations_du_jour,
            "taux_abonnement": round(float(np.mean([a.abonnes for a in self.menages])), 3),
        })

    def resume(self) -> dict:
        if not self.journal:
            return {}
        produit = sum(j["produit_m3"] for j in self.journal)
        collecte = sum(j["collecte_m3"] for j in self.journal)
        return {
            "jours": len(self.journal),
            "produit_m3": round(produit),
            "collecte_m3": round(collecte),
            "taux_collecte": round(collecte / produit, 3) if produit else 0,
            "volume_depotoirs_m3": round(self.volume_depotoirs),
            "depense_fcfa": round(sum(j["depense_fcfa"] for j in self.journal)),
            "points_satures": self.journal[-1]["points_satures"],
            "taux_abonnement_final": self.journal[-1]["taux_abonnement"],
            "verbalisations": sum(j["verbalisations"] for j in self.journal),
        }


def simuler(demande: dict, plan: dict, parametres: dict, jours: int = 30, graine: int = 2026) -> dict:
    """Fait tourner la filière pendant `jours` jours et renvoie le journal et le résumé."""
    modele = Filiere(demande, plan, parametres, graine)
    for _ in range(max(1, min(int(jours), 365))):
        modele.step()
    return {"journal": modele.journal, "resume": modele.resume(),
            "agents": {"menages": len(modele.menages), "precollecteurs": len(modele.precollecteurs),
                       "brigade": 1, "mairie": 1}}
