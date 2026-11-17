/* T23 : essai de l'appel « Parler à la mairie », dans un vrai navigateur.
 *
 *     node outils/essai_appel.mjs            (l'application doit tourner)
 *
 * Deux contextes Chromium, lancés avec un faux micro et sans fenêtre d'autorisation :
 *   - un téléphone (420 px, position permise), qui touche 2 sur le menu d'accueil ;
 *   - l'agent « agent » (mairie), qui voit le bandeau, décroche, et suit la carte.
 * On vérifie que les deux connexions WebRTC passent à « connected » en moins de 10 s, que la
 * voix circule vraiment (octets reçus des deux côtés) par une adresse du réseau local, que le
 * point bouge sur la carte de l'agent en moins de 5 s quand le téléphone se déplace, et que
 * l'agent lit « Appel terminé » quand le téléphone raccroche. Puis les cas d'échec : chacun
 * doit retomber sur le formulaire (touche 1).
 *
 * Réglages : ADRESSE (défaut http://127.0.0.1:8099), MDP_AGENT (défaut « essai »), CAPTURES
 * (dossier où ranger les captures d'écran, facultatif).
 *
 * Ce script passe DEUX vrais appels. Le serveur en accepte au plus 5 par téléphone en dix
 * minutes : au-delà de deux lancements en dix minutes, attendre ou relancer l'application.
 * Les échecs « personne ne décroche », « agents occupés » et « réseau coupé » sont joués en
 * faisant répondre le serveur à sa place (page.route) : le téléphone vit exactement ce qu'il
 * vivrait, sans attendre 90 s ni encombrer le serveur. Le serveur, lui, est vérifié pour ces
 * cas par tests/test_appels.py.
 */
import { chromium } from "playwright";
import { join } from "node:path";

const base = process.env.ADRESSE || "http://127.0.0.1:8099";
const MDP_AGENT = process.env.MDP_AGENT || "essai";
const CAPTURES = process.env.CAPTURES || "";
const TEL = { width: 420, height: 860 };
const ECRAN = { width: 1366, height: 768 };
const OUAGA = { latitude: 12.3714, longitude: -1.5197, accuracy: 12 };
const FAUX_MEDIAS = ["--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"];

const bilan = [];
const dehors = new Set();
const erreurs = [];
const navigateur = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", ...FAUX_MEDIAS] });
// Le même, mais sans le faux « Autoriser » : la demande de micro est refusée.
const navigateurSansMicro = await chromium.launch({ args: FAUX_MEDIAS });

function noter(ok, texte, detail = "") {
  bilan.push({ ok, texte });
  console.log(`  ${ok ? "✔" : "✘"} ${texte}${detail ? " — " + detail : ""}`);
}

async function etape(nom, action) {
  console.log(nom);
  try { await action(); } catch (e) { noter(false, nom, e.message.split("\n")[0].slice(0, 200)); }
}

async function capture(page, nom) {
  if (CAPTURES) await page.screenshot({ path: join(CAPTURES, nom) }).catch(() => {});
}

/* Chaque page est surveillée : requêtes qui sortiraient de la machine, erreurs de console.
   Un enregistrement mooré manquant (404 sous /audio/moore/) n'est pas une erreur : la page
   est faite pour s'en passer. `tolerer` liste les refus provoqués exprès par un cas d'échec. */
function surveiller(page, tolerer = null) {
  page.on("request", (r) => {
    const u = r.url();
    if (!u.startsWith(base) && !u.startsWith("blob:") && !u.startsWith("data:")) dehors.add(u);
  });
  page.on("pageerror", (e) => erreurs.push(page.url() + " : " + e.message));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const ou = (m.location() && m.location().url) || "";
    if (/status of 404/.test(m.text()) && ou.includes("/signaler/audio/moore/")) return;
    if (tolerer && tolerer.test(m.text() + " " + ou)) return;
    erreurs.push(page.url() + " : " + m.text() + (ou ? " (" + ou + ")" : ""));
  });
}

/* On garde une référence à chaque RTCPeerConnection de la page, pour lire son état et ses
   statistiques depuis l'essai. Cela ne change rien au fonctionnement de la page. */
