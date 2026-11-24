/* Gestion de cave — petits comportements de confort.
   Tout fonctionne aussi sans JavaScript : le serveur refait toujours les calculs. */
(function () {
  "use strict";

  function formaterFcfa(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " F";
  }

  function entier(valeur) {
    var n = parseInt(valeur, 10);
    return isNaN(n) || n < 0 ? 0 : n;
  }

  // ---- Boutons « Imprimer » ----
  document.querySelectorAll("[data-imprimer]").forEach(function (bouton) {
    bouton.addEventListener("click", function () { window.print(); });
  });

  // ---- Grille des produits : boutons + / −, recherche, total ----
  var formulaire = document.querySelector("[data-grille-produits]");
  if (formulaire) {
    var lignes = Array.prototype.slice.call(formulaire.querySelectorAll(".produit-ligne"));

    function typeVente() {
      var coche = formulaire.querySelector("input[name=type_vente]:checked");
      return coche ? coche.value : "detail";
    }

    function recalculer() {
      var total = 0, caisses = 0, type = typeVente();
      lignes.forEach(function (ligne) {
        var champ = ligne.querySelector("input[type=number]");
        var q = entier(champ.value);
        var prix = entier(ligne.getAttribute(type === "gros" ? "data-prix-gros" : "data-prix-detail"));
        var affichePrix = ligne.querySelector("[data-prix]");
        if (affichePrix) { affichePrix.textContent = formaterFcfa(prix) + " la caisse"; }
        total += q * prix;
        caisses += q;
        ligne.classList.toggle("choisi", q > 0);
      });
      var zoneTotal = formulaire.querySelector("[data-total]");
      if (zoneTotal) { zoneTotal.textContent = formaterFcfa(total); }
      var zoneCaisses = formulaire.querySelector("[data-caisses]");
      if (zoneCaisses) { zoneCaisses.textContent = caisses + " caisse" + (caisses > 1 ? "s" : ""); }
      var verse = formulaire.querySelector("input[name=montant_verse]");
      if (verse) { verse.max = total; }
    }

    lignes.forEach(function (ligne) {
      var champ = ligne.querySelector("input[type=number]");
      ligne.querySelectorAll("[data-pas]").forEach(function (bouton) {
        bouton.addEventListener("click", function () {
          var max = champ.max ? entier(champ.max) : Infinity;
          var nouveau = entier(champ.value) + parseInt(bouton.getAttribute("data-pas"), 10);
          champ.value = Math.max(0, Math.min(max, nouveau)) || "";
          recalculer();
        });
      });
      champ.addEventListener("input", recalculer);
    });

    formulaire.querySelectorAll("input[name=type_vente]").forEach(function (radio) {
      radio.addEventListener("change", recalculer);
    });

    // Recherche d'un produit par son nom
    var recherche = formulaire.querySelector("[data-recherche]");
    if (recherche) {
      recherche.addEventListener("input", function () {
        var texte = recherche.value.trim().toLowerCase();
        lignes.forEach(function (ligne) {
          var nom = ligne.getAttribute("data-nom").toLowerCase();
          ligne.classList.toggle("cache", texte !== "" && nom.indexOf(texte) === -1);
        });
      });
    }

    // Comptant ou crédit : on n'affiche le montant versé que pour un crédit
    var zoneCredit = formulaire.querySelector("[data-zone-credit]");
    function majPaiement() {
      var coche = formulaire.querySelector("input[name=paiement]:checked");
      if (zoneCredit) { zoneCredit.classList.toggle("cache", !coche || coche.value !== "credit"); }
    }
    formulaire.querySelectorAll("input[name=paiement]").forEach(function (radio) {
      radio.addEventListener("change", majPaiement);
    });

    // Nouveau client : on vide la liste déroulante si on tape un nom, et inversement
    var choixClient = formulaire.querySelector("select[name=client]");
    var nouveauClient = formulaire.querySelector("input[name=nouveau_client_nom]");
    if (choixClient && nouveauClient) {
      nouveauClient.addEventListener("input", function () { if (nouveauClient.value) { choixClient.value = ""; } });
      choixClient.addEventListener("change", function () { if (choixClient.value) { nouveauClient.value = ""; } });
    }

    majPaiement();
    recalculer();
  }

  // ---- Bulles d'information sur les graphiques ----
  var bulle = null;
  function montrerBulle(element, x, y) {
    if (!bulle) {
      bulle = document.createElement("div");
      bulle.className = "bulle";
      document.body.appendChild(bulle);
    }
    bulle.textContent = "";
    var titre = document.createElement("div");
    titre.textContent = element.getAttribute("data-titre");
    bulle.appendChild(titre);
    var total = document.createElement("strong");
    total.textContent = element.getAttribute("data-total");
    bulle.appendChild(total);
    [["detail", "Détail", "var(--serie-detail)"], ["gros", "Gros", "var(--serie-gros)"]].forEach(function (serie) {
      var valeur = element.getAttribute("data-" + serie[0]);
      if (valeur === null) { return; }
      var ligne = document.createElement("div");
      var trait = document.createElement("span");
      trait.className = "trait";
      trait.style.background = serie[2];
      ligne.appendChild(trait);
      ligne.appendChild(document.createTextNode(valeur + " — " + serie[1]));
      bulle.appendChild(ligne);
    });
    bulle.style.display = "block";
    var largeur = bulle.offsetWidth, hauteur = bulle.offsetHeight;
    var gauche = Math.min(window.innerWidth - largeur - 8, Math.max(8, x - largeur / 2));
    var haut = y - hauteur - 12;
    if (haut < 8) { haut = y + 16; }
    bulle.style.left = gauche + "px";
    bulle.style.top = haut + "px";
  }
  function cacherBulle() { if (bulle) { bulle.style.display = "none"; } }

  document.querySelectorAll("[data-titre]").forEach(function (element) {
    element.addEventListener("pointermove", function (e) { montrerBulle(element, e.clientX, e.clientY); });
    element.addEventListener("pointerleave", cacherBulle);
    element.addEventListener("focus", function () {
      var r = element.getBoundingClientRect();
      montrerBulle(element, r.left + r.width / 2, r.top);
    });
    element.addEventListener("blur", cacherBulle);
  });
})();
