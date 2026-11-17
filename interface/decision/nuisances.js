/* Poste de travail des nuisances : caniveaux bouchés, abattoirs clandestins, déversement de
   toilettes, eaux usées de poisson et de poulet.

   La mairie reçoit tout et oriente ; ensuite c'est le service que la nature désigne qui agit.
   Un agent ne voit donc ici que ce qui relève de lui, et ne peut avancer que d'un cran. */
"use strict";

const element = (id) => document.getElementById(id);
let session = null;        // { agent, poste, poste_nom, jeton }
let chaine = null;         // étapes, natures et comptes, tels que le serveur les décrit
let filtre = "pour_moi";
let natureFiltre = "";
let choisi = null;

function echapper(texte) {
  const n = document.createElement("span");
  n.textContent = texte == null ? "" : String(texte);
  return n.innerHTML;
}

/* T16 : une position déduite d'un lieu connu n'est pas un relevé GPS. L'agent doit le voir
   avant d'envoyer une équipe : on l'écrit en toutes lettres, avec le lieu et la précision. */
function avertissementLieu(signalements) {
  const depuisUnLieu = (signalements || []).filter((s) => s.source_position === "lieu");
  if (!depuisUnLieu.length) return "";
  return depuisUnLieu.map((s) => `<p class="position-lieu">⚠ Position approximative : déduite du
    lieu « ${echapper(s.lieu_nom || "?")} » (± ${Math.round(s.precision_m || 150)} m), pas d'un GPS.
    Chercher aux abords ; voir le repère dans le commentaire.</p>`).join("");
}

/* La file est classée par urgence et non par ordre d'arrivée : chaque ligne porte sa note et
   surtout ses raisons. Un agent doit pouvoir contester le classement, donc le comprendre. */
function pastilleDePriorite(dossier) {
  const p = dossier.priorite;
  if (!p) return "";
  const niveau = p.note >= 60 ? "haute" : p.note >= 35 ? "moyenne" : "basse";
  return `<span class="priorite ${niveau}" title="${echapper(p.raisons.join(" · ") || "aucun facteur particulier")}">${Math.round(p.note)}</span>`;
}

function raisonsDePriorite(dossier) {
  const p = dossier.priorite;
  return p && p.raisons.length ? `<div class="ligne-raisons">${echapper(p.raisons.join(" · "))}</div>` : "";
}

function dateCourte(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—"
    : d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/* Depuis combien de temps ça dure : plus parlant qu'une date pour juger de l'urgence. */
function depuis(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const heures = Math.max(0, Math.round((Date.now() - d.getTime()) / 3600000));
  return heures < 24 ? `${heures} h` : `${Math.round(heures / 24)} jour(s)`;
}

const SERVICES = { mairie: "Mairie", brigade: "Brigade Laabal",
                   collecte: "Équipe de collecte", onea: "ONEA" };

async function appel(adresse, options = {}) {
  const entetes = {};
  if (session?.jeton) entetes["X-Jeton"] = session.jeton;
  if (options.json) entetes["Content-Type"] = "application/json";
  const reponse = await fetch(adresse, {
    method: options.methode || "GET", headers: entetes,
    body: options.json ? JSON.stringify(options.json) : undefined,
  });
  if (reponse.status === 401) { montrerConnexion(); throw new Error("Connexion requise"); }
  const resultat = await reponse.json().catch(() => ({}));
  if (!reponse.ok) throw new Error(resultat.erreur || "Erreur " + reponse.status);
  return resultat;
}

/* ------------------------------------------------------------------ connexion */
function montrerConnexion() {
  session = null;
  element("connexion").hidden = false;
  element("travail").hidden = true;
  element("deconnexion").hidden = true;
  element("session").textContent = "";
}

async function ouvrirLePoste(info) {
  session = info;
  element("connexion").hidden = true;
  element("travail").hidden = false;
  element("deconnexion").hidden = false;
  element("session").textContent = info.agent;
  await rafraichir();
}

element("connexion").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  const erreur = element("erreur-connexion");
  erreur.hidden = true;
  try {
    await ouvrirLePoste(await appel("/api/connexion", { methode: "POST", json: {
      nom: element("nom").value, mot_de_passe: element("mot-de-passe").value } }));
  } catch (e) {
    erreur.textContent = e.message;
    erreur.hidden = false;
  }
});