const ESPION_WEBRTC = () => {
  const Vrai = window.RTCPeerConnection;
  if (!Vrai) return;
  window.__connexions = [];
  window.RTCPeerConnection = function (...args) {
    const pc = new Vrai(...args);
    window.__connexions.push(pc);
    return pc;
  };
  window.RTCPeerConnection.prototype = Vrai.prototype;
};

async function telephone(options = {}, nav = navigateur, tolerer = null) {
  const ctx = await nav.newContext({
    viewport: TEL, locale: "fr-FR", isMobile: true, hasTouch: true, ignoreHTTPSErrors: true,
    permissions: ["geolocation", "microphone"], geolocation: OUAGA, ...options,
  });
  await ctx.addInitScript(ESPION_WEBRTC);
  ctx.on("page", (p) => surveiller(p, tolerer));
  const page = await ctx.newPage();
  return { ctx, page };
}

async function versLeMenu(page) {
  await page.goto(base + "/signaler/", { waitUntil: "networkidle" });
  await page.waitForSelector("#menu-accueil:not([hidden])", { timeout: 15000 });
}

/* L'état de la page d'appel (téléphone ou agent), tel qu'elle l'écrit sur <body>. */
const etatDeLAppel = (page) => page.evaluate(() => document.body.dataset.appel || "");

async function attendreEtat(page, etat, delai) {
  await page.waitForFunction((e) => document.body.dataset.appel === e, etat, { timeout: delai });
}

/* L'état WebRTC vu de l'intérieur : connexion, octets audio reçus, type d'adresse utilisée. */
async function webrtc(page) {
  return page.evaluate(async () => {
    const pc = (window.__connexions || []).at(-1);
    if (!pc) return null;
    const stats = await pc.getStats();
    let recus = 0, paire = null;
    const types = {};
    stats.forEach((s) => {
      if (s.type === "inbound-rtp" && s.kind === "audio") recus += s.bytesReceived || 0;
      if (s.type === "candidate-pair" && s.nominated && s.state === "succeeded") paire = s;
      if (s.type === "local-candidate" || s.type === "remote-candidate") types[s.id] = s.candidateType;
    });
    return { etat: pc.connectionState, recus,
             local: paire ? types[paire.localCandidateId] : null,
             distant: paire ? types[paire.remoteCandidateId] : null,
             serveursIce: pc.getConfiguration().iceServers.length };
  });
}

/* Le cas d'échec est réussi si le téléphone le dit et montre la touche 1, qui mène au formulaire. */
async function retombeSurLeFormulaire(page, attendu, nomCapture = "") {
  await attendreEtat(page, "echec", 20000);
  if (nomCapture) await capture(page, nomCapture);
  const phrase = await page.textContent("#appel-texte");
  const touche1 = await page.isVisible("#appel-formulaire");
  await page.click("#appel-formulaire");
  const formulaire = await page.isVisible("#formulaire");
  const ecranAppel = await page.isVisible("#appel");
  noter(attendu.test(phrase) && touche1 && formulaire && !ecranAppel,
        "message court, touche 1, retour au formulaire", phrase);
}

// ------------------------------------------------------------------------------------------
let agent, page;            // l'agent, connecté une fois pour toutes
let tel;                    // le téléphone de l'essai principal

await etape("L'agent de la mairie se connecte", async () => {
  agent = await navigateur.newContext({ viewport: ECRAN, locale: "fr-FR", ignoreHTTPSErrors: true,
                                        permissions: ["microphone"] });
  await agent.addInitScript(ESPION_WEBRTC);
  // Avant la connexion, la page demandée répond 401 (c'est la page de connexion) : attendu.
  agent.on("page", (p) => surveiller(p, /status of 401 .*\/decision\/dossiers\.html/));
  page = await agent.newPage();
  await page.goto(base + "/decision/dossiers.html", { waitUntil: "networkidle" });
  await page.fill("#formulaire #nom", "agent");
  await page.fill("#formulaire #mot-de-passe", MDP_AGENT);
  await Promise.all([page.waitForLoadState("load"), page.click("#formulaire button[type=submit]")]);
  await page.waitForSelector(".barre", { timeout: 30000 });
  // La sonnerie est chargée par la barre, pour la mairie seulement.
  await page.waitForFunction(() => !!document.querySelector('script[src="/decision/sonnerie.js"]'),
                             null, { timeout: 10000 });
  noter(true, "connecté, sonnerie chargée sur la page des dossiers");
});

