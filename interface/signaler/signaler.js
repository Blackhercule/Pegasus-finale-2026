/* Signalement d'un dépotoir depuis un téléphone.

   Deux exigences guident ce fichier :
   - ça doit marcher sans réseau (le signalement attend dans le téléphone et part tout seul) ;
   - aucune donnée personnelle : l'appareil se donne un pseudonyme tiré au hasard, rien d'autre. */
"use strict";

const ATTENTE = "signalements-en-attente";
const PSEUDO = "pseudonyme-appareil";
const GUIDAGE = "guidage-moore";

/* Guidage parlé en mooré, pour qui ne lit pas le français. Ce sont de vrais enregistrements
   rangés dans /signaler/audio/moore/ : aucune synthèse vocale, donc rien à télécharger et une
   prononciation juste. Si un fichier manque, la page fonctionne comme avant, en silence. */
const AUDIOS = ["bienvenue", "position", "taille", "depot", "photo", "vocal", "identite", "merci"];
let guidageActif = false;
let lecture = null;

function jouer(nom, force = false) {
  if (!guidageActif && !force) return;
  if (!AUDIOS.includes(nom)) return;
  try {
    if (lecture) { lecture.pause(); lecture = null; }
    const son = new Audio(`/signaler/audio/moore/${nom}.mp3`);
    son.addEventListener("error", () => { lecture = null; });
    lecture = son;
    son.play().catch(() => { lecture = null; });
  } catch { /* un navigateur qui refuse de jouer un son ne doit rien casser */ }
}

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

/* ------------------------------------------------------------------ photos */
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

const photos = { photo: null, photo_cnib: null, photo_visage: null };

function brancherPhoto(champ, apercuId) {
  element(champ).addEventListener("change", async (evenement) => {
    const fichier = evenement.target.files[0];
    if (!fichier) return;
    try {
      photos[champ] = await reduire(fichier);
      const apercu = element(apercuId);
      apercu.src = URL.createObjectURL(photos[champ]);
      apercu.hidden = false;
      if (champ === "photo_cnib") jouer("identite");
    } catch {
      photos[champ] = null;
      afficher("La photo n'a pas pu être lue. Vous pouvez envoyer sans photo.", "erreur");
    }
  });
}
brancherPhoto("photo", "apercu");
brancherPhoto("photo_cnib", "apercu-cnib");
brancherPhoto("photo_visage", "apercu-visage");

/* ------------------------------------------------------------------ message vocal */
let enregistreur = null;
let morceaux = [];
let messageVocal = null;

async function basculerEnregistrement() {
  const bouton = element("enregistrer");
  if (enregistreur && enregistreur.state === "recording") {
    enregistreur.stop();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    element("etat-vocal").textContent = "Ce téléphone ne permet pas d'enregistrer la voix ici.";
    return;
  }
  try {
    const flux = await navigator.mediaDevices.getUserMedia({ audio: true });
    morceaux = [];
    enregistreur = new MediaRecorder(flux);
    enregistreur.addEventListener("dataavailable", (e) => { if (e.data.size) morceaux.push(e.data); });
    enregistreur.addEventListener("stop", () => {
      flux.getTracks().forEach((piste) => piste.stop());
      messageVocal = new Blob(morceaux, { type: enregistreur.mimeType || "audio/webm" });
      const ecoute = element("ecoute-vocal");
      ecoute.src = URL.createObjectURL(messageVocal);
      ecoute.hidden = false;
      bouton.classList.remove("enregistre");
      bouton.textContent = "Réenregistrer";
      element("etat-vocal").textContent = "Message enregistré. Vous pouvez le réécouter.";
    });
    enregistreur.start();
    bouton.classList.add("enregistre");
    bouton.textContent = "Appuyer pour arrêter";
    element("etat-vocal").textContent = "Enregistrement en cours… parlez.";
  } catch {
    element("etat-vocal").textContent = "Le microphone n'est pas autorisé pour ce site.";
  }
}
element("enregistrer").addEventListener("click", basculerEnregistrement);

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
const depotChoisi = groupeDeChoix("depot");

