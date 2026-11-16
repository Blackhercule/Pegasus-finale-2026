/* Vérification des signalements par un agent de la mairie.

   Un signalement « à vérifier » attend une décision humaine ; un signalement écarté reste
   visible avec son motif. Rien n'est effacé : on voit toujours ce que le serveur a refusé
   et pourquoi (c'est ce qu'on montre au jury quand il injecte des signalements piégés). */
"use strict";

const element = (id) => document.getElementById(id);
let jeton = null;
let filtre = "a_verifier";

async function appel(adresse, options = {}) {
  const entetes = { ...(options.entetes || {}) };
  if (jeton) entetes["X-Jeton"] = jeton;
  if (options.json) entetes["Content-Type"] = "application/json";
  const reponse = await fetch(adresse, {
    method: options.methode || "GET",
    headers: entetes,
    body: options.json ? JSON.stringify(options.json) : options.corps,
  });
  if (reponse.status === 401) { montrerConnexion(); throw new Error("Connexion requise"); }
  const resultat = await reponse.json().catch(() => ({}));
  if (!reponse.ok) throw new Error(resultat.erreur || "Erreur " + reponse.status);
  return resultat;
}

function montrerConnexion() {
  jeton = null;
  element("connexion").hidden = false;
  element("travail").hidden = true;
  element("session").textContent = "";
}

function montrerTravail(nom) {
  element("connexion").hidden = true;
  element("travail").hidden = false;
  element("session").textContent = "Agent : " + nom;
  charger();
}

element("connexion").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  const erreur = element("erreur-connexion");
  erreur.hidden = true;
  try {
    const resultat = await appel("/api/connexion", {
      methode: "POST",
      json: { nom: element("nom").value, mot_de_passe: element("mot-de-passe").value },
    });
    jeton = resultat.jeton;
    montrerTravail(resultat.agent);
  } catch (e) {
    erreur.textContent = e.message;
    erreur.hidden = false;
  }
});

/* ------------------------------------------------------------------ tableau */
const ETATS = { verifie: "Vérifié", recevable: "Recevable", a_verifier: "À vérifier", rejete: "Écarté" };

function echapper(texte) {
  /* Un commentaire vient du terrain, ou d'un lot du jury : il peut contenir des balises.
     On l'insère comme du texte, jamais comme du HTML. */
  const noeud = document.createElement("span");
  noeud.textContent = texte == null ? "" : String(texte);
  return noeud.innerHTML;
}

function heure(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—"
    : d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function charger() {
  const adresse = "/api/signalements" + (filtre ? "?statut=" + filtre : "");
  const lignes = await appel(adresse);
  const corps = element("lignes");
  if (!lignes.length) {
    corps.innerHTML = '<tr><td colspan="7" class="vide">Aucun signalement dans cette catégorie.</td></tr>';
    return;
  }
  corps.innerHTML = lignes.map((s) => {
    const lieu = s.latitude == null ? "—"
      : `${Number(s.latitude).toFixed(5)}, ${Number(s.longitude).toFixed(5)}`;
    const motifs = s.motifs && s.motifs.length
      ? `<span class="motifs">${echapper(s.motifs.join(", "))}</span>` : "";
    const commentaire = s.commentaire
      ? `<span class="motifs" style="color:inherit">${echapper(s.commentaire)}</span>` : "";
    const decision = s.statut === "verifie" || s.statut === "rejete" ? ""
      : `<div class="decision">
           <button type="button" data-id="${s.id}" data-action="verifier">Vérifier</button>
           <button type="button" class="rejeter" data-id="${s.id}" data-action="rejeter">Écarter</button>
         </div>`;
    return `<tr class="${s.statut}">
      <td>${s.id}</td>
      <td>${heure(s.date_reception)}</td>
      <td>${lieu}${commentaire}</td>
      <td>${echapper(s.taille || "—")}</td>
      <td>${echapper(s.source)}</td>
      <td><span class="etat ${s.statut}">${ETATS[s.statut] || s.statut}</span>${motifs}</td>
      <td>${decision}</td>
    </tr>`;
  }).join("");
}

element("lignes").addEventListener("click", async (evenement) => {
  const bouton = evenement.target.closest("button[data-action]");
  if (!bouton) return;
  bouton.disabled = true;
  try {
    await appel(`/api/signalements/${bouton.dataset.id}/${bouton.dataset.action}`, { methode: "POST" });
    await charger();
  } catch (e) {
    bouton.disabled = false;
    alert(e.message);
  }
});

element("filtres").addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("button");
  if (!bouton) return;
  filtre = bouton.dataset.statut;
  element("filtres").querySelectorAll("button").forEach((b) => b.classList.toggle("actif", b === bouton));
  charger().catch(() => {});
});

/* ------------------------------------------------------------------ lot */
element("envoyer-lot").addEventListener("click", async () => {
  const champ = element("fichier-lot");
  const message = element("resultat-lot");
  if (!champ.files.length) { message.textContent = "Choisissez d'abord un fichier."; message.className = "message erreur"; message.hidden = false; return; }
  const corps = new FormData();
  corps.append("fichier", champ.files[0]);
  try {
    const resultat = await appel("/api/signalements/lot", { methode: "POST", corps });
    const detail = Object.entries(resultat.comptes)
      .map(([statut, n]) => `${n} ${ETATS[statut] || statut}`).join(" · ");
    message.textContent = `${resultat.recus} ligne(s) reçue(s) : ${detail || "aucune retenue"}.`;
    message.className = "message succes";
    message.hidden = false;
    await charger();
  } catch (e) {
    message.textContent = e.message;
    message.className = "message erreur";
    message.hidden = false;
  }
});

/* Au chargement : l'agent est peut-être déjà connecté, sa session dure. */
fetch("/api/session")
  .then((r) => (r.ok ? r.json() : Promise.reject()))
  .then((s) => { jeton = s.jeton; montrerTravail(s.agent); })
  .catch(montrerConnexion);
