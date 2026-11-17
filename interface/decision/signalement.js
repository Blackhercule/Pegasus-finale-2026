/* Détail d'un dossier (T22) : /decision/signalement.html?type=depotoir|fuite|nuisance&id=…
 *
 * Tout vient de l'adresse de détail de la chaîne (/api/dossiers/<id>, /api/fuites/<id>,
 * /api/nuisances/<id>) et de sa chaîne d'étapes. Les actions sont les mêmes appels que sur les
 * postes de travail : « avancer » (avec ce que l'agent a constaté), « classer » (mairie
 * seulement), « effacer les pièces d'identité » (dépotoirs, mairie). Le serveur vérifie de toute
 * façon que le poste a le droit d'agir : la page ne fait que ne pas proposer ce qui serait refusé.
 *
 * L'identité facultative du déclarant n'est affichée que si le serveur la renvoie, c'est-à-dire
 * à un agent connecté. Tout ce qu'un habitant a tapé est posé avec textContent.
 */
"use strict";

(function () {
  const { CHAINES, appel, ouvrirLaSession, el, nombre, date, niveau, titreDuDossier } = Plateforme;
  const $ = (id) => document.getElementById(id);
  const parametres = new URLSearchParams(window.location.search);
  const type = parametres.get("type");
  const id = Number(parametres.get("id"));
  const chaine = CHAINES[type];

  const DEPOTS = { plein_air: "à même le sol", bac: "dans un bac", caniveau: "dans un caniveau",
                   fosse: "dans une fosse", berge: "sur une berge", autre: "autre" };
  const TYPES = { menager: "ménagers", gravats: "gravats", mixte: "mélangés", autre: "autre" };
  const POSTES = { mairie: "Mairie", brigade: "Brigade Laabal", collecte: "Équipe de collecte", onea: "ONEA" };

  let session = null;
  let etapes = null;

  function erreur(texte) {
    $("titre").textContent = "Dossier introuvable";
    $("erreur").textContent = texte;
    $("erreur").hidden = false;
  }

  function lignesInformations(d) {
    const premier = d.signalements[0] || {};
    const communes = [
      ["Signalé le", date(d.premier_vu)],
      ["Dernier signalement", date(d.dernier_vu)],
      ["Signalements", `${d.nb_signalements}, de ${d.nb_sources} appareil(s) différent(s)`],
      ["Position", `${Number(d.latitude).toFixed(5)}, ${Number(d.longitude).toFixed(5)}`],
    ];
    if (type === "fuite") {
      return [["Ampleur", d.ampleur_nom], ["Quartier", d.quartier || "non précisé"],
              ["Référence ONEA", d.reference_onea || "pas encore transmise"], ...communes];
    }
    if (type === "nuisance") {
      return [["Nature", d.nature_nom], ["Gravité", d.gravite_nom],
              ["Service compétent", POSTES[d.service] || d.service || "—"],
              ["Quartier", d.quartier || "non précisé"], ...communes];
    }
    return [["Volume estimé", nombre(d.volume_m3, 1) + " m³"],
            ["Superficie", d.surface_m2 ? nombre(d.surface_m2) + " m²" : "non mesurée"],
            ["Dépôt", d.depot ? DEPOTS[d.depot] : "non précisé"],
            ["Déchets", TYPES[premier.type] || "non précisé"], ...communes];
  }

  function galerie(signalements) {
    const photos = signalements.filter((s) => s.photo);
    if (!photos.length) return el("p", { class: "sans-photo" }, "Aucune photo pour ce dossier.");
    const image = el("img", { alt: "Photo du signalement" });
    const legende = el("figcaption");
    const montrer = (s, bouton) => {
      image.src = "/api/fichiers/" + encodeURI(s.photo);
      const masques = [];
      if (s.visages_masques) masques.push(s.visages_masques + " visage(s) masqué(s)");
      if (s.plaques_masquees) masques.push(s.plaques_masquees + " plaque(s) masquée(s)");
      legende.textContent = "Prise le " + date(s.date_observation) + (masques.length ? " · " + masques.join(", ") : "");
      vignettes.querySelectorAll("button").forEach((b) => b.setAttribute("aria-current", String(b === bouton)));
    };
    const vignettes = el("div", { class: "vignettes" });
    photos.forEach((s, i) => {
      const bouton = el("button", { type: "button", "aria-label": "Photo " + (i + 1) },
                        el("img", { src: "/api/fichiers/" + encodeURI(s.photo), alt: "" }));
      bouton.addEventListener("click", () => montrer(s, bouton));
      vignettes.append(bouton);
    });
    const bloc = el("div", {}, el("figure", { class: "galerie-principale" }, image, legende));
    if (photos.length > 1) bloc.append(vignettes);
    montrer(photos[0], vignettes.querySelector("button"));
    return bloc;
  }

  function temoins(d) {
    const avec = d.signalements.filter((s) => s.declarant_nom || s.declarant_telephone || s.photo_cnib || s.photo_visage);
    if (!avec.length) return null;
    const bloc = el("div");
    for (const s of avec) {
      bloc.append(el("dl", { class: "informations" },
        el("dt", {}, "Nom"), el("dd", {}, s.declarant_nom || "—"),
        el("dt", {}, "Téléphone"), el("dd", {}, s.declarant_telephone || "—")));
      const pieces = el("div", { class: "vignettes" });
      if (s.photo_cnib) pieces.append(el("img", { src: "/api/fichiers/" + encodeURI(s.photo_cnib), alt: "CNIB" }));
      if (s.photo_visage) pieces.append(el("img", { src: "/api/fichiers/" + encodeURI(s.photo_visage), alt: "Portrait" }));
      if (pieces.children.length) bloc.append(pieces);
    }
    if (type === "depotoir" && session.poste === "mairie") {
      const effacer = el("button", { type: "button", class: "bouton danger" }, "Effacer les pièces d'identité");
      effacer.addEventListener("click", async () => {
        if (!confirm("Effacer définitivement la CNIB, le portrait et le téléphone de ce dossier ?")) return;
        await appel(`/api/dossiers/${id}/identites`, { methode: "DELETE" });
        await charger();
      });
      bloc.append(el("div", { class: "boutons" }, effacer));
    }
    return bloc;
  }

  function historique(d) {
    if (!d.journal.length) {
      return [el("li", {}, el("span", { class: "quand" }, date(d.premier_vu)),
                 el("span", { class: "quoi" }, "Dossier ouvert par un signalement"))];
    }
    return d.journal.map((e) => el("li", {},
      el("span", { class: "quand" }, date(e.date)),
      el("span", { class: "quoi" }, (etapes.etapes[e.etape]?.nom || e.etape)),
      " — ", e.auteur, " (", POSTES[e.poste] || e.poste, ")",
      e.detail ? el("span", { class: "detail" }, e.detail) : null));
  }

  /* Les actions de l'étape, pour le seul poste qui en a le droit. */
  function actions(d) {
    const etape = etapes.etapes[d.etape] || {};
    $("explication").textContent = d.explication_etape || etape.explication || "";
    const clos = etape.suivante === null;
    if (clos) return [el("p", { class: "aide" }, "Ce dossier est clos : il n'y a plus rien à faire.")];
    const aMoi = d.poste_attendu === session.poste;
    const peutClasser = session.poste === "mairie";
    if (!aMoi && !peutClasser) {
      return [el("p", { class: "aide" }, "Ce dossier attend le poste « "
        + (POSTES[d.poste_attendu] || d.poste_attendu || "—") + " ».")];
    }
    const champ = el("textarea", { id: "detail-action", rows: 3, maxlength: 500,
      placeholder: "Ce que vous avez constaté ou fait (facultatif pour avancer, obligatoire pour classer)" });
    const message = el("p", { class: "message", role: "status" });
    const boutons = el("div", { class: "boutons" });
    const agir = async (action, corps) => {
      boutons.querySelectorAll("button").forEach((b) => { b.disabled = true; });
      try {
        await appel(chaine.detail + id + "/" + action, { methode: "POST", json: corps });
        await charger();
        $("actions").prepend(el("p", { class: "message ok", role: "status" }, "C'est enregistré."));
      } catch (e) {
        message.className = "message erreur-action";
        message.textContent = e.message;
        boutons.querySelectorAll("button").forEach((b) => { b.disabled = false; });
      }
    };
    if (aMoi) {
      const avancer = el("button", { type: "button", class: "bouton", id: "avancer" },
                         d.action_attendue || etape.action || "Faire avancer");
      avancer.addEventListener("click", () => agir("avancer", { detail: champ.value }));
      boutons.append(avancer);
    }
    if (peutClasser) {
      const classer = el("button", { type: "button", class: "bouton danger", id: "classer" }, "Classer sans suite");
      classer.addEventListener("click", () => {
        if (!champ.value.trim()) {
          message.className = "message erreur-action";
          message.textContent = "Écrivez d'abord pourquoi le dossier est classé sans suite.";
          champ.focus();
          return;
        }
        agir("classer", { motif: champ.value.trim() });
      });
      boutons.append(classer);
    }
    return [champ, boutons, message];
  }

  async function charger() {
    // Le détail ne contient pas la note d'urgence : elle est calculée pour les listes. On la
    // reprend donc dans la liste de la même chaîne, pour afficher exactement la même note.
    const [d, liste] = await Promise.all([appel(chaine.detail + id), appel(chaine.liste)]);
    d.priorite = d.priorite || (liste.find((x) => x.id === id) || {}).priorite || null;
    const famille = { ordures: "Dépotoir", eau: "Fuite d'eau", nuisance: "Nuisance" }[chaine.famille];
    document.title = titreDuDossier(type, d) + " — Assainissement de Ouaga";
    $("fil-dossier").textContent = famille + " n° " + d.id;
    $("titre").textContent = titreDuDossier(type, d);
    $("sous-titre").textContent = famille + " n° " + d.id + " · " + (d.etape_nom || "")
      + (d.quartier ? " · " + d.quartier : "");
    $("etiquettes").replaceChildren(el("span", { class: "etiquette " + chaine.famille }, famille),
                                    el("span", { class: "etiquette" }, d.etape_nom));

    const note = Math.round(d.priorite?.note || 0);
    if (!d.priorite) {
      $("urgence-grande").replaceChildren(el("span", { class: "sous" }, "urgence non calculée"));
    } else $("urgence-grande").replaceChildren(
      el("span", { class: "urgence " + niveau(note), "aria-label": "Urgence " + note + " sur 100" }, note),
      el("span", { class: "sous" }, "urgence"));
    const raisons = d.priorite?.raisons || [];
    $("raisons").replaceChildren(...(raisons.length ? raisons.map((r) => el("li", {}, r))
      : [el("li", {}, "Aucun facteur d'urgence particulier.")]));

    $("galerie").replaceChildren(galerie(d.signalements));
    $("informations").replaceChildren(...lignesInformations(d).flatMap(([nom, valeur]) =>
      [el("dt", {}, nom), el("dd", {}, valeur ?? "—")]));

    const depuisUnLieu = d.signalements.filter((s) => s.source_position === "lieu");
    $("avertissement-lieu").replaceChildren(...depuisUnLieu.map((s) => el("p", { class: "position-lieu" },
      "⚠ Position approximative : déduite du lieu « " + (s.lieu_nom || "?") + " » (± "
      + Math.round(s.precision_m || 150) + " m), pas d'un GPS. Chercher aux abords.")));
    $("pourquoi").hidden = !d.pourquoi;
    $("pourquoi").textContent = d.pourquoi || "";

    const voix = d.signalements.filter((s) => s.message_vocal);
    $("bloc-voix").hidden = !voix.length;
    $("voix").replaceChildren(...voix.map((s) => el("audio", { controls: true, preload: "none",
                                                               src: "/api/fichiers/" + encodeURI(s.message_vocal) })));
    const ecrits = d.signalements.filter((s) => (s.commentaire || "").trim());
    $("bloc-commentaires").hidden = !ecrits.length;
    $("commentaires").replaceChildren(...ecrits.map((s) => el("li", {},
      el("span", { class: "quand" }, date(s.date_observation)), s.commentaire)));

    const blocTemoins = temoins(d);
    $("bloc-temoins").hidden = !blocTemoins;
    $("temoins").replaceChildren(...(blocTemoins ? [blocTemoins] : []));

    $("historique").replaceChildren(...historique(d));
    $("actions").replaceChildren(...actions(d));
    $("contenu").hidden = false;
  }

  async function demarrer() {
    if (!chaine || !Number.isInteger(id) || id <= 0) {
      erreur("Adresse incomplète : il faut un type (depotoir, fuite ou nuisance) et un numéro.");
      return;
    }
    session = await ouvrirLaSession();
    etapes = await appel(chaine.chaine);
    await charger();
  }

  demarrer().catch((e) => erreur("Ce dossier n'a pas pu être chargé : " + e.message));
})();
