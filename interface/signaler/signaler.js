/* Signalement d'un dépotoir depuis un téléphone.

   Deux exigences guident ce fichier :
   - ça doit marcher sans réseau (le signalement attend dans le téléphone et part tout seul) ;
   - aucune donnée personnelle : l'appareil se donne un pseudonyme tiré au hasard, rien d'autre. */
"use strict";

const ATTENTE = "signalements-en-attente";
const PSEUDO = "pseudonyme-appareil";

const element = (id) => document.getElementById(id);
const stockage = {
  lire(cle, defaut) {
    try { return JSON.parse(localStorage.getItem(cle)) ?? defaut; } catch { return defaut; }
  },
  ecrire(cle, valeur) {
    try { localStorage.setItem(cle, JSON.stringify(valeur)); } catch { /* navigation privée : tant pis */ }
  },
};

/* Pseudonyme de l'appareil : un identifiant au hasard, jamais un nom ni un numéro. */
function pseudonyme() {
  let nom = stockage.lire(PSEUDO, null);
  if (!nom) {
    const hasard = crypto.getRandomValues(new Uint8Array(8));
    nom = "appareil-" + Array.from(hasard, (o) => o.toString(16).padStart(2, "0")).join("");
    stockage.ecrire(PSEUDO, nom);
  }
  return nom;
}

/* ------------------------------------------------------------------ position */
let position = null;
let surveillance = null;

function afficherPosition() {
  const p = element("position");
  if (!position) { p.className = "position absente"; p.textContent = "Position inconnue : sortez à l'air libre, puis relancez."; return; }
  const precision = Math.round(position.precision_m);
  const bonne = precision <= 30;
  p.className = "position " + (bonne ? "bonne" : "faible");
  p.textContent = `Position ${bonne ? "bonne" : "approximative"} · précision ${precision} m`
    + ` (${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)})`;
}

function localiser() {
  const p = element("position");
  if (!navigator.geolocation) { p.className = "position absente"; p.textContent = "Ce téléphone ne donne pas sa position."; return; }
  p.className = "position"; p.textContent = "Recherche de votre position…";
  if (surveillance !== null) navigator.geolocation.clearWatch(surveillance);
  surveillance = navigator.geolocation.watchPosition(
    (brut) => {
      position = { latitude: brut.coords.latitude, longitude: brut.coords.longitude,
                   precision_m: brut.coords.accuracy };
      afficherPosition();
    },
    (erreur) => {
      position = null;
      p.className = "position absente";
      p.textContent = erreur.code === erreur.PERMISSION_DENIED
        ? "Localisation refusée : autorisez-la pour ce site, puis relancez."
        : "Position introuvable pour l'instant.";
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 10000 });
}

/* ------------------------------------------------------------------ photo */
let photo = null;

/* Une photo de téléphone pèse plusieurs mégaoctets : on la réduit avant l'envoi,
   sinon rien ne part en bord de réseau faible. */
function reduire(fichier, cote = 1280, qualite = 0.7) {
  return new Promise((resoudre, rejeter) => {
    const lecteur = new FileReader();
    lecteur.onerror = () => rejeter(new Error("Photo illisible"));
    lecteur.onload = () => {
      const image = new Image();
      image.onerror = () => rejeter(new Error("Photo illisible"));
      image.onload = () => {
        const facteur = Math.min(1, cote / Math.max(image.width, image.height));
        const toile = document.createElement("canvas");
        toile.width = Math.round(image.width * facteur);
        toile.height = Math.round(image.height * facteur);
        toile.getContext("2d").drawImage(image, 0, 0, toile.width, toile.height);
        toile.toBlob((b) => (b ? resoudre(b) : rejeter(new Error("Photo illisible"))), "image/jpeg", qualite);
      };
      image.src = lecteur.result;
    };
    lecteur.readAsDataURL(fichier);
  });
}

element("photo").addEventListener("change", async (evenement) => {
  const fichier = evenement.target.files[0];
  if (!fichier) return;
  try {
    photo = await reduire(fichier);
    const apercu = element("apercu");
    apercu.src = URL.createObjectURL(photo);
    apercu.hidden = false;
  } catch {
    photo = null;
    afficher("La photo n'a pas pu être lue. Vous pouvez envoyer sans photo.", "erreur");
  }
});

