# Énoncé — challenge 01 « Assainissement de Ouaga »

Source : le document officiel « Challenges finaux — Hackathon des Universités 2026 », reçu le
17/11 et rangé dans `enonce/`. Il remplace la photo de la feuille d'ouverture. Les exigences
reprennent l'énoncé sans l'interpréter.

**Les livrables sont désormais connus**, et trois d'entre eux n'étaient pas dans la photo
d'origine : le masquage automatique des visages et des plaques, la matrice de contribution, et
le jeu de signalements en GeoJSON. Voir les sections « Livrables » ci-dessous.

## En une phrase

« Un outil libre d'aide à la décision, du signalement des dépotoirs sauvages jusqu'au plan de
gestion de la ville, avec simulation de tous les acteurs. »

Thème de l'année : **l'Open Source**. La proposition de chaque équipe est à valider par le jury.
16 finalistes, 8 équipes par sujet.

## Exigences

| N° | Exigence (texte de l'énoncé) | Rubrique |
|---|---|---|
| E1 | Cartographie des dépotoirs et signalements vérifiés | Ce que l'outil fait |
| E2 | Plan de gestion : emplacement des points de regroupement | Ce que l'outil fait |
| E3 | Plan de gestion : tournées optimisées | Ce que l'outil fait |
| E4 | Simulation multi-agents : ménages, pré-collecteurs, brigade Laabal, mairie | Ce que l'outil fait |
| E5 | Paramètres modifiables et mis à jour (population, abonnements, camions, fréquences, budget) pour comparer des scénarios | Ce que l'outil fait |
| E6 | Carte ouverte (OpenStreetMap, Open Buildings) | Données |
| E7 | Signalements collectés par chaque équipe dans son secteur | Données |
| E8 | Paramètres de départ fixés avec la mairie | Données |
| E9 | Le jury garde un jeu de test caché | Données |
| E10 | Le jury injecte des signalements piégés | Épreuve en direct |
| E11 | Le jury change les paramètres (camions en panne, saison des pluies, nouveau quartier) : le plan doit se recalculer et rester cohérent | Épreuve en direct |
| E12 | La première carte ouverte des dépotoirs de Ouaga, versée dans OpenStreetMap | Bien commun |
| E13 | Un simulateur réutilisable par d'autres communes | Bien commun |
| E14 | Aucune dépendance à des données indisponibles | Chaque sujet |
| E15 | Une épreuve en direct impossible à préparer | Chaque sujet |
| E16 | Code sous licence libre et bien commun à la sortie | Chaque sujet |
| E17 | Mots-clés du sujet : cartographie, optimisation, simulation multi-agents, mobile | Étiquettes |
| E18 | Application de signalement hors connexion, **qui masque automatiquement les visages et les plaques d'immatriculation sur les photos** | Livrables |
| E19 | Moteur d'optimisation et simulateur multi-agents, paramètres dans un fichier documenté | Livrables |
| E20 | Tableau de bord des scénarios et plan de gestion **d'un arrondissement** | Livrables |
| E21 | Jeu de signalements en GeoJSON, sous licence ouverte | Livrables |
| E22 | Rapport : démarche, paramètres, scénarios simulés, résultats et plan de gestion | Livrables |
| E23 | Vidéo de démonstration (3 min) : du signalement à la tournée, puis un changement de paramètres et le plan recalculé | Livrables |
| E24 | Dépôt Git **public** sous licence libre | Livrables communs |
| E25 | Déploiement en une commande | Livrables communs |
| E26 | Rapport technique : contexte, architecture, choix, résultats, limites | Livrables communs |
| E27 | **Matrice de contribution par membre et par couche**, avec les briques réutilisées et leur licence | Livrables communs |

## Échéances

| Quoi | Quand |
|---|---|
| Validation de la proposition par le jury | inconnu |
| Fin du développement | inconnu (finale annoncée du 16 au 18 novembre) |
| Limite de soumission | inconnu |
| Épreuve en direct devant le jury | inconnu |

## Livrables

### Communs aux deux challenges

> Dépôt Git public sous licence libre · déploiement en une commande · vidéo de démonstration de
> 3 minutes · rapport technique (contexte, architecture, choix, résultats, limites) · matrice de
> contribution par membre et par couche, avec les briques réutilisées et leur licence

### Propres au challenge 01

> - Application de signalement hors connexion, qui masque automatiquement les visages et les
>   plaques d'immatriculation sur les photos
> - Moteur d'optimisation et simulateur multi-agents, paramètres dans un fichier documenté
> - Tableau de bord des scénarios et plan de gestion d'un arrondissement
> - Jeu de signalements en GeoJSON, sous licence ouverte
> - Rapport : démarche, paramètres, scénarios simulés, résultats et plan de gestion
> - Vidéo de démonstration (3 min) : du signalement à la tournée, puis un changement de
>   paramètres et le plan recalculé

### Où nous en sommes au 17/11 au matin

| Livrable | État |
|---|---|
| Dépôt Git public sous licence libre | Licence AGPL-3.0 en place, mais le dépôt est **privé**. À basculer. Historique vérifié : aucun secret |
| Déploiement en une commande | Fait (`installer.sh`) |
| Vidéo de 3 minutes | À refaire : la nôtre fait 2 min 18 s et montre l'ancien habillage, sans les fuites, les nuisances ni l'accueil parlé |
| Rapport technique | Éparpillé dans `docs/` ; pas de rapport unique |
| **Matrice de contribution** | **Manquante** |
| Signalement hors connexion | Fait |
| **Masquage des visages et des plaques** | **Manquant** |
| Moteur et simulateur, paramètres documentés | Fait (`donnees/ouagadougou/parametres.json`) |
| Tableau de bord des scénarios | Fait |
| Plan de gestion **d'un arrondissement** | Nous couvrons la commune entière ; le découpage par arrondissement n'est pas fait (les arrondissements manquent dans l'extrait OpenStreetMap) |
| **Jeu de signalements en GeoJSON sous licence ouverte** | **Manquant** comme jeu de données publié |
| Rapport du challenge | À assembler |

## Critères de notation et soumission

Le document officiel n'en dit rien : toujours à demander aux organisateurs.

## Questions à poser aux organisateurs

1. Sous quelle forme et à quelle heure la proposition doit-elle être validée par le jury ?
2. Quelle est l'heure limite de soumission, quels sont les critères de notation et par quel
   moyen remet-on les livrables ? (Les livrables eux-mêmes sont connus depuis le 17/11.)
3. « Plan de gestion d'un arrondissement » : lequel ? Les arrondissements ne sont pas
   cartographiés dans l'extrait OpenStreetMap dont nous disposons.
3. Sous quelle forme le jury injecte-t-il ses signalements (fichier, formulaire, API), avec
   quels champs ? Le jeu de test caché a-t-il le même format ?
4. Quand et comment sont remis les paramètres de départ fixés avec la mairie ?
5. Quel secteur est attribué à l'équipe pour la collecte des signalements, et jusqu'à quand ?
6. Pour le versement dans OpenStreetMap : quelles étiquettes, quel compte, et qui valide avant
   l'envoi ?
7. Le code du sprint et les assistants IA restent-ils autorisés pour la finale ?
