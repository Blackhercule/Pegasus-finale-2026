// Page de connexion de l'espace des services.
// Elle est servie à l'adresse que l'on a demandée (par exemple /decision/scenarios.html) : une
// fois le mot de passe accepté, il suffit de recharger cette adresse pour arriver à la bonne page.
"use strict";

/* Où chacun travaille. Quelqu'un qui se connecte depuis l'entrée générale ne doit pas tomber
   sur une page qui ne le concerne pas : l'ONEA n'a rien à faire dans les dossiers de
   dépotoirs, et un agent de collecte n'a rien à décider sur les fuites. */
const PAGE_DU_POSTE = {
  mairie: "/decision/dossiers.html",
  brigade: "/decision/dossiers.html",
  collecte: "/decision/dossiers.html",
  onea: "/decision/fuites.html",
};

/* Vrai si l'on arrive par l'entrée générale, et non parce qu'on a demandé une page précise.
   Dans ce second cas on respecte la demande : on recharge l'adresse voulue. */
function entreeGenerale() {
  const chemin = window.location.pathname;
  return chemin === "/decision/" || chemin === "/decision/index.html"
         || chemin === "/decision/connexion.html";
}

document.getElementById("formulaire").addEventListener("submit", async (evenement) => {
  evenement.preventDefault();
  const erreur = document.getElementById("erreur");
  erreur.hidden = true;
  let reponse;
  try {
    reponse = await fetch("/api/connexion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nom: document.getElementById("nom").value,
        mot_de_passe: document.getElementById("mot-de-passe").value,
      }),
    });
  } catch (e) {
    erreur.textContent = "Serveur injoignable.";
    erreur.hidden = false;
    return;
  }
  if (reponse.ok) {
    const session = await reponse.json().catch(() => ({}));
    const destination = PAGE_DU_POSTE[session.poste];
    if (entreeGenerale() && destination) {
      window.location.assign(destination);
    } else {
      window.location.reload();
    }
    return;
  }
  const resultat = await reponse.json().catch(() => ({}));
  document.getElementById("mot-de-passe").value = "";
  erreur.textContent = resultat.erreur || "Connexion impossible.";
  erreur.hidden = false;
});
