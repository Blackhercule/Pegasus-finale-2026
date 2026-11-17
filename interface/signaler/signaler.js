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
const AUDIOS = ["bienvenue", "nature", "position", "taille", "depot", "ampleur",
                "gravite", "photo", "vocal", "identite", "merci"];
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
  if (position && position.lieu) {
    // T16 : position tirée d'un lieu connu. On le dit, avec sa précision honnête.
    p.className = "position faible";
    p.textContent = `Position approximative : près de « ${position.lieu.nom} » (± ${PRECISION_LIEU_M} m)`;
    return;
  }
  if (!position) { p.className = "position absente"; p.textContent = "Position inconnue : sortez à l'air libre, puis relancez."; return; }
  const precision = Math.round(position.precision_m);
  const bonne = precision <= 30;
  p.className = "position " + (bonne ? "bonne" : "faible");
  p.textContent = `Position ${bonne ? "bonne" : "approximative"} · précision ${precision} m`
    + ` (${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)})`;
}

function localiser() {
  const p = element("position");
  position = null;                         // « Relancer » abandonne un lieu choisi

  if (!navigator.geolocation) {
    p.className = "position absente"; p.textContent = "Ce téléphone ne donne pas sa position.";
    ouvrirLeChoixDeLieu();
    return;
  }
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
      ouvrirLeChoixDeLieu();             // pas de position : on propose tout de suite un lieu
      p.className = "position absente";
      p.textContent = erreur.code === erreur.PERMISSION_DENIED
        ? "Localisation refusée : autorisez-la pour ce site, puis relancez."
        : "Position introuvable pour l'instant.";
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 10000 });
}

/* ------------------------------------------------------------------ lieu connu (T16)
   Quand la position ne marche pas (refusée, introuvable, téléphone ancien), l'habitant
   choisit un lieu connu dans une liste : marchés, écoles, universités, santé. La liste vient
   du serveur (/api/lieux) et le service worker la garde : la recherche marche hors ligne. */
const PRECISION_LIEU_M = 150;
let lieux = null;

