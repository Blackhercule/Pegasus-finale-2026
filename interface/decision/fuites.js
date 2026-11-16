/* Poste de travail des fuites d'eau. Deux postes s'y relaient : la mairie confirme la fuite et
   la transmet à l'ONEA, l'ONEA déclare la réparation. Même principe que les dépotoirs : on ne
   voit que ce qui attend son poste, et tout passage est daté et signé. */
"use strict";

const element = (id) => document.getElementById(id);
let session = null;        // { agent, poste, poste_nom, jeton }
let chaine = null;         // les étapes, telles que le serveur les décrit
let filtre = "pour_moi";
let choisie = null;

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

/* Combien de temps l'eau coule déjà : c'est ce qui décide de l'urgence, bien plus que la date. */
function depuis(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const heures = Math.max(0, Math.round((Date.now() - d.getTime()) / 3600000));
  if (heures < 24) return `${heures} h`;
  return `${Math.round(heures / 24)} jour(s)`;
}

const AMPLEURS = { suintement: "suintement", jet: "jet d'eau", inondation: "inondation" };

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
  const ordre = ["signale", "transmis", "repare", "classe"];
  const qui = { mairie: "Mairie", onea: "ONEA" };
  element("chaine").innerHTML = ordre.map((cle) => {
    const etape = chaine.etapes[cle];
    const aMoi = etape.poste === session.poste;
    const clos = etape.poste === null;
    return `<li class="${aMoi ? "mon-poste" : ""} ${clos ? "close" : ""}" title="${echapper(etape.explication)}">
      <span class="nombre">${comptes[cle] ?? 0}</span>
      <span class="nom">${echapper(etape.nom)}</span>
      <span class="qui">${etape.poste ? echapper(qui[etape.poste] || etape.poste) : "dossier clos"}</span>
    </li>`;
  }).join("");
}

/* ------------------------------------------------------------------ liste */
async function rafraichir() {
  chaine = await appel("/api/fuites/chaine");
  afficherLaChaine(chaine.comptes);
  const fuites = await appel("/api/fuites" + (filtre === "pour_moi" ? "?pour_moi=1" : ""));
  element("titre-liste").textContent = filtre === "pour_moi"
    ? "Fuites qui m'attendent" : "Toutes les fuites";
  element("lignes").innerHTML = fuites.length ? fuites.map((f) => `
    <tr data-id="${f.id}" class="${choisie === f.id ? "choisi" : ""}">
      <td>
        <div class="ligne-titre">FUITE-${String(f.id).padStart(5, "0")} ·
          ${echapper(f.quartier || "quartier non précisé")}</div>
        <div class="ligne-detail">${echapper(AMPLEURS[f.ampleur] || "ampleur non précisée")}
          · ${echapper(f.etape_nom)} · coule depuis ${depuis(f.premier_vu)}
          · ${f.nb_signalements} signalement(s)</div>
      </td>
    </tr>`).join("")
    : `<tr><td class="vide">${filtre === "pour_moi"
        ? "Aucune fuite n'attend votre poste." : "Aucune fuite signalée pour l'instant."}</td></tr>`;
  if (choisie) afficherFuite(choisie).catch(() => {});
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
  choisie = Number(ligne.dataset.id);
  element("lignes").querySelectorAll("tr").forEach((l) => l.classList.toggle("choisi", l === ligne));
  afficherFuite(choisie).catch((e) => alert(e.message));
});

