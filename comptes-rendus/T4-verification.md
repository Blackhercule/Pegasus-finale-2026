# T4 — déjà faite par le coordinateur, non refaite ; défauts trouvés — 16/11 18 h 55

- Session : dans le cloud.
- Franck m'a demandé T4 (« fais T4 et pousse sur main »). J'avais commencé une version à part
  quand `main` a reçu celle du coordinateur, marquée « Fait » dans `TACHES.md`. Selon la règle
  de `TACHES.md`, je ne l'ai **pas refaite** : ma version n'est ni poussée ni fusionnée.
- En revanche, j'ai lancé mes propres pièges (une soixantaine) contre la T4 de `main`
  (commit 63390cc, contrôles inchangés depuis sauf ajouts). Défauts relevés, à corriger par un
  correctif si l'équipe le décide :
  - **Erreurs 500** sur `POST /api/signalements` : latitude, volume, précision ou longueur
    donnés comme un entier de 400 chiffres (`float()` lève `OverflowError` dans `nombre()`) ;
    un texte contenant une moitié de caractère `"\ud800"` (commentaire, source, id_client :
    refus d'encodage UTF-8 à l'écriture) ; un corps JSON emboîté 200 000 fois
    (`RecursionError`). Aussi `GET /api/signalements?limite=abc` et `?limite=1e9`.
  - **Pièges pris en compte** : date illisible (« hier matin », mois 13, nombre, liste)
    remplacée par l'heure de réception au lieu d'être rejetée ; volume `1e999`, `NaN` ou en
    lettres ignoré quand une taille valable est donnée ; taille inconnue ignorée quand un volume
    est donné ; type inconnu changé en « autre » ; commentaire de 600 ou 1 000 000 caractères
    et source de 200 caractères tronqués au lieu d'être rejetés (la conception dit
    `format_invalide`) ; précision en lettres ignorée.
  - **Lots** : deux lignes d'un même fichier avec deux sources inventées font un dépotoir
    « vérifié » (un fichier peut se confirmer lui-même) ; mille copies du même point donnent
    mille signalements recevables ; le même fichier envoyé deux fois compte deux fois ; une
    ligne GeoJSON dont la géométrie est un texte fait refuser **tout** le lot (400) ; un CSV
    venant d'un tableur (marque en tête de fichier, ou points-virgules et virgules décimales)
    est entièrement rejeté.
  - Photo : seuls les premiers octets sont lus ; « 3 octets de JPEG puis du HTML » est accepté.
    Le risque reste faible (servi en `image/jpeg` avec `nosniff`).
- Ma version parallèle (contrôles et lecture de lots robustes, 72 pièges, 146 tests) peut
  servir de source pour un correctif ; elle est gardée hors du dépôt pour ne pas embrouiller.
