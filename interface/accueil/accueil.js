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