/* Superficie : on la montre pendant la saisie, pour que la personne voie ce qu'elle déclare. */
function majSuperficie() {
  const longueur = Number(element("longueur_m").value);
  const largeur = Number(element("largeur_m").value);
  element("superficie").textContent = (longueur > 0 && largeur > 0)
    ? `Superficie estimée : ${Math.round(longueur * largeur)} m²` : "";
}
["longueur_m", "largeur_m"].forEach((id) =>
  element(id).addEventListener("input", majSuperficie));

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
  Object.entries(signalement.champs).forEach(([cle, valeur]) => {
    if (valeur !== "" && valeur !== null && valeur !== undefined) corps.append(cle, valeur);
  });
  if (signalement.photo) corps.append("photo", signalement.photo, "photo.jpg");
  if (signalement.photo_cnib) corps.append("photo_cnib", signalement.photo_cnib, "cnib.jpg");
  if (signalement.photo_visage) corps.append("photo_visage", signalement.photo_visage, "visage.jpg");
  if (signalement.message_vocal) corps.append("message_vocal", signalement.message_vocal, "voix.webm");
  const reponse = await fetch("/api/signalements", { method: "POST", body: corps });
  if (!reponse.ok) throw new Error("Le serveur a répondu " + reponse.status);
  return reponse.json();
}

/* L'attente ne garde que les informations essentielles : ni photo, ni voix, ni pièce
   d'identité ne dorment dans le téléphone. */
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
      taille: tailleChoisie(), type: typeChoisi(), depot: depotChoisi(),
      longueur_m: element("longueur_m").value, largeur_m: element("largeur_m").value,
      commentaire: element("commentaire").value, source: pseudonyme(),
      declarant_nom: element("declarant_nom").value,
      declarant_telephone: element("declarant_telephone").value,
    },
    photo: null,
  };
  try {
    const resultat = await envoyer({ ...signalement, ...photos, message_vocal: messageVocal });
    if (resultat.statut !== "rejete") jouer("merci");
    afficher(resultat.statut === "rejete"
      ? "Signalement enregistré mais écarté : " + (resultat.motifs || []).join(", ")
      : "Signalement enregistré. Merci !", resultat.statut === "rejete" ? "erreur" : "succes");
  } catch {
    mettreEnAttente(signalement);          // sans réseau : il partira tout seul
    afficher("Pas de réseau : le signalement est gardé et partira automatiquement.", "attente");
  } finally {
    bouton.disabled = false;
    element("commentaire").value = "";
    Object.keys(photos).forEach((cle) => { photos[cle] = null; });
    messageVocal = null;
    ["apercu", "apercu-cnib", "apercu-visage", "ecoute-vocal"].forEach((id) => {
      element(id).hidden = true;
    });
    element("etat-vocal").textContent = "";
    element("enregistrer").textContent = "Appuyer pour parler";
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

element("relancer-position").addEventListener("click", () => { localiser(); jouer("position"); });

element("guidage").addEventListener("click", () => {
  guidageActif = !guidageActif;
  stockage.ecrire(GUIDAGE, guidageActif);
  element("guidage").setAttribute("aria-pressed", String(guidageActif));
  element("guidage").classList.toggle("actif", guidageActif);
  element("accueil-moore").hidden = !guidageActif;
  if (guidageActif) jouer("bienvenue", true);
  else if (lecture) { lecture.pause(); lecture = null; }
});

/* Chaque étape peut être réécoutée en touchant son haut-parleur, même sans le guidage. */
document.querySelectorAll(".parler").forEach((bouton) =>
  bouton.addEventListener("click", () => jouer(bouton.dataset.audio, true)));

/* Une étape que l'on commence se fait lire à voix haute, quand le guidage est allumé. */
["taille", "depot"].forEach((id) =>
  element(id).addEventListener("click", () => jouer(id)));
element("photo").addEventListener("click", () => jouer("photo"));
element("enregistrer").addEventListener("click", () => jouer("vocal"));
element("bloc-identite").addEventListener("toggle", () => {
  if (element("bloc-identite").open) jouer("identite");
});
element("envoyer-attente").addEventListener("click", () => viderLAttente().catch(() => {}));
window.addEventListener("online", etatDuReseau);
window.addEventListener("offline", etatDuReseau);

pseudonyme();
guidageActif = stockage.lire(GUIDAGE, false) === true;
element("guidage").setAttribute("aria-pressed", String(guidageActif));
element("guidage").classList.toggle("actif", guidageActif);
element("accueil-moore").hidden = !guidageActif;
localiser();
etatDuReseau();
afficherAttente();
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/signaler/service-worker.js").catch(() => {});
}