/* ------------------------------------------------------------------ détail */
async function afficherFuite(identifiant) {
  const f = await appel("/api/fuites/" + identifiant);
  const etape = chaine.etapes[f.etape];
  const aMoi = etape.poste === session.poste;

  const photos = f.signalements.filter((s) => s.photo).map((s) =>
    `<figure><img src="/api/fichiers/${encodeURI(s.photo)}" alt="Photo de la fuite">
       <figcaption>${dateCourte(s.date_observation)}</figcaption></figure>`).join("");
  const voix = f.signalements.filter((s) => s.message_vocal).map((s) =>
    `<audio controls src="/api/fichiers/${encodeURI(s.message_vocal)}"></audio>`).join("");

  const temoins = f.signalements.filter((s) => s.declarant_nom || s.declarant_telephone);
  const blocTemoins = temoins.length ? `
    <div class="prive">
      <h3>Déclarant joignable</h3>
      <p class="avertissement">Renseignements facultatifs, donnés volontairement. Utiles si
        l'équipe de l'ONEA ne retrouve pas la fuite sur place.</p>
      ${temoins.map((s) => `
        <dl>
          <dt>Nom</dt><dd>${echapper(s.declarant_nom || "—")}</dd>
          <dt>Téléphone</dt><dd>${echapper(s.declarant_telephone || "—")}</dd>
        </dl>`).join("")}
    </div>` : "";

  const action = etape.suivante === "transmis"
    ? `<input id="detail-action" maxlength="60" placeholder="N° du bordereau ou de l'appel à l'ONEA (facultatif)">`
    : `<textarea id="detail-action" rows="2" maxlength="500"
                 placeholder="Ce qui a été fait sur place (facultatif)"></textarea>`;

  element("detail").innerHTML = `
    <h2>FUITE-${String(f.id).padStart(5, "0")} — ${echapper(f.etape_nom)}</h2>
    <p class="aide">${echapper(etape.explication)}</p>
    <dl>
      <dt>Ampleur</dt><dd>${echapper(f.ampleur_nom)}</dd>
      <dt>Quartier</dt><dd>${echapper(f.quartier || "non précisé")}</dd>
      <dt>L'eau coule depuis</dt><dd>${depuis(f.premier_vu)} (premier signalement le ${dateCourte(f.premier_vu)})</dd>
      <dt>Signalements</dt><dd>${f.nb_signalements}, de ${f.nb_sources} source(s)</dd>
      <dt>Position</dt><dd>${Number(f.latitude).toFixed(5)}, ${Number(f.longitude).toFixed(5)}</dd>
      <dt>Référence ONEA</dt><dd>${echapper(f.reference_onea || "pas encore transmise")}</dd>
    </dl>
    ${avertissementLieu(f.signalements)}
    ${photos ? `<div class="vignettes">${photos}</div>` : ""}
    ${voix ? `<h3 class="aide">Message vocal du déclarant</h3>${voix}` : ""}
    ${blocTemoins}
    <h3 class="aide">Qui a fait quoi</h3>
    <ul class="journal">${f.journal.length ? f.journal.map((e) => `
      <li><span class="quand">${dateCourte(e.date)}</span> —
        <span class="qui">${echapper(e.auteur)}</span>
        : ${echapper(chaine.etapes[e.etape]?.nom || e.etape)}${e.detail ? " — " + echapper(e.detail) : ""}</li>`).join("")
      : "<li>Rien encore : la fuite vient d'être signalée.</li>"}</ul>
    ${aMoi ? `
      <div class="actions-dossier">
        ${action}
        <div class="ligne">
          <button type="button" id="avancer">${echapper(etape.action)}</button>
          ${session.poste === "mairie" ? `<button type="button" class="rejeter secondaire" id="classer">
            Classer sans suite</button>` : ""}
        </div>
      </div>` : `<p class="aide">Cette fuite attend le poste « ${
        echapper(etape.poste === "onea" ? "ONEA" : etape.poste || "—")} ».</p>`}
  `;

  element("avancer")?.addEventListener("click", () => agir("avancer",
    { detail: element("detail-action").value }));
  element("classer")?.addEventListener("click", () => {
    const motif = prompt("Pourquoi cette fuite est-elle classée sans suite ?");
    if (motif !== null) agir("classer", { motif });
  });
}

async function agir(action, corps) {
  try {
    await appel(`/api/fuites/${choisie}/${action}`, { methode: "POST", json: corps });
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
