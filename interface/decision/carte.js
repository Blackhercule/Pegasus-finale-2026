/* Carte de décision : fond de carte hors ligne (PMTiles) + nos couches.
   Tout vient de cette machine : le fond, les polices, les données. */
"use strict";

maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-csp-worker.js");
maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile);

const COULEURS = { depotoir: "#e4572e", decharge: "#8a6a3b", eau: "#3d7ea6", limite: "#1d1d1b", densite: "#2f6f4e" };
const etat = (texte) => { document.getElementById("etat-chargement").textContent = texte; };

/* Le style Protomaps demande trois variantes de Noto ; nous n'en embarquons qu'une, et aucune
   planche de pictogrammes : on remplace les polices et on retire les couches à pictogrammes. */
function couchesDuFond() {
  return basemaps.layers("fond", basemaps.namedFlavor("light"), { lang: "fr" })
    .filter((c) => !(c.layout && c.layout["icon-image"]))
    .map((c) => (c.layout && c.layout["text-font"]
      ? { ...c, layout: { ...c.layout, "text-font": ["noto"] } } : c));
}

function style(origine) {
  return {
    version: 8,
    glyphs: origine + "/vendor/polices/{fontstack}/{range}.pbf",
    sources: {
      fond: {
        type: "vector", url: "pmtiles://" + origine + "/donnees/fond.pmtiles",
        attribution: "© les contributeurs d'OpenStreetMap",
      },
    },
    layers: couchesDuFond(),
  };
}

const carte = new maplibregl.Map({
  container: "carte",
  style: style(location.origin),
  center: [-1.5197, 12.3714],
  zoom: 11,
  attributionControl: { compact: true },
});
carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
carte.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }));

async function json(adresse) {
  const reponse = await fetch(adresse);
  if (!reponse.ok) throw new Error(adresse + " : " + reponse.status);
  return reponse.json();
}

carte.on("load", async () => {
  try {
    const [commune, eau, zones, lieux] = await Promise.all([
      json("/donnees/commune.geojson"), json("/donnees/eau.geojson"),
      json("/donnees/zones.geojson"), json("/donnees/lieux.geojson"),
    ]);

    carte.addSource("commune", { type: "geojson", data: commune });
    carte.addLayer({ id: "limite", type: "line", source: "commune",
      paint: { "line-color": COULEURS.limite, "line-width": 2, "line-dasharray": [3, 2] } });

    carte.addSource("eau", { type: "geojson", data: eau });
    carte.addLayer({ id: "eau", type: "fill", source: "eau",
      paint: { "fill-color": COULEURS.eau, "fill-opacity": 0.55 } });

    /* Densité de bâti : elle sert à répartir la population, donc la quantité de déchets produits. */
    carte.addSource("zones", { type: "geojson", data: zones });
    carte.addLayer({ id: "densite", type: "fill", source: "zones", layout: { visibility: "none" },
      paint: {
        "fill-color": ["interpolate", ["linear"], ["get", "nb_batiments"],
          0, "#eaf2ec", 25, "#bcd9c6", 75, "#7fb996", 150, "#4b9470", 300, "#2f6f4e"],
        "fill-opacity": 0.75,
      } });

    const dechets = { type: "FeatureCollection",
      features: lieux.features.filter((f) => ["decharge", "dechets"].includes(f.properties.type)) };
    carte.addSource("decharges", { type: "geojson", data: dechets });
    carte.addLayer({ id: "decharges", type: "circle", source: "decharges",
      paint: { "circle-radius": 4, "circle-color": COULEURS.decharge,
               "circle-stroke-width": 1, "circle-stroke-color": "#fff", "circle-opacity": 0.85 } });

    /* Les dépotoirs signalés : le rayon grandit avec le volume estimé. */
    carte.addSource("depotoirs", { type: "geojson", data: await json("/api/depotoirs") });
    carte.addLayer({ id: "depotoirs", type: "circle", source: "depotoirs",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["get", "volume_m3"], 0, 6, 20, 11, 100, 20],
        "circle-color": COULEURS.depotoir, "circle-opacity": 0.75,
        "circle-stroke-width": 2, "circle-stroke-color": "#fff",
      } });

    carte.fitBounds(bornes(commune), { padding: 30, duration: 0 });
    await rafraichir();
    etat(dechets.features.length + " sites de déchets déjà cartographiés dans OpenStreetMap.");
  } catch (erreur) {
    etat("Erreur de chargement : " + erreur.message);
  }
});

function bornes(collection) {
  const b = new maplibregl.LngLatBounds();
  const parcourir = (c) => (typeof c[0] === "number" ? b.extend(c) : c.forEach(parcourir));
  collection.features.forEach((f) => parcourir(f.geometry.coordinates));
  return b;
}

async function rafraichir() {
  const comptes = await json("/api/comptes");
  const mettre = (id, valeur) => { document.getElementById(id).textContent = valeur ?? 0; };
  mettre("n-depotoirs", comptes.depotoirs);
  mettre("n-verifie", comptes.verifie);
  mettre("n-attente", (comptes.recevable || 0) + (comptes.a_verifier || 0));
  mettre("n-rejete", comptes.rejete);
  const source = carte.getSource("depotoirs");
  if (source) source.setData(await json("/api/depotoirs"));
}
setInterval(() => rafraichir().catch(() => {}), 10000);

document.getElementById("couches").addEventListener("change", (evenement) => {
  const couche = evenement.target.dataset.couche;
  if (carte.getLayer(couche)) {
    carte.setLayoutProperty(couche, "visibility", evenement.target.checked ? "visible" : "none");
  }
});

carte.on("click", "depotoirs", (evenement) => {
  const p = evenement.features[0].properties;
  const bloc = document.getElementById("bloc-selection");
  const date = (valeur) => (valeur ? String(valeur).slice(0, 10).split("-").reverse().join("/") : "—");
  document.getElementById("selection").innerHTML =
    `<dt>Numéro</dt><dd>${p.id}</dd>` +
    `<dt>Volume estimé</dt><dd>${Number(p.volume_m3).toFixed(0)} m³</dd>` +
    `<dt>Signalements</dt><dd>${p.nb_signalements} (${p.nb_sources} source${p.nb_sources > 1 ? "s" : ""})</dd>` +
    `<dt>Premier vu</dt><dd>${date(p.premier_vu)}</dd>` +
    `<dt>Dernier vu</dt><dd>${date(p.dernier_vu)}</dd>`;
  bloc.hidden = false;
});
carte.on("mouseenter", "depotoirs", () => { carte.getCanvas().style.cursor = "pointer"; });
carte.on("mouseleave", "depotoirs", () => { carte.getCanvas().style.cursor = ""; });