/* ------------------------------------------------------------------ choix (taille, type) */
function groupeDeChoix(id) {
  const groupe = element(id);
  groupe.addEventListener("click", (evenement) => {
    const bouton = evenement.target.closest("button");
    if (!bouton) return;
    groupe.querySelectorAll("button").forEach((b) => b.classList.toggle("actif", b === bouton));
  });
  return () => groupe.querySelector("button.actif").dataset.valeur;
}
const tailleChoisie = groupeDeChoix("taille");
const typeChoisi = groupeDeChoix("type");

/* ------------------------------------------------------------------ envoi */
function afficher(texte, genre) {
  const m = element("message");
  m.textContent = texte;
  m.className = "message " + genre;
  m.hidden = false;
}

function identifiantUnique() {
  return pseudonyme() + "-" + Date.now().toString(36) + "-"
    + crypto.getRandomValues(new Uint32Array(1))[0].toString(36);
}

async function envoyer(signalement) {
  const corps = new FormData();
  Object.entries(signalement.champs).forEach(([cle, valeur]) => corps.append(cle, valeur));
  if (signalement.photo) corps.append("photo", signalement.photo, "photo.jpg");
  const reponse = await fetch("/api/signalements", { method: "POST", body: corps });
  if (!reponse.ok) throw new Error("Le serveur a répondu " + reponse.status);
  return reponse.json();
}

function mettreEnAttente(signalement) {
  const file = stockage.lire(ATTENTE, []);
  file.push(signalement);
  stockage.ecrire(ATTENTE, file);
  afficherAttente();
}

function afficherAttente() {
  const file = stockage.lire(ATTENTE, []);
  element("bloc-attente").hidden = file.length === 0;
  element("attente").textContent = file.length === 1
    ? "1 signalement attend le réseau."
    : `${file.length} signalements attendent le réseau.`;
}

/* Les signalements gardés dans le téléphone repartent dès que le réseau revient.
   La photo n'est pas conservée dans l'attente : seules les informations essentielles le sont. */
let videEnCours = false;

async function viderLAttente() {
  // Le retour du réseau peut déclencher deux appels à la suite : sans ce verrou, le même
  // signalement partirait deux fois.
  if (videEnCours) return;
  const file = stockage.lire(ATTENTE, []);
  if (!file.length) return;
  videEnCours = true;
  const restants = [];
  for (const signalement of file) {
    try { await envoyer(signalement); } catch { restants.push(signalement); }
  }
  videEnCours = false;
  stockage.ecrire(ATTENTE, restants);
  afficherAttente();
  if (restants.length < file.length) {
    afficher(`${file.length - restants.length} signalement(s) en attente envoyé(s).`, "succes");
  }
}

element("formulaire").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  if (!position) { afficher("Position inconnue : impossible d'enregistrer le dépotoir.", "erreur"); return; }
  const bouton = element("envoyer");
  bouton.disabled = true;
  const signalement = {
    champs: {
      id_client: identifiantUnique(),
      latitude: position.latitude, longitude: position.longitude,
      precision_m: Math.round(position.precision_m),
      date_observation: new Date().toISOString(),
      taille: tailleChoisie(), type: typeChoisi(),
      commentaire: element("commentaire").value, source: pseudonyme(),
    },
    photo: null,
  };
  try {
    const resultat = await envoyer({ ...signalement, photo });
    afficher(resultat.statut === "rejete"
      ? "Signalement enregistré mais écarté : " + (resultat.motifs || []).join(", ")
      : "Signalement enregistré. Merci !", resultat.statut === "rejete" ? "erreur" : "succes");
  } catch {
    mettreEnAttente(signalement);          // sans réseau : il partira tout seul
    afficher("Pas de réseau : le signalement est gardé et partira automatiquement.", "attente");
  } finally {
    bouton.disabled = false;
    element("commentaire").value = "";
    photo = null;
    element("apercu").hidden = true;
  }
});

/* ------------------------------------------------------------------ réseau et démarrage */
function etatDuReseau() {
  const r = element("reseau");
  const enLigne = navigator.onLine;
  r.className = "reseau" + (enLigne ? "" : " hors-ligne");
  r.textContent = enLigne ? "Connecté au serveur de la mairie" : "Hors ligne : les signalements seront gardés";
  if (enLigne) viderLAttente().catch(() => {});
}

element("relancer-position").addEventListener("click", localiser);
element("envoyer-attente").addEventListener("click", () => viderLAttente().catch(() => {}));
window.addEventListener("online", etatDuReseau);
window.addEventListener("offline", etatDuReseau);

pseudonyme();
localiser();
etatDuReseau();
afficherAttente();
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/signaler/service-worker.js").catch(() => {});
}
