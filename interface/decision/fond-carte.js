/* Le fond de carte hors ligne, pour les petites cartes (T23) : détail d'un dossier, appel.
 *
 * Même fond que la grande carte (carte.js) : le fichier fond.pmtiles servi par notre machine,
 * le style Protomaps embarqué, la police Noto de vendor/. Aucune tuile, aucune police ne vient
 * d'Internet (E14). La grande carte garde son propre code, qui marche : ce fichier en reprend
 * seulement la recette.
 */
"use strict";

const FondCarte = (function () {
  // La couleur de la terre dans le style clair de Protomaps (voir carte.js).
  const TERRE = "#e2dfda";
  let pret = false;

  function preparer() {
    if (pret) return;
    // Une seule fois par page, et seulement si la grande carte ne l'a pas déjà fait.
    if (!window.__fondCartePret) {
      maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-csp-worker.js");
      maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile);
      window.__fondCartePret = true;
    }
    pret = true;
  }

  function couches() {
    return basemaps.layers("fond", basemaps.namedFlavor("light"), { lang: "fr" })
      .filter((c) => !(c.layout && c.layout["icon-image"]))
      .map((c) => (c.layout && c.layout["text-font"]
        ? { ...c, layout: { ...c.layout, "text-font": ["noto"] } } : c))
      .map((c) => (c.type === "background"
        ? { ...c, paint: { ...c.paint, "background-color": TERRE } } : c));
  }

  function style() {
    return {
      version: 8,
      glyphs: location.origin + "/vendor/polices/{fontstack}/{range}.pbf",
      sources: { fond: { type: "vector", url: "pmtiles://" + location.origin + "/donnees/fond.pmtiles",
                         attribution: "© les contributeurs d'OpenStreetMap" } },
      layers: couches(),
    };
  }

  /* Une carte dans `conteneur`, centrée sur [lon, lat]. */
  function carte(conteneur, centre, zoom = 15, options = {}) {
    preparer();
    return new maplibregl.Map({
      container: conteneur, style: style(), center: centre, zoom,
      attributionControl: { compact: true }, ...options,
    });
  }

  return { carte };
})();
