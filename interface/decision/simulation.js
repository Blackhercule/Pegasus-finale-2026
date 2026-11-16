/* La simulation vue de près : qui fait quoi, et ce que ça donne jour après jour. */
"use strict";

const element = (id) => document.getElementById(id);
const nombre = (v, d = 0) => (v == null ? "—"
  : Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }));

const SERIES = [
  { cle: "produit_m3", nom: "Produits", couleur: "#6c7772" },
  { cle: "collecte_m3", nom: "Collectés par les camions", couleur: "#2f6f4e" },
  { cle: "precollecte_m3", nom: "Ramassés par les pré-collecteurs", couleur: "#1d4f91" },
];

function echapper(texte) {
  const n = document.createElement("span");
  n.textContent = texte == null ? "" : String(texte);
  return n.innerHTML;
}

/* Graphique dessiné en SVG par nos soins : aucune bibliothèque chargée. */
function dessinerCourbes(journal) {
  const largeur = 820, hauteur = 260, marge = { haut: 14, droite: 14, bas: 28, gauche: 58 };
  const jours = journal.length;
  const valeurs = SERIES.map((s) => journal.map((j) => j[s.cle] || 0));
  const maximum = Math.max(1, ...valeurs.flat());
  const x = (i) => marge.gauche + (i / Math.max(1, jours - 1)) * (largeur - marge.gauche - marge.droite);
  const y = (v) => hauteur - marge.bas - (v / maximum) * (hauteur - marge.haut - marge.bas);

  const graduations = [0, 0.25, 0.5, 0.75, 1].map((part) => {
    const valeur = maximum * part;
    return `<line x1="${marge.gauche}" x2="${largeur - marge.droite}" y1="${y(valeur)}" y2="${y(valeur)}" stroke="#e6e2d8"/>
            <text x="${marge.gauche - 8}" y="${y(valeur) + 4}" text-anchor="end" font-size="11"
                  fill="#6c7772">${nombre(valeur)}</text>`;
  }).join("");

  const courbes = SERIES.map((s, rang) => {
    const chemin = valeurs[rang].map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    return `<path d="${chemin}" fill="none" stroke="${s.couleur}" stroke-width="2.2"/>`;
  }).join("");

  element("courbes").innerHTML =
    `<svg viewBox="0 0 ${largeur} ${hauteur}" role="img"
          aria-label="Déchets produits, collectés et ramassés, par jour, en mètres cubes">
       ${graduations}${courbes}
       <text x="${marge.gauche}" y="${hauteur - 8}" font-size="11" fill="#6c7772">jour 1</text>
       <text x="${largeur - marge.droite}" y="${hauteur - 8}" text-anchor="end" font-size="11"
             fill="#6c7772">jour ${jours}</text>
     </svg>
     <div class="legende">${SERIES.map((s) =>
       `<span><i style="background:${s.couleur}"></i>${s.nom}</span>`).join("")}</div>`;
}

function afficherJournal(journal) {
  const colonnes = [
    ["Jour", (j) => j.jour], ["Produits", (j) => nombre(j.produit_m3)],
    ["Pré-collecte", (j) => nombre(j.precollecte_m3)], ["Camions", (j) => nombre(j.collecte_m3)],
    ["Nettoyé", (j) => nombre(j.nettoye_m3)], ["En dépotoir", (j) => nombre(j.volume_depotoirs_m3)],
    ["Points saturés", (j) => j.points_satures], ["Pannes", (j) => j.pannes],
    ["Verbalisations", (j) => j.verbalisations], ["Abonnés", (j) => nombre(j.taux_abonnement * 100, 1) + " %"],
  ];
  element("journal").innerHTML =
    `<tr>${colonnes.map(([nom]) => `<th>${nom}</th>`).join("")}</tr>`
    + journal.map((j) => `<tr>${colonnes.map(([, lire]) => `<td>${lire(j)}</td>`).join("")}</tr>`).join("");
}

function afficherBilan(resume) {
  const cases = [
    ["Taux de collecte", nombre(resume.taux_collecte * 100, 1) + " %"],
    ["Déchets en dépotoir", nombre(resume.volume_depotoirs_m3) + " m³"],
    ["Points saturés", nombre(resume.points_satures)],
    ["Dépense", nombre(resume.depense_fcfa) + " F"],
    ["Abonnés à la fin", nombre(resume.taux_abonnement_final * 100, 1) + " %"],
  ];
  element("bilan").innerHTML = cases.map(([nom, valeur]) =>
    `<div><span class="valeur">${valeur}</span><span class="nom">${nom}</span></div>`).join("");
}

function afficherActeurs(resultat) {
  const agents = resultat.simulation.agents;
  const journal = resultat.simulation.journal;
  const dernier = journal[journal.length - 1];
  const moyenne = (cle) => journal.reduce((t, j) => t + (j[cle] || 0), 0) / journal.length;
  const total = (cle) => journal.reduce((t, j) => t + (j[cle] || 0), 0);

  element("n-menages").textContent = nombre(agents.menages) + " groupes";
  element("n-precollecteurs").textContent = nombre(agents.precollecteurs);
  element("n-brigade").textContent = nombre(resultat.parametres_utilises?.effectif_brigade
    ?? resultat.simulation.effectif_brigade ?? 0) + " agents";
  element("n-mairie").textContent = nombre(resultat.camions_disponibles) + " camions";

  element("a-produit").textContent = nombre(moyenne("produit_m3")) + " m³/jour";
  element("a-abonnes").textContent = nombre(dernier.taux_abonnement * 100, 1) + " %";
  element("a-precollecte").textContent = nombre(moyenne("precollecte_m3")) + " m³/jour";
  element("a-verbalisations").textContent = nombre(total("verbalisations"));
  element("a-collecte").textContent = nombre(moyenne("collecte_m3")) + " m³/jour";
  const pannes = total("pannes");
  element("a-pannes").textContent = nombre(pannes) + (pannes > 1 ? " jours" : " jour");
}

element("lancer").addEventListener("click", async () => {
  const bouton = element("lancer");
  const jours = Number(element("jours").value);
  const parametres = { saison: element("saison").checked ? "pluies" : "seche" };
  if (element("sans_brigade").checked) parametres.effectif_brigade = 0;
  bouton.disabled = true;
  element("etat").textContent = "Simulation en cours…";
  try {
    const reponse = await fetch("/api/scenario", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nom: "Simulation", jours, parametres }),
    });
    const resultat = await reponse.json();
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur " + reponse.status);
    afficherActeurs(resultat);
    afficherBilan(resultat.simulation.resume);
    dessinerCourbes(resultat.simulation.journal);
    afficherJournal(resultat.simulation.journal);
    element("resultats").hidden = false;
    element("etat").textContent = `${jours} jours simulés. Le plan de gestion a été recalculé avant.`;
  } catch (erreur) {
    element("etat").textContent = "Erreur : " + erreur.message;
  } finally {
    bouton.disabled = false;
  }
});

element("lancer").click();
