// La barre commune aux sept pages de décision (T14) : sections, poste connecté, menu ☰.
//
// Elle est écrite UNE fois, ici, et chaque page la charge : changer une section se fait à un
// seul endroit. Tout est construit avec createElement et textContent, jamais avec du HTML
// en texte : un nom de poste ne peut pas devenir du code.
"use strict";

(function () {
  const SECTIONS = [
    ["Carte", "/decision/"],
    ["Dépotoirs", "/decision/dossiers.html"],
    ["Fuites d'eau", "/decision/fuites.html"],
    ["Nuisances", "/decision/nuisances.html"],
    ["Vérifier", "/decision/verifier.html"],
    ["Simulation", "/decision/simulation.html"],
    ["Scénarios", "/decision/scenarios.html"],
  ];
  const SVG = "http://www.w3.org/2000/svg";

  function creer(balise, classe, texte) {
    const noeud = document.createElement(balise);
    if (classe) noeud.className = classe;
    if (texte) noeud.textContent = texte;
    return noeud;
  }

  // L'étoile jaune du drapeau, dessinée en SVG dans la page : aucun fichier image chargé (E14).
  function etoile() {
    const dessin = document.createElementNS(SVG, "svg");
    dessin.setAttribute("viewBox", "0 0 100 100");
    dessin.setAttribute("class", "barre__etoile");
    dessin.setAttribute("aria-hidden", "true");
    const branches = [];
    for (let i = 0; i < 10; i += 1) {
      // Cinq pointes : on alterne un point sur le grand cercle (48) et un sur le petit (19).
      const rayon = i % 2 === 0 ? 48 : 19;
      const angle = (Math.PI / 5) * i - Math.PI / 2;
      branches.push((50 + rayon * Math.cos(angle)).toFixed(1) + "," + (52 + rayon * Math.sin(angle)).toFixed(1));
    }
    const forme = document.createElementNS(SVG, "polygon");
    forme.setAttribute("points", branches.join(" "));
    dessin.append(forme);
    return dessin;
  }

  // --- La barre ---------------------------------------------------------------------------
  const barre = creer("header", "barre");

  const marque = creer("a", "barre__marque", "Assainissement de Ouaga");
  marque.href = "/decision/";

  const nav = creer("nav", "barre__sections");
  nav.setAttribute("aria-label", "Sections");
  const ici = location.pathname.replace(/index\.html$/, "");
  for (const [nom, adresse] of SECTIONS) {
    const lien = creer("a", "", nom);
    lien.href = adresse;
    if (ici === adresse) lien.setAttribute("aria-current", "page"); // la section ouverte
    nav.append(lien);
  }

  const compte = creer("div", "barre__compte");
  const poste = creer("span", "barre__poste");
  const changer = creer("button", "barre__changer", "Changer de poste");
  changer.type = "button";
  changer.addEventListener("click", async () => {
    await fetch("/api/deconnexion", { method: "POST" }).catch(() => {});
    location.reload(); // sans session, la page de connexion s'affiche à la même adresse
  });
  // L'étoile est posée dans la zone de droite, avant le nom du poste : elle ne passe jamais
  // sous du texte.
  compte.append(etoile(), poste, changer);

  barre.append(marque, nav, compte);

  // --- Le menu ☰ : seulement sur une page qui a un panneau de réglages (la carte) -------
  const panneau = document.getElementById("panneau");
  if (panneau) {
    document.body.classList.add("avec-panneau");
    const menu = creer("button", "barre__menu", "☰");
    menu.type = "button";
    menu.setAttribute("aria-label", "Couches et réglages");
    menu.setAttribute("aria-controls", "panneau");
    menu.setAttribute("aria-expanded", "false");
    compte.append(menu);

    const voile = creer("div", "voile-panneau"); // toucher à côté du panneau le referme
    document.body.append(voile);
    panneau.setAttribute("tabindex", "-1");

    const ouvrir = (ouvert) => {
      document.body.classList.toggle("panneau-ouvert", ouvert);
      menu.setAttribute("aria-expanded", String(ouvert));
      if (ouvert) panneau.focus();
    };
    menu.addEventListener("click", () => ouvrir(!document.body.classList.contains("panneau-ouvert")));
    voile.addEventListener("click", () => ouvrir(false));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && document.body.classList.contains("panneau-ouvert")) {
        ouvrir(false);
        menu.focus();
      }
    });
    // Un dépotoir choisi sur la carte s'affiche dans le panneau : on l'ouvre pour le montrer.
    const selection = document.getElementById("bloc-selection");
    if (selection) {
      new MutationObserver(() => { if (!selection.hidden) ouvrir(true); })
        .observe(selection, { attributes: true, attributeFilter: ["hidden"] });
    }
  }

  document.body.prepend(barre);
  // La carte a mesuré son cadre avant que la barre change la mise en page : on lui demande de
  // se remesurer (MapLibre écoute l'événement « resize » de la fenêtre).
  if (panneau) window.dispatchEvent(new Event("resize"));

  fetch("/api/session")
    .then((r) => (r.ok ? r.json() : null))
    .then((s) => { if (!s || !s.agent) return;
      // « Mairie — confirmation et programmation » : dans la barre, le premier mot suffit.
      poste.textContent = (s.poste_nom || s.poste).split(" — ")[0] + " · " + s.agent;
      poste.title = s.poste_nom || "";
    })
    .catch(() => {});
})();
