/* Filme la démonstration dans un vrai navigateur, scène par scène (T21).
 *
 *     python outils/donnees_demonstration.py   (remplit la base : dossiers à toutes les étapes)
 *     node outils/filmer.mjs                   (filme les scènes dans /tmp/video)
 *     python outils/monter_video.py            (assemble la vidéo de 3 minutes)
 *
 * Rien n'est mis en scène : ce sont les vraies pages, avec les vraies données. L'ordre suit
 * l'énoncé : « du signalement à la tournée, puis un changement de paramètres et le plan
 * recalculé ».
 *
 * Réglages par variables d'environnement :
 *   ADRESSE   adresse de l'application (défaut http://127.0.0.1:8099)
 *   SORTIE    dossier des scènes filmées (défaut /tmp/video)
 *   MDP_AGENT, MDP_BRIGADE, MDP_COLLECTE, MDP_ONEA : mots de passe des postes
 *             (défaut : ceux de outils/donnees_demonstration.py)
 *
 * Quand une page calcule longtemps (comparaison, simulation), le moment où le résultat apparaît
 * est noté dans <scène>/coupes.json : le montage commence la scène un peu avant, pour ne pas
 * montrer trente secondes d'attente.
 *
 * Playwright doit être installé (npm install playwright) et l'application doit tourner.
 */
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const base = process.env.ADRESSE || "http://127.0.0.1:8099";
const sortie = process.env.SORTIE || "/tmp/video";
const MDP = {
  agent: process.env.MDP_AGENT || "essai",
  brigade: process.env.MDP_BRIGADE || "essai-b",
  collecte: process.env.MDP_COLLECTE || "essai-c",
  onea: process.env.MDP_ONEA || "essai-o",
};
const navigateur = await chromium.launch({
  args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
});

const ECRAN = { width: 1280, height: 720 };
const TEL = { width: 420, height: 720 };
const attendre = (page, ms) => page.waitForTimeout(ms);

async function scene(nom, taille, action, options = {}) {
  const debut = Date.now();
  const ctx = await navigateur.newContext({
    viewport: taille, deviceScaleFactor: 1, locale: "fr-FR",
    recordVideo: { dir: `${sortie}/${nom}`, size: taille },
    permissions: ["geolocation", "microphone"],
    geolocation: { latitude: 12.3714, longitude: -1.5197, accuracy: 9 },
    ...options,
  });
  const page = await ctx.newPage();
  page.on("dialog", (d) => d.accept("Riverains sensibilisés, un récidiviste verbalisé"));
  // Pour couper l'attente au montage : « le résultat est là, à t secondes ».
  const marquer = (cle) => {
    writeFileSync(`${sortie}/${nom}/coupes.json`,
                  JSON.stringify({ [cle]: (Date.now() - debut) / 1000 }));
  };
  try {
    await action(page, marquer);
  } catch (e) {
    console.log("!! " + nom + " : " + e.message.slice(0, 200));
  }
  await attendre(page, 600);
  await ctx.close();
  console.log("scène", nom, "ok", ((Date.now() - debut) / 1000).toFixed(1), "s");
}

/* Depuis T13, la partie décision demande une connexion : la page de connexion s'affiche à
   l'adresse demandée, puis la page elle-même. */
async function seConnecter(page, adresse, nom) {
  await page.goto(base + adresse, { waitUntil: "networkidle", timeout: 90000 });
  if (await page.isVisible("#formulaire #nom")) {
    await page.fill("#nom", nom);
    await attendre(page, 300);
    await page.fill("#mot-de-passe", MDP[nom]);
    await attendre(page, 300);
    await page.click("#formulaire button[type=submit]");
    await page.waitForSelector(".barre", { timeout: 60000 });
  }
}

// 1. Un habitant : la page d'accueil, puis le signalement sur son téléphone.
await scene("01-signaler", TEL, async (page) => {
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await attendre(page, 3500);
  await page.click(".signaler");
  await page.waitForURL("**/signaler/");
  await attendre(page, 2500);                                 // l'accueil parlé, premier écran
  if (await page.isVisible("#accueil-passer")) await page.click("#accueil-passer");
  await attendre(page, 2500);                                 // les six choses à signaler
  await page.click('#nature button[data-valeur="ordures"]');
  await attendre(page, 1500);
  await page.locator("#taille").scrollIntoViewIfNeeded();
  await page.click('#taille button[data-valeur="tres_grand"]'); await attendre(page, 1000);
  await page.click("details.mesures summary"); await attendre(page, 600);
  await page.fill("#longueur_m", "12"); await attendre(page, 400);
  await page.fill("#largeur_m", "6"); await attendre(page, 1500);
  await page.locator("#depot").scrollIntoViewIfNeeded();
  await page.click('#depot button[data-valeur="caniveau"]'); await attendre(page, 1500);
  await page.locator("#enregistrer").scrollIntoViewIfNeeded();
  await page.click("#enregistrer"); await attendre(page, 2500);   // il parle au lieu d'écrire
  await page.click("#enregistrer"); await attendre(page, 1500);
  await page.click("#envoyer");
  await page.waitForSelector("#message:not(:empty)", { timeout: 20000 });
  await attendre(page, 3000);
});