await etape("Le téléphone : menu 1-2-3 sur le dernier écran d'accueil", async () => {
  tel = await telephone();
  await versLeMenu(tel.page);
  const visibles = await tel.page.evaluate(() =>
    ["menu-1", "menu-2", "menu-3"].map((i) => !document.getElementById(i).hidden));
  const continuer = await tel.page.isVisible("#accueil-continuer");
  noter(visibles.every(Boolean) && !continuer, "touches 1, 2 et 3 visibles, « Continuer » remplacé");
  await capture(tel.page, "T23-4-telephone-menu.png");
});

let debutDecrochage = 0;
await etape("Le téléphone touche 2 ; l'agent voit le bandeau et décroche", async () => {
  await tel.page.click("#menu-2");
  await attendreEtat(tel.page, "sonne", 15000);
  noter(true, "le téléphone affiche « ça sonne »", await tel.page.textContent("#appel-titre"));
  await capture(tel.page, "T23-4-telephone-sonne.png");
  const t0 = Date.now();
  await page.waitForSelector(".sonnerie:not([hidden])", { timeout: 6000 });
  noter(true, `le bandeau apparaît chez l'agent en ${((Date.now() - t0) / 1000).toFixed(1)} s`,
        await page.textContent(".sonnerie"));
  await capture(page, "T23-4-agent-bandeau.png");
  debutDecrochage = Date.now();
  await Promise.all([page.waitForURL(/\/decision\/appel\.html\?id=\d+/), page.click(".sonnerie__decrocher")]);
});

await etape("Les deux navigateurs se joignent (moins de 10 s)", async () => {
  await Promise.all([attendreEtat(page, "en_communication", 10000),
                     attendreEtat(tel.page, "en_communication", 10000)]);
  const duree = (Date.now() - debutDecrochage) / 1000;
  const [cAgent, cTel] = await Promise.all([webrtc(page), webrtc(tel.page)]);
  noter(cAgent.etat === "connected" && cTel.etat === "connected" && duree < 10,
        `les deux RTCPeerConnection sont « connected », ${duree.toFixed(1)} s après « Décrocher »`);
  noter(cAgent.serveursIce === 0 && cTel.serveursIce === 0, "aucun serveur STUN ni TURN configuré");
  noter(cAgent.local === "host" && cAgent.distant === "host",
        "la voix passe par des adresses du réseau local (candidats « host »)",
        `agent : ${cAgent.local}/${cAgent.distant}, téléphone : ${cTel.local}/${cTel.distant}`);
  // Le faux micro de Chromium émet un bip : on attend que des octets audio arrivent des deux côtés.
  await page.waitForTimeout(2500);
  const [rAgent, rTel] = await Promise.all([webrtc(page), webrtc(tel.page)]);
  noter(rAgent.recus > 1000 && rTel.recus > 1000, "la voix circule dans les deux sens",
        `reçu par l'agent : ${rAgent.recus} o, par le téléphone : ${rTel.recus} o`);
  noter(await page.textContent("#etat") === "En communication" &&
        await tel.page.textContent("#appel-titre") === "En communication", "les deux écrans disent « En communication »");
});

