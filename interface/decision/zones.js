/* Zones à risque (C14) : carte thermique, quartiers les plus touchés, historique d'une zone,
 * dépôts récurrents, curage avant la saison des pluies.
 *
 * La carte thermique est une couche « heatmap » de MapLibre, calculée dans le navigateur à
 * partir des points : chaque signalement retenu pèse 1 s'il est vérifié, ½ s'il attend.
 * Tout le texte est posé avec textContent (Plateforme.el) : un nom ne devient jamais du code.
 */
"use strict";

(function () {
  const { appel, ouvrirLaSession, el, date, nombre } = Plateforme;
  const $ = (id) => document.getElementById(id);
  const CENTRE = [-1.5247, 12.3686];
  let carte = null, positions = {}, quartierChoisi = "";

  function filtres() {
    const p = new URLSearchParams();
    if ($("f-nature").value) p.set("nature", $("f-nature").value);
    if ($("f-jours").value) p.set("jours", $("f-jours").value);
    return p;
  }

  // ------------------------------------------------------------------ carte thermique
  function preparerCarte() {
    carte = FondCarte.carte("carte", CENTRE, 11.2);
    carte.addControl(new maplibregl.NavigationControl({ showCompass: false }));
    return new Promise((ok) => carte.on("load", () => {
      carte.addSource("points", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      carte.addLayer({
        id: "chaleur", type: "heatmap", source: "points", maxzoom: 17,
        paint: {
          "heatmap-weight": ["get", "poids"],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 10, 1, 15, 3],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 10, 18, 15, 40],
          "heatmap-opacity": 0.8,
          "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(253,231,196,0)", 0.2, "#fde7c4", 0.45, "#f6a04d", 0.7, "#e2541f", 1, "#b3001b"],
        },
      });
      carte.addLayer({
        id: "points-proches", type: "circle", source: "points", minzoom: 14,
        paint: { "circle-radius": 5, "circle-color": "#b3001b", "circle-stroke-color": "#fff",
                 "circle-stroke-width": 1.5 },
      });
      ok();
    }));
  }

  async function chargerPoints() {
    const p = filtres();
    if (quartierChoisi) p.set("quartier", quartierChoisi);
    const { points } = await appel("/api/territoire/points?" + p);
    carte.getSource("points").setData({ type: "FeatureCollection", features: points.map((x) => ({
      type: "Feature", properties: { poids: x.poids },
      geometry: { type: "Point", coordinates: [x.longitude, x.latitude] } })) });
    // Un quartier choisi : on cadre la carte sur SES signalements (son nom n'est qu'un repère).
    if (quartierChoisi && points.length) {
      const lons = points.map((x) => x.longitude), lats = points.map((x) => x.latitude);
      carte.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
                      { padding: 60, maxZoom: 15, duration: 800 });
    }
    $("compte").textContent = nombre(points.length) + " signalement" + (points.length > 1 ? "s" : "")
      + " retenu" + (points.length > 1 ? "s" : "") + (quartierChoisi ? " à " + quartierChoisi : "");
  }

  // ------------------------------------------------------------------ quartiers
  async function chargerQuartiers(premiere) {
    const r = await appel("/api/territoire/quartiers?" + filtres());
    positions = r.positions;
    if (premiere) {
      for (const [cle, nom] of Object.entries(r.natures)) $("f-nature").append(el("option", { value: cle }, nom));
      for (const nom of [...r.noms].sort((a, b) => a.localeCompare(b, "fr")))
        $("f-quartier").append(el("option", { value: nom }, nom));
    }
    const liste = $("classement");
    liste.replaceChildren();
    const touches = r.quartiers.filter((q) => q.indice > 0);
    if (!touches.length) liste.append(el("li", { class: "vide" }, "Aucun signalement retenu pour ces filtres."));
    touches.forEach((q, i) => {
      const bouton = el("button", { type: "button", "aria-pressed": q.quartier === quartierChoisi ? "true" : "false" },
        el("span", { class: "rang" }, String(i + 1)),
        el("span", {}, el("span", { class: "nom" }, q.quartier),
          el("span", { class: "detail" }, `${q.signalements} signalement(s) · ${q.ouverts} dossier(s) ouvert(s)`
            + (q.recurrents ? ` · ${q.recurrents} dépôt(s) récurrent(s)` : "")
            + (q.volume_m3 ? ` · ${nombre(q.volume_m3, 1)} m³` : ""))),
        el("span", { class: "indice", title: "Indice de priorité" }, String(q.indice)));
      bouton.addEventListener("click", () => choisirQuartier(q.quartier));
      liste.append(el("li", {}, bouton));
    });
  }

  async function choisirQuartier(nom) {
    quartierChoisi = nom;
    $("f-quartier").value = nom;
    if (!nom) carte.flyTo({ center: CENTRE, zoom: 11.2 });
    await Promise.all([chargerPoints(), chargerQuartiers(false), chargerHistorique()]);
  }

  // ------------------------------------------------------------------ historique
  async function chargerHistorique() {
    const liste = $("historique");
    liste.replaceChildren();
    if (!quartierChoisi) {
      $("titre-historique").textContent = "Historique d'une zone";
      $("aide-historique").hidden = false;
      return;
    }
    $("titre-historique").textContent = "Historique : " + quartierChoisi;
    $("aide-historique").hidden = true;
    const { historique } = await appel("/api/territoire/historique?quartier=" + encodeURIComponent(quartierChoisi));
    if (!historique.length) liste.append(el("li", { class: "vide" }, "Rien n'a encore été signalé ici."));
    for (const e of historique) {
      liste.append(el("li", {}, el("time", {}, date(e.date)), e.quoi,
        e.statut ? " — " + ({ verifie: "vérifié", rejete: "écarté" }[e.statut] || "à vérifier") : "",
        e.detail ? el("span", { class: "detail" }, " « " + e.detail + " »") : ""));
    }
  }

  // ------------------------------------------------------------------ récurrents et curage
  async function chargerRecurrents() {
    const { recurrents } = await appel("/api/territoire/recurrents");
    const liste = $("recurrents");
    liste.replaceChildren();
    if (!recurrents.length) liste.append(el("li", { class: "vide" }, "Aucun dépôt récurrent pour l'instant."));
    for (const r of recurrents.slice(0, 30)) {
      const lien = el("a", { href: "/decision/signalement.html?type=depotoir&id=" + r.dossiers[0] },
        el("span", { class: "points" }, String(r.dossiers.length)),
        el("span", {}, el("span", { class: "titre" }, r.quartier + " — dossiers " + r.dossiers.join(", ")),
          el("span", { class: "raisons" }, `${r.semaines} semaine(s) avec des signalements · ${nombre(r.volume_m3, 1)} m³`)));
      liste.append(el("li", {}, lien));
    }
  }

  async function chargerCurage() {
    const c = await appel("/api/territoire/curage");
    $("compte-a-rebours").textContent = c.jours_avant_les_pluies > 0
      ? `Saison des pluies dans ${c.jours_avant_les_pluies} jours` : "Saison des pluies en cours";
    const liste = $("curage");
    liste.replaceChildren();
    if (!c.a_curer.length) liste.append(el("li", { class: "vide" }, "Aucun caniveau à curer signalé."));
    for (const l of c.a_curer.slice(0, 40)) {
      liste.append(el("li", {}, el("a", { href: l.lien },
        el("span", { class: "points", title: "Points d'urgence" }, String(l.points)),
        el("span", {}, el("span", { class: "titre" }, `${l.genre} — ${l.quartier} (${l.reference})`),
          el("span", { class: "raisons" }, l.raisons.join(" · "))))));
    }
  }

  async function demarrer() {
    await ouvrirLaSession();
    await preparerCarte();
    await chargerQuartiers(true);
    await Promise.all([chargerPoints(), chargerRecurrents(), chargerCurage()]);
    $("f-quartier").addEventListener("change", () => choisirQuartier($("f-quartier").value));
    for (const id of ["f-nature", "f-jours"])
      $(id).addEventListener("change", () => Promise.all([chargerPoints(), chargerQuartiers(false)]));
  }

  document.addEventListener("DOMContentLoaded", () => demarrer().catch((e) => {
    $("compte").textContent = "Erreur : " + e.message;
  }));
})();
