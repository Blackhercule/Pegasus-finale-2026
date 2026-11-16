/* Poste de travail : chaque agent ne voit que les dossiers qui l'attendent, et ne peut faire
   avancer que ce qui relève de son poste. Tout passage est daté et signé. */
"use strict";

const element = (id) => document.getElementById(id);
let session = null;        // { agent, poste, poste_nom, jeton }
let chaine = null;         // les étapes, telles que le serveur les décrit
let filtre = "pour_moi";
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

function dateCourte(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—"
    : d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const nombre = (v, d = 0) => (v == null ? "—"
  : Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }));

const DEPOTS = { plein_air: "à même le sol", bac: "dans un bac", caniveau: "dans un caniveau",
                 fosse: "dans une fosse", berge: "sur une berge", autre: "autre" };
const TYPES = { menager: "ménagers", gravats: "gravats", mixte: "mélangés", autre: "autre" };

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
  element("titre-poste").textContent = "Poste de travail";
}

async function ouvrirLePoste(info) {
  session = info;
  element("connexion").hidden = true;
  element("travail").hidden = false;
  element("deconnexion").hidden = false;
  element("session").textContent = info.agent;
  element("titre-poste").textContent = info.poste_nom || "Poste de travail";
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
  const ordre = ["signale", "confirme", "constat", "a_collecter", "collecte", "classe"];
  element("chaine").innerHTML = ordre.map((cle) => {
    const etape = chaine.etapes[cle];
    const aMoi = etape.poste === session.poste;
    const clos = etape.poste === null;
    return `<li class="${aMoi ? "mon-poste" : ""} ${clos ? "close" : ""}" title="${echapper(etape.explication)}">
      <span class="nombre">${comptes[cle] ?? 0}</span>
      <span class="nom">${echapper(etape.nom)}</span>
      <span class="qui">${etape.poste ? echapper(chaine.postes[etape.poste].split(" — ")[0]) : "dossier clos"}</span>
    </li>`;
  }).join("");
}

/* ------------------------------------------------------------------ liste */
async function rafraichir() {
  const info = await appel("/api/chaine");
  chaine = info;
  afficherLaChaine(info.comptes);
  const dossiers = await appel("/api/dossiers" + (filtre === "pour_moi" ? "?pour_moi=1" : ""));
  element("titre-liste").textContent = filtre === "pour_moi"
    ? "Dossiers qui m'attendent" : "Tous les dossiers";
  element("lignes").innerHTML = dossiers.length ? dossiers.map((d) => `
    <tr data-id="${d.id}" class="${choisi === d.id ? "choisi" : ""}">
      <td>
        <div class="ligne-titre">Dossier ${d.id} · ${nombre(d.volume_m3, 1)} m³${
          d.surface_m2 ? " · " + nombre(d.surface_m2) + " m²" : ""}</div>
        <div class="ligne-detail">${echapper(d.etape_nom)} · ${d.nb_signalements} signalement(s)
          · vu le ${dateCourte(d.premier_vu)}${d.depot ? " · " + DEPOTS[d.depot] : ""}</div>
      </td>
    </tr>`).join("")
    : `<tr><td class="vide">${filtre === "pour_moi"
        ? "Aucun dossier n'attend votre poste." : "Aucun dossier pour l'instant."}</td></tr>`;
  if (choisi) afficherDossier(choisi).catch(() => {});
}

element("filtres").addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("button");
  if (!bouton) return;
  filtre = bouton.dataset.filtre;
  element("filtres").querySelectorAll("button").forEach((b) => b.classList.toggle("actif", b === bouton));
  rafraichir().catch((e) => alert(e.message));
});

element("lignes").addEventListener("click", (evenement) => {
  const ligne = evenement.target.closest("tr[data-id]");
  if (!ligne) return;
  choisi = Number(ligne.dataset.id);
  element("lignes").querySelectorAll("tr").forEach((l) => l.classList.toggle("choisi", l === ligne));
  afficherDossier(choisi).catch((e) => alert(e.message));
});