await etape("La carte de l'agent suit l'habitant", async () => {
  await page.waitForSelector(".point-habitant", { timeout: 8000 });
  const avant = await page.evaluate(() => ({ ...document.getElementById("carte-appel").dataset }));
  noter(Math.abs(Number(avant.latitude) - OUAGA.latitude) < 1e-4, "le point bleu est à la position du téléphone",
        `${avant.latitude}, ${avant.longitude}`);
  noter(/Position mise à jour il y a \d+ s/.test(await page.textContent("#position")),
        "« position mise à jour il y a N s »", await page.textContent("#position"));
  const ecranAvant = await page.locator(".point-habitant").boundingBox();
  await capture(page, "T23-4-agent-en-communication.png");
  // L'habitant marche ~300 m vers le nord-est.
  const ailleurs = { latitude: OUAGA.latitude + 0.002, longitude: OUAGA.longitude + 0.002, accuracy: 8 };
  const t0 = Date.now();
  await tel.ctx.setGeolocation(ailleurs);
  await page.waitForFunction((lat) => Math.abs(Number(document.getElementById("carte-appel").dataset.latitude) - lat) < 1e-4,
                             ailleurs.latitude, { timeout: 5000 });
  const duree = (Date.now() - t0) / 1000;
  await page.waitForTimeout(300);
  const ecranApres = await page.locator(".point-habitant").boundingBox();
  const deplacement = Math.hypot(ecranApres.x - ecranAvant.x, ecranApres.y - ecranAvant.y);
  noter(duree < 5 && deplacement > 20, `le point a bougé sur la carte en ${duree.toFixed(1)} s`,
        `${Math.round(deplacement)} px à l'écran`);
  const trajet = await page.evaluate(() => {
    const c = document.querySelector("#carte-appel");
    return !!c && !!document.querySelector(".maplibregl-canvas");
  });
  noter(trajet, "carte dessinée avec le fond hors ligne");
  await capture(page, "T23-4-agent-carte-suit.png");
  if (CAPTURES) {
    await page.setViewportSize(TEL);
    await page.waitForTimeout(500);
    await capture(page, "T23-4-agent-appel-420.png");
    await page.setViewportSize(ECRAN);
  }
  await capture(tel.page, "T23-4-telephone-en-communication.png");
});

