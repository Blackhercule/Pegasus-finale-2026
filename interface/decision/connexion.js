// Page de connexion de l'espace des services.
// Elle est servie à l'adresse que l'on a demandée (par exemple /decision/scenarios.html) : une
// fois le mot de passe accepté, il suffit de recharger cette adresse pour arriver à la bonne page.
"use strict";

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
    window.location.reload();
    return;
  }
  const resultat = await reponse.json().catch(() => ({}));
  document.getElementById("mot-de-passe").value = "";
  erreur.textContent = resultat.erreur || "Connexion impossible.";
  erreur.hidden = false;
});
