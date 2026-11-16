# Bibliothèques de la carte, copiées dans le dépôt

Rien n'est chargé depuis Internet à l'exécution (exigence E14). Ces fichiers viennent des
paquets npm officiels, copiés tels quels le 16/11/2026.

| Dossier | Paquet et version | Licence | Projet |
|---|---|---|---|
| `maplibre-gl/` | `maplibre-gl` 5.24.1 | BSD-3-Clause (`LICENSE.txt`) | https://github.com/maplibre/maplibre-gl-js |
| `pmtiles/` | `pmtiles` 4.5.0 | BSD-3-Clause | https://github.com/protomaps/PMTiles |
| `protomaps-basemaps/` | `@protomaps/basemaps` 5.7.2 | BSD-3-Clause | https://github.com/protomaps/basemaps |
| `polices/lato/` | `@fontsource/lato` 5.2.9 (police Lato, graisses 400 et 700) | OFL-1.1 pour la police, MIT pour le paquet | https://www.latofonts.com/ |
| `polices/noto/` | `smp-noto-glyphs` 2.0.0 (police GoNotoKurrent, tirée de Noto Sans) | MIT pour le paquet, OFL-1.1 pour la police | https://github.com/digidem/styled-map-package |

## Comment les charger

MapLibre est pris dans sa version « CSP » : son code de calcul est un fichier à part, et non un
script fabriqué à la volée. Nos pages peuvent ainsi interdire tout script venu d'ailleurs.

```html
<link rel="stylesheet" href="/vendor/maplibre-gl/maplibre-gl.css">
<script src="/vendor/maplibre-gl/maplibre-gl-csp.js"></script>
<script src="/vendor/pmtiles/pmtiles.js"></script>
<script src="/vendor/protomaps-basemaps/basemaps.js"></script>
```

```js
maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-csp-worker.js");
maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile);
// Le style Protomaps cite trois polices ; nous n'en fournissons qu'une : on la met partout.
// Les couches à pictogrammes sont retirées, faute de planche de pictogrammes.
const couches = basemaps.layers("fond", basemaps.namedFlavor("light"), {lang: "fr"})
  .filter(c => !(c.layout && c.layout["icon-image"]))
  .map(c => c.layout && c.layout["text-font"] ? {...c, layout: {...c.layout, "text-font": ["noto"]}} : c);
const carte = new maplibregl.Map({
  container: "carte",
  style: {
    version: 8,
    glyphs: location.origin + "/vendor/polices/{fontstack}/{range}.pbf",
    sources: {fond: {type: "vector", url: "pmtiles://" + location.origin + "/donnees/fond.pmtiles",
                     attribution: "© les contributeurs d'OpenStreetMap"}},
    layers: couches,
  },
});
```

Ce chargement est essayé dans un navigateur à chaque tournage de la vidéo de démonstration
(`outils/filmer.mjs`) : la carte s'affiche sans aucune requête vers Internet.