/* « Marché de Gounghin » → « marche de gounghin » : on cherche sans accents ni majuscules. */
function sansAccents(texte) {
  return texte.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

async function chargerLesLieux() {
  if (lieux) return lieux;
  try {
    const reponse = await fetch("/api/lieux");
    if (!reponse.ok) throw new Error();
    lieux = (await reponse.json()).map((l) => ({ ...l, cle: sansAccents(l.nom + " " + l.genre) }));
  } catch {
    lieux = null;
  }
  return lieux;
}

function ouvrirLeChoixDeLieu() {
  element("bloc-lieu").hidden = false;
  element("sans-gps").setAttribute("aria-expanded", "true");
  chargerLesLieux().then(chercherUnLieu);
}

/* Tous les mots tapés doivent se trouver dans le nom (ou le genre) : « marche gounghin »
   trouve « Marché de Gounghin ». On montre les huit premiers. */
function chercherUnLieu() {
  const liste = element("resultats-lieu");
  const mots = sansAccents(element("recherche-lieu").value).split(/\s+/).filter(Boolean);
  liste.replaceChildren();
  if (!lieux) {
    const vide = document.createElement("li");
    vide.textContent = "Liste des lieux indisponible : ouvrez la page une fois avec le réseau.";
    liste.append(vide);
    return;
  }
  if (!mots.length) return;
  const trouves = lieux.filter((l) => mots.every((mot) => l.cle.includes(mot))).slice(0, 8);
  if (!trouves.length) {
    const vide = document.createElement("li");
    vide.textContent = "Aucun lieu trouvé. Essayez un autre mot.";
    liste.append(vide);
  }
  for (const lieu of trouves) {
    const ligne = document.createElement("li");
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.setAttribute("aria-pressed", String(position?.lieu?.id === lieu.id));
    bouton.textContent = lieu.nom;          // texte, jamais HTML
    const genre = document.createElement("small");
    genre.textContent = lieu.genre;
    bouton.append(genre);
    bouton.addEventListener("click", () => choisirUnLieu(lieu));
    ligne.append(bouton);
    liste.append(ligne);
  }
}

function choisirUnLieu(lieu) {
  // Le GPS ne doit plus remplacer le lieu choisi par une position qu'il trouverait plus tard.
  if (surveillance !== null) { navigator.geolocation.clearWatch(surveillance); surveillance = null; }
  position = { latitude: lieu.latitude, longitude: lieu.longitude,
               precision_m: PRECISION_LIEU_M, lieu };
  afficherPosition();
  chercherUnLieu();
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
const ampleurChoisie = groupeDeChoix("ampleur");
const graviteChoisie = groupeDeChoix("gravite");
const natureChoisie = groupeDeChoix("nature");

/* Ce qui change d'une nature à l'autre : le titre de la photo, et les mots des trois niveaux
   de gravité. « Un peu bouché » et « un seau d'eau » décrivent la même graduation, mais
   personne ne dirait l'un pour l'autre : les mots doivent être ceux de la chose signalée.
   Le texte « pourquoi » dit à l'habitant pourquoi son signalement compte. */
const PAR_NATURE = {
  ordures: { photo: "Photo du tas" },
  fuite_eau: { photo: "Photo de la fuite" },
  caniveau_bouche: {
    photo: "Photo du caniveau",
    titre: "Le caniveau est bouché comment ?",
    niveaux: ["Un peu bouché", "L'eau ne passe plus", "Ça déborde dans la rue"],
    pourquoi: "Un caniveau bouché renvoie l'eau dans les cours dès la première pluie, "
              + "et l'eau qui stagne élève les moustiques.",
  },
  toilettes_plein_air: {
    photo: "Photo du déversement",
    titre: "Il y en a combien ?",
    niveaux: ["Une flaque", "Ça coule dans la rue", "Toute la rue est touchée"],
    pourquoi: "Des matières de vidange répandues dans la rue, c'est le choléra et la fièvre "
              + "typhoïde à portée de pied nu.",
  },
  abattoir_clandestin: {
    photo: "Photo du lieu",
    titre: "C'est à quelle fréquence ?",
    niveaux: ["De temps en temps", "Plusieurs fois par semaine", "Tous les jours"],
    pourquoi: "Une bête abattue hors d'un abattoir n'est pas inspectée, et le sang et les "
              + "viscères restent sur place.",
  },
  eaux_usees_animales: {
    photo: "Photo du déversement",
    titre: "Il y en a combien ?",
    niveaux: ["Quelques seaux", "Un fût ou plus", "Ça coule en permanence"],
    pourquoi: "Les eaux de lavage des poissonneries et des poulaillers attirent les mouches "
              + "et empestent tout un quartier.",
  },
};

/* Un tas d'ordures et une fuite d'eau ne se décrivent pas pareil : on n'affiche que les
   étapes qui servent. Les autres sont retirées de la page, donc elles ne sont pas non plus
   comptées dans la numérotation des étapes (voir la feuille de style). */
function ajusterLesEtapes() {
  const nature = natureChoisie();
  // Un bloc peut servir à plusieurs natures : data-pour en contient la liste.
  document.querySelectorAll("[data-pour]").forEach((bloc) => {
    bloc.hidden = !bloc.dataset.pour.split(" ").includes(nature);
  });
  const propre = PAR_NATURE[nature] || {};
  element("titre-photo").textContent = propre.photo || "Photo";
  if (propre.titre) element("titre-gravite").firstChild.textContent = propre.titre + " ";
  if (propre.niveaux) {
    element("gravite").querySelectorAll(".mot").forEach((mot, rang) => {
      mot.textContent = propre.niveaux[rang];
    });
  }
  element("pourquoi-nature").textContent = propre.pourquoi || "";
  element("commentaire").placeholder = nature === "ordures"
    ? "Ou écrivez ici : repère, rue, depuis quand…"
    : "Ou écrivez ici : la rue, le repère, depuis quand ça dure…";
  element("envoyer").textContent = nature === "ordures"
    ? "Enregistrer le signalement" : "Envoyer le signalement à la mairie";
}
element("nature").addEventListener("click", ajusterLesEtapes);

/* Superficie : on la montre pendant la saisie, pour que la personne voie ce qu'elle déclare. */
function majSuperficie() {
  const longueur = Number(element("longueur_m").value);
  const largeur = Number(element("largeur_m").value);
  element("superficie").textContent = (longueur > 0 && largeur > 0)
    ? `Superficie estimée : ${Math.round(longueur * largeur)} m²` : "";
}
["longueur_m", "largeur_m"].forEach((id) =>
  element(id).addEventListener("input", majSuperficie));

/* ------------------------------------------------------------------ écrans d'accueil parlés

   Quatre écrans s'enchaînent à l'ouverture de la page. Chacun fait entendre un message en
   mooré, et « Continuer » passe au suivant ; après le quatrième, le formulaire s'affiche.
   « Passer le guidage » ouvre le formulaire tout de suite.

   Pour changer un titre, un texte ou un fichier, il n'y a que cette liste à modifier : les
   écrans se fabriquent à partir d'elle. Les fichiers sont dans /signaler/audio/moore/.

   Le nombre d'écrans suit les enregistrements RÉELLEMENT présents : au chargement, on demande
   au serveur lesquels existent et on ne garde que ceux-là. Un message pas encore enregistré ne
   fabrique donc pas un écran muet, et le jour où on l'ajoute, son écran apparaît tout seul,
   sans toucher au code. Si aucun n'est là, on va droit au formulaire : jamais d'écran qui
   empêche quelqu'un de signaler. */
const ACCUEIL_PREVUS = [
  { fichier: "accueil-1.mp3", titre: "Bienvenue",
    texte: "Bienvenue sur la plateforme d'assainissement de Ouagadougou." },
  { fichier: "accueil-2.mp3", titre: "Ce que vous pouvez signaler",
    texte: "Un tas d'ordures, ou une fuite d'eau sur une conduite." },
  { fichier: "accueil-3.mp3", titre: "Comment faire",
    texte: "Touchez les grandes images, ou parlez : vous n'avez rien à écrire." },
  { fichier: "accueil-4.mp3", titre: "Votre nom n'est pas obligatoire",
    texte: "Vous pouvez signaler sans donner votre nom ni votre numéro." },
];

let ACCUEIL = ACCUEIL_PREVUS;      // remplacé au chargement par ceux qui existent vraiment
let rangAccueil = 0;
let sonAccueil = null;

/* Demande au serveur quels enregistrements existent. En tête (HEAD) : on ne télécharge pas le
   son, on demande seulement s'il est là. Hors ligne, le service worker répond depuis son cache
   pour ceux qu'il a déjà ; les autres sont simplement écartés. */
async function accueilsDisponibles() {
  const presents = await Promise.all(ACCUEIL_PREVUS.map(async (ecran) => {
    const adresse = "/signaler/audio/moore/" + ecran.fichier;
    try {
      const r = await fetch(adresse, { method: "HEAD" });
      if (r.ok) return ecran;
    } catch {
      // Pas de réseau : on regarde dans la réserve du service worker. Sans cela, l'accueil
      // parlé disparaîtrait hors ligne, c'est-à-dire là où il est le plus utile.
    }
    try {
      return (await caches.match(adresse)) ? ecran : null;
    } catch {
      return null;
    }
  }));
  return presents.filter(Boolean);
}

function arreterLAccueil() {
  if (sonAccueil) { sonAccueil.pause(); sonAccueil = null; }
}

/* Joue le message de l'écran courant. `automatique` distingue la lecture lancée toute seule
   à l'arrivée sur l'écran de celle demandée par le bouton : un navigateur refuse la première
   tant que la personne n'a rien touché, et ce refus ne doit pas ressembler à une panne. */
function jouerLAccueil(automatique) {
  arreterLAccueil();
  const ecran = ACCUEIL[rangAccueil];
  const etat = element("accueil-etat");
  etat.textContent = "";
  const son = new Audio("/signaler/audio/moore/" + ecran.fichier);
  son.addEventListener("error", () => {
    sonAccueil = null;
    etat.textContent = "Message non enregistré pour l'instant.";
  });
  sonAccueil = son;
  son.play()
    .then(() => { etat.textContent = "Lecture en cours…"; })
    .catch(() => {
      sonAccueil = null;
      // Si le fichier manque, l'événement « error » a déjà écrit le vrai motif : on ne
      // l'écrase pas par un message qui ferait croire à un simple refus du navigateur.
      if (etat.textContent) return;
      etat.textContent = automatique ? "Touchez le haut-parleur pour écouter." : "";
    });
}

function afficherLAccueil(automatique) {
  const ecran = ACCUEIL[rangAccueil];
  element("accueil-progression").textContent =
    ACCUEIL.length > 1 ? `${rangAccueil + 1} sur ${ACCUEIL.length}` : "";
  element("accueil-numero").textContent = String(rangAccueil + 1);
  element("accueil-titre").textContent = ecran.titre;
  element("accueil-texte").textContent = ecran.texte;
  element("accueil-continuer").textContent =
    rangAccueil === ACCUEIL.length - 1 ? "Commencer le signalement" : "Continuer";
  element("accueil-ecouter-mot").textContent = "Écouter";
  jouerLAccueil(automatique);
}

function fermerLAccueil() {
  arreterLAccueil();
  element("accueil").hidden = true;
}

element("accueil-ecouter").addEventListener("click", () => jouerLAccueil(false));
element("accueil-passer").addEventListener("click", fermerLAccueil);
element("revoir-accueil").addEventListener("click", () => ouvrirLAccueil());
element("accueil-continuer").addEventListener("click", () => {
  rangAccueil += 1;
  if (rangAccueil >= ACCUEIL.length) { fermerLAccueil(); return; }
  afficherLAccueil(true);
});

async function ouvrirLAccueil() {
  ACCUEIL = await accueilsDisponibles();
  if (!ACCUEIL.length) { fermerLAccueil(); return; }   // rien d'enregistré : droit au formulaire
  rangAccueil = 0;
  element("accueil").hidden = false;
  afficherLAccueil(true);
}

/* ------------------------------------------------------------------ envoi */
function afficher(texte, genre) {
  const m = element("message");
  m.textContent = texte;
  m.className = "message " + genre;
  m.hidden = false;
}

/* Le repère donné à la main (« derrière le marché, côté nord ») part avec le commentaire. */
function commentaireAvecRepere() {
  const repere = position && position.lieu ? element("repere").value.trim() : "";
  const commentaire = element("commentaire").value;
  return repere ? `Repère : ${repere}. ${commentaire}`.trim() : commentaire;
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
  if (!position) { afficher("Position inconnue : impossible d'enregistrer le signalement.", "erreur"); return; }
  const bouton = element("envoyer");
  bouton.disabled = true;
  const nature = natureChoisie();
  const communs = {
    id_client: identifiantUnique(),
    nature,
    latitude: position.latitude, longitude: position.longitude,
    precision_m: Math.round(position.precision_m),
    // T16 : d'où vient la position. Le serveur reprend la position du lieu dans SA liste.
    source_position: position.lieu ? "lieu" : "gps",
    lieu_id: position.lieu ? position.lieu.id : "",
    date_observation: new Date().toISOString(),
    commentaire: commentaireAvecRepere(), source: pseudonyme(),
    declarant_nom: element("declarant_nom").value,
    declarant_telephone: element("declarant_telephone").value,
  };
  let propres;
  if (nature === "fuite_eau") {
    propres = { ampleur: ampleurChoisie(), quartier: element("quartier").value };
  } else if (nature === "ordures") {
    propres = { taille: tailleChoisie(), type: typeChoisi(), depot: depotChoisi(),
                longueur_m: element("longueur_m").value, largeur_m: element("largeur_m").value };
  } else {
    propres = { gravite: graviteChoisie(), quartier: element("quartier").value };
  }
  const signalement = { champs: { ...communs, ...propres }, photo: null };
  try {
    const resultat = await envoyer({ ...signalement, ...photos, message_vocal: messageVocal });
    if (resultat.statut !== "rejete") jouer("merci");
    const reussi = nature === "ordures"
      ? "Signalement enregistré. Merci !"
      : "Signalement enregistré. La mairie l'orientera vers le service compétent. Merci !";
    afficher(resultat.statut === "rejete"
      ? "Signalement enregistré mais écarté : " + (resultat.motifs || []).join(", ")
      : reussi, resultat.statut === "rejete" ? "erreur" : "succes");
  } catch {
    mettreEnAttente(signalement);          // sans réseau : il partira tout seul
    afficher("Pas de réseau : le signalement est gardé et partira automatiquement.", "attente");
  } finally {
    bouton.disabled = false;
    element("commentaire").value = "";
    element("repere").value = "";
    element("quartier").value = "";
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
element("sans-gps").addEventListener("click", ouvrirLeChoixDeLieu);
element("recherche-lieu").addEventListener("input", chercherUnLieu);

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
["nature", "taille", "depot", "ampleur", "gravite"].forEach((id) =>
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
ajusterLesEtapes();
ouvrirLAccueil();
localiser();
etatDuReseau();
afficherAttente();
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/signaler/service-worker.js").catch(() => {});
}