element("deconnexion").addEventListener("click", async () => {
  await fetch("/api/deconnexion", { method: "POST" });
  montrerConnexion();
});

/* ------------------------------------------------------------------ la chaîne */
function afficherLaChaine(comptes) {
  const ordre = ["signale", "confirme", "traite", "classe"];
  element("chaine").innerHTML = ordre.map((cle) => {
    const etape = chaine.etapes[cle];
    // L'étape « orienté » n'a pas un seul poste : elle en a un par nature. Elle est donc à
    // moi dès que l'une des natures dont j'ai la charge y est.
    const aMoi = cle === "confirme"
      ? Object.values(chaine.natures).some((n) => n.poste === session.poste)
      : etape.poste === session.poste;
    const clos = cle === "traite" || cle === "classe";
    return `<li class="${aMoi ? "mon-poste" : ""} ${clos ? "close" : ""}">
      <span class="nombre">${comptes[cle] ?? 0}</span>
      <span class="nom">${echapper(etape.nom)}</span>
      <span class="qui">${clos ? "dossier clos"
        : echapper(cle === "confirme" ? "selon la nature" : SERVICES[etape.poste] || etape.poste)}</span>
    </li>`;
  }).join("");
}

function afficherLesFiltresDeNature(parNature) {
  const boutons = [`<button type="button" data-nature="" class="${natureFiltre ? "" : "actif"}">
      Toutes natures</button>`];
  for (const [cle, n] of Object.entries(chaine.natures)) {
    boutons.push(`<button type="button" data-nature="${cle}" class="${
      natureFiltre === cle ? "actif" : ""}">${echapper(n.nom)} (${parNature[cle] ?? 0})</button>`);
  }
  element("filtres-nature").innerHTML = boutons.join("");
}

/* ------------------------------------------------------------------ liste */
async function rafraichir() {
  chaine = await appel("/api/nuisances/chaine");
  afficherLaChaine(chaine.comptes);
  afficherLesFiltresDeNature(chaine.par_nature);
  const parametres = new URLSearchParams();
  if (filtre === "pour_moi") parametres.set("pour_moi", "1");
  if (natureFiltre) parametres.set("nature", natureFiltre);
  const liste = await appel("/api/nuisances?" + parametres.toString());
  element("titre-liste").textContent = filtre === "pour_moi"
    ? "Signalements qui m'attendent" : "Tous les signalements";
  element("lignes").innerHTML = liste.length ? liste.map((n) => `
    <tr data-id="${n.id}" class="${choisi === n.id ? "choisi" : ""}">
      <td>
        <div class="ligne-titre">${pastilleDePriorite(n)} ${echapper(n.nature_nom)} ·
          ${echapper(n.quartier || "quartier non précisé")}</div>
        <div class="ligne-detail">${echapper(n.gravite_nom)} · ${echapper(n.etape_nom)}
          · dure depuis ${depuis(n.premier_vu)} · ${n.nb_signalements} signalement(s)</div>
      ${raisonsDePriorite(n)}
      </td>
    </tr>`).join("")
    : `<tr><td class="vide">${filtre === "pour_moi"
        ? "Aucun signalement n'attend votre poste." : "Aucun signalement pour l'instant."}</td></tr>`;
  if (choisi) afficherNuisance(choisi).catch(() => {});
}

element("filtres").addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("button");
  if (!bouton) return;
  filtre = bouton.dataset.filtre;
  element("filtres").querySelectorAll("button").forEach((b) => b.classList.toggle("actif", b === bouton));
  rafraichir().catch((e) => alert(e.message));
});

element("filtres-nature").addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("button");
  if (!bouton) return;
  natureFiltre = bouton.dataset.nature;
  rafraichir().catch((e) => alert(e.message));
});

element("lignes").addEventListener("click", (evenement) => {
  const ligne = evenement.target.closest("tr[data-id]");
  if (!ligne) return;
  choisi = Number(ligne.dataset.id);
  element("lignes").querySelectorAll("tr").forEach((l) => l.classList.toggle("choisi", l === ligne));
  afficherNuisance(choisi).catch((e) => alert(e.message));
});

