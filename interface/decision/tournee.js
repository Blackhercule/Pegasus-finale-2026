/* « Ma tournée du jour » : les visites qui attendent ce poste, groupées en un seul trajet.

   Pourquoi cet écran existe : un agent qui a douze constats à faire se déplaçait douze fois,
   et souvent deux dossiers voisins étaient visités deux jours différents, simplement parce
   qu'ils étaient arrivés dans le désordre. Ici il voit son trajet du matin, dans l'ordre, avec
   ce que le groupement fait gagner.

   Le calcul est celui des tournées des camions : mêmes économies de Clarke et Wright, même
   réseau de rues. Seule la contrainte change — la journée de l'agent au lieu de la benne. */
"use strict";

(function () {
  const bouton = document.getElementById("preparer-tournee");
  const sortie = document.getElementById("tournee");
  if (!bouton || !sortie) return;

  const proteger = (texte) => {
    const n = document.createElement("span");
    n.textContent = texte == null ? "" : String(texte);
    return n.innerHTML;
  };

  const NOMS = {
    depotoir: "Dépotoir", fuite_eau: "Fuite d'eau", caniveau_bouche: "Caniveau bouché",
    abattoir_clandestin: "Abattoir clandestin", toilettes_plein_air: "Toilettes en plein air",
    eaux_usees_animales: "Eaux usées de poisson ou poulet",
  };

  bouton.addEventListener("click", async () => {
    bouton.disabled = true;
    sortie.innerHTML = '<p class="aide">Calcul en cours…</p>';
    let resultat;
    try {
      const reponse = await fetch("/api/inspection", {
        headers: window.jetonDeSession ? { "X-Jeton": window.jetonDeSession } : {} });
      if (!reponse.ok) throw new Error("Erreur " + reponse.status);
      resultat = await reponse.json();
    } catch (e) {
      sortie.innerHTML = `<p class="message erreur">${proteger(e.message)}</p>`;
      bouton.disabled = false;
      return;
    }
    bouton.disabled = false;

    if (!resultat.tournees.length) {
      sortie.innerHTML = '<p class="vide">Rien à visiter pour l\'instant.</p>';
      return;
    }

    const e = resultat.economie;
    const trajets = resultat.tournees.map((t) => `
      <div class="sortie-terrain">
        <h3>Agent ${t.agent} · sortie ${t.sortie} — ${t.nb_visites} visite(s),
          ${t.duree_min} min, ${t.distance_km} km</h3>
        <ol class="etapes-tournee">
          ${t.etapes.map((etape) => `<li><span class="genre">${
            proteger(NOMS[etape.genre] || etape.genre)}</span> ${proteger(etape.id)}</li>`).join("")}
        </ol>
      </div>`).join("");

    sortie.innerHTML = `
      <div class="economie">
        <p><strong>${e.sorties_evitees}</strong> déplacement(s) évité(s) aujourd'hui.</p>
        <p>${e.heures_sans_groupement} h si l'on sortait une fois par dossier
           → <strong>${e.heures_avec_groupement} h</strong> en groupant
           (${e.heures_gagnees} h gagnées).</p>
        <p>Il faut <strong>${resultat.agents_necessaires}</strong> agent(s) sur le terrain
           aujourd'hui, sur ${resultat.agents} disponible(s).</p>
      </div>
      ${trajets}
      <p class="aide">Départ et retour : ${proteger(resultat.base.nom)}.
        ${resultat.injoignables.length
          ? `${resultat.injoignables.length} dossier(s) hors d'atteinte dans la journée.` : ""}
        ${resultat.non_visites.length
          ? `${resultat.non_visites.length} dossier(s) reporté(s) au jour suivant.` : ""}</p>`;
  });
})();
