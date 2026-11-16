/* Carte de décision : fond de carte hors ligne (PMTiles) + nos couches.
   Tout vient de cette machine : le fond, les polices, les données. */
"use strict";

maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-csp-worker.js");
maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile);

const COULEURS = { depotoir: "#c8102e", decharge: "#6e6457", eau: "#2f7da6",
                   limite: "#1b2033", densite: "#1e2455", fuite: "#0090d4", nuisance: "#7b3fa0" };
// La couleur de la terre dans le style clair de Protomaps.
const TERRE = "#e2dfda";

const etat = (texte) => { document.getElementById("etat-chargement").textContent = texte; };

/* Le style Protomaps demande trois variantes de Noto ; nous n'en embarquons qu'une, et aucune
   planche de pictogrammes : on remplace les polices et on retire les couches à pictogrammes. */
function couchesDuFond() {
  return basemaps.layers("fond", basemaps.namedFlavor("light"), { lang: "fr" })
    .filter((c) => !(c.layout && c.layout["icon-image"]))
    .map((c) => (c.layout && c.layout["text-font"]
      ? { ...c, layout: { ...c.layout, "text-font": ["noto"] } } : c))
    /* Notre fond de carte ne couvre que la commune et sa marge : au-delà, c'est la couleur de
       fond du style qui se voit, et elle est grise là où la terre est beige. D'où une bande
       grise au bord sur les grands écrans. On aligne le fond sur la couleur de la terre : le
       bord de l'extrait ne se distingue plus. */
    .map((c) => (c.type === "background"
      ? { ...c, paint: { ...c.paint, "background-color": TERRE } } : c));
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
          0, "#eceef7", 25, "#c6cbe5", 75, "#9aa2cf", 150, "#5b63a8", 300, "#1e2455"],
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

    carte.addSource("fuites", { type: "geojson", data: await json("/api/fuites/carte") });
    carte.addLayer({ id: "fuites", type: "circle", source: "fuites",
      paint: {
        "circle-radius": ["match", ["get", "ampleur"],
          "inondation", 11, "jet", 8, "suintement", 6, 6],
        "circle-color": COULEURS.fuite, "circle-opacity": 0.85,
        "circle-stroke-width": 2, "circle-stroke-color": "#fff",
      } });

    /* Caniveaux, abattages clandestins, déversements : un losange violet, encore une autre
       forme, pour qu'on distingue les trois familles d'un coup d'œil sur la carte. */
    carte.addSource("nuisances", { type: "geojson", data: await json("/api/nuisances/carte") });
    carte.addLayer({ id: "nuisances", type: "circle", source: "nuisances",
      paint: {
        "circle-radius": ["match", ["get", "gravite"], "grave", 10, "moyen", 8, "leger", 6, 6],
        "circle-color": COULEURS.nuisance, "circle-opacity": 0.85,
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
  const ETAPES = { signale: "Signalé", confirme: "Confirmé par la mairie",
                   constat: "Constat de la brigade", a_collecter: "À collecter",
                   collecte: "Collecté", classe: "Classé sans suite" };
  const DEPOTS = { plein_air: "à même le sol", bac: "dans un bac", caniveau: "dans un caniveau",
                   fosse: "dans une fosse", berge: "sur une berge", autre: "autre" };
  document.getElementById("selection").innerHTML =
    `<dt>Numéro</dt><dd>${p.id}</dd>` +
    `<dt>Étape</dt><dd>${ETAPES[p.etape] || p.etape || "—"}</dd>` +
    `<dt>Volume estimé</dt><dd>${Number(p.volume_m3).toFixed(0)} m³</dd>` +
    (p.surface_m2 ? `<dt>Superficie</dt><dd>${Number(p.surface_m2).toFixed(0)} m²</dd>` : "") +
    (p.depot ? `<dt>Dépôt</dt><dd>${DEPOTS[p.depot] || p.depot}</dd>` : "") +
    `<dt>Signalements</dt><dd>${p.nb_signalements} (${p.nb_sources} source${p.nb_sources > 1 ? "s" : ""})</dd>` +
    `<dt>Premier vu</dt><dd>${date(p.premier_vu)}</dd>` +
    `<dt>Dernier vu</dt><dd>${date(p.dernier_vu)}</dd>`;
  bloc.hidden = false;
});
carte.on("mouseenter", "depotoirs", () => { carte.getCanvas().style.cursor = "pointer"; });
carte.on("mouseleave", "depotoirs", () => { carte.getCanvas().style.cursor = ""; });

/* ------------------------------------------------------------------ plan de gestion */
const REGLAGES = ["nb_camions", "camions_en_panne", "taux_abonnement", "frequence_collecte_jours"];
const UNITES = { taux_abonnement: " %", frequence_collecte_jours: " j" };

REGLAGES.forEach((nom) => {
  const curseur = document.getElementById(nom);
  const sortie = document.getElementById("sortie-" + nom);
  const afficher = () => { sortie.textContent = curseur.value + (UNITES[nom] || ""); };
  curseur.addEventListener("input", afficher);
  afficher();
});

function parametresChoisis() {
  const p = {};
  REGLAGES.forEach((nom) => { p[nom] = Number(document.getElementById(nom).value); });
  p.taux_abonnement = p.taux_abonnement / 100;
  p.saison = document.getElementById("saison").checked ? "pluies" : "seche";
  p.mode_strict = document.getElementById("mode_strict").checked;
  return p;
}

function nombre(valeur, decimales = 0) {
  return Number(valeur).toLocaleString("fr-FR", { minimumFractionDigits: decimales,
                                                  maximumFractionDigits: decimales });
}

/* Les tournées deviennent des lignes sur la carte : décharge → arrêts → décharge. */
function tourneesEnLignes(plan) {
  const depart = [plan.decharge.longitude, plan.decharge.latitude];
  return { type: "FeatureCollection", features: plan.tournees.map((t) => ({
    type: "Feature",
    properties: { camion: t.camion, rotation: t.rotation, volume: t.volume_m3, duree: t.duree_min },
    // T15 : le tracé par les rues, calculé par le serveur. S'il manque (aucun chemin trouvé),
    // on garde le trait droit d'arrêt en arrêt : la tournée reste visible.
    geometry: { type: "LineString",
                coordinates: t.geometrie && t.geometrie.length > 1 ? t.geometrie
                  : [depart, ...t.etapes.map((e) => [e.longitude, e.latitude]), depart] },
  })) };
}

function pointsEnGeojson(plan) {
  return { type: "FeatureCollection", features: plan.points.map((p) => ({
    type: "Feature",
    properties: { id: p.id, m3: p.m3_par_passage, habitants: Math.round(p.habitants),
                  sature: p.sature, jour: p.jour_du_cycle,
                  desservi: !plan.non_desservis.includes("point-" + p.id) },
    geometry: { type: "Point", coordinates: [p.longitude, p.latitude] },
  })) };
}

function afficherResume(plan) {
  const c = plan.couts;
  const lignes = [
    ["Points de regroupement", nombre(plan.points_resume.nombre)],
    ["À vider aujourd'hui", nombre(plan.points_resume.a_vider_aujourd_hui)],
    ["Tournées", nombre(plan.tournees.length)],
    ["Arrêts non desservis", nombre(plan.non_desservis.length)],
    ["Distance par jour", nombre(c.km_par_jour) + " km"],
    ["Coût par mois", nombre(c.cout_par_mois) + " F"],
    ["Calculé en", plan.calcule_en_s + " s"],
  ];
  document.getElementById("resume-plan").innerHTML = lignes
    .map(([nom, valeur]) => `<div class="ligne"><span>${nom}</span><span>${valeur}</span></div>`).join("");

  const marques = { ok: "✓", attention: "!", probleme: "✗" };
  document.getElementById("controles").innerHTML = plan.controles.map((v) =>
    `<li class="${v.etat}"><span class="marque">${marques[v.etat]}</span>`
    + `<span><span class="nom">${v.nom}</span><span class="detail">${v.detail}</span></span></li>`).join("");
  document.getElementById("bloc-controles").hidden = false;
}

async function calculerLePlan() {
  const bouton = document.getElementById("recalculer");
  bouton.disabled = true;
  bouton.textContent = "Calcul en cours…";
  etat("Calcul du plan…");
  try {
    const reponse = await fetch("/api/plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parametresChoisis()),
    });
    const plan = await reponse.json();
    if (!reponse.ok) throw new Error(plan.erreur || "Erreur " + reponse.status);
    dessinerLePlan(plan);
    afficherResume(plan);
    etat(`Plan recalculé en ${plan.calcule_en_s} s · jour ${plan.jour_du_cycle} sur `
         + `${plan.frequence_collecte_jours} du cycle.`);
  } catch (erreur) {
    etat("Plan impossible : " + erreur.message);
  } finally {
    bouton.disabled = false;
    bouton.textContent = "Recalculer le plan";
  }
}

