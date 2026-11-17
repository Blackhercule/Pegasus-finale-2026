/* La petite carte du détail d'un dossier (T23, partie 2) : la position avec une épingle, comme
 * une position envoyée dans une messagerie, et un lien vers la grande carte centrée dessus.
 *
 *     MiniCarte.monter(conteneur, longitude, latitude, lien)
 *
 * Les pages refont leur détail à chaque action : une carte dont le cadre a disparu de la page
 * est retirée (map.remove()), sinon chaque clic laisserait un contexte WebGL ouvert.
 */
"use strict";

const MiniCarte = (function () {
  let cartes = [];

  function nettoyer(conteneur) {
    cartes = cartes.filter((c) => {
      const perimee = !document.contains(c.getContainer()) || c.getContainer() === conteneur;
      if (perimee) c.remove();
      return !perimee;
    });
  }

  function monter(conteneur, longitude, latitude, lien) {
    if (!conteneur) return;
    nettoyer(conteneur);
    const lon = Number(longitude), lat = Number(latitude);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      conteneur.textContent = "Position inconnue.";
      return;
    }
    if (lien) lien.href = "/decision/?lon=" + lon.toFixed(6) + "&lat=" + lat.toFixed(6);
    if (typeof maplibregl === "undefined") {   // bibliothèque absente : on ne casse pas le détail
      conteneur.textContent = "Carte indisponible.";
      return;
    }
    const carte = FondCarte.carte(conteneur, [lon, lat], 15, {
      scrollZoom: false,          // la molette fait défiler la page, pas la carte
      dragRotate: false, pitchWithRotate: false,
    });
    carte.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    new maplibregl.Marker({ color: "#c8102e" }).setLngLat([lon, lat]).addTo(carte);
    cartes.push(carte);
  }

  /* « Me déconnecter » : on retire les cartes AVANT que la déconnexion parte (écoute en phase
     de capture, donc avant le bouton lui-même). Sinon les tuiles encore en chemin arrivent
     sans session, et le navigateur affiche une erreur dans la console. */
  document.addEventListener("click", (e) => {
    if (e.target instanceof Element && e.target.closest(".barre__changer")) {
      cartes.forEach((c) => c.remove());
      cartes = [];
    }
  }, true);

  return { monter };
})();