/* ------------------------------------------------------------------ détail */
async function afficherDossier(identifiant) {
  const d = await appel("/api/dossiers/" + identifiant);
  const etape = chaine.etapes[d.etape];
  const aMoi = etape.poste === session.poste;

  const photos = d.signalements.filter((s) => s.photo).map((s) =>
    `<figure><img src="/api/fichiers/${encodeURI(s.photo)}" alt="Photo du dépotoir">
       <figcaption>${dateCourte(s.date_observation)}</figcaption></figure>`).join("");
  const voix = d.signalements.filter((s) => s.message_vocal).map((s) =>
    `<audio controls src="/api/fichiers/${encodeURI(s.message_vocal)}"></audio>`).join("");

  const temoins = d.signalements.filter((s) => s.declarant_nom || s.photo_cnib || s.declarant_telephone);
  const blocTemoins = temoins.length ? `
    <div class="prive">
      <h3>Déclarant qui accepte d'être témoin</h3>
      <p class="avertissement">Renseignements facultatifs, donnés volontairement. À effacer dès
        la clôture du dossier.</p>
      ${temoins.map((s) => `
        <dl>
          <dt>Nom</dt><dd>${echapper(s.declarant_nom || "—")}</dd>
          <dt>Téléphone</dt><dd>${echapper(s.declarant_telephone || "—")}</dd>
        </dl>
        <div class="vignettes">
          ${s.photo_cnib ? `<figure><img src="/api/fichiers/${encodeURI(s.photo_cnib)}" alt="CNIB">
             <figcaption>CNIB</figcaption></figure>` : ""}
          ${s.photo_visage ? `<figure><img src="/api/fichiers/${encodeURI(s.photo_visage)}" alt="Portrait">
             <figcaption>Portrait</figcaption></figure>` : ""}
        </div>`).join("")}
      ${session.poste === "mairie" ? `<button type="button" class="secondaire" id="effacer-identites">
        Effacer les pièces d'identité</button>` : ""}
    </div>` : "";

  const premier = d.signalements[0] || {};
  element("detail").innerHTML = `
    <h2>Dossier ${d.id} — ${echapper(d.etape_nom)}</h2>
    <p class="aide">${echapper(etape.explication)}</p>
    <dl>
      <dt>Volume estimé</dt><dd>${nombre(d.volume_m3, 1)} m³</dd>
      <dt>Superficie</dt><dd>${d.surface_m2 ? nombre(d.surface_m2) + " m²" : "non mesurée"}</dd>
      <dt>Dépôt</dt><dd>${d.depot ? DEPOTS[d.depot] : "non précisé"}</dd>
      <dt>Déchets</dt><dd>${TYPES[premier.type] || "non précisé"}</dd>
      <dt>Signalé depuis</dt><dd>le ${dateCourte(d.premier_vu)} (dernier signalement le ${dateCourte(d.dernier_vu)})</dd>
      <dt>Signalements</dt><dd>${d.nb_signalements}, de ${d.nb_sources} source(s)</dd>
      <dt>Position</dt><dd>${Number(d.latitude).toFixed(5)}, ${Number(d.longitude).toFixed(5)}</dd>
    </dl>
    ${avertissementLieu(d.signalements)}
    ${photos ? `<div class="vignettes">${photos}</div>` : ""}
    ${voix ? `<h3 class="aide">Message vocal du déclarant</h3>${voix}` : ""}
    ${blocTemoins}
    <h3 class="aide">Qui a fait quoi</h3>
    <ul class="journal">${d.journal.length ? d.journal.map((e) => `
      <li><span class="quand">${dateCourte(e.date)}</span> —
        <span class="qui">${echapper(e.auteur)}</span> (${echapper(chaine.postes[e.poste]?.split(" — ")[0] || e.poste)})
        : ${echapper(chaine.etapes[e.etape]?.nom || e.etape)}${e.detail ? " — " + echapper(e.detail) : ""}</li>`).join("")
      : "<li>Rien encore : le dossier vient d'être ouvert par un signalement.</li>"}</ul>
    ${aMoi ? `
      <div class="actions-dossier">
        <textarea id="detail-action" rows="2" maxlength="500"
                  placeholder="Ce que vous avez constaté ou fait (facultatif)"></textarea>
        <div class="ligne">
          <button type="button" id="avancer">${echapper(etape.action)}</button>
          ${session.poste === "mairie" ? `<button type="button" class="rejeter secondaire" id="classer">
            Classer sans suite</button>` : ""}
        </div>
      </div>` : `<p class="aide">Ce dossier attend le poste « ${
        echapper(chaine.postes[etape.poste] || "—")} ».</p>`}
  `;

  element("avancer")?.addEventListener("click", () => agir("avancer",
    { detail: element("detail-action").value }));
  element("classer")?.addEventListener("click", () => {
    const motif = prompt("Pourquoi ce dossier est-il classé sans suite ?");
    if (motif !== null) agir("classer", { motif });
  });
  element("effacer-identites")?.addEventListener("click", async () => {
    if (!confirm("Effacer définitivement la CNIB, le portrait et le téléphone de ce dossier ?")) return;
    await appel(`/api/dossiers/${identifiant}/identites`, { methode: "DELETE" });
    await afficherDossier(identifiant);
  });
}

async function agir(action, corps) {
  try {
    await appel(`/api/dossiers/${choisi}/${action}`, { methode: "POST", json: corps });
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