function dessinerLePlan(plan) {
  const points = pointsEnGeojson(plan);
  const lignes = tourneesEnLignes(plan);
  if (carte.getSource("points")) {
    carte.getSource("points").setData(points);
    carte.getSource("tournees").setData(lignes);
    carte.getSource("decharge").setData(pointDecharge(plan));
    return;
  }
  carte.addSource("tournees", { type: "geojson", data: lignes });
  carte.addLayer({ id: "tournees", type: "line", source: "tournees",
    paint: { "line-color": "#8a6a00", "line-width": 1.6, "line-opacity": 0.65 } }, "depotoirs");

  carte.addSource("points", { type: "geojson", data: points });
  carte.addLayer({ id: "points", type: "circle", source: "points",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["get", "m3"], 0, 4, 30, 8, 120, 13],
      /* Bleu : desservi. Rouge sombre : laissé de côté faute de camions ou de temps. */
      "circle-color": ["case", ["get", "desservi"], "#3b47a0", "#8d2b1e"],
      "circle-opacity": 0.8, "circle-stroke-width": 1.2, "circle-stroke-color": "#fff",
    } }, "depotoirs");

  carte.addSource("decharge", { type: "geojson", data: pointDecharge(plan) });
  carte.addLayer({ id: "decharge", type: "circle", source: "decharge",
    paint: { "circle-radius": 9, "circle-color": "#1b2033", "circle-stroke-width": 3,
             "circle-stroke-color": "#ffff00" } });

  carte.on("click", "points", (evenement) => {
    const p = evenement.features[0].properties;
    new maplibregl.Popup({ offset: 10 })
      .setLngLat(evenement.lngLat)
      .setHTML(`<strong>Point de regroupement ${p.id}</strong>`
        + `${nombre(p.habitants)} habitants · ${nombre(p.m3, 1)} m³ par passage<br>`
        + `Jour ${p.jour} du cycle · ${p.desservi ? "desservi" : "non desservi"}`
        + `${p.sature ? "<br><em>saturé : à vider plus souvent</em>" : ""}`)
      .addTo(carte);
  });
  carte.on("mouseenter", "points", () => { carte.getCanvas().style.cursor = "pointer"; });
  carte.on("mouseleave", "points", () => { carte.getCanvas().style.cursor = ""; });
}

function pointDecharge(plan) {
  return { type: "FeatureCollection", features: [{
    type: "Feature", properties: { nom: plan.decharge.nom },
    geometry: { type: "Point", coordinates: [plan.decharge.longitude, plan.decharge.latitude] },
  }] };
}

document.getElementById("recalculer").addEventListener("click", calculerLePlan);
carte.on("load", () => { setTimeout(() => calculerLePlan().catch(() => {}), 500); });
