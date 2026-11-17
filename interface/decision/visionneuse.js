/* Visionneuse de photos (T23, partie 1) : un clic sur la photo d'un signalement l'ouvre en
 * grand, plein écran sur fond sombre.
 *
 * Un seul fichier, branché sur toutes les pages d'agent qui montrent des photos. Il n'a pas
 * besoin que les pages le préviennent : il écoute les clics sur toute image dont l'adresse
 * commence par /api/fichiers/public/ — c'est là que le serveur range la photo du tas, déjà
 * masquée (T17). La CNIB et le portrait du déclarant sont rangés dans prive/ : ils ne sont donc
 * jamais concernés, et restent comme avant.
 *
 * Fermer : Échap, un clic à côté de la photo, ou le bouton ✕. Plusieurs photos dans la page :
 * ← et → (ou les deux boutons) passent de l'une à l'autre.
 */
"use strict";

(function () {
  const PREFIXE = "/api/fichiers/public/";
  let fond = null, image = null, legende = null, precedent = null, suivant = null, fermer = null;
  let photos = [], rang = 0, declencheur = null;

  function bouton(classe, texte, libelle, action) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "visionneuse__bouton " + classe;
    b.textContent = texte;
    b.setAttribute("aria-label", libelle);
    b.addEventListener("click", (e) => { e.stopPropagation(); action(); });
    return b;
  }

  function construire() {
    fond = document.createElement("div");
    fond.className = "visionneuse";
    fond.setAttribute("role", "dialog");
    fond.setAttribute("aria-modal", "true");
    fond.setAttribute("aria-label", "Photo en grand");
    fond.hidden = true;
    image = document.createElement("img");
    image.className = "visionneuse__image";
    image.alt = "Photo du signalement, en grand";
    legende = document.createElement("p");
    legende.className = "visionneuse__legende";
    fermer = bouton("visionneuse__fermer", "✕", "Fermer", ferme);
    precedent = bouton("visionneuse__prec", "‹", "Photo précédente", () => aller(-1));
    suivant = bouton("visionneuse__suiv", "›", "Photo suivante", () => aller(1));
    fond.append(image, legende, fermer, precedent, suivant);
    // Un clic ailleurs que sur la photo ou un bouton ferme la visionneuse.
    fond.addEventListener("click", (e) => { if (e.target !== image) ferme(); });
    document.body.append(fond);
  }

  /* Les photos de la page, sans doublon (la galerie montre la même photo en grand et en
     vignette). Les adresses sont celles que la page a posées elle-même. */
  function photosDeLaPage() {
    const vues = new Set();
    const liste = [];
    document.querySelectorAll('img[src^="' + PREFIXE + '"]').forEach((img) => {
      const src = img.getAttribute("src");
      if (vues.has(src)) return;
      vues.add(src);
      liste.push(src);
    });
    return liste;
  }

  function montrer() {
    image.src = photos[rang];
    legende.textContent = photos.length > 1 ? "Photo " + (rang + 1) + " sur " + photos.length : "";
    precedent.hidden = suivant.hidden = photos.length < 2;
  }

  function aller(sens) {
    if (photos.length < 2) return;
    rang = (rang + sens + photos.length) % photos.length;
    montrer();
  }

  function ouvre(src, origine) {
    if (!fond) construire();
    photos = photosDeLaPage();
    if (!photos.includes(src)) photos.unshift(src);
    rang = photos.indexOf(src);
    declencheur = origine;
    montrer();
    fond.hidden = false;
    document.body.classList.add("visionneuse-ouverte");
    fermer.focus();
  }

  function ferme() {
    if (!fond || fond.hidden) return;
    fond.hidden = true;
    image.removeAttribute("src");
    document.body.classList.remove("visionneuse-ouverte");
    if (declencheur && document.contains(declencheur)) declencheur.focus();
  }

  document.addEventListener("click", (e) => {
    const img = e.target instanceof Element ? e.target.closest("img") : null;
    if (!img || (fond && fond.contains(img))) return;
    const src = img.getAttribute("src") || "";
    if (!src.startsWith(PREFIXE)) return;
    e.preventDefault();
    ouvre(src, img.closest("button, a") || img);
  });

  document.addEventListener("keydown", (e) => {
    if (!fond || fond.hidden) return;
    if (e.key === "Escape") { e.preventDefault(); ferme(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); aller(-1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); aller(1); }
    else if (e.key === "Tab") { e.preventDefault(); fermer.focus(); }   // le focus reste dans la boîte
  });
})();
