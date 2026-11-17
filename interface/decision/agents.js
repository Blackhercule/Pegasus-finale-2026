/* Gestion des comptes d'agents, réservée à la mairie.

   Tout ce qui vient du serveur est posé avec textContent, jamais en HTML : un nom d'agent
   ne peut pas devenir du code dans la page de la personne qui gère les comptes. C'est
   précisément la page qu'un attaquant viserait. */
"use strict";

const element = (id) => document.getElementById(id);
let jeton = null;

function message(texte, genre) {
  const m = element("message");
  m.textContent = texte;
  m.className = "message " + (genre || "");
  m.hidden = !texte;
}

async function appel(adresse, options = {}) {
  const entetes = { "Content-Type": "application/json" };
  if (jeton) entetes["X-Jeton"] = jeton;
  const reponse = await fetch(adresse, {
    method: options.methode || "GET", headers: entetes,
    body: options.corps ? JSON.stringify(options.corps) : undefined,
  });
  const resultat = await reponse.json().catch(() => ({}));
  if (!reponse.ok) throw new Error(resultat.erreur || "Erreur " + reponse.status);
  return resultat;
}

function cellule(texte, classe) {
  const td = document.createElement("td");
  td.textContent = texte;
  if (classe) td.className = classe;
  return td;
}

async function afficher() {
  const { agents, postes } = await appel("/api/agents");

  const choix = element("poste");
  if (!choix.options.length) {
    for (const [cle, nom] of Object.entries(postes)) {
      const option = document.createElement("option");
      option.value = cle;
      option.textContent = nom;
      choix.append(option);
    }
  }

  const corps = element("agents");
  corps.replaceChildren();
  if (!agents.length) {
    const ligne = document.createElement("tr");
    const td = cellule("Aucun compte individuel pour l'instant. Les quatre comptes de démarrage "
                       + "restent utilisables.", "vide");
    td.colSpan = 5;
    ligne.append(td);
    corps.append(ligne);
    return;
  }
  for (const a of agents) {
    const ligne = document.createElement("tr");
    if (!a.actif) ligne.className = "inactif";
    ligne.append(cellule(a.nom), cellule(a.identifiant, "identifiant"),
                 cellule((postes[a.poste] || a.poste).split(" — ")[0]),
                 cellule(a.actif ? "actif" : "désactivé le " + (a.desactive_le || "").slice(0, 10),
                         a.actif ? "etat-actif" : "etat-inactif"));
    const action = document.createElement("td");
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = a.actif ? "rejeter secondaire" : "secondaire";
    bouton.textContent = a.actif ? "Désactiver" : "Réactiver";
    bouton.addEventListener("click", async () => {
      try {
        await appel(`/api/agents/${a.id}/${a.actif ? "desactiver" : "activer"}`,
                    { methode: "POST", corps: {} });
        message(a.actif ? `${a.nom} n'a plus accès, dès maintenant.` : `${a.nom} a de nouveau accès.`,
                "succes");
        await afficher();
      } catch (e) {
        message(e.message, "erreur");
      }
    });
    action.append(bouton);
    ligne.append(action);
    corps.append(ligne);
  }
}

element("nouveau").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  try {
    const cree = await appel("/api/agents", { methode: "POST", corps: {
      nom: element("nom").value, identifiant: element("identifiant").value,
      poste: element("poste").value, mot_de_passe: element("mot-de-passe").value,
    } });
    element("nouveau").reset();
    message(`Compte créé pour ${cree.nom} (${cree.identifiant}).`, "succes");
    await afficher();
  } catch (e) {
    message(e.message, "erreur");
  } finally {
    element("mot-de-passe").value = "";   // le mot de passe ne reste pas affiché dans la page
  }
});

fetch("/api/session")
  .then((r) => (r.ok ? r.json() : Promise.reject()))
  .then((s) => {
    jeton = s.jeton;
    if (s.poste !== "mairie") {
      message("Seule la mairie gère les comptes des agents.", "erreur");
      element("nouveau").hidden = true;
      return;
    }
    return afficher();
  })
  .catch(() => message("Connexion requise.", "erreur"));
