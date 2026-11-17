/* La liste latérale de la carte (T22) : les dossiers ouverts des trois chaînes, du plus urgent
 * au moins urgent. Un clic centre la carte sur le dossier ; un lien ouvre sa page de détail.
 *
 * Ce fichier s'ajoute à la carte SANS toucher à carte.js : le panneau ☰, les couches, les
 * réglages du plan, « Recalculer » et les contrôles de cohérence sont exactement ceux d'avant.
 * Il n'utilise de la carte que `carte.flyTo` et `carte.resize`.
 */
"use strict";

(function () {
  const { CHAINES, appel, el, pastilleUrgence, titreDuDossier, adresseDuDetail, estClos } = Plateforme;
  const NOMS = { depotoir: "Dépotoirs", fuite: "Fuites", nuisance: "Nuisances" };
  let tous = [];
  let filtre = "";
  let repere = null;                       // le marqueur posé sur le dossier choisi

  const application = document.getElementById("application");
  const liste = el("ol", { class: "liste-carte__elements" }, el("li", { class: "liste-carte__vide" }, "Chargement…"));
  const compte = el("span", { class: "liste-carte__compte" });
  const filtres = el("div", { class: "liste-carte__filtres", role: "group", "aria-label": "Filtrer la liste" });
  for (const [cle, nom] of [["", "Tous"], ...Object.entries(NOMS)]) {
    const bouton = el("button", { type: "button", "data-filtre": cle, "aria-pressed": String(cle === "") }, nom);
    bouton.addEventListener("click", () => {
      filtre = cle;
      filtres.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === bouton)));
      afficher();
    });
    filtres.append(bouton);
  }
  const bascule = el("button", { type: "button", class: "liste-carte__bascule", "aria-expanded": "false",
                                 "aria-controls": "liste-carte" }, "Liste des signalements");
  const cote = el("aside", { class: "liste-carte", id: "liste-carte", "aria-label": "Signalements ouverts" },
    el("div", { class: "liste-carte__entete" }, el("h2", {}, "Signalements ouverts"), compte),
    filtres, liste);
  application.prepend(cote);
  application.append(bascule);
  document.body.classList.add("avec-liste");
  // La carte a mesuré son cadre avant que la liste prenne sa place : elle se remesure.
  carte.on("load", () => carte.resize());
  carte.resize();

  // Sur téléphone, la liste est un volet qu'on ouvre et ferme.
  bascule.addEventListener("click", () => {
    const ouvert = !document.body.classList.contains("liste-ouverte");
    document.body.classList.toggle("liste-ouverte", ouvert);
    bascule.setAttribute("aria-expanded", String(ouvert));
    bascule.textContent = ouvert ? "Voir la carte" : "Liste des signalements";
  });

  function centrer(x) {
    const position = [x.d.longitude, x.d.latitude];
    carte.flyTo({ center: position, zoom: 16, duration: 900 });
    if (repere) repere.remove();
    repere = new maplibregl.Marker({ element: el("div", { class: "liste-carte__repere" }) })
      .setLngLat(position).addTo(carte);
    if (document.body.classList.contains("liste-ouverte")) bascule.click();   // téléphone : on montre la carte
  }

  function ligne(x) {
    const { type, d } = x;
    const quoi = [d.etape_nom, d.quartier].filter(Boolean).join(" · ");
    const choisir = el("button", { type: "button", class: "liste-carte__choisir",
                                   title: "Centrer la carte sur ce dossier" },
      pastilleUrgence(d.priorite),
      el("span", {}, el("strong", {}, titreDuDossier(type, d)), el("span", { class: "quoi" }, quoi)));
    choisir.addEventListener("click", () => {
      liste.querySelectorAll(".choisi").forEach((n) => n.classList.remove("choisi"));
      choisir.parentElement.classList.add("choisi");
      centrer(x);
    });
    return el("li", { class: "famille-" + CHAINES[type].famille }, choisir,
              el("a", { href: adresseDuDetail(type, d.id), class: "liste-carte__ouvrir" }, "Ouvrir le dossier"));
  }

  function afficher() {
    const retenus = tous.filter((x) => !filtre || x.type === filtre);
    compte.textContent = String(retenus.length);
    liste.replaceChildren(...(retenus.length ? retenus.map(ligne)
      : [el("li", { class: "liste-carte__vide" }, "Aucun dossier ouvert.")]));
  }

  async function charger() {
    await Plateforme.ouvrirLaSession();
    const types = Object.keys(CHAINES);
    const [listes, chaines] = await Promise.all([
      Promise.all(types.map((t) => appel(CHAINES[t].liste))),
      Promise.all(types.map((t) => appel(CHAINES[t].chaine))),
    ]);
    tous = types.flatMap((type, i) => listes[i]
      .filter((d) => !estClos(chaines[i], d.etape) && d.latitude != null)
      .map((d) => ({ type, d })));
    tous.sort((a, b) => (b.d.priorite?.note || 0) - (a.d.priorite?.note || 0));
    afficher();
  }

  charger().catch((e) => liste.replaceChildren(el("li", { class: "liste-carte__vide" }, "Liste indisponible : " + e.message)));
})();
