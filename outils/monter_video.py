"""Monte la vidéo de démonstration à partir des scènes filmées dans le navigateur.

    node outils/filmer.mjs           (filme les scènes dans /tmp/video)
    python outils/monter_video.py [scènes] [vidéo.mp4]    (les assemble en un seul fichier)

Chaque scène reçoit un bandeau avec sa phrase, et la vidéo s'ouvre et se ferme sur un carton.
Tout est fait avec ffmpeg : aucun service en ligne, aucun montage à la main.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

# Dans l'ordre imposé par l'énoncé : « du signalement à la tournée, puis un changement de
# paramètres et le plan recalculé ».
SCENES = [
    ("01-signaler", "1. Un habitant signale un dépotoir depuis son téléphone",
     "Accueil parlé en mooré, mesure du tas, message vocal — sans compte, et même sans réseau"),
    ("02-sans-gps", "Sans GPS : il choisit un lieu connu",
     "Marchés, écoles, centres de santé ; la mairie saura que la position est approximative"),
    ("03-pieges", "2. Le jury injecte 42 signalements piégés",
     "Chacun est écarté avec son motif, aucun n'entre dans le plan, le serveur tient"),
    ("04-chaine", "3. Le signalement ouvre un dossier qui passe de poste en poste",
     "Mairie, brigade Laabal, mairie : chaque passage est daté et signé"),
    ("05-tournee", "4. Jusqu'à la tournée : le camion passe par le dépotoir",
     "Points de regroupement et tournées optimisées, tracées rue par rue"),
    ("06-parametres", "5. Le jury change les paramètres : 8 camions en panne, saison des pluies",
     "Le plan se recalcule en quelques secondes et affiche ses propres contrôles de cohérence"),
    ("07-scenarios", "6. Comparer des scénarios",
     "Camions, fréquence de passage, abonnements : chaque levier chiffré côte à côte"),
    ("08-simulation", "7. Simulation multi-agents de la filière",
     "Ménages, pré-collecteurs, brigade Laabal et mairie, un jour par pas de temps"),
]

TITRE = ("Assainissement de Ouaga", "Du signalement d'un dépotoir au plan de gestion de la ville",
         "Équipe PEGASUS — Université Joseph Ki-Zerbo")
FIN = ("Code libre, données ouvertes", "AGPL-3.0 · OpenStreetMap (ODbL) · aucune dépendance à Internet",
       "175 tests automatisés · déploiement en une commande")

# Une scène qui attend un long calcul commence AVANT_RESULTAT secondes avant que le résultat
# s'affiche (moment noté par filmer.mjs dans coupes.json) : on ne montre pas l'attente.
AVANT_RESULTAT = 2.0

POLICE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
POLICE_GRASSE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LARGEUR, HAUTEUR = 1280, 720
# Bleu marine et jaune des portails de l'administration, comme l'interface.
VERT, OR = "0x1e2455", "0xfcd116"


def echapper(texte: str) -> str:
    """ffmpeg lit le texte dans un filtre : les deux-points et les apostrophes doivent être protégés."""
    return texte.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def carton(chemin: str, lignes, secondes: float = 3.0) -> None:
    """Un carton de texte, sur fond bleu marine."""
    dessins = []
    tailles = (54, 30, 24)
    positions = (HAUTEUR // 2 - 90, HAUTEUR // 2 - 10, HAUTEUR // 2 + 50)
    for texte, taille, y in zip(lignes, tailles, positions):
        dessins.append(
            f"drawtext=fontfile={POLICE_GRASSE if taille > 40 else POLICE}:"
            f"text='{echapper(texte)}':fontcolor={'white' if taille > 40 else '0xd8e2dc'}:"
            f"fontsize={taille}:x=(w-text_w)/2:y={y}")
    dessins.append(f"drawbox=x=0:y={HAUTEUR // 2 + 100}:w=iw:h=4:color={OR}@1:t=fill")
    lancer(["ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c={VERT}:s={LARGEUR}x{HAUTEUR}:d={secondes}:r=25",
            "-vf", ",".join(dessins), "-pix_fmt", "yuv420p", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "23", chemin])


def scene(source: str, chemin: str, titre: str, sous_titre: str, debut: float = 0) -> None:
    """Met la scène au format, puis pose le bandeau de texte en bas. `debut` coupe l'attente."""
    bandeau = HAUTEUR - 112
    filtres = [
        # La scène garde ses proportions ; le reste de l'image est rempli en bleu marine.
        f"scale={LARGEUR}:{HAUTEUR}:force_original_aspect_ratio=decrease",
        f"pad={LARGEUR}:{HAUTEUR}:(ow-iw)/2:(oh-ih)/2:color={VERT}",
        f"drawbox=x=0:y={bandeau}:w=iw:h=112:color=black@0.72:t=fill",
        f"drawbox=x=0:y={bandeau}:w=iw:h=4:color={OR}@1:t=fill",
        f"drawtext=fontfile={POLICE_GRASSE}:text='{echapper(titre)}':fontcolor=white:"
        f"fontsize=27:x=40:y={bandeau + 26}",
        f"drawtext=fontfile={POLICE}:text='{echapper(sous_titre)}':fontcolor=0xdde1f2:"
        f"fontsize=20:x=40:y={bandeau + 66}",
        "fps=25", "format=yuv420p",
    ]
    lancer(["ffmpeg", "-y", "-ss", f"{debut:.2f}", "-i", source, "-vf", ",".join(filtres),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an", chemin])


def lancer(commande) -> None:
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        sys.exit(resultat.stderr[-1500:])


def principal():
    source = sys.argv[1] if len(sys.argv) > 1 else "/tmp/video"
    sortie = sys.argv[2] if len(sys.argv) > 2 else "/tmp/Demonstration-Assainissement-de-Ouaga.mp4"
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg est nécessaire.")
    travail = tempfile.mkdtemp(prefix="montage-")
    morceaux = []

    debut = os.path.join(travail, "00-titre.mp4")
    carton(debut, TITRE, 5.0)
    morceaux.append(debut)

    for nom, titre, sous_titre in SCENES:
        dossier = os.path.join(source, nom)
        fichiers = ([f for f in sorted(os.listdir(dossier)) if f.endswith(".webm")]
                    if os.path.isdir(dossier) else [])
        if not fichiers:
            print(f"scène absente, ignorée : {nom}")
            continue
        chemin = os.path.join(travail, nom + ".mp4")
        debut = 0.0
        coupes = os.path.join(dossier, "coupes.json")
        if os.path.exists(coupes):
            with open(coupes, encoding="utf-8") as f:
                debut = max(0.0, float(json.load(f)["resultat"]) - AVANT_RESULTAT)
        scene(os.path.join(dossier, fichiers[0]), chemin, titre, sous_titre, debut)
        morceaux.append(chemin)
        print("monté :", nom)

    fin = os.path.join(travail, "99-fin.mp4")
    carton(fin, FIN, 6.0)
    morceaux.append(fin)

    liste = os.path.join(travail, "morceaux.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for chemin in morceaux:
            f.write(f"file '{chemin}'\n")
    lancer(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", liste,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", sortie])
    duree = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", sortie], capture_output=True, text=True).stdout.strip()
    print(f"\nVidéo écrite : {sortie} ({float(duree):.0f} s, "
          f"{os.path.getsize(sortie) / 1e6:.1f} Mo)")
    shutil.rmtree(travail, ignore_errors=True)


if __name__ == "__main__":
    principal()
