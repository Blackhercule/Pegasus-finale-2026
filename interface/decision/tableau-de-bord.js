/* Tableau de bord de la mairie (T22) : les trois chaînes d'un coup d'œil.
 *
 * Il ne lit que des adresses qui existent : les listes de dossiers (classées par urgence), les
 * chaînes (étapes et nombre de dossiers à chacune), le contour de la commune pour la petite
 * carte. Le plan de gestion, plus long à calculer, n'est demandé que sur un clic.
 */
"use strict";

(function () {
  const { CHAINES, appel, ouvrirLaSession, el, svg, nombre, pastilleUrgence, titreDuDossier,
          adresseDuDetail, estClos, barres } = Plateforme;
  const $ = (id) => document.getElementById(id);
  const COULEURS = { depotoir: "#a0522d", fuite: "#0077b6", nuisance: "#6b3fa0" };

  /* Les étapes d'une chaîne dans l'ordre du travail : de « signalé » en suivant les
     « suivante », puis les étapes de clôture qui restent (classé sans suite…). */
  function ordreDesEtapes(chaine) {
    const ordre = [];
    let cle = "signale";
    while (cle && chaine.etapes[cle] && !ordre.includes(cle)) {
      ordre.push(cle);
      cle = chaine.etapes[cle].suivante;
    }
    for (const autre of Object.keys(chaine.etapes)) if (!ordre.includes(autre)) ordre.push(autre);
    return ordre;
  }

  function graphiqueDesEtapes(chaine, couleur) {
    return barres(ordreDesEtapes(chaine).map((cle) => ({
      libelle: chaine.etapes[cle].nom, valeur: chaine.comptes[cle] || 0,
      couleur: chaine.etapes[cle].suivante === null ? "#0e6b3a" : couleur,
    })));
  }

  function remplir(id, contenu) {
    $(id).replaceChildren(contenu);
  }

  /* La petite carte : le contour de la commune et un point par dossier ouvert, dessinés en
     SVG. La projection est la plus simple qui soit (longitude et latitude à plat, corrigées de
     la latitude) : à l'échelle d'une ville, l'écart avec une vraie projection est invisible. */
  function miniCarte(contour, dossiers) {
    const geometrie = contour.features[0].geometry;
    const polygones = geometrie.type === "Polygon" ? [geometrie.coordinates] : geometrie.coordinates;
    const points = polygones.flat(2);
    const lons = points.map((p) => p[0]), lats = points.map((p) => p[1]);
    const ouest = Math.min(...lons), est = Math.max(...lons), sud = Math.min(...lats), nord = Math.max(...lats);
    const facteur = Math.cos(((sud + nord) / 2) * Math.PI / 180);
    const largeur = 400, marge = 12;
    const echelle = (largeur - 2 * marge) / ((est - ouest) * facteur);
    const hauteur = Math.round((nord - sud) * echelle + 2 * marge);
    const x = (lon) => marge + (lon - ouest) * facteur * echelle;
    const y = (lat) => marge + (nord - lat) * echelle;

    const dessin = svg("svg", { viewBox: `0 0 ${largeur} ${hauteur}`, class: "mini-carte",
                                role: "img", "aria-label": "Carte des dossiers ouverts" });
    const trace = polygones.map((polygone) => polygone.map((anneau) =>
      "M" + anneau.map((p) => x(p[0]).toFixed(1) + "," + y(p[1]).toFixed(1)).join("L") + "Z").join("")).join("");
    dessin.append(svg("path", { d: trace, fill: "#ffffff", stroke: "#1e2455", "stroke-width": 1.5,
                                "stroke-dasharray": "5 3" }));
    // Les plus urgents en dernier, pour qu'ils soient dessinés par-dessus.
    for (const { type, d } of [...dossiers].sort((a, b) => a.note - b.note)) {
      if (d.latitude == null || d.longitude == null) continue;
      const lien = svg("a", { href: adresseDuDetail(type, d.id) });
      lien.append(svg("title", {}, titreDuDossier(type, d) + " — urgence " + Math.round(d.priorite?.note || 0)));
      lien.append(svg("circle", { cx: x(d.longitude).toFixed(1), cy: y(d.latitude).toFixed(1),
                                  r: 4 + Math.min(6, (d.priorite?.note || 0) / 15),
                                  fill: COULEURS[type], "fill-opacity": 0.85, stroke: "#fff", "stroke-width": 1.5 }));
      dessin.append(lien);
    }
    return dessin;
  }

  function ligneDeFile(type, d) {
    const quoi = [CHAINES[type].nom, d.etape_nom, d.quartier].filter(Boolean).join(" · ");
    const raisons = d.priorite && d.priorite.raisons.length ? d.priorite.raisons.join(" · ") : "aucun facteur particulier";
    return el("li", {}, el("a", { href: adresseDuDetail(type, d.id) },
      pastilleUrgence(d.priorite),
      el("span", {}, el("span", { class: "titre" }, titreDuDossier(type, d)),
         el("span", { class: "raisons" }, quoi), el("span", { class: "raisons" }, raisons))));
  }

  async function charger() {
    const session = await ouvrirLaSession();
    $("sous-titre").textContent = "Ce qui attend les services aujourd'hui, le "
      + new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })
      + " · " + (session.poste_nom || "").split(" — ")[0];

    const types = Object.keys(CHAINES);
    const [listes, chaines] = await Promise.all([
      Promise.all(types.map((t) => appel(CHAINES[t].liste))),
      Promise.all(types.map((t) => appel(CHAINES[t].chaine))),
    ]);
    const ouverts = {};
    types.forEach((t, i) => {
      ouverts[t] = listes[i].filter((d) => !estClos(chaines[i], d.etape));
    });
    const tous = types.flatMap((t) => ouverts[t].map((d) => ({ type: t, d, note: d.priorite?.note || 0 })));
    tous.sort((a, b) => b.note - a.note);

    $("c-ouverts").textContent = nombre(tous.length);
    $("c-urgents").textContent = nombre(tous.filter((x) => x.note >= 60).length);
    $("c-depotoirs").textContent = nombre(ouverts.depotoir.length);
    $("c-fuites").textContent = nombre(ouverts.fuite.length);
    $("c-nuisances").textContent = nombre(ouverts.nuisance.length);

    const file = tous.slice(0, 8).map((x) => ligneDeFile(x.type, x.d));
    $("file").replaceChildren(...(file.length ? file : [el("li", { class: "vide" }, "Aucun dossier ouvert.")]));

    remplir("g-depotoirs", graphiqueDesEtapes(chaines[0], COULEURS.depotoir));
    remplir("g-fuites", graphiqueDesEtapes(chaines[1], COULEURS.fuite));
    remplir("g-nuisances", graphiqueDesEtapes(chaines[2], COULEURS.nuisance));
    const parNature = { "Dépotoirs": { valeur: ouverts.depotoir.length, couleur: COULEURS.depotoir },
                        "Fuites d'eau": { valeur: ouverts.fuite.length, couleur: COULEURS.fuite } };
    for (const n of ouverts.nuisance) {
      const nom = n.nature_nom || "Autre nuisance";
      parNature[nom] = parNature[nom] || { valeur: 0, couleur: COULEURS.nuisance };
      parNature[nom].valeur += 1;
    }
    remplir("g-natures", barres(Object.entries(parNature).map(([libelle, v]) => ({ libelle, ...v })),
                                { marge: 190 }));

    try {
      const contour = await fetch("/donnees/commune.geojson").then((r) => r.json());
      remplir("mini-carte", miniCarte(contour, tous));
    } catch {
      remplir("mini-carte", el("p", { class: "vide" }, "Contour de la commune indisponible."));
    }
  }

  /* Le plan de gestion, sur demande : GET /api/plan avec les paramètres de départ. */
  $("calculer").addEventListener("click", async () => {
    const bouton = $("calculer");
    bouton.disabled = true;
    $("etat-plan").textContent = "Calcul en cours…";
    const debut = performance.now();
    try {
      const plan = await appel("/api/plan");
      const alertes = (plan.controles || []).filter((c) => c.etat !== "ok").length;
      const lignes = [
        ["Points de regroupement", nombre(plan.points.length)],
        ["Tournées", nombre(plan.tournees.length)],
        ["Camions disponibles", nombre(plan.camions_disponibles)],
        ["Arrêts non desservis", nombre(plan.non_desservis.length)],
        ["Kilomètres par jour", nombre(plan.couts.km_par_jour)],
        ["Coût mensuel", nombre(plan.couts.cout_par_mois) + " F CFA"],
        ["Contrôles de cohérence en alerte", alertes + " sur " + (plan.controles || []).length],
      ];
      $("chiffres-plan").tBodies[0].replaceChildren(...lignes.map(([nom, valeur]) =>
        el("tr", {}, el("th", { scope: "row" }, nom), el("td", {}, valeur))));
      $("chiffres-plan").hidden = false;
      $("etat-plan").textContent = "Calculé en " + ((performance.now() - debut) / 1000).toFixed(1) + " s.";
    } catch (e) {
      $("etat-plan").textContent = "Le plan n'a pas pu être calculé : " + e.message;
    } finally {
      bouton.disabled = false;
    }
  });

  charger().catch((e) => {
    $("file").replaceChildren(el("li", { class: "vide" }, "Chargement impossible : " + e.message));
  });
})();
