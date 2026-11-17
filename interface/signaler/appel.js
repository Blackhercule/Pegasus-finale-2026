/* T23 : appeler un agent de la mairie depuis la page Signaler (touches 2 et 3 du menu).

   Qui envoie quoi :
     1. ce téléphone fabrique une « offre » (un texte SDP : ses adresses sur le réseau local et
        de quoi chiffrer) et la remet au serveur avec sa position ; le serveur répond par un
        numéro d'appel et un jeton secret, le seul moyen d'agir ensuite sur CET appel ;
     2. toutes les secondes, il demande au serveur où en est l'appel (le jeton voyage dans
        l'en-tête X-Appel-Jeton, jamais dans l'adresse) ; quand un agent décroche, le serveur lui
        passe la « réponse » de l'agent ;
     3. avec l'offre et la réponse, les deux navigateurs se joignent DIRECTEMENT sur le Wi-Fi :
        la voix ne passe pas par le serveur, et elle est chiffrée par le navigateur (DTLS-SRTP) ;
     4. pendant l'appel, la position part toutes les 3 s, pour la carte de l'agent.

   Aucun serveur STUN ni TURN (iceServers vide) : seules les adresses du réseau local sont
   proposées, rien ne sort de la ville.

   Si quelque chose ne marche pas (micro refusé, personne ne décroche, agents occupés, réseau
   coupé), on le dit en une phrase et on montre la touche 1 : on retombe TOUJOURS sur le
   formulaire. La position refusée n'empêche pas l'appel : l'agent lit « position non partagée ». */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // Les touches 2 et 3 n'apparaissent que si ce téléphone sait passer l'appel : WebRTC, le
  // micro, et une page sûre (HTTPS, ou l'ordinateur lui-même), sans laquelle le navigateur
  // refuse le micro. Sinon le menu n'offre que la touche 1, qui marche partout.
  const possible = typeof RTCPeerConnection === "function" && window.isSecureContext &&
    !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  if (!possible) return;

  const SONDAGE_MS = 1000;            // « où en est l'appel ? » toutes les secondes
  const POSITION_MS = 3000;           // la position part toutes les 3 s
  const ADRESSES_MAX_MS = 3000;       // on rassemble ses adresses réseau au plus 3 s
  const RACCORDEMENT_MAX_MS = 15000;  // décroché, mais la voix ne passe pas : on abandonne
  const PANNES_RESEAU_MAX = 5;        // 5 sondages ratés de suite (5 s) : réseau coupé

  const ecran = $("appel");
  const titre = $("appel-titre");
  const texte = $("appel-texte");
  const voix = $("appel-voix");
  const boutonRaccrocher = $("appel-raccrocher");
  const boutonFormulaire = $("appel-formulaire");

  let appel = null;   // tout ce qui concerne l'appel en cours (null : aucun appel)

  $("menu-2").hidden = false;
  $("menu-3").hidden = false;
  $("menu-2").addEventListener("click", appeler);
  $("menu-3").addEventListener("click", appeler);
  boutonRaccrocher.addEventListener("click", () => raccrocher("Vous avez raccroché. Appel terminé."));
  boutonFormulaire.addEventListener("click", versLeFormulaire);
  // On quitte la page en pleine communication : on prévient le serveur, pour que l'agent
  // l'apprenne tout de suite (keepalive : la requête part même si la page se ferme).
  window.addEventListener("pagehide", () => { if (appel) prevenirLeServeur(true); });

  /* L'écran d'appel : un titre, une phrase, et selon l'état le bouton rouge ou la touche 1.
     `etat` sert aussi au style (l'icône qui bat) et à l'essai automatisé. */
  function montrer(etat, leTitre, laPhrase) {
    ecran.hidden = false;
    ecran.dataset.etat = etat;
    document.body.dataset.appel = etat;
    titre.textContent = leTitre;
    texte.textContent = laPhrase;
    const fini = etat === "echec" || etat === "fini";
    boutonRaccrocher.hidden = fini;
    boutonFormulaire.hidden = !fini;
    (fini ? boutonFormulaire : boutonRaccrocher).focus();
  }

  function versLeFormulaire() {
    ecran.hidden = true;
    document.body.dataset.appel = "";
    if (typeof fermerLAccueil === "function") fermerLAccueil();   // défini dans signaler.js
    window.scrollTo(0, 0);
  }

  async function appeler() {
    if (appel) return;                                  // un seul appel à la fois
    if (typeof fermerLAccueil === "function") fermerLAccueil();
    appel = { id: null, jeton: null, pc: null, micro: null, suivi: null, position: null,
              minuteries: [], pannes: 0, reponseRecue: false, connecte: false };
    const cetAppel = appel;
    montrer("preparation", "Appel de la mairie…", "Autorisez le micro pour parler à un agent.");

    // 1. Le micro. Refusé : pas d'appel possible, on propose le formulaire.
    try {
      cetAppel.micro = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch {
      echouer("Le micro n'est pas autorisé : l'appel ne peut pas partir. " +
              "Vous pouvez faire votre signalement vous-même.");
      return;
    }
    if (appel !== cetAppel) { cetAppel.micro.getTracks().forEach((p) => p.stop()); return; }

    // 2. La position, suivie pendant tout l'appel. Refusée : l'appel passe quand même.
    if (navigator.geolocation) {
      cetAppel.suivi = navigator.geolocation.watchPosition(
        (p) => { cetAppel.position = { latitude: p.coords.latitude, longitude: p.coords.longitude,
                                       precision_m: Math.round(p.coords.accuracy) }; },
        () => {},   // refusée ou perdue un instant : on garde la dernière connue
        // maximumAge de 5 s, comme le formulaire qui suit déjà la position sur cette page : on
        // reçoit tout de suite la position qu'il vient d'obtenir, puis chaque nouvelle.
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    }

    // 3. La connexion directe : sans serveur STUN ni TURN, seulement le réseau local.
    montrer("preparation", "Appel de la mairie…", "Préparation de l'appel…");
    const pc = new RTCPeerConnection({ iceServers: [] });
    cetAppel.pc = pc;
    cetAppel.micro.getTracks().forEach((piste) => pc.addTrack(piste, cetAppel.micro));
    pc.addEventListener("track", (e) => { voix.srcObject = e.streams[0]; voix.play().catch(() => {}); });
    pc.addEventListener("connectionstatechange", () => suivreLaConnexion(cetAppel));
    let offre;
    try {
      await pc.setLocalDescription(await pc.createOffer());
      await adressesRassemblees(pc);
      offre = pc.localDescription.sdp;
    } catch {
      echouer("Ce téléphone n'a pas pu préparer l'appel. Vous pouvez faire votre signalement vous-même.");
      return;
    }
    if (appel !== cetAppel) return;

    // 4. Le serveur met en relation : il garde l'offre jusqu'à ce qu'un agent décroche.
    let r;
    try {
      r = await fetch("/api/appels", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({ offre }, cetAppel.position || {})),
      });
    } catch {
      echouer("Le réseau ne répond pas : l'appel n'a pas pu partir. Vous pouvez faire votre signalement vous-même.");
      return;
    }
    if (appel !== cetAppel) return;
    if (!r.ok) {
      const motif = r.status === 503 ? "Tous les agents sont occupés. Réessayez dans un moment."
        : r.status === 429 ? "Trop d'appels depuis ce téléphone. Réessayez plus tard."
        : "L'appel n'a pas pu partir.";
      echouer(motif + " Vous pouvez faire votre signalement vous-même.");
      return;
    }
    const cree = await r.json();
    cetAppel.id = cree.id;
    cetAppel.jeton = cree.jeton;
    montrer("sonne", "Appel de la mairie… ça sonne", "Un agent va vous répondre. Restez sur cette page.");

    cetAppel.minuteries.push(setInterval(() => sonder(cetAppel), SONDAGE_MS));
    cetAppel.minuteries.push(setInterval(() => envoyerLaPosition(cetAppel), POSITION_MS));
  }

  /* Attend que le navigateur ait trouvé ses adresses sur le réseau local (au plus 3 s), pour
     tout envoyer en une fois : une offre, une réponse, c'est tout. */
  function adressesRassemblees(pc) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((fini) => {
      const verifier = () => { if (pc.iceGatheringState === "complete") { clearTimeout(plafond); fini(); } };
      const plafond = setTimeout(fini, ADRESSES_MAX_MS);
      pc.addEventListener("icegatheringstatechange", verifier);
    });
  }

  function entetes() {
    return { "Content-Type": "application/json", "X-Appel-Jeton": appel ? appel.jeton : "" };
  }

  /* « Où en est l'appel ? » — toutes les secondes. */
  async function sonder(cetAppel) {
    if (appel !== cetAppel || cetAppel.sondageEnCours) return;
    cetAppel.sondageEnCours = true;
    try {
      const r = await fetch("/api/appels/" + cetAppel.id,
                            { headers: { "X-Appel-Jeton": cetAppel.jeton }, cache: "no-store" });
      if (appel !== cetAppel) return;
      if (r.status === 404) { finir("Appel terminé."); return; }
      if (!r.ok) throw new Error(String(r.status));
      cetAppel.pannes = 0;
      const etat = await r.json();
      if (etat.etat === "en_cours" && !cetAppel.reponseRecue && etat.reponse) {
        // Un agent a décroché : sa réponse permet aux deux navigateurs de se joindre.
        cetAppel.reponseRecue = true;
        montrer("raccordement", "Un agent a décroché", "Connexion…");
        await cetAppel.pc.setRemoteDescription({ type: "answer", sdp: etat.reponse });
        // La voix doit passer dans les 15 s ; sinon (Wi-Fi qui isole les appareils…) on le dit.
        cetAppel.minuteries.push(setTimeout(() => {
          if (appel === cetAppel && !cetAppel.connecte) {
            echouer("La communication n'a pas pu s'établir. Vous pouvez faire votre signalement vous-même.");
          }
        }, RACCORDEMENT_MAX_MS));
      } else if (etat.etat === "sans_reponse") {
        echouer("Personne n'a répondu. Vous pouvez faire votre signalement vous-même.");
      } else if (etat.etat === "termine") {
        finir("L'agent a raccroché. Appel terminé.");
      }
    } catch {
      if (appel !== cetAppel) return;
      cetAppel.pannes += 1;
      if (cetAppel.pannes >= PANNES_RESEAU_MAX) {
        echouer("Le réseau est coupé : l'appel s'arrête. Vous pouvez faire votre signalement vous-même.");
      }
    } finally {
      cetAppel.sondageEnCours = false;
    }
  }

  function suivreLaConnexion(cetAppel) {
    if (appel !== cetAppel) return;
    const etat = cetAppel.pc.connectionState;
    if (etat === "connected") {
      cetAppel.connecte = true;
      montrer("en_communication", "En communication", "Vous parlez avec un agent de la mairie.");
    } else if (etat === "failed") {
      echouer("La communication a été coupée. Vous pouvez faire votre signalement vous-même.");
    }
  }

  async function envoyerLaPosition(cetAppel) {
    if (appel !== cetAppel || !cetAppel.position) return;
    try {
      await fetch("/api/appels/" + cetAppel.id + "/position", {
        method: "POST", headers: entetes(), body: JSON.stringify(cetAppel.position),
      });
    } catch { /* le sondage s'occupe de dire si le réseau est coupé */ }
  }

  /* Prévient le serveur que ce téléphone raccroche (si l'appel lui est connu). */
  function prevenirLeServeur(enQuittantLaPage = false) {
    if (!appel || !appel.id) return;
    fetch("/api/appels/" + appel.id + "/raccrocher",
          { method: "POST", headers: entetes(), keepalive: enQuittantLaPage }).catch(() => {});
  }

  /* Coupe tout ce que l'appel a ouvert : micro, suivi de la position, minuteries, connexion. */
  function nettoyer() {
    if (!appel) return;
    appel.minuteries.forEach((m) => { clearInterval(m); clearTimeout(m); });
    if (appel.suivi !== null && navigator.geolocation) navigator.geolocation.clearWatch(appel.suivi);
    if (appel.micro) appel.micro.getTracks().forEach((piste) => piste.stop());
    if (appel.pc) appel.pc.close();
    voix.srcObject = null;
    appel = null;
  }

  function raccrocher(phrase) {
    prevenirLeServeur();
    nettoyer();
    montrer("fini", "Appel terminé", phrase);
  }

  function finir(phrase) {
    nettoyer();
    montrer("fini", "Appel terminé", phrase);
  }

  function echouer(phrase) {
    prevenirLeServeur();
    nettoyer();
    montrer("echec", "L'appel n'a pas abouti", phrase);
  }
})();
