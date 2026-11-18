/* Garde la page utilisable sans réseau : les fichiers sont mis de côté à la première visite. */
"use strict";
const CACHE = "signaler-v6";
const FICHIERS = ["/signaler/", "/accueil/images/brigade-verte.jpg", "/accueil/images/nettoyage-rue.jpg", "/signaler/index.html", "/signaler/style.css",
                  "/signaler/signaler.js", "/signaler/appel.js", "/signaler/manifeste.webmanifest",
                  // T16 : la liste des lieux connus, pour choisir un lieu même hors ligne.
                  "/api/lieux"];

/* Les messages parlés de l'accueil. Ils sont mis de côté UN PAR UN et non avec le reste :
   tous ne sont pas encore enregistrés, et avec addAll un seul fichier manquant ferait échouer
   toute l'installation du service worker — la page entière cesserait de marcher hors ligne. */
const AUDIOS = ["/signaler/audio/moore/accueil-1.mp3", "/signaler/audio/moore/accueil-2.mp3",
                "/signaler/audio/moore/accueil-3.mp3", "/signaler/audio/moore/accueil-4.mp3",
                "/signaler/audio/moore/menu.mp3"];

self.addEventListener("install", (evenement) => {
  evenement.waitUntil(caches.open(CACHE)
    .then((c) => c.addAll(FICHIERS)
      .then(() => Promise.all(AUDIOS.map((a) => c.add(a).catch(() => {})))))
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(caches.keys()
    .then((noms) => Promise.all(noms.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (evenement) => {
  const requete = evenement.request;
  // Les envois de signalements ne passent jamais par la réserve : ils doivent atteindre le serveur.
  const chemin = new URL(requete.url).pathname;
  // Seule adresse d'API gardée : la liste des lieux (données publiques, jamais un signalement).
  if (requete.method !== "GET" || (chemin.startsWith("/api/") && chemin !== "/api/lieux")) return;
  evenement.respondWith(
    fetch(requete)
      .then((reponse) => {
        const copie = reponse.clone();
        caches.open(CACHE).then((c) => c.put(requete, copie)).catch(() => {});
        return reponse;
      })
      .catch(() => caches.match(requete).then((r) => r || caches.match("/signaler/index.html"))));
});
