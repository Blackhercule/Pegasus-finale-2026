# Cahier des charges — Gestion de cave (version 1)

Ce document reprend les besoins exprimés oralement par l'équipe et précise ce que fait la
première version de l'application. Les points encore ouverts sont listés à la fin (§ 7) :
à trancher ensemble avant la version 2.

## 1. Contexte

Une cave (dépôt de boissons) vend des boissons **par caisse** : bières, sucreries, eaux… Le
propriétaire (le **patron**) n'est pas toujours sur place ; plusieurs **gérants** tiennent le
comptoir. Il faut :

- enregistrer chaque vente, au **détail** ou en **gros**, et remettre un **reçu clair** ;
- suivre les clients qui paient **à crédit** et ce qu'ils doivent ;
- tenir compte des **bouteilles cassées** et des **caisses disparues** ;
- **faire les comptes en fin de soirée** ;
- permettre au patron de **tout suivre, même à distance**, et de voir l'**évolution mois par mois**.

## 2. Les acteurs

| Acteur | Accès | Ce qu'il fait |
|---|---|---|
| **Patron** (propriétaire) | Identifiant + mot de passe | Voit tout, en direct : ventes de chaque gérant, argent encaissé, crédits, stock, pertes, journal de toutes les opérations, statistiques. Crée et bloque les comptes des gérants. Fixe les prix. Seul à pouvoir annuler une opération. |
| **Gérant** | Identifiant + mot de passe (donnés par le patron) | Vend (détail ou gros), imprime les reçus, inscrit les crédits et les remboursements, enregistre les arrivages et les casses, fait les comptes de **sa** caisse en fin de journée. |
| **Client** | Aucun | Reçoit un reçu. S'il prend à crédit, sa dette est suivie à son nom. |

## 3. Besoins fonctionnels

