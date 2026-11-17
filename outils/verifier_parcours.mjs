/* Rejoue dans un vrai navigateur la liste « Ce qui doit encore marcher » de T22.
 *
 *     python outils/donnees_demonstration.py        (dossiers à toutes les étapes)
 *     node outils/verifier_parcours.mjs             (l'application doit tourner)
 *
 * Réglages : ADRESSE (défaut http://127.0.0.1:8099), MDP_AGENT, MDP_BRIGADE, MDP_COLLECTE,
 * MDP_ONEA (défaut : ceux de donnees_demonstration.py), CAPTURES (dossier, facultatif),
 * PAGES (liste d'adresses à contrôler en 1366 et 420 px, séparées par des virgules).
 *
 * Chaque vérification affiche ✔ ou ✘ ; le script continue après un échec et finit par le
 * bilan. Il relève aussi les erreurs de la console et toute requête qui sortirait de la machine.
 */
import { chromium } from "playwright";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const base = process.env.ADRESSE || "http://127.0.0.1:8099";
const CAPTURES = process.env.CAPTURES || "";
const MDP = {
  agent: process.env.MDP_AGENT || "essai", brigade: process.env.MDP_BRIGADE || "essai-b",
  collecte: process.env.MDP_COLLECTE || "essai-c", onea: process.env.MDP_ONEA || "essai-o",
};
const PAGES = (process.env.PAGES || "/,/signaler/,/decision/").split(",").filter(Boolean);
const TEL = { width: 420, height: 860 };
const ECRAN = { width: 1366, height: 768 };

const bilan = [];
const dehors = new Set();
const erreurs = [];
const navigateur = await chromium.launch({
  args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
});

function noter(ok, texte, detail = "") {
  bilan.push({ ok, texte });
  console.log(`  ${ok ? "✔" : "✘"} ${texte}${detail ? " — " + detail : ""}`);
}

async function contexte(taille, options = {}) {
  const ctx = await navigateur.newContext({
    viewport: taille, locale: "fr-FR", permissions: ["geolocation", "microphone"],
    geolocation: { latitude: 12.3714, longitude: -1.5197, accuracy: 9 }, ...options,
  });
  ctx.on("page", surveiller);
  return ctx;
}

function surveiller(page) {
  page.on("request", (r) => {
    const u = r.url();
    if (!u.startsWith(base) && !u.startsWith("blob:") && !u.startsWith("data:")) dehors.add(u);
  });
  page.on("pageerror", (e) => erreurs.push(page.url() + " : " + e.message));
  page.on("console", (m) => {
    // Les refus 401/403/404/429 provoqués exprès par ce script ne sont pas des erreurs de page.
    if (m.type() === "error" && !/status of 40[134]|status of 429/.test(m.text())) {
      erreurs.push(page.url() + " : " + m.text());
    }
  });
  page.on("dialog", (d) => d.accept("Vérification automatique"));
}

async function etape(nom, action) {
  console.log(nom);
  try { await action(); } catch (e) { noter(false, nom, e.message.split("\n")[0].slice(0, 160)); }
}

/* Une petite photo JPEG (un tas brun sur fond de terre), écrite ici pour ne dépendre d'aucun
   fichier : la page la réduit et la ré-encode avant l'envoi, le serveur la masque (T17). */
const PHOTO = Buffer.from("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAB4AKADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwBtFFFcJ1BRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUVBNdRQkqzZYfwgc1Tk1CRuI1Ce/U01FsLmnRWK1xOxyZX/A4qKq5Bcxv0VgVIs8y42yuMdBnijkDmNuisuPUJV++A4/I1bhvIpcDO1jxg1Li0O5ZooopAFFFFABRRRQAUUUUAFFFFACEgAknAHU1m3N6zkrCdq/3u5pdQuNzeSh+Vfve5qlVxj1ZLYUUUVoIKKKKACiiigAooooAs2148OFb5k9D1H0rURldQyHKnoawqs2Vx5Mu1j8jdfY+tRKI0zWooorMoKKKKACiiigApkz+XC78cDIz60+q99/x5v+H8xQtwMgkkkk5J6miiityAooooAKKKKACiiigAooooAKKKKANi0kMlsjE5YcGp6p6Z/x7t/vn+Qq5WL3LQUUUUgCiiigApsi742TONwIzTqKAMFlKsVYYIODSVoahbk/vkGf73+NZ9bJ3RDCiiimAUUUUAFFFFABRRRQAUUVcsLcu4lcfKv3fc0m7AXraMxW6I3UDmpaKKxLCiiigAooooAKKKKACqFzY5JeDv8Awf4Vfopp2CxgspU4YEEdiKStuSGOX/WID79/zqpJpw6xSfg3+NWpomxn0VYaxuAcBA3uCKj8ib/nlJ/3yaq6ER0VJ5E3/PKT/vk09bK4bHyYB7kjii6AgoAJIAGSegq/Hpx6yyfgv+NW4reKIDYgyP4jyalzQ7FK2sWbDTfKv93uf8K0QAAABgDoKWiobuUkFFFFIAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAP//Z", "base64");

