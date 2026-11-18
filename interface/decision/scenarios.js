/* Comparaison de scénarios : on change les moyens, on voit ce que ça donne (exigence E5). */
"use strict";

const COULEURS = ["#0b5e47", "#c8102e", "#b45309"];
const REGLAGES = [
  { cle: "nb_camions", nom: "Camions", min: 0, max: 100, pas: 1, defaut: 24 },
  { cle: "camions_en_panne", nom: "Camions en panne", min: 0, max: 50, pas: 1, defaut: 0 },
  { cle: "taux_abonnement", nom: "Abonnés", min: 0, max: 100, pas: 5, defaut: 35, unite: " %", facteur: 0.01 },
  { cle: "frequence_collecte_jours", nom: "Passage tous les", min: 1, max: 7, pas: 1, defaut: 3, unite: " j" },
  { cle: "capacite_point_m3", nom: "Capacité d'un point", min: 10, max: 120, pas: 10, defaut: 30, unite: " m³" },
  { cle: "effectif_brigade", nom: "Brigade Laabal", min: 0, max: 300, pas: 10, defaut: 60 },
];
const NOMS_PAR_DEFAUT = ["Aujourd'hui", "Avec plus de moyens", "Troisième scénario"];

function construireScenario(numero) {
  const bloc = document.createElement("div");
  bloc.className = "scenario";
  bloc.dataset.numero = numero;
  bloc.innerHTML =
    `<input class="titre" value="${NOMS_PAR_DEFAUT[numero] || "Scénario " + (numero + 1)}">`
    + REGLAGES.map((r) => `
      <label>${r.nom}
        <span class="ligne">
          <input type="range" data-cle="${r.cle}" min="${r.min}" max="${r.max}" step="${r.pas}"
                 value="${r.defaut}">
          <output>${r.defaut}${r.unite || ""}</output>
        </span>
      </label>`).join("")
    + `<label class="case"><input type="checkbox" data-cle="saison"> Saison des pluies</label>`;
  bloc.addEventListener("input", (evenement) => {
    const curseur = evenement.target;
    if (curseur.type !== "range") return;
    const reglage = REGLAGES.find((r) => r.cle === curseur.dataset.cle);
    curseur.parentElement.querySelector("output").textContent = curseur.value + (reglage.unite || "");
  });
  return bloc;
}

const conteneur = document.getElementById("scenarios");
[0, 1].forEach((n) => conteneur.appendChild(construireScenario(n)));
/* Le deuxième scénario part avec plus de moyens, pour montrer tout de suite l'intérêt. */
const deuxieme = conteneur.children[1];
deuxieme.querySelector('[data-cle="nb_camions"]').value = 45;
deuxieme.querySelector('[data-cle="frequence_collecte_jours"]').value = 1;
deuxieme.querySelector('[data-cle="taux_abonnement"]').value = 60;
deuxieme.dispatchEvent(new Event("input", { bubbles: true }));
deuxieme.querySelectorAll("input[type=range]").forEach((c) => {
  const reglage = REGLAGES.find((r) => r.cle === c.dataset.cle);
  c.parentElement.querySelector("output").textContent = c.value + (reglage.unite || "");
});

function lireScenario(bloc) {
  const parametres = {};
  bloc.querySelectorAll("input[type=range]").forEach((curseur) => {
    const reglage = REGLAGES.find((r) => r.cle === curseur.dataset.cle);
    parametres[reglage.cle] = Number(curseur.value) * (reglage.facteur || 1);
  });
  parametres.saison = bloc.querySelector('[data-cle="saison"]').checked ? "pluies" : "seche";
  return { nom: bloc.querySelector(".titre").value.slice(0, 80), parametres };
}

const nombre = (v, d = 0) => (v == null ? "—"
  : Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }));

const INDICATEURS = [
  { titre: "Résultat" },
  { nom: "Taux de collecte", lire: (s) => s.taux_collecte, format: (v) => nombre(v * 100, 1) + " %", mieux: "haut" },
  { nom: "Déchets en dépotoir", lire: (s) => s.volume_depotoirs_m3, format: (v) => nombre(v) + " m³", mieux: "bas" },
  { nom: "Points saturés", lire: (s) => s.points_satures, format: nombre, mieux: "bas" },
  { titre: "Plan de gestion" },
  { nom: "Points de regroupement", lire: (s) => s.points, format: nombre },
  { nom: "Tournées par jour", lire: (s) => s.tournees, format: nombre },
  { nom: "Arrêts non desservis", lire: (s) => s.non_desservis, format: nombre, mieux: "bas" },
  { titre: "Moyens et argent" },
  { nom: "Kilomètres par jour", lire: (s) => s.km_par_jour, format: (v) => nombre(v) + " km" },
  { nom: "Coût par mois", lire: (s) => s.cout_par_mois, format: (v) => nombre(v) + " F", mieux: "bas" },
  { nom: "Solde mensuel", lire: (s) => s.solde_mensuel, format: (v) => nombre(v) + " F", mieux: "haut" },
];

