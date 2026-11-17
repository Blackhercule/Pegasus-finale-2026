/* Plateforme (T22) : ce que partagent le tableau de bord, l'explorateur et la page de détail.
 *
 * Rien n'est inventé côté serveur : ces pages lisent les adresses qui existent déjà. Ce qui
 * vient d'un habitant (commentaire, quartier, nom de lieu) est posé avec textContent, jamais en
 * HTML : un signalement piégé ne peut pas devenir du code dans la page de l'agent.
 */
"use strict";

const Plateforme = (function () {
  const SVG = "http://www.w3.org/2000/svg";
  let session = null;

  /* Les trois chaînes de traitement, et ce qu'il faut pour les lire. */
  const CHAINES = {
    depotoir: { liste: "/api/dossiers", detail: "/api/dossiers/", chaine: "/api/chaine",
                nom: "Dépotoir", famille: "ordures", page: "/decision/dossiers.html" },
    fuite: { liste: "/api/fuites", detail: "/api/fuites/", chaine: "/api/fuites/chaine",
             nom: "Fuite d'eau", famille: "eau", page: "/decision/fuites.html" },
    nuisance: { liste: "/api/nuisances", detail: "/api/nuisances/", chaine: "/api/nuisances/chaine",
                nom: "Nuisance", famille: "nuisance", page: "/decision/nuisances.html" },
  };

  /* Un appel à l'API. Le jeton de session part avec chaque action (en-tête X-Jeton) ; sans
     session, on recharge la page, et le serveur affiche la connexion à la même adresse. */
  async function appel(adresse, options = {}) {
    const entetes = {};
    if (session?.jeton) entetes["X-Jeton"] = session.jeton;
    if (options.json) entetes["Content-Type"] = "application/json";
    const reponse = await fetch(adresse, {
      method: options.methode || "GET", headers: entetes,
      body: options.json ? JSON.stringify(options.json) : undefined,
    });
    if (reponse.status === 401) { window.location.reload(); throw new Error("Connexion requise"); }
    const resultat = await reponse.json().catch(() => ({}));
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur " + reponse.status);
    return resultat;
  }

  async function ouvrirLaSession() {
    session = await appel("/api/session");
    return session;
  }

  /* Construit un élément : el("p", { class: "aide" }, "texte", autreElement). Le texte est
     toujours posé comme du texte. */
  function el(balise, attributs = {}, ...enfants) {
    const noeud = document.createElement(balise);
    for (const [nom, valeur] of Object.entries(attributs || {})) {
      if (valeur === null || valeur === undefined || valeur === false) continue;
      if (nom === "class") noeud.className = valeur;
      else noeud.setAttribute(nom, valeur === true ? "" : String(valeur));
    }
    for (const enfant of enfants.flat()) {
      if (enfant === null || enfant === undefined || enfant === false) continue;
      noeud.append(enfant instanceof Node ? enfant : String(enfant));
    }
    return noeud;
  }

  function svg(balise, attributs = {}, texte) {
    const noeud = document.createElementNS(SVG, balise);
    for (const [nom, valeur] of Object.entries(attributs)) noeud.setAttribute(nom, String(valeur));
    if (texte !== undefined) noeud.textContent = String(texte);
    return noeud;
  }

  const nombre = (v, d = 0) => (v == null || Number.isNaN(Number(v)) ? "—"
    : Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }));

  function date(iso, avecHeure = true) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("fr-FR", avecHeure
      ? { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }
      : { day: "2-digit", month: "long", year: "numeric" });
  }

  /* Haute à partir de 60, moyenne à partir de 35 : les mêmes seuils que les postes de travail. */
  function niveau(note) {
    return note >= 60 ? "haute" : note >= 35 ? "moyenne" : "basse";
  }

  function pastilleUrgence(priorite) {
    const note = priorite ? Math.round(priorite.note) : 0;
    const raisons = priorite && priorite.raisons.length ? priorite.raisons.join(" · ") : "aucun facteur particulier";
    return el("span", { class: "urgence " + niveau(note), title: "Urgence " + note + " : " + raisons,
                        "aria-label": "Urgence " + note + " sur 100" }, note);
  }

  /* Ce qu'est un dossier, en quelques mots, selon sa chaîne. */
  function titreDuDossier(type, d) {
    if (type === "fuite") return "Fuite — " + (d.ampleur_nom || "ampleur inconnue").split(" (")[0];
    if (type === "nuisance") return d.nature_nom || "Nuisance";
    return "Dépotoir de " + nombre(d.volume_m3, 1) + " m³";
  }

  function adresseDuDetail(type, id) {
    return "/decision/signalement.html?type=" + encodeURIComponent(type) + "&id=" + encodeURIComponent(id);
  }

  /* Une étape close est une étape sans suivante (collecté, réparée, traité, classé). */
  function estClos(chaine, etape) {
    const e = chaine && chaine.etapes[etape];
    return Boolean(e) && e.suivante === null;
  }

  /* Graphique en barres horizontales, en SVG : [{ libelle, valeur, couleur }]. */
  function barres(donnees, { largeur = 520, hauteurBarre = 22, ecart = 10, marge = 150 } = {}) {
    // Sur un téléphone, le dessin est plus étroit : le texte garde alors une taille lisible.
    if (window.innerWidth < 640) { largeur = 340; marge = Math.min(marge, 140); }
    const max = Math.max(1, ...donnees.map((d) => d.valeur));
    const hauteur = donnees.length * (hauteurBarre + ecart) + ecart;
    const dessin = svg("svg", { viewBox: `0 0 ${largeur} ${hauteur}`, class: "barres", role: "img" });
    const zone = largeur - marge - 50;
    donnees.forEach((d, i) => {
      const y = ecart + i * (hauteurBarre + ecart);
      dessin.append(svg("text", { x: marge - 10, y: y + hauteurBarre * 0.7, "text-anchor": "end" }, d.libelle));
      dessin.append(svg("rect", { x: marge, y, width: zone, height: hauteurBarre, rx: 5, class: "fond" }));
      const w = Math.max(d.valeur ? 3 : 0, (d.valeur / max) * zone);
      dessin.append(svg("rect", { x: marge, y, width: w, height: hauteurBarre, rx: 5, fill: d.couleur || "#1e2455" }));
      dessin.append(svg("text", { x: marge + w + 8, y: y + hauteurBarre * 0.7, class: "valeur" }, d.valeur));
    });
    dessin.setAttribute("aria-label", donnees.map((d) => d.libelle + " : " + d.valeur).join(", "));
    return dessin;
  }

  return { CHAINES, appel, ouvrirLaSession, el, svg, nombre, date, niveau, pastilleUrgence,
           titreDuDossier, adresseDuDetail, estClos, barres, get session() { return session; } };
})();
