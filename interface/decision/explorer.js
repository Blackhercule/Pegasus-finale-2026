/* Explorer (T22) : tous les dossiers en grille de cartes, filtrés sans recharger la page.
 *
 * Les listes ne contiennent pas les photos : chaque carte va chercher le détail de son dossier
 * au moment où elle apparaît à l'écran (IntersectionObserver). Ainsi la page reste légère même
 * si le jury injecte des centaines de signalements.
 */
"use strict";

(function () {
  const { CHAINES, appel, ouvrirLaSession, el, nombre, date, pastilleUrgence, titreDuDossier,
          adresseDuDetail, estClos } = Plateforme;
  const $ = (id) => document.getElementById(id);
  const SANS_QUARTIER = "__aucun__";
  let dossiers = [];                  // [{ type, d, nature, quartier, clos }]

  /* Le quartier d'un dossier : saisi par l'habitant pour une fuite ou une nuisance. Les
     dépotoirs n'en ont pas (les quartiers manquent dans l'extrait OpenStreetMap). */
  const quartierDe = (d) => (d.quartier || "").trim();

  function natureDe(type, d) {
    if (type === "depotoir") return "Dépotoir";
    if (type === "fuite") return "Fuite d'eau";
    return d.nature_nom || "Nuisance";
  }

  function carte(x) {
    const { type, d } = x;
    const photo = el("div", { class: "photo" },
      el("div", { class: "sans" }, el("span", { "aria-hidden": "true" }, "📷"), el("span", {}, "Pas de photo")),
      pastilleUrgence(d.priorite));
    const lieu = [x.quartier || (type === "depotoir" ? "" : "Quartier non précisé"),
                  "vu le " + date(d.premier_vu, false)].filter(Boolean).join(" · ");
    const lien = el("a", { class: "tuile", href: adresseDuDetail(type, d.id) },
      photo,
      el("div", { class: "corps" },
        el("div", { class: "ligne" },
          // Pour une nuisance, le titre dit déjà laquelle : l'étiquette dit seulement la famille.
          el("span", { class: "etiquette " + CHAINES[type].famille },
             type === "nuisance" ? "Nuisance" : x.nature),
          el("span", { class: "etiquette" + (x.clos ? " clos" : "") }, d.etape_nom)),
        el("h2", {}, titreDuDossier(type, d)),
        el("p", { class: "lieu" }, lieu),
        el("p", { class: "raisons" }, d.priorite && d.priorite.raisons.length
          ? d.priorite.raisons.join(" · ") : "Aucun facteur d'urgence particulier.")));
    lien.dataset.type = type;
    lien.dataset.id = d.id;
    return el("li", {}, lien);
  }

  /* La photo d'un dossier, chargée quand sa carte devient visible. */
  const observateur = new IntersectionObserver((entrees) => {
    for (const entree of entrees) {
      if (!entree.isIntersecting) continue;
      observateur.unobserve(entree.target);
      const { type, id } = entree.target.dataset;
      appel(CHAINES[type].detail + id).then((detail) => {
        const avec = (detail.signalements || []).find((s) => s.photo);
        if (!avec) return;
        const image = el("img", { src: "/api/fichiers/" + encodeURI(avec.photo), alt: "" });
        // La photo prend la place de « Pas de photo » une fois chargée, pas avant.
        image.addEventListener("load", () => entree.target.querySelector(".photo .sans")?.remove());
        entree.target.querySelector(".photo").prepend(image);
      }).catch(() => {});
    }
  }, { rootMargin: "200px" });

  function afficher() {
    const nature = $("f-nature").value, etape = $("f-etape").value, quartier = $("f-quartier").value;
    const retenus = dossiers.filter((x) =>
      (!nature || x.nature === nature)
      && (etape === "" || (etape === "ouverts" ? !x.clos : x.d.etape_nom === etape))
      && (!quartier || (quartier === SANS_QUARTIER ? !x.quartier : x.quartier === quartier)));
    $("compte").textContent = retenus.length + " dossier" + (retenus.length > 1 ? "s" : "")
      + " sur " + dossiers.length;
    const cartes = retenus.map(carte);
    $("grille").replaceChildren(...(cartes.length ? cartes
      : [el("li", { class: "vide" }, "Aucun dossier ne correspond à ces filtres.")]));
    $("grille").querySelectorAll(".tuile").forEach((t) => observateur.observe(t));
  }

  function options(id, valeurs) {
    const select = $(id);
    for (const [valeur, libelle] of valeurs) select.append(el("option", { value: valeur }, libelle));
  }

  async function charger() {
    await ouvrirLaSession();
    const types = Object.keys(CHAINES);
    const [listes, chaines] = await Promise.all([
      Promise.all(types.map((t) => appel(CHAINES[t].liste))),
      Promise.all(types.map((t) => appel(CHAINES[t].chaine))),
    ]);
    dossiers = types.flatMap((type, i) => listes[i].map((d) => ({
      type, d, nature: natureDe(type, d), quartier: quartierDe(d), clos: estClos(chaines[i], d.etape),
    })));
    dossiers.sort((a, b) => (b.d.priorite?.note || 0) - (a.d.priorite?.note || 0));

    const tri = (a, b) => a.localeCompare(b, "fr");
    options("f-nature", [...new Set(dossiers.map((x) => x.nature))].sort(tri).map((n) => [n, n]));
    options("f-etape", [...new Set(dossiers.map((x) => x.d.etape_nom))].sort(tri).map((n) => [n, n]));
    const quartiers = [...new Set(dossiers.map((x) => x.quartier).filter(Boolean))].sort(tri);
    options("f-quartier", [...quartiers.map((q) => [q, q]), [SANS_QUARTIER, "Non précisé"]]);
    afficher();
  }

  $("filtres").addEventListener("change", afficher);
  // « Effacer » remet les listes à leur premier choix, puis on réaffiche.
  $("filtres").addEventListener("reset", () => setTimeout(afficher, 0));
  $("filtres").addEventListener("submit", (e) => e.preventDefault());

  charger().catch((e) => {
    $("grille").replaceChildren(el("li", { class: "vide" }, "Chargement impossible : " + e.message));
  });
})();