await etape("Le téléphone raccroche : l'agent lit « Appel terminé »", async () => {
  const t0 = Date.now();
  await tel.page.click("#appel-raccrocher");
  await page.waitForFunction(() => document.getElementById("etat").textContent === "Appel terminé",
                             null, { timeout: 8000 });
  noter(true, `« Appel terminé » chez l'agent en ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  const restes = await page.evaluate(() => ({
    point: !!document.querySelector(".point-habitant"),
    coordonnees: document.getElementById("coordonnees").textContent,
    donnees: document.getElementById("carte-appel").dataset.latitude,
  }));
  noter(!restes.point && !restes.coordonnees && restes.donnees === undefined,
        "la position a disparu de l'écran de l'agent");
  const liste = await page.evaluate(async () => (await fetch("/api/appels")).json());
  const fini = liste.find((a) => a.etat === "termine");
  noter(!!fini && fini.position === null && fini.trajet.length === 0, "le serveur a effacé la position");
  noter(await etatDeLAppel(tel.page) === "fini" && await tel.page.isVisible("#appel-formulaire"),
        "le téléphone propose ensuite la touche 1");
  await capture(page, "T23-4-agent-termine.png");
  await tel.ctx.close();
});

// ------------------------------------------------------------------ les cas d'échec
await etape("Échec : micro refusé", async () => {
  const t = await telephone({ permissions: ["geolocation"] }, navigateurSansMicro);
  await versLeMenu(t.page);
  await t.page.click("#menu-2");
  await retombeSurLeFormulaire(t.page, /micro/i, "T23-4-echec-micro.png");
  await capture(t.page, "T23-4-echec-retour-au-formulaire.png");
  await t.ctx.close();
});

/* Un faux appel : le serveur ne le voit jamais, la page croit l'avoir créé. */
async function fauxAppel(t, apres) {
  await t.page.route("**/api/appels", (r) => r.request().method() === "POST"
    ? r.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: 990001, jeton: "essai" }) })
    : r.continue());
  await t.page.route("**/api/appels/990001**", apres);
}

await etape("Échec : personne ne décroche", async () => {
  const t = await telephone({}, navigateur, /990001/);
  await fauxAppel(t, (r) => r.fulfill({ status: 200, contentType: "application/json",
    body: JSON.stringify({ id: 990001, etat: r.request().method() === "GET" ? "sans_reponse" : "sonne" }) }));
  await versLeMenu(t.page);
  await t.page.click("#menu-3");                                      // la touche 3 aussi
  await retombeSurLeFormulaire(t.page, /Personne n'a répondu/);
  await t.ctx.close();
});

await etape("Échec : tous les agents sont occupés", async () => {
  const t = await telephone({}, navigateur, /status of 503/);
  await t.page.route("**/api/appels", (r) => r.fulfill({ status: 503, contentType: "application/json",
    body: JSON.stringify({ erreur: "Tous les agents sont occupés. Réessayez dans un moment." }) }));
  await versLeMenu(t.page);
  await t.page.click("#menu-2");
  await retombeSurLeFormulaire(t.page, /occupés/, "T23-4-echec-occupes.png");
  await t.ctx.close();
});

await etape("Échec : réseau coupé pendant que ça sonne", async () => {
  const t = await telephone({}, navigateur, /990001|ERR_INTERNET_DISCONNECTED/);
  await fauxAppel(t, (r) => r.abort("internetdisconnected"));
  await versLeMenu(t.page);
  await t.page.click("#menu-2");
  await attendreEtat(t.page, "sonne", 10000);
  await retombeSurLeFormulaire(t.page, /réseau est coupé/);
  await t.ctx.close();
});

await etape("Échec : réseau coupé avant l'appel", async () => {
  const t = await telephone({}, navigateur, /ERR_INTERNET_DISCONNECTED/);
  await t.page.route("**/api/appels", (r) => r.abort("internetdisconnected"));
  await versLeMenu(t.page);
  await t.page.click("#menu-2");
  await retombeSurLeFormulaire(t.page, /réseau ne répond pas/);
  await t.ctx.close();
});

await etape("Position refusée : l'appel passe, l'agent lit « position non partagée »", async () => {
  const t = await telephone({ permissions: ["microphone"], geolocation: undefined });
  await page.goto(base + "/decision/dossiers.html", { waitUntil: "networkidle" });
  await versLeMenu(t.page);
  await t.page.click("#menu-2");
  await attendreEtat(t.page, "sonne", 15000);
  await page.waitForSelector(".sonnerie:not([hidden])", { timeout: 6000 });
  const bandeau = await page.textContent(".sonnerie__detail");
  await Promise.all([page.waitForURL(/appel\.html/), page.click(".sonnerie__decrocher")]);
  await Promise.all([attendreEtat(page, "en_communication", 10000),
                     attendreEtat(t.page, "en_communication", 10000)]);
  await page.waitForTimeout(1500);
  const ligne = await page.textContent("#position");
  noter(/non partagée/.test(bandeau) && /Position non partagée/.test(ligne),
        "en communication sans position", `bandeau : ${bandeau} · page : ${ligne}`);
  // Cette fois, c'est l'agent qui raccroche : le téléphone doit l'apprendre.
  await page.click("#raccrocher");
  await attendreEtat(t.page, "fini", 6000);
  noter(/L'agent a raccroché/.test(await t.page.textContent("#appel-texte")),
        "l'agent raccroche : le téléphone l'apprend", await t.page.textContent("#appel-texte"));
  await t.ctx.close();
});

await etape("Sans WebRTC, les touches 2 et 3 ne s'affichent pas", async () => {
  const t = await telephone();
  await t.ctx.addInitScript(() => { delete window.RTCPeerConnection; });
  await versLeMenu(t.page);
  const visibles = await t.page.evaluate(() =>
    ["menu-1", "menu-2", "menu-3"].map((i) => !document.getElementById(i).hidden));
  noter(visibles[0] && !visibles[1] && !visibles[2], "seule la touche 1 reste");
  await t.page.click("#menu-1");
  noter(await t.page.isVisible("#formulaire") && !(await t.page.isVisible("#accueil")), "1 ouvre le formulaire");
  await t.ctx.close();
});

await etape("« Revoir les messages d'accueil » ramène au menu", async () => {
  const t = await telephone();
  await versLeMenu(t.page);
  await t.page.click("#accueil-passer");
  noter(await t.page.isVisible("#formulaire") && !(await t.page.isVisible("#accueil")), "« Passer le guidage » mène au formulaire");
  await t.page.click("#revoir-accueil");
  await t.page.waitForSelector("#menu-accueil:not([hidden])", { timeout: 5000 });
  noter(true, "le menu 1-2-3 est revenu");
  await t.ctx.close();
});

await agent.close();
await navigateur.close();
await navigateurSansMicro.close();

noter(dehors.size === 0, "aucune requête vers Internet", [...dehors].slice(0, 3).join(" "));
noter(erreurs.length === 0, "aucune erreur dans la console", erreurs.slice(0, 3).join(" | "));
const echecs = bilan.filter((b) => !b.ok);
console.log(`\nBilan : ${bilan.length - echecs.length} réussies, ${echecs.length} en échec.`);
process.exit(echecs.length ? 1 : 0);
