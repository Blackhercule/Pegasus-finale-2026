/* Collecteurs (C14) : enregistrement, véhicules, calendrier de passage, collectes déclarées,
 * centres de collecte, plaintes des habitants, campagnes de salubrité.
 * Seule la mairie enregistre ; la collecte déclare aussi ses collectes. Tout le texte est posé
 * avec textContent (Plateforme.el).
 */
"use strict";

(function () {
  const { appel, ouvrirLaSession, el, date, nombre } = Plateforme;
  const $ = (id) => document.getElementById(id);
  const JOURS_COURTS = { lundi: "lun", mardi: "mar", mercredi: "mer", jeudi: "jeu", vendredi: "ven",
                         samedi: "sam", dimanche: "dim" };
  let donnees = null;

  const kg = (v) => (v >= 1000 ? nombre(v / 1000, 1) + " t" : nombre(v) + " kg");

  function erreur(message) {
    $("erreur").hidden = !message;
    $("erreur").textContent = message || "";
  }

  function remplirSelect(select, options, vide) {
    const garde = select.value;
    select.replaceChildren(...(vide ? [el("option", { value: "" }, vide)] : []),
      ...options.map(([v, t]) => el("option", { value: v }, t)));
    if (garde) select.value = garde;
  }

  function afficher() {
    const d = donnees;
    $("total").textContent = `${d.collecteurs.length} collecteur(s) · ${kg(d.bilan.total_kg)} évacués`;
    // Liste.
    const corps = $("liste");
    corps.replaceChildren();
    if (!d.collecteurs.length) corps.append(el("tr", {}, el("td", { colspan: 6, class: "petit" }, "Aucun collecteur enregistré.")));
    for (const c of d.collecteurs) {
      const vehicules = c.vehicules.length
        ? c.vehicules.map((v) => d.vehicules[v.genre] + (v.immatriculation ? " " + v.immatriculation : "")).join(", ")
        : "—";
      corps.append(el("tr", {},
        el("td", {}, el("span", { class: "nom" }, c.nom),
          el("span", { class: "petit" }, d.genres[c.genre] + (c.telephone_service ? " · " + c.telephone_service : "")
            + (c.actif ? "" : " · inactif"))),
        el("td", {}, c.quartiers.join(", ") || "—"),
        el("td", {}, c.jours.join(", ") || "—"),
        el("td", {}, vehicules),
        el("td", {}, kg(c.quantite_kg)),
        el("td", {}, String(c.plaintes))));
    }
    // Choix.
    const collecteurs = d.collecteurs.map((c) => [c.id, c.nom]);
    document.querySelectorAll(".choix-collecteur").forEach((s) => remplirSelect(s, collecteurs));
    document.querySelectorAll(".choix-quartier").forEach((s) => remplirSelect(s, d.quartiers.map((q) => [q, q]), "—"));
    remplirSelect($("choix-centre"), d.centres.map((c) => [c.id, c.nom]), "—");
    // Calendrier.
    const tableau = $("calendrier");
    tableau.replaceChildren(el("thead", {}, el("tr", {}, el("th", {}, "Quartier"),
      ...d.jours.map((j) => el("th", {}, JOURS_COURTS[j])))));
    const lignes = el("tbody");
    const quartiers = Object.keys(d.calendrier).sort((a, b) => a.localeCompare(b, "fr"));
    if (!quartiers.length) lignes.append(el("tr", {}, el("td", { colspan: 8, class: "petit" }, "Aucun passage prévu.")));
    for (const q of quartiers) {
      lignes.append(el("tr", {}, el("th", {}, q), ...d.jours.map((j) => {
        const qui = d.calendrier[q][j] || [];
        return el("td", { class: qui.length ? "passe" : "" }, qui.join(", "));
      })));
    }
    tableau.append(lignes);
    // Bilan.
    const bilan = $("bilan");
    bilan.replaceChildren();
    if (!d.bilan.par_collecteur.length) bilan.append(el("tr", {}, el("td", { colspan: 4, class: "petit" }, "Aucune collecte déclarée.")));
    for (const b of d.bilan.par_collecteur)
      bilan.append(el("tr", {}, el("td", {}, b.mois), el("td", {}, b.nom), el("td", {}, String(b.collectes)),
        el("td", {}, kg(b.quantite_kg))));
    // Centres, plaintes, campagnes.
    $("centres").replaceChildren(...(d.centres.length ? d.centres.map((c) => el("li", {}, c.nom,
      el("span", { class: "petit" }, `Reçu : ${kg(c.recu_kg)}` + (c.capacite_t ? ` · capacité ${nombre(c.capacite_t)} t` : ""))))
      : [el("li", { class: "petit" }, "Aucun centre enregistré.")]));
    $("plaintes").replaceChildren(...(d.plaintes.length ? d.plaintes.map((p) => el("li", {},
      `${p.collecteur} — ${p.motif_nom}`, el("span", { class: "petit" }, date(p.date) + (p.quartier ? " · " + p.quartier : ""))))
      : [el("li", { class: "petit" }, "Aucune plainte.")]));
    $("campagnes").replaceChildren(...(d.campagnes.length ? d.campagnes.map((c) => el("li", {}, c.titre,
      el("span", { class: "petit" }, [date(c.date, false), c.quartier, c.organisateur,
        c.participants ? c.participants + " participants" : "", c.quantite_kg ? kg(c.quantite_kg) + " enlevés" : ""]
        .filter(Boolean).join(" · "))))
      : [el("li", { class: "petit" }, "Aucune campagne publiée.")]));
  }

  function preparerCases() {
    $("choix-jours").replaceChildren(...donnees.jours.map((j) => el("label", {},
      el("input", { type: "checkbox", name: "jours", value: j }), j)));
    $("choix-quartiers").replaceChildren(...donnees.quartiers.map((q) => el("label", {},
      el("input", { type: "checkbox", name: "quartiers", value: q }), q)));
  }

  async function charger() {
    donnees = await appel("/api/collecteurs");
    afficher();
  }

  function envoyerFormulaire(id, adresse, prepare) {
    $(id).addEventListener("submit", async (evenement) => {
      evenement.preventDefault();
      const formulaire = evenement.target;
      const valeurs = Object.fromEntries(new FormData(formulaire));
      try {
        const envoi = prepare ? prepare(valeurs, formulaire) : valeurs;
        await appel(typeof adresse === "function" ? adresse(valeurs) : adresse, { methode: "POST", json: envoi });
        erreur("");
        formulaire.reset();
        formulaire.querySelectorAll("input[type=date]").forEach((i) => { i.value = new Date().toISOString().slice(0, 10); });
        await charger();
      } catch (e) { erreur(e.message); }
    });
  }

  async function demarrer() {
    const session = await ouvrirLaSession();
    if (session.poste !== "mairie") document.body.classList.add("pas-mairie");
    await charger();
    preparerCases();
    envoyerFormulaire("form-collecteur", "/api/collecteurs", (v, f) => ({
      ...v, jours: [...f.querySelectorAll("input[name=jours]:checked")].map((i) => i.value),
      quartiers: [...f.querySelectorAll("input[name=quartiers]:checked")].map((i) => i.value) }));
    envoyerFormulaire("form-vehicule", (v) => `/api/collecteurs/${v.collecteur}/vehicules`);
    envoyerFormulaire("form-collecte", "/api/collectes", (v) => ({ ...v, collecteur_id: Number(v.collecteur_id),
      centre_id: v.centre_id ? Number(v.centre_id) : null }));
    envoyerFormulaire("form-centre", "/api/centres");
    envoyerFormulaire("form-campagne", "/api/campagnes");
    const aujourdhui = new Date().toISOString().slice(0, 10);
    document.querySelectorAll("input[type=date]").forEach((i) => { i.value = aujourdhui; });
  }

  document.addEventListener("DOMContentLoaded", () => demarrer().catch((e) => erreur(e.message)));
})();
