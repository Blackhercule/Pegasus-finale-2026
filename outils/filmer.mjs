/* Filme la démonstration dans un vrai navigateur, scène par scène.
 *
 *     python outils/donnees_demonstration.py      (remplit la base)
 *     node outils/filmer.mjs                      (filme dans /tmp/video)
 *     python outils/monter_video.py               (assemble la vidéo)
 *
 * Rien n'est mis en scène : ce sont les vraies pages, avec les vraies données.
 * Playwright doit être installé (npm install playwright), et l'application doit tourner.
 */
import { chromium } from "playwright";
const base = "http://127.0.0.1:8099";
const sortie = "/tmp/video";
const n = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });

async function scene(nom, taille, action, options = {}) {
  const ctx = await n.newContext({
    viewport: taille, deviceScaleFactor: 1, locale: "fr-FR",
    recordVideo: { dir: `${sortie}/${nom}`, size: taille },
    permissions: ["geolocation", "microphone"],
    geolocation: { latitude: 12.3714, longitude: -1.5197, accuracy: 9 },
    ...options,
  });
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.accept("Riverains sensibilisés, un récidiviste verbalisé"));
  try { await action(page); } catch (e) { console.log("!! " + nom + " : " + e.message.slice(0, 160)); }
  await page.waitForTimeout(700);
  await ctx.close();
  console.log("scène", nom, "ok");
}

const ECRAN = { width: 1280, height: 720 };
const TEL = { width: 420, height: 720 };
const attendre = (p, ms) => p.waitForTimeout(ms);

// 1. la carte, hors ligne
await scene("01-carte", ECRAN, async (page) => {
  await page.goto(base + "/decision/", { waitUntil: "networkidle", timeout: 90000 });
  await page.waitForFunction(() => document.getElementById("resume-plan").children.length > 0,
    { timeout: 120000 });
  await attendre(page, 2500);
  await page.mouse.move(800, 400);
  await page.mouse.wheel(0, -260);
  await attendre(page, 2600);
});

// 2. signalement depuis un téléphone
await scene("02-signaler", TEL, async (page) => {
  await page.goto(base + "/signaler/", { waitUntil: "networkidle" });
  await attendre(page, 1400);
  await page.click("#guidage"); await attendre(page, 900);
  await page.click('#taille button[data-valeur="tres_grand"]'); await attendre(page, 700);
  await page.click("details.mesures summary"); await attendre(page, 500);
  await page.fill("#longueur_m", "12"); await page.fill("#largeur_m", "6");
  await attendre(page, 1200);
  await page.click('#depot button[data-valeur="caniveau"]'); await attendre(page, 900);
  await page.click("#enregistrer"); await attendre(page, 2200);
  await page.click("#enregistrer"); await attendre(page, 1600);
  await page.click("#envoyer"); await attendre(page, 2200);
});

// 3. la chaîne : mairie, brigade, mairie, collecte
await scene("03-chaine", ECRAN, async (page) => {
  const seConnecter = async (nom, mdp) => {
    await page.goto(base + "/decision/dossiers.html", { waitUntil: "networkidle" });
    if (await page.isVisible("#connexion")) {
      await page.fill("#nom", nom); await page.fill("#mot-de-passe", mdp);
      await page.click("#connexion button[type=submit]");
    }
    await page.waitForSelector("#travail:not([hidden])", { timeout: 20000 });
    await attendre(page, 1100);
  };
  await seConnecter("agent", "essai");
  await page.click("#lignes tr[data-id]"); await attendre(page, 2200);
  await page.fill("#detail-action", "Confirmé sur place avec le chef de quartier");
  await attendre(page, 900);
  await page.click("#avancer"); await attendre(page, 1600);
  await page.click("#deconnexion");
  await seConnecter("brigade", "essai-b");
  await page.click("#lignes tr[data-id]"); await attendre(page, 1800);
  await page.fill("#detail-action", "Riverains sensibilisés, un récidiviste verbalisé");
  await attendre(page, 900);
  await page.click("#avancer"); await attendre(page, 1500);
  await page.click("#deconnexion");
  await seConnecter("collecte", "essai-c");
  await attendre(page, 1800);
});

// 4. les pièges du jury
await scene("04-pieges", ECRAN, async (page) => {
  await page.goto(base + "/decision/verifier.html", { waitUntil: "networkidle" });
  if (await page.isVisible("#connexion")) {
    await page.fill("#nom", "agent"); await page.fill("#mot-de-passe", "essai");
    await page.click("#connexion button[type=submit]");
  }
  await page.waitForSelector("#travail:not([hidden])");
  await attendre(page, 900);
  await page.setInputFiles("#fichier-lot", "/home/claude/pegasus-finale-2026/tests/pieges-jury.json");
  await attendre(page, 700);
  await page.click("#envoyer-lot");
  await page.waitForTimeout(2500);
  await page.click('#filtres button[data-statut="rejete"]');
  await attendre(page, 3000);
});

// 5. le plan et les changements du jury
await scene("05-plan", ECRAN, async (page) => {
  await page.goto(base + "/decision/", { waitUntil: "networkidle", timeout: 90000 });
  await page.waitForFunction(() => document.getElementById("resume-plan").children.length > 0,
    { timeout: 120000 });
  await attendre(page, 1800);
  await page.fill("#camions_en_panne", "14");
  await page.check("#saison");
  await attendre(page, 1200);
  await page.click("#recalculer");
  await page.waitForFunction(() => !document.getElementById("recalculer").disabled, { timeout: 120000 });
  await attendre(page, 3200);
});

// 6. comparer des scénarios
await scene("06-scenarios", { width: 1280, height: 900 }, async (page) => {
  await page.goto(base + "/decision/scenarios.html", { waitUntil: "networkidle" });
  await page.selectOption("#jours", "30");
  await attendre(page, 900);
  await page.click("#comparer");
  await page.waitForFunction(() => document.getElementById("etat").textContent.includes("comparés"),
    { timeout: 240000 });
  await attendre(page, 1500);
  await page.mouse.wheel(0, 700);
  await attendre(page, 3000);
});

// 7. la simulation
await scene("07-simulation", { width: 1280, height: 900 }, async (page) => {
  await page.goto(base + "/decision/simulation.html", { waitUntil: "networkidle" });
  await page.waitForFunction(() => !document.getElementById("resultats").hidden, { timeout: 180000 });
  await attendre(page, 2500);
  await page.mouse.wheel(0, 600);
  await attendre(page, 2600);
});

await n.close();
console.log("terminé");
