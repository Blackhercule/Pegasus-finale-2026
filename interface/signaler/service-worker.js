/* Garde la page utilisable sans réseau : les fichiers sont mis de côté à la première visite. */
"use strict";
const CACHE = "signaler-v1";
const FICHIERS = ["/signaler/", "/signaler/index.html", "/signaler/style.css",
                  "/signaler/signaler.js", "/signaler/manifeste.webmanifest"];

self.addEventListener("install", (evenement) => {
  evenement.waitUntil(caches.open(CACHE).then((c) => c.addAll(FICHIERS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evenement) => {
  evenement.waitUntil(caches.keys()
    .then((noms) => Promise.all(noms.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (evenement) => {
  const requete = evenement.request;
  // Les envois de signalements ne passent jamais par la réserve : ils doivent atteindre le serveur.
  if (requete.method !== "GET" || new URL(requete.url).pathname.startsWith("/api/")) return;
  evenement.respondWith(
    fetch(requete)
      .then((reponse) => {
        const copie = reponse.clone();
        caches.open(CACHE).then((c) => c.put(requete, copie)).catch(() => {});
        return reponse;
      })
      .catch(() => caches.match(requete).then((r) => r || caches.match("/signaler/index.html"))));
});
