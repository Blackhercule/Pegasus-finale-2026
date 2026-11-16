# Proposition de l'équipe PEGASUS — challenge 01 « Assainissement de Ouaga »

## En une phrase

Un outil libre qui suit toute la chaîne — **signaler, vérifier, cartographier, planifier,
simuler, comparer, partager** — installé en une commande sur un PC de la mairie, et qui
fonctionne sans Internet.

## Adopter, adapter, améliorer

| | Ce que nous faisons | Briques open source |
|---|---|---|
| **Adopter** | Nous ne réinventons ni la carte, ni l'optimisation, ni la simulation | OpenStreetMap et Open Buildings (données), MapLibre et PMTiles (carte hors ligne), OR-Tools (tournées), SciPy (trajets sur le réseau routier), Mesa (simulation multi-agents), Flask et SQLite (application) |
| **Adapter** | Nous les réglons pour Ouagadougou : limites de la commune et de ses secteurs, réseau de voies revêtues ou non, saison des pluies, acteurs réels de la filière (ménages, pré-collecteurs, brigade Laabal, mairie), interface en français utilisable sur téléphone | Fichiers de données et de paramètres propres à la commune |
| **Améliorer** | Nous ajoutons ce qui manque entre ces briques : des contrôles qui écartent les signalements piégés en expliquant pourquoi, un plan qui se recalcule en quelques secondes et affiche lui-même ses contrôles de cohérence, la comparaison de scénarios, et l'export vers OpenStreetMap | Notre code, sous licence libre AGPL-3.0, avec ses tests automatisés |

## Ce que le jury verra

1. **Signaler** : sur un téléphone, position, photo et taille du dépotoir ; la saisie fonctionne
   sans réseau et s'envoie au retour.
2. **Vérifier** : chaque signalement est contrôlé (dans la commune, pas dans un barrage, date et
   volume plausibles, doublons regroupés, rafales d'une même source mises de côté). Un
   signalement écarté affiche son motif.
3. **Cartographier** : la carte des dépotoirs vérifiés, sur un fond OpenStreetMap servi par
   notre propre machine.
4. **Planifier** : l'emplacement des points de regroupement et les tournées des camions, avec
   leurs capacités, leurs horaires et le budget.
5. **Simuler** : ménages, pré-collecteurs, brigade Laabal et mairie agissent jour après jour ;
   on lit l'effet sur les tonnes collectées, les dépotoirs et les coûts.
6. **Comparer** : on change la population, les abonnements, les camions, les fréquences ou le
   budget, et deux scénarios s'affichent côte à côte.

## Face à l'épreuve en direct

- **Signalements piégés** : ils passent par les mêmes contrôles que les autres. Seuls les
  signalements recevables entrent dans le plan ; les autres restent visibles avec leur motif.
- **Camions en panne, saison des pluies, nouveau quartier** : ce sont des paramètres, pas du
  code. Le plan est recalculé, et une liste de contrôles dit s'il reste cohérent : capacités
  respectées, horaires tenus, budget tenu ou dépassement chiffré, points non desservis nommés.

## Bien commun

- La carte des dépotoirs vérifiés, exportée au format d'OpenStreetMap et versée par un membre de
  l'équipe après relecture, selon les règles de la communauté.
- Un outil réutilisable par une autre commune : il suffit de fournir son extrait
  OpenStreetMap et son fichier de paramètres.
- Aucune dépendance à un service en ligne : données, fond de carte et bibliothèques sont dans
  le dépôt.
