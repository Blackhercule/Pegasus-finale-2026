/* T23 : « ça sonne partout » pour la mairie.
 *
 * barre.js charge ce fichier sur toutes les pages, seulement pour le poste mairie (et pas sur
 * la page d'appel elle-même). Toutes les 2 s, il demande au serveur s'il y a un appel qui sonne.
 * Si oui : un bandeau bien visible « 📞 Un habitant appelle », avec Décrocher et Ignorer, et une
 * sonnerie fabriquée par le navigateur (API Web Audio : aucun fichier son de plus).
 *
 * « Ignorer » ne vaut que pour cet onglet (sessionStorage) : l'appel continue de sonner chez
 * les autres agents de la mairie.
 */
"use strict";

(function () {
  if (location.pathname === "/decision/appel.html") return;

  const SONDAGE_MS = 2000;
  const RYTHME_MS = 3000;                  // une sonnerie toutes les 3 s
  const IGNORES = "appels-ignores";

  const feuille = document.createElement("link");
  feuille.rel = "stylesheet";
  feuille.href = "/decision/sonnerie.css";
  document.head.append(feuille);

  let bandeau = null, detail = null, decrocher = null;
  let audio = null;         // le « haut-parleur » Web Audio, créé au premier appel qui sonne
  let rythme = null;
  let minuterie = null;

  function ignores() {
    try { return JSON.parse(sessionStorage.getItem(IGNORES) || "[]"); } catch { return []; }
  }

  function ignorer(id) {
    const liste = ignores().concat(id).slice(-50);
    try { sessionStorage.setItem(IGNORES, JSON.stringify(liste)); } catch { /* sans stockage : tant pis */ }
    cacher();
  }

  function construire() {
    bandeau = document.createElement("div");
    bandeau.className = "sonnerie";
    bandeau.setAttribute("role", "alert");
    const titre = document.createElement("strong");
    titre.className = "sonnerie__titre";
    titre.textContent = "📞 Un habitant appelle";
    detail = document.createElement("span");
    detail.className = "sonnerie__detail";
    decrocher = document.createElement("a");
    decrocher.className = "sonnerie__decrocher";
    decrocher.textContent = "Décrocher";
    const boutonIgnorer = document.createElement("button");
    boutonIgnorer.type = "button";
    boutonIgnorer.className = "sonnerie__ignorer";
    boutonIgnorer.textContent = "Ignorer";
    boutonIgnorer.addEventListener("click", () => ignorer(Number(bandeau.dataset.appel)));
    bandeau.append(titre, detail, decrocher, boutonIgnorer);
    document.body.append(bandeau);
  }

  function montrer(a, autres) {
    if (!bandeau) construire();
    bandeau.hidden = false;
    bandeau.dataset.appel = String(a.id);
    const ou = !a.position ? "position non partagée"
      : a.position.hors_commune ? "position hors de la commune" : "position partagée";
    detail.textContent = `ça sonne depuis ${a.sonne_depuis_s} s · ${ou}` +
      (autres ? ` · ${autres} autre${autres > 1 ? "s" : ""} en attente` : "");
    decrocher.href = "/decision/appel.html?id=" + encodeURIComponent(a.id);
    sonner();
    // Son bloqué par le navigateur (aucun clic encore sur cette page) : on le dit.
    if (audio && audio.state !== "running") {
      detail.textContent += " · 🔇 cliquez sur la page pour entendre la sonnerie";
    }
  }

  function cacher() {
    if (bandeau) bandeau.hidden = true;
    taire();
  }

  /* La sonnerie : deux notes brèves, répétées. Un oscillateur fabrique le son, un « gain »
     l'allume et l'éteint en douceur (sans claquement). */
  function bip(debut, duree, frequence) {
    const oscillateur = audio.createOscillator();
    const volume = audio.createGain();
    oscillateur.type = "sine";
    oscillateur.frequency.value = frequence;
    volume.gain.setValueAtTime(0, debut);
    volume.gain.linearRampToValueAtTime(0.18, debut + 0.02);
    volume.gain.setValueAtTime(0.18, debut + duree - 0.03);
    volume.gain.linearRampToValueAtTime(0, debut + duree);
    oscillateur.connect(volume).connect(audio.destination);
    oscillateur.start(debut);
    oscillateur.stop(debut + duree);
  }

  function sonner() {
    if (rythme) return;
    const Haut = window.AudioContext || window.webkitAudioContext;
    if (!Haut) return;                       // navigateur sans Web Audio : le bandeau suffit
    if (!audio) audio = new Haut();
    if (audio.state === "suspended") audio.resume().catch(() => {});
    const jouer = () => {
      const t = audio.currentTime + 0.05;
      bip(t, 0.35, 880);
      bip(t + 0.5, 0.35, 880);
    };
    jouer();
    rythme = setInterval(jouer, RYTHME_MS);
  }

  function taire() {
    clearInterval(rythme);
    rythme = null;
  }

  // Un navigateur ne laisse jouer un son qu'après un premier geste sur la page : au premier
  // clic, on réveille la sonnerie si elle attendait. Le bandeau, lui, s'affiche toujours.
  document.addEventListener("pointerdown", () => {
    if (audio && audio.state === "suspended") audio.resume().catch(() => {});
  });

  async function sonder() {
    let liste;
    try {
      const r = await fetch("/api/appels", { cache: "no-store" });
      if (r.status === 401 || r.status === 403) { clearInterval(minuterie); cacher(); return; }
      if (!r.ok) return;
      liste = await r.json();
    } catch {
      return;                                  // réseau coupé un instant : on réessaiera
    }
    const deCote = ignores();
    const sonnent = liste.filter((a) => a.etat === "sonne" && !deCote.includes(a.id));
    if (sonnent.length) montrer(sonnent[0], sonnent.length - 1);
    else cacher();
  }

  minuterie = setInterval(sonder, SONDAGE_MS);
  sonder();
})();