| N° | Besoin | Dans la version 1 |
|---|---|---|
| **F1** | Chaque personne a son compte (identifiant + mot de passe). Le patron crée les comptes des gérants, change leur mot de passe, les désactive quand ils quittent la cave. | Oui — page **Gérants** |
| **F2** | **Espace du patron** : tout suivre, même absent. | Oui — **Tableau de bord** (chiffres du jour, chaque gérant, dettes, alertes de stock, dernières opérations ; mise à jour toute seule chaque minute) et **Journal** (qui a fait quoi, à quelle heure : ventes, arrivages, casses, remboursements, annulations, changements de prix, connexions, mots de passe refusés). |
| **F3** | **Espace du gérant** : accès rapide aux opérations du comptoir. | Oui — gros boutons : Nouvelle vente, Crédit/remboursement, Arrivage, Casse/perte, Mes comptes du jour. |
| **F4** | **Répertorier les boissons** : nom, format, nombre de bouteilles par caisse, prix. | Oui — page **Produits et prix** (prix d'achat, prix détail et prix gros d'une caisse, seuil d'alerte). |
| **F5** | **Vente au détail et vente en gros**, toujours par caisse (le détail, c'est une ou quelques caisses ; le gros, de grandes quantités pour les revendeurs). | Oui — le gérant choisit « Détail » ou « Gros » ; le prix de la caisse change en conséquence. Plusieurs boissons par vente. |
| **F6** | **Tirer un reçu clair.** | Oui — reçu imprimable (format ticket 80 mm, ou A4, ou PDF depuis le téléphone) : cave, n° du reçu, date et heure, gérant, client, boissons, prix, total, payé, reste à payer, dette totale du client. |
| **F7** | **Ventes à crédit** : savoir qui a payé à crédit, combien il doit, et enregistrer ses remboursements. | Oui — vente payée en totalité, en partie ou pas du tout ; page **Clients et crédits** (qui doit combien, historique) ; remboursement avec reçu. |
| **F8** | **Stock** des boissons, avec arrivages du fournisseur. | Oui — page **Arrivages** ; stock calculé automatiquement (en caisses + bouteilles) ; alerte quand un produit passe sous son seuil. |
| **F9** | **Bouteilles cassées, caisses disparues.** | Oui — page **Casses et pertes** : type (cassées, disparues, avariées, autre), quantité en caisses et/ou bouteilles, explication. Retiré du stock, valorisé au prix d'achat, visible par le patron. |
| **F10** | **Les comptes de fin de soirée** : nombre d'opérations, transactions, total détail et gros, crédits du jour pris en compte. | Oui — page **Point du jour** (imprimable), pour toute la cave ou pour un gérant : ventes détail / gros, argent encaissé par mode (espèces, Orange Money, Moov Money), **espèces attendues en caisse**, crédits accordés, remboursements reçus, casses, arrivages, ventes annulées, détail par boisson et par gérant. |
| **F11** | **Statistiques du mois** pour suivre l'évolution dans le temps ; les besoins. | Oui — page **Statistiques** (patron) : chiffre d'affaires et comparaison avec le mois précédent, marge estimée, part du gros et du détail, évolution sur 12 mois, ventes de chaque jour, boissons les plus vendues, ventes par gérant. Et dans **Stock**, les **besoins** : ce qu'il faut commander pour tenir 30 jours au rythme des ventes. |
| **F12** | Corriger une erreur sans pouvoir effacer en cachette. | Oui — seul le patron **annule** une opération, avec un motif obligatoire ; elle reste visible, barrée, dans les listes et le journal. |

## 4. Règles de gestion

1. **Le stock n'est jamais tapé à la main** : il vaut toujours *arrivages − ventes − pertes*. Le
   stock de départ s'enregistre comme un arrivage « Stock initial ».
2. On ne peut pas vendre ni déclarer perdu **plus que le stock**.
3. Le **prix est figé sur chaque vente** : changer un prix ne modifie pas les reçus passés.
4. Une vente **à crédit** (même partiel) exige un **client** (choisi ou créé pendant la vente).
5. Un remboursement ne peut pas dépasser ce que le client doit.
6. **Dette d'un client** = crédits des ventes − remboursements (opérations annulées exclues).
7. **Espèces attendues en caisse** = espèces reçues pour les ventes + espèces reçues en remboursement.
8. Un **gérant ne voit que ses propres ventes, reçus et comptes** ; le patron voit tout.
9. **Seul le patron** fixe les prix, gère les comptes, annule une opération, voit les statistiques
   et le journal.
10. Une opération n'est **jamais effacée** : elle est annulée, avec qui, quand et pourquoi.
11. On ne peut pas annuler un arrivage dont les caisses sont déjà vendues.

## 5. Exigences non fonctionnelles

- **En français**, avec des termes de tous les jours.
- **Utilisable sur téléphone** (gros boutons, une colonne) comme sur PC.
- **En ligne et gratuit** pour l'essai : hébergement Render, plan gratuit (voir `HEBERGEMENT.md`).
  Peut aussi tourner sur un PC de la cave (voir `README.md`).
- **Sécurité** : mots de passe stockés hachés par Django (jamais en clair) ; règles de mot de passe
  (8 caractères minimum, pas trop courant, pas proche de l'identifiant) ; connexion en HTTPS une
  fois en ligne ; session fermée au bout de 12 heures ; protection des formulaires (jeton CSRF) ;
  tentatives de connexion refusées inscrites au journal ; aucun secret dans le code.
- **Simple à expliquer** : un seul langage (Python, avec Django), pas de bibliothèque JavaScript,
  code commenté en français.

## 6. Hors de la version 1 (pistes pour la suite)

- **Emballages consignés** (caisses et bouteilles vides rendues ou dues par les clients).
- **Clôture de caisse enregistrée** : saisir l'argent compté en fin de soirée et garder l'écart.
- Envoi du reçu par **WhatsApp ou SMS**, impression sur **imprimante ticket Bluetooth**.
- Remise ou **prix négocié** pour un gros client.
- **Export Excel** des ventes et des comptes.
- **Blocage après plusieurs mots de passe faux** (aujourd'hui, ils sont seulement inscrits au journal).
- Fonctionnement **sans Internet** sur le téléphone, puis synchronisation.
- Plusieurs caves pour un même patron.
- Sauvegarde automatique de la base.

## 7. Questions à trancher

1. **Gros ou détail** : le gérant choisit-il, ou faut-il basculer automatiquement en gros à partir
   d'un nombre de caisses (ex. 10) ?
2. **Prix de gros** : un prix unique par boisson suffit-il, ou y a-t-il des prix par client ?
3. **Annulations** : faut-il permettre au gérant d'annuler sa propre vente dans les minutes qui
   suivent (aujourd'hui : patron seulement) ?
4. **Consignes** : faut-il suivre les caisses vides dès la version 2 ?
5. **Modes de paiement** : espèces, Orange Money, Moov Money, autre — en manque-t-il ?
6. Quelles **boissons, formats et prix réels** mettre au départ ? (Ceux de la démonstration sont fictifs.)