async function passerLAccueil(page) {
  await page.goto(base + "/signaler/", { waitUntil: "networkidle" });
  if (await page.isVisible("#accueil-passer")) await page.click("#accueil-passer");
}

async function attendreLeMessage(page) {
  await page.waitForFunction(() => document.getElementById("message").textContent.trim() !== "",
    null, { timeout: 30000 });
  return page.locator("#message").textContent();
}

async function seConnecter(page, adresse, nom) {
  await page.goto(base + adresse, { waitUntil: "networkidle" });
  await page.fill("#formulaire #nom", nom);
  await page.fill("#formulaire #mot-de-passe", MDP[nom]);
  await Promise.all([page.waitForLoadState("load"), page.click("#formulaire button[type=submit]")]);
  await page.waitForSelector(".barre", { timeout: 30000 });
}

async function api(page, chemin) {
  return page.evaluate(async (c) => (await fetch(c)).json(), chemin);
}

// 1. Signaler un tas d'ordures depuis le téléphone, avec photo.
await etape("1. Signaler un tas d'ordures avec photo (420 px)", async () => {
  const ctx = await contexte(TEL);
  const page = await ctx.newPage();
  await passerLAccueil(page);
  await page.click('#nature button[data-valeur="ordures"]');
  await page.click('#taille button[data-valeur="grand"]');
  await page.setInputFiles("#photo", { name: "tas.jpg", mimeType: "image/jpeg", buffer: PHOTO });
  await page.waitForSelector("#apercu:not([hidden])", { timeout: 10000 });
  await page.click("#envoyer");
  const message = await attendreLeMessage(page);
  noter(/enregistr/i.test(message) && !/écarté/i.test(message), "le signalement est enregistré", message.trim());
  if (CAPTURES) await page.screenshot({ path: join(CAPTURES, "parcours-signaler.png") });
  await ctx.close();
});

// 2. Signaler une fuite d'eau.
await etape("2. Signaler une fuite d'eau", async () => {
  const ctx = await contexte(TEL);
  const page = await ctx.newPage();
  await passerLAccueil(page);
  await page.click('#nature button[data-valeur="fuite_eau"]');
  await page.click('#ampleur button[data-valeur="jet"]');
  await page.fill("#quartier", "Gounghin");
  await page.click("#envoyer");
  const message = await attendreLeMessage(page);
  noter(/enregistr/i.test(message) && !/écarté/i.test(message), "la fuite est enregistrée", message.trim());
  await ctx.close();
});

// 3. Signaler sans GPS en choisissant un lieu connu.
await etape("3. Signaler sans GPS, depuis un lieu connu", async () => {
  const ctx = await contexte(TEL, { permissions: [] });
  const page = await ctx.newPage();
  await passerLAccueil(page);
  await page.click('#nature button[data-valeur="ordures"]');
  await page.click("#sans-gps");
  await page.fill("#recherche-lieu", "universite ki-zerbo");
  await page.getByRole("button", { name: /Université Joseph Ki-Zerbo/ }).first().click();
  await page.click('#taille button[data-valeur="moyen"]');
  await page.click("#envoyer");
  const message = await attendreLeMessage(page);
  noter(/enregistr/i.test(message), "le signalement par lieu est enregistré", message.trim());
  await ctx.close();
});

// 4. Chaque poste arrive sur sa page.
await etape("4. Connexion : chaque poste arrive sur sa page", async () => {
  for (const [nom, attendu] of [["onea", /fuites\.html$/], ["agent", /\/decision\/.+\.html$/]]) {
    const ctx = await contexte(ECRAN);
    const page = await ctx.newPage();
    await seConnecter(page, "/decision/", nom);
    const ou = new URL(page.url()).pathname;
    noter(attendu.test(ou), `« ${nom} » arrive sur ${ou}`);
    await ctx.close();
  }
});