// 2. Sans GPS : choisir un lieu connu (T16).
await scene("02-sans-gps", TEL, async (page) => {
  await page.goto(base + "/signaler/", { waitUntil: "networkidle" });
  if (await page.isVisible("#accueil-passer")) await page.click("#accueil-passer");
  await page.locator("#position").scrollIntoViewIfNeeded();
  await attendre(page, 1500);
  await page.click("#sans-gps"); await attendre(page, 800);
  await page.type("#recherche-lieu", "marche gounghin", { delay: 90 });
  await attendre(page, 1200);
  await page.getByRole("button", { name: /Marché de Gounghin/ }).first().click();
  await attendre(page, 1000);
  await page.type("#repere", "derrière le marché, côté nord", { delay: 50 });
  await attendre(page, 2000);
}, { permissions: [] });                                       // la localisation est refusée

// 3. Le jury injecte ses signalements piégés.
await scene("03-pieges", ECRAN, async (page) => {
  await seConnecter(page, "/decision/verifier.html", "agent");
  await page.waitForSelector("#travail:not([hidden])");
  await attendre(page, 1500);
  await page.setInputFiles("#fichier-lot", join(RACINE, "tests", "pieges-jury.json"));
  await attendre(page, 800);
  await page.click("#envoyer-lot");
  await attendre(page, 3000);
  await page.click('#filtres button[data-statut="rejete"]');
  await attendre(page, 4500);
  await page.mouse.move(640, 500);
  await page.mouse.wheel(0, 400);
  await attendre(page, 3500);
});

// 4. Le signalement devient un dossier qui passe de poste en poste.
await scene("04-chaine", ECRAN, async (page) => {
  await seConnecter(page, "/decision/dossiers.html", "agent");
  await page.waitForSelector("#travail:not([hidden])");
  await attendre(page, 1500);
  await page.click("#lignes tr[data-id]"); await attendre(page, 2500);
  await page.fill("#detail-action", "Confirmé sur place avec le chef de quartier");
  await attendre(page, 1000);
  await page.click("#avancer"); await attendre(page, 2000);
  await page.click(".barre__changer");                         // changer de poste
  await seConnecter(page, "/decision/dossiers.html", "brigade");
  await page.waitForSelector("#travail:not([hidden])");
  await attendre(page, 1200);
  await page.click("#lignes tr[data-id]"); await attendre(page, 2000);
  await page.fill("#detail-action", "Riverains sensibilisés, un récidiviste verbalisé");
  await attendre(page, 1000);
  await page.click("#avancer"); await attendre(page, 2000);
  await page.click(".barre__changer");
  await seConnecter(page, "/decision/dossiers.html", "agent");
  await page.waitForSelector("#travail:not([hidden])");
  await attendre(page, 1000);
  await page.click("#lignes tr[data-id]"); await attendre(page, 1500);
  await page.click("#avancer"); await attendre(page, 2500);     // inscrit dans la tournée
});

// 5. Jusqu'à la tournée : la carte, puis une tournée qui passe par un dépotoir, rue par rue.
await scene("05-tournee", ECRAN, async (page) => {
  await seConnecter(page, "/decision/", "agent");
  const reponse = await page.waitForResponse((r) => r.url().includes("/api/plan"), { timeout: 120000 });
  const plan = await reponse.json();
  await attendre(page, 3500);
  const tournee = plan.tournees.find((t) => t.etapes.some((e) => e.genre === "depotoir") && t.geometrie)
    || plan.tournees.find((t) => t.geometrie);
  await page.evaluate((trace) => {
    const lons = trace.map((c) => c[0]), lats = trace.map((c) => c[1]);
    carte.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
                    { padding: 70, duration: 4000 });
  }, tournee.geometrie);
  await attendre(page, 7000);
});

// 6. Le jury change les paramètres : le plan se recalcule.
await scene("06-parametres", ECRAN, async (page) => {
  await seConnecter(page, "/decision/", "agent");
  await page.waitForResponse((r) => r.url().includes("/api/plan"), { timeout: 120000 });
  await attendre(page, 2000);
  await page.click(".barre__menu"); await attendre(page, 1500);
  await page.locator("#reglages").scrollIntoViewIfNeeded();
  await attendre(page, 1000);
  await page.fill("#camions_en_panne", "8");
  await page.dispatchEvent("#camions_en_panne", "input");
  await attendre(page, 1200);
  await page.check("#saison"); await attendre(page, 1200);
  await page.click("#recalculer");
  await page.waitForFunction(() => !document.getElementById("recalculer").disabled, { timeout: 120000 });
  await attendre(page, 1500);
  await page.locator("#bloc-controles").scrollIntoViewIfNeeded();
  await attendre(page, 5000);                                   // les contrôles de cohérence
  await page.keyboard.press("Escape");
  await attendre(page, 3500);                                   // le nouveau plan sur la carte
});

// 7. Comparer des scénarios.
await scene("07-scenarios", { width: 1280, height: 720 }, async (page, marquer) => {
  await seConnecter(page, "/decision/scenarios.html", "agent");
  await page.selectOption("#jours", "30");
  await attendre(page, 800);
  await page.click("#comparer");
  await page.waitForFunction(() => document.getElementById("etat").textContent.includes("comparés"),
    { timeout: 300000 });
  marquer("resultat");
  await attendre(page, 3000);
  await page.mouse.move(640, 400);
  await page.mouse.wheel(0, 500);
  await attendre(page, 4500);
});

// 8. La simulation des quatre acteurs.
await scene("08-simulation", { width: 1280, height: 720 }, async (page, marquer) => {
  await seConnecter(page, "/decision/simulation.html", "agent");
  await page.waitForFunction(() => !document.getElementById("resultats").hidden, { timeout: 240000 });
  marquer("resultat");
  await attendre(page, 3500);
  await page.mouse.move(640, 400);
  await page.mouse.wheel(0, 450);
  await attendre(page, 4000);
});

await navigateur.close();
console.log("terminé");
