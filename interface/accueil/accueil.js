// Page d'accueil : affiche les trois chiffres publics. Si le serveur ne répond pas, les tirets
// restent : la page et le bouton « Signaler » fonctionnent quand même.
"use strict";
fetch("/api/publics")
  .then((reponse) => (reponse.ok ? reponse.json() : {}))
  .then((chiffres) => {
    for (const nom of ["signalements", "depotoirs", "dossiers_traites"]) {
      if (Number.isInteger(chiffres[nom])) {
        document.getElementById(nom).textContent = chiffres[nom].toLocaleString("fr-FR");
      }
    }
  })
  .catch(() => {});

// ------------------------------------------------------------------ C14 : services aux habitants
// Collecteurs du quartier, plainte « il n'est pas passé », quartiers les plus propres,
// campagnes, et les points de CE téléphone. Tout est posé avec textContent.
(function () {
  const $ = (id) => document.getElementById(id);
  const lire = (adresse) => fetch(adresse).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));
  let motifs = {};

  function creer(balise, classe, texte) {
    const n = document.createElement(balise);
    if (classe) n.className = classe;
    if (texte !== undefined) n.textContent = texte;
    return n;
  }

  // Le même pseudonyme que la page Signaler : un nombre tiré au hasard, gardé dans ce téléphone.
  function pseudonyme() {
    try { return JSON.parse(localStorage.getItem("pseudonyme-appareil")) || ""; } catch { return ""; }
  }

  async function plainte(collecteur, quartier, motif) {
    const reponse = await fetch("/api/public/plaintes", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ collecteur_id: collecteur.id, quartier, motif, source: pseudonyme() }) });
    const resultat = await reponse.json().catch(() => ({}));
    $("merci").hidden = false;
    $("merci").textContent = reponse.ok ? "Merci : la mairie a reçu votre message pour " + collecteur.nom + "."
      : (resultat.erreur || "Envoi impossible pour l'instant.");
  }

  async function afficherCollecteurs() {
    const quartier = $("quartier").value;
    const liste = $("collecteurs");
    liste.replaceChildren();
    $("merci").hidden = true;
    if (!quartier) return;
    const { collecteurs } = await lire("/api/public/collecteurs?quartier=" + encodeURIComponent(quartier));
    if (!collecteurs.length) {
      liste.append(creer("li", "vide", "Aucun collecteur enregistré dans ce quartier pour l'instant."));
      return;
    }
    for (const c of collecteurs) {
      const carte = creer("li", "collecteur");
      carte.append(creer("strong", "", c.nom), creer("span", "genre", c.genre),
        creer("span", "jours", c.jours.length ? "Passe le " + c.jours.join(", ") : "Jours à confirmer"));
      if (c.telephone_service) carte.append(creer("span", "tel", "Service : " + c.telephone_service));
      const choix = creer("select", "motif");
      choix.setAttribute("aria-label", "Signaler un problème avec " + c.nom);
      choix.append(creer("option", "", "Signaler un problème…"));
      choix.firstChild.value = "";
      for (const [cle, texte] of Object.entries(motifs)) {
        const o = creer("option", "", texte); o.value = cle; choix.append(o);
      }
      choix.addEventListener("change", () => { if (choix.value) plainte(c, quartier, choix.value); choix.value = ""; });
      carte.append(choix);
      liste.append(carte);
    }
  }

  async function demarrer() {
    const r = await lire("/api/public/quartiers");
    motifs = r.motifs;
    for (const q of [...r.quartiers].sort((a, b) => a.localeCompare(b, "fr"))) {
      const o = creer("option", "", q); o.value = q; $("quartier").append(o);
    }
    $("quartier").addEventListener("change", () => afficherCollecteurs().catch(() => {}));
    const propres = $("propres");
    propres.replaceChildren();
    for (const q of r.classement.slice(0, 5)) {
      const li = creer("li", "");
      li.append(creer("strong", "", q.quartier), creer("span", "",
        q.ouverts ? q.ouverts + " dépotoir(s) ouvert(s)" : "aucun dépotoir ouvert"));
      propres.append(li);
    }
    const { campagnes } = await lire("/api/public/campagnes");
    if (campagnes.length) {
      $("campagnes").replaceChildren(...campagnes.slice(0, 5).map((c) => {
        const li = creer("li", "");
        const morceaux = [c.date && new Date(c.date).toLocaleDateString("fr-FR"), c.quartier, c.organisateur,
          c.participants ? c.participants + " participants" : "",
          c.quantite_kg ? (c.quantite_kg >= 1000 ? (c.quantite_kg / 1000).toLocaleString("fr-FR") + " t"
            : c.quantite_kg + " kg") + " enlevés" : ""].filter(Boolean);
        li.append(creer("strong", "", c.titre), creer("span", "", morceaux.join(" · ")));
        return li;
      }));
    }
    const source = pseudonyme();
    if (source) {
      const p = await lire("/api/public/points?source=" + encodeURIComponent(source));
      $("mes-points").hidden = false;
      $("mes-points").textContent = `Vos points : ${p.points} (${p.verifies} signalement(s) vérifié(s) depuis ce téléphone, 10 points chacun)`;
    }
  }

  demarrer().catch(() => {});
})();
