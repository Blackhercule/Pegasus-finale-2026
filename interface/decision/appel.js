/* T23 : l'agent de la mairie décroche, parle avec l'habitant et voit où il se trouve.
 *
 * Dans l'ordre :
 *   1. on demande au serveur l'« offre » du téléphone (un texte SDP : ses adresses sur le réseau
 *      local, et de quoi chiffrer) ;
 *   2. on la donne à notre navigateur, on branche notre micro, et il fabrique la « réponse » ;
 *   3. on remet cette réponse au serveur (POST …/decrocher) : le téléphone la récupère, et les
 *      deux navigateurs se joignent DIRECTEMENT sur le Wi-Fi. La voix ne passe pas par le
 *      serveur ; elle est chiffrée par les navigateurs (DTLS-SRTP), pas par notre code ;
 *   4. toutes les secondes, on demande au serveur l'état de l'appel et la dernière position,
 *      qu'on dessine sur la carte : point bleu, cercle de précision, trajet parcouru.
 *
 * Aucun serveur STUN ni TURN (iceServers vide) : seul le réseau local sert.
 * À la fin de l'appel, la position disparaît de l'écran (et le serveur l'a déjà effacée).
 */
"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const id = Number(new URLSearchParams(location.search).get("id"));

  const SONDAGE_MS = 1000;
  const ADRESSES_MAX_MS = 3000;
  const RACCORDEMENT_MAX_MS = 15000;
  const POSITION_ANCIENNE_S = 15;
  const CENTRE_OUAGA = [-1.5197, 12.3714];

  let session = null;
  let pc = null;
  let micro = null;
  let decroche = false;
  let fini = false;
  let connecte = false;
  let debut = null;
  let minuteries = [];
  let carte = null, carteChargee = false, point = null, dejaCentree = false;
  let derniere = null;     // la dernière position reçue, pour la carte qui se charge après

  function dire(etat, phrase) {
    document.body.dataset.appel = etat;
    $("etat").textContent = phrase;
  }

  function avertir(phrase) {
    $("avertissement").hidden = false;
    $("avertissement").textContent = phrase;
  }

  /* ------------------------------------------------------------------ la carte */
  function preparerLaCarte() {
    if (typeof maplibregl === "undefined" || typeof FondCarte === "undefined") return;
    carte = FondCarte.carte($("carte-appel"), CENTRE_OUAGA, 12);
    carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    carte.on("load", () => {
      // Le cercle de précision, puis le trajet en trait fin : dessous le point.
      carte.addSource("precision", { type: "geojson", data: vide() });
      carte.addLayer({ id: "precision-fond", type: "fill", source: "precision",
                       paint: { "fill-color": "#1a73e8", "fill-opacity": 0.15 } });
      carte.addLayer({ id: "precision-bord", type: "line", source: "precision",
                       paint: { "line-color": "#1a73e8", "line-width": 1, "line-opacity": 0.6 } });
      carte.addSource("trajet", { type: "geojson", data: vide() });
      carte.addLayer({ id: "trajet", type: "line", source: "trajet",
                       paint: { "line-color": "#1a73e8", "line-width": 2, "line-opacity": 0.7 } });
      carteChargee = true;
      if (derniere) dessiner(derniere.position, derniere.trajet);
    });
  }

  const vide = () => ({ type: "FeatureCollection", features: [] });

  /* Un cercle de `rayon` mètres autour d'un point, en 48 côtés. À cette échelle, un degré de
     latitude vaut 111 320 m, et un degré de longitude un peu moins, selon la latitude. */
  function cercle(lon, lat, rayon) {
    const pas = [];
    for (let i = 0; i <= 48; i += 1) {
      const angle = (i / 48) * 2 * Math.PI;
      pas.push([lon + (rayon * Math.cos(angle)) / (111320 * Math.cos((lat * Math.PI) / 180)),
                lat + (rayon * Math.sin(angle)) / 111320]);
    }
    return { type: "Feature", geometry: { type: "Polygon", coordinates: [pas] }, properties: {} };
  }

  function dessiner(position, trajet) {
    derniere = { position, trajet };
    if (!carte || !carteChargee) return;
    if (!position) { effacerLaCarte(); return; }
    const lieu = [position.longitude, position.latitude];
    if (!point) {
      const rond = document.createElement("div");
      rond.className = "point-habitant";
      rond.title = "L'habitant";
      point = new maplibregl.Marker({ element: rond }).setLngLat(lieu).addTo(carte);
    } else {
      point.setLngLat(lieu);
    }
    $("carte-appel").dataset.longitude = String(position.longitude);
    $("carte-appel").dataset.latitude = String(position.latitude);
    carte.getSource("precision").setData(position.precision_m
      ? { type: "FeatureCollection", features: [cercle(lieu[0], lieu[1], position.precision_m)] } : vide());
    carte.getSource("trajet").setData(trajet && trajet.length > 1
      ? { type: "Feature", geometry: { type: "LineString", coordinates: trajet }, properties: {} } : vide());
    // La carte suit l'habitant : la première fois on s'approche, ensuite on ne bouge que
    // s'il sort de l'écran (l'agent peut regarder autour sans que la carte lui échappe).
    if (!dejaCentree) {
      carte.jumpTo({ center: lieu, zoom: 16 });
      dejaCentree = true;
    } else if (!carte.getBounds().contains(lieu)) {
      carte.easeTo({ center: lieu, duration: 600 });
    }
  }

  function effacerLaCarte() {
    if (point) { point.remove(); point = null; }
    delete $("carte-appel").dataset.longitude;
    delete $("carte-appel").dataset.latitude;
    if (carte && carteChargee) {
      carte.getSource("precision").setData(vide());
      carte.getSource("trajet").setData(vide());
    }
  }

  function afficherLaPosition(position) {
    const ligne = $("position");
    if (!position) {
      ligne.textContent = "Position non partagée par l'habitant.";
      ligne.className = "appel-position absente";
      $("coordonnees").textContent = "";
      return;
    }
    const age = Math.round(position.age_s);
    ligne.textContent = `Position mise à jour il y a ${age} s` +
      (position.precision_m ? ` · précision ± ${position.precision_m} m` : "") +
      (position.hors_commune ? " · hors de la commune" : "");
    ligne.className = "appel-position" + (age > POSITION_ANCIENNE_S ? " ancienne" : "");
    $("coordonnees").textContent =
      `${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)}`;
  }

  /* ------------------------------------------------------------------ l'appel */
  function adressesRassemblees() {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((pret) => {
      const plafond = setTimeout(pret, ADRESSES_MAX_MS);
      pc.addEventListener("icegatheringstatechange", () => {
        if (pc.iceGatheringState === "complete") { clearTimeout(plafond); pret(); }
      });
    });
  }

  function poster(adresse, corps, keepalive = false) {
    return fetch(adresse, {
      method: "POST", keepalive,
      headers: { "Content-Type": "application/json", "X-Jeton": session ? session.jeton : "" },
      body: JSON.stringify(corps || {}),
    });
  }

  async function decrocher() {
    if (!Number.isInteger(id) || id < 1) { terminer("Appel inconnu."); return; }
    session = await fetch("/api/session").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (!session || !session.agent) { terminer("Connexion requise."); return; }
    if (session.poste !== "mairie") { terminer("Seule la mairie répond aux appels des habitants."); return; }

    // 1. L'offre du téléphone.
    let offre;
    try {
      const r = await fetch(`/api/appels/${id}/offre`, { cache: "no-store" });
      const corps = await r.json().catch(() => ({}));
      if (!r.ok) { terminer(corps.erreur || "Cet appel ne sonne plus."); return; }
      offre = corps.offre;
    } catch {
      terminer("Le serveur ne répond pas.");
      return;
    }

    // 2. Notre micro. Refusé : on écoute quand même, mais l'habitant ne nous entendra pas.
    try {
      micro = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch {
      micro = null;
      avertir("Micro refusé : vous entendez l'habitant, mais il ne vous entend pas. " +
              "Autorisez le micro pour cette page, puis rappelez si besoin.");
    }

    pc = new RTCPeerConnection({ iceServers: [] });
    pc.addEventListener("track", (e) => { $("voix").srcObject = e.streams[0]; $("voix").play().catch(() => {}); });
    pc.addEventListener("connectionstatechange", suivreLaConnexion);
    try {
      // D'abord l'offre, PUIS notre micro : ainsi notre voix part dans le même canal que celle
      // de l'habitant arrive, et la réponse le dit.
      await pc.setRemoteDescription({ type: "offer", sdp: offre });
      if (micro) micro.getTracks().forEach((piste) => pc.addTrack(piste, micro));
      await pc.setLocalDescription(await pc.createAnswer());
      await adressesRassemblees();
    } catch {
      terminer("Ce navigateur n'a pas pu répondre à l'appel.");
      return;
    }

    // 3. On décroche : le serveur passe notre réponse au téléphone.
    let r;
    try {
      r = await poster(`/api/appels/${id}/decrocher`, { reponse: pc.localDescription.sdp });
    } catch {
      terminer("Le serveur ne répond pas.");
      return;
    }
    if (!r.ok) {
      const corps = await r.json().catch(() => ({}));
      terminer(corps.erreur || "Impossible de décrocher cet appel.");
      return;
    }
    decroche = true;
    debut = Date.now();
    dire("raccordement", "Connexion avec le téléphone…");
    $("micro").disabled = !micro;
    $("raccrocher").disabled = false;
    minuteries.push(setInterval(sonder, SONDAGE_MS));
    minuteries.push(setTimeout(() => {
      if (!fini && !connecte) {
        raccrocher("La voix ne passe pas entre le téléphone et cet ordinateur. " +
                   "Le Wi-Fi isole peut-être les appareils.");
      }
    }, RACCORDEMENT_MAX_MS));
    sonder();
  }

  function suivreLaConnexion() {
    if (fini) return;
    if (pc.connectionState === "connected") {
      connecte = true;
      dire("en_communication", "En communication");
    } else if (pc.connectionState === "failed") {
      raccrocher("La communication a été coupée.");
    }
  }

  /* 4. Toutes les secondes : l'état de l'appel et la position. */
  async function sonder() {
    if (fini) return;
    let liste;
    try {
      const r = await fetch("/api/appels", { cache: "no-store" });
      if (!r.ok) return;
      liste = await r.json();
    } catch {
      return;
    }
    if (fini) return;
    const a = liste.find((x) => x.id === id);
    if (!a || a.etat === "termine" || a.etat === "sans_reponse") {
      terminer("L'habitant a raccroché.");
      return;
    }
    const secondes = Math.round((Date.now() - debut) / 1000);
    $("duree").textContent = `Durée : ${Math.floor(secondes / 60)} min ${String(secondes % 60).padStart(2, "0")} s`;
    afficherLaPosition(a.position);
    dessiner(a.position, a.trajet);
  }

  /* L'agent raccroche : on prévient le serveur, qui le dira au téléphone. */
  function raccrocher(phrase = "Vous avez raccroché.") {
    if (fini) return;
    if (decroche) poster(`/api/appels/${id}/terminer`).catch(() => {});
    terminer(phrase);
  }

  /* Fin de l'appel, quelle qu'en soit la raison : tout est coupé, la position disparaît. */
  function terminer(motif) {
    fini = true;
    minuteries.forEach((m) => { clearInterval(m); clearTimeout(m); });
    minuteries = [];
    if (micro) micro.getTracks().forEach((piste) => piste.stop());
    if (pc) pc.close();
    $("voix").srcObject = null;
    dire("fini", "Appel terminé");
    $("duree").textContent = motif;
    $("micro").disabled = true;
    $("raccrocher").disabled = true;
    $("actions").hidden = true;
    $("retour").hidden = false;
    derniere = null;
    effacerLaCarte();
    $("position").textContent = "La position n'est plus affichée : l'appel est terminé.";
    $("position").className = "appel-position";
    $("coordonnees").textContent = "";
  }

  $("raccrocher").addEventListener("click", () => raccrocher());
  $("micro").addEventListener("click", () => {
    if (!micro) return;
    const coupe = $("micro").getAttribute("aria-pressed") !== "true";
    micro.getAudioTracks().forEach((piste) => { piste.enabled = !coupe; });
    $("micro").setAttribute("aria-pressed", String(coupe));
    $("micro").textContent = coupe ? "🎙 Rétablir le micro" : "🎙 Couper le micro";
  });
  // On ferme la page en pleine communication : on raccroche proprement.
  window.addEventListener("pagehide", () => {
    if (decroche && !fini) poster(`/api/appels/${id}/terminer`, {}, true).catch(() => {});
  });

  preparerLaCarte();
  decrocher();
})();