/* ------------------------------------------------------------------ détail */
async function afficherNuisance(identifiant) {
  const n = await appel("/api/nuisances/" + identifiant);
  const aMoi = n.poste_attendu === session.poste;

  const photos = n.signalements.filter((s) => s.photo).map((s) =>
    `<figure><img src="/api/fichiers/${encodeURI(s.photo)}" alt="Photo du signalement">
       <figcaption>${dateCourte(s.date_observation)}</figcaption></figure>`).join("");
  const voix = n.signalements.filter((s) => s.message_vocal).map((s) =>
    `<audio controls src="/api/fichiers/${encodeURI(s.message_vocal)}"></audio>`).join("");

  const temoins = n.signalements.filter((s) => s.declarant_nom || s.declarant_telephone);
  const blocTemoins = temoins.length ? `
    <div class="prive">
      <h3>Déclarant joignable</h3>
      <p class="avertissement">Renseignements facultatifs, donnés volontairement. À effacer
        dès la clôture du dossier.</p>
      ${temoins.map((s) => `
        <dl>
          <dt>Nom</dt><dd>${echapper(s.declarant_nom || "—")}</dd>
          <dt>Téléphone</dt><dd>${echapper(s.declarant_telephone || "—")}</dd>
        </dl>`).join("")}
    </div>` : "";

  element("detail").innerHTML = `
    <h2>NUIS-${String(n.id).padStart(5, "0")} — ${echapper(n.nature_nom)}</h2>
    <p class="aide">${echapper(n.explication_etape || "")}</p>
    <dl>
      <dt>État du dossier</dt><dd>${echapper(n.etape_nom)}</dd>
      <dt>Service compétent</dt><dd>${echapper(SERVICES[n.service] || n.service || "—")}</dd>
      <dt>Gravité</dt><dd>${echapper(n.gravite_nom)}</dd>
      <dt>Quartier</dt><dd>${echapper(n.quartier || "non précisé")}</dd>
      <dt>Ça dure depuis</dt><dd>${depuis(n.premier_vu)} (premier signalement le ${dateCourte(n.premier_vu)})</dd>
      <dt>Signalements</dt><dd>${n.nb_signalements}, de ${n.nb_sources} source(s)</dd>
      <dt>Position</dt><dd>${Number(n.latitude).toFixed(5)}, ${Number(n.longitude).toFixed(5)}</dd>
    </dl>
    ${avertissementLieu(n.signalements)}
    ${n.pourquoi ? `<p class="aide">${echapper(n.pourquoi)}</p>` : ""}
    ${photos ? `<div class="vignettes">${photos}</div>` : ""}
    ${voix ? `<h3 class="aide">Message vocal du déclarant</h3>${voix}` : ""}
    ${blocTemoins}
    <h3 class="aide">Qui a fait quoi</h3>
    <ul class="journal">${n.journal.length ? n.journal.map((e) => `
      <li><span class="quand">${dateCourte(e.date)}</span> —
        <span class="qui">${echapper(e.auteur)}</span> (${echapper(SERVICES[e.poste] || e.poste)})
        : ${echapper(chaine.etapes[e.etape]?.nom || e.etape)}${e.detail ? " — " + echapper(e.detail) : ""}</li>`).join("")
      : "<li>Rien encore : le dossier vient d'être ouvert par un signalement.</li>"}</ul>
    ${aMoi ? `
      <div class="actions-dossier">
        <textarea id="detail-action" rows="2" maxlength="500"
                  placeholder="Ce que vous avez constaté ou fait (facultatif)"></textarea>
        <div class="ligne">
          <button type="button" id="avancer">${echapper(n.action_attendue || "Faire avancer")}</button>
          ${session.poste === "mairie" ? `<button type="button" class="rejeter secondaire" id="classer">
            Classer sans suite</button>` : ""}
        </div>
      </div>` : `<p class="aide">Ce dossier attend le poste « ${
        echapper(SERVICES[n.poste_attendu] || n.poste_attendu || "—")} ».</p>`}
  `;

  element("avancer")?.addEventListener("click", () => agir("avancer",
    { detail: element("detail-action").value }));
  element("classer")?.addEventListener("click", () => {
    const motif = prompt("Pourquoi ce dossier est-il classé sans suite ?");
    if (motif !== null) agir("classer", { motif });
  });
}

async function agir(action, corps) {
  try {
    await appel(`/api/nuisances/${choisi}/${action}`, { methode: "POST", json: corps });
    await rafraichir();
  } catch (e) {
    alert(e.message);
  }
}

/* ------------------------------------------------------------------ démarrage */
fetch("/api/session")
  .then((r) => (r.ok ? r.json() : Promise.reject()))
  .then(ouvrirLePoste)
  .catch(montrerConnexion);