// 5. Un dossier suit toute la chaîne : mairie → brigade → mairie → collecte.
await etape("5. Un dossier de bout en bout, jusqu'à « collecté »", async () => {
  const ctx = await contexte(ECRAN);
  const page = await ctx.newPage();
  await seConnecter(page, "/decision/dossiers.html", "agent");
  const dossiers = await api(page, "/api/dossiers");
  const cible = dossiers.filter((d) => d.etape === "signale").sort((a, b) => b.id - a.id)[0];
  if (!cible) throw new Error("aucun dossier à l'étape « signalé »");
  const tour = [["agent", "confirme"], ["brigade", "constat"], ["agent", "a_collecter"], ["collecte", "collecte"]];
  for (const [nom, apres] of tour) {
    if (nom !== "agent" || apres !== "confirme") {
      await page.click(".barre__changer");                      // « Me déconnecter »
      await page.waitForSelector("#formulaire #nom", { timeout: 20000 });
      await seConnecter(page, "/decision/dossiers.html", nom);
    }
    await page.waitForSelector("#travail:not([hidden])");
    await page.click('#filtres button[data-filtre="tous"]').catch(() => {});
    await page.click(`#lignes tr[data-id="${cible.id}"]`);
    await page.waitForSelector("#avancer", { timeout: 15000 });
    await page.click("#avancer");
    await page.waitForFunction(async ([id, e]) => {
      const r = await fetch("/api/dossiers/" + id);
      return r.ok && (await r.json()).etape === e;
    }, [cible.id, apres], { timeout: 15000 });
  }
  const fin = await api(page, "/api/dossiers/" + cible.id);
  noter(fin.etape === "collecte", `dossier ${cible.id} : ${fin.etape_nom}`);
  await page.click(".barre__changer");
  await page.waitForSelector("#formulaire #nom", { timeout: 20000 });
  noter(true, "« Me déconnecter » ramène à la page de connexion");
  await ctx.close();
});

// 6. Le lot de pièges du jury depuis « Vérifier ».
await etape("6. Les pièges du jury depuis « Vérifier »", async () => {
  const ctx = await contexte(ECRAN);
  const page = await ctx.newPage();
  await seConnecter(page, "/decision/verifier.html", "agent");
  await page.waitForSelector("#travail:not([hidden])");
  await page.setInputFiles("#fichier-lot", join(RACINE, "tests", "pieges-jury.json"));
  await page.click("#envoyer-lot");
  await page.waitForFunction(() => /reçue|rejet|écart/i.test(document.getElementById("resultat-lot").textContent),
    null, { timeout: 30000 });
  noter(true, "lot traité", (await page.locator("#resultat-lot").textContent()).trim().slice(0, 90));
  await page.click('#filtres button[data-statut="rejete"]').catch(() => {});
  await page.waitForTimeout(1500);
  const motifs = await page.locator("#lignes").textContent();
  noter(/format|coordonn|commune|date|volume|eau/i.test(motifs), "les motifs de rejet s'affichent");
  await ctx.close();
});

// 7. La carte : 14 camions en panne, saison des pluies, recalcul, contrôles de cohérence.
await etape("7. Carte : 14 camions en panne et saison des pluies", async () => {
  const ctx = await contexte(ECRAN);
  const page = await ctx.newPage();
  await seConnecter(page, "/decision/index.html", "agent");
  // La connexion mène chaque poste à sa page : on revient ensuite sur la carte.
  await page.goto(base + "/decision/index.html", { waitUntil: "networkidle" });
  // Le premier plan se calcule au chargement : on attend qu'il soit affiché.
  await page.waitForFunction(() => document.getElementById("resume-plan").children.length > 0,
    null, { timeout: 120000 });
  await page.click(".barre__menu");
  await page.fill("#camions_en_panne", "14");
  await page.dispatchEvent("#camions_en_panne", "input");
  await page.check("#saison");
  const [reponse] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/plan") && r.request().method() === "POST", { timeout: 120000 }),
    page.click("#recalculer"),
  ]);
  const plan = await reponse.json();
  await page.waitForFunction(() => document.querySelectorAll("#controles li").length > 0, null, { timeout: 30000 });
  noter(plan.camions_disponibles === 10, `plan recalculé avec ${plan.camions_disponibles} camions`);
  noter(true, `${await page.locator("#controles li").count()} contrôles de cohérence affichés`);
  if (CAPTURES) await page.screenshot({ path: join(CAPTURES, "parcours-carte.png") });
  await ctx.close();
});

// 8. Rien ne déborde, à 1366 et à 420 px.
await etape("8. Débordements", async () => {
  for (const taille of [ECRAN, TEL]) {
    const ctx = await contexte(taille);
    const page = await ctx.newPage();
    await seConnecter(page, "/decision/connexion.html", "agent").catch(() => {});
    for (const adresse of PAGES) {
      await page.goto(base + adresse, { waitUntil: "networkidle" }).catch(() => {});
      if (await page.isVisible("#accueil-passer").catch(() => false)) await page.click("#accueil-passer");
      await page.waitForTimeout(800);
      const largeur = await page.evaluate(() => document.documentElement.scrollWidth);
      noter(largeur <= taille.width, `${adresse} à ${taille.width} px`, largeur > taille.width ? `${largeur} px` : "");
    }
    await ctx.close();
  }
});

await navigateur.close();
noter(dehors.size === 0, "aucune requête vers Internet", [...dehors].slice(0, 3).join(" "));
noter(erreurs.length === 0, "aucune erreur dans la console", erreurs.slice(0, 3).join(" | "));
const echecs = bilan.filter((b) => !b.ok);
console.log(`\nBilan : ${bilan.length - echecs.length} réussies, ${echecs.length} en échec.`);
process.exit(echecs.length ? 1 : 0);