function afficherTableau(scenarios) {
  const lignes = [`<tr><th>Indicateur</th>${scenarios.map((s) =>
    `<th class="valeur-chiffree">${echapper(s.nom)}</th>`).join("")}</tr>`];
  for (const indicateur of INDICATEURS) {
    if (indicateur.titre) {
      lignes.push(`<tr class="titre-ligne"><td colspan="${scenarios.length + 1}">${indicateur.titre}</td></tr>`);
      continue;
    }
    const valeurs = scenarios.map(indicateur.lire);
    const connues = valeurs.filter((v) => v != null);
    const extreme = indicateur.mieux === "haut" ? Math.max(...connues)
      : indicateur.mieux === "bas" ? Math.min(...connues) : null;
    lignes.push(`<tr><td>${indicateur.nom}</td>` + valeurs.map((v) => {
      const classe = extreme != null && connues.length > 1 && v === extreme ? " mieux" : "";
      return `<td class="valeur-chiffree${classe}">${v == null ? "—" : indicateur.format(v)}</td>`;
    }).join("") + "</tr>");
  }
  document.getElementById("tableau-resultats").innerHTML = lignes.join("");
}

function echapper(texte) {
  const n = document.createElement("span");
  n.textContent = texte;
  return n.innerHTML;
}

/* Un graphique dessiné par nos soins, en SVG : aucune bibliothèque chargée. */
function dessinerCourbes(series) {
  if (!series.length || !series[0].valeurs.length) {
    document.getElementById("graphique").hidden = true;
    return;
  }
  const largeur = 760, hauteur = 240, marge = { haut: 14, droite: 14, bas: 28, gauche: 56 };
  const jours = series[0].valeurs.length;
  const maximum = Math.max(1, ...series.flatMap((s) => s.valeurs));
  const x = (i) => marge.gauche + (i / Math.max(1, jours - 1)) * (largeur - marge.gauche - marge.droite);
  const y = (v) => hauteur - marge.bas - (v / maximum) * (hauteur - marge.haut - marge.bas);

  const graduations = [0, 0.25, 0.5, 0.75, 1].map((part) => {
    const valeur = maximum * part;
    return `<line x1="${marge.gauche}" x2="${largeur - marge.droite}" y1="${y(valeur)}" y2="${y(valeur)}"
                  stroke="#dfe2ec"/>
            <text x="${marge.gauche - 8}" y="${y(valeur) + 4}" text-anchor="end" font-size="11"
                  fill="#666e85">${nombre(valeur / 1000, 0)} k</text>`;
  }).join("");

  const courbes = series.map((s, rang) => {
    const chemin = s.valeurs.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    return `<path d="${chemin}" fill="none" stroke="${COULEURS[rang % COULEURS.length]}" stroke-width="2.2"/>`;
  }).join("");

  document.getElementById("courbes").innerHTML =
    `<svg viewBox="0 0 ${largeur} ${hauteur}" role="img" aria-label="Déchets accumulés en dépotoir, en milliers de mètres cubes">
       ${graduations}${courbes}
       <text x="${largeur - marge.droite}" y="${hauteur - 8}" text-anchor="end" font-size="11"
             fill="#666e85">jour ${jours}</text>
       <text x="${marge.gauche}" y="${hauteur - 8}" font-size="11" fill="#666e85">jour 1</text>
     </svg>
     <div class="legende">${series.map((s, rang) =>
       `<span><i style="background:${COULEURS[rang % COULEURS.length]}"></i>${echapper(s.nom)}</span>`).join("")}</div>`;
  document.getElementById("graphique").hidden = false;
}

document.getElementById("comparer").addEventListener("click", async () => {
  const bouton = document.getElementById("comparer");
  const etat = document.getElementById("etat");
  const jours = Number(document.getElementById("jours").value);
  const demandes = [...conteneur.children].map(lireScenario);
  bouton.disabled = true;
  etat.textContent = "Calcul des scénarios…";
  try {
    const reponse = await fetch("/api/comparer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jours, scenarios: demandes }),
    });
    const resultat = await reponse.json();
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur " + reponse.status);
    afficherTableau(resultat.scenarios);
    document.getElementById("resultats").hidden = false;
    // Les courbes jour par jour viennent d'un second appel, un scénario à la fois.
    const series = [];
    for (const demande of demandes) {
      const r = await fetch("/api/scenario", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...demande, jours }),
      }).then((x) => x.json());
      series.push({ nom: demande.nom, valeurs: (r.simulation?.journal || []).map((j) => j.volume_depotoirs_m3) });
    }
    dessinerCourbes(series);
    etat.textContent = `${resultat.scenarios.length} scénarios comparés sur ${jours} jours.`;
  } catch (erreur) {
    etat.textContent = "Erreur : " + erreur.message;
  } finally {
    bouton.disabled = false;
  }
});
