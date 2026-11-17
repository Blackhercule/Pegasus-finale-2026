/* Capture une page à 1366 px et à 420 px, connecté comme `agent` (T22).
 *
 *     node outils/capturer_page.mjs /decision/tableau-de-bord.html prefixe [dossier] [cliquer]
 *
 * Écrit <dossier>/<prefixe>-1366.png et <prefixe>-420.png (page entière), et signale tout
 * débordement horizontal, toute erreur de console et toute requête hors de la machine.
 * `cliquer` (facultatif) : sélecteur d'un bouton à presser avant la capture, dont on attend
 * la fin du traitement (il redevient actif).
 */
import { chromium } from "playwright";

const [adresse, prefixe, dossier = "/tmp", cliquer = ""] = process.argv.slice(2);
const base = process.env.ADRESSE || "http://127.0.0.1:8099";
const nav = await chromium.launch();
let probleme = 0;
for (const largeur of [1366, 420]) {
  const ctx = await nav.newContext({ viewport: { width: largeur, height: largeur > 500 ? 768 : 860 },
                                     locale: "fr-FR", permissions: ["geolocation"],
                                     geolocation: { latitude: 12.3714, longitude: -1.5197, accuracy: 9 } });
  const page = await ctx.newPage();
  const erreurs = [], dehors = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/status of 40[134]/.test(m.text())) erreurs.push(m.text()); });
  page.on("request", (r) => { if (!r.url().startsWith(base) && !/^(blob|data):/.test(r.url())) dehors.push(r.url()); });
  if (adresse.startsWith("/decision/")) {
    await page.goto(base + adresse, { waitUntil: "networkidle" });
    if (await page.isVisible("#formulaire #nom")) {
      await page.fill("#formulaire #nom", process.env.COMPTE || "agent");
      await page.fill("#formulaire #mot-de-passe", process.env.MDP || "essai");
      await page.click("#formulaire button[type=submit]");
      await page.waitForLoadState("networkidle");
      if (new URL(page.url()).pathname !== new URL(base + adresse).pathname) {
        await page.goto(base + adresse, { waitUntil: "networkidle" });
      }
    }
  } else {
    await page.goto(base + adresse, { waitUntil: "networkidle" });
  }
  if (await page.isVisible("#accueil-passer").catch(() => false)) await page.click("#accueil-passer");
  await page.waitForTimeout(1500);
  if (cliquer) {
    await page.click(cliquer);
    await page.waitForFunction((s) => !document.querySelector(s).disabled, cliquer, { timeout: 120000 });
    await page.waitForTimeout(500);
  }
  // On parcourt la page jusqu'en bas : ce qui se charge à l'apparition (photos) est chargé.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 500) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(800);
  const debord = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: `${dossier}/${prefixe}-${largeur}.png`, fullPage: true });
  const ok = debord <= largeur && !erreurs.length && !dehors.length;
  if (!ok) probleme += 1;
  console.log(`${largeur} px : largeur ${debord}${debord > largeur ? " DÉBORDE" : ""}, erreurs ${erreurs.length} ${erreurs.slice(0, 2).join(" | ")}, hors machine ${dehors.length}`);
  await ctx.close();
}
await nav.close();
process.exit(probleme ? 1 : 0);
