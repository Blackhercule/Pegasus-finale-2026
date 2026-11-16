"""Monte la vidéo de démonstration à partir des scènes filmées dans le navigateur.

    node outils/filmer.mjs           (filme les scènes dans /tmp/video)
    python outils/monter_video.py    (les assemble en un seul fichier)

Chaque scène reçoit un bandeau avec sa phrase, et la vidéo s'ouvre et se ferme sur un carton.
Tout est fait avec ffmpeg : aucun service en ligne, aucun montage à la main.
"""

import os
import shutil
import subprocess
import sys
import tempfile

SCENES = [
    ("01-carte", "La carte de décision, servie par notre propre machine",
     "Aucune connexion à Internet : fond de carte, données et calculs sont sur le poste"),
    ("02-signaler", "Signaler un dépotoir depuis un téléphone",
     "Guidage parlé en mooré, mesure du tas, message vocal — la page marche sans réseau"),
    ("03-chaine", "Un signalement ouvre un dossier qui passe de poste en poste",
     "Mairie, brigade Laabal, puis équipe de collecte : chaque passage est daté et signé"),
    ("04-pieges", "Le jury injecte 42 signalements piégés",
     "Chacun est écarté avec son motif, et le serveur ne tombe jamais"),
    ("05-plan", "Le jury change les paramètres : 14 camions en panne, saison des pluies",
     "Le plan se recalcule en 5 secondes et nomme les arrêts qu'il ne peut plus desservir"),
    ("06-scenarios", "Comparer des scénarios",
     "Ajouter des camions ne suffit pas : il faut aussi la fréquence et les abonnements"),
    ("07-simulation", "Simulation de la filière, un jour par pas de temps",
     "Ménages, pré-collecteurs, brigade Laabal et mairie"),
]

TITRE = ("Assainissement de Ouaga", "Outil libre d'aide à la décision",
         "Équipe PEGASUS — Université Joseph Ki-Zerbo")
FIN = ("Code libre, données ouvertes", "github.com/Blackhercule/Pegasus-finale-2026",
       "64 tests automatisés · aucune dépendance à Internet")

POLICE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
POLICE_GRASSE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LARGEUR, HAUTEUR = 1280, 720
VERT, OR = "0x12302a", "0xb8862b"


def echapper(texte: str) -> str:
    """ffmpeg lit le texte dans un filtre : les deux-points et les apostrophes doivent être protégés."""
    return texte.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def carton(chemin: str, lignes, secondes: float = 3.0) -> None:
    """Un carton de texte, sur fond vert."""
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


def scene(source: str, chemin: str, titre: str, sous_titre: str) -> None:
    """Met la scène au format, puis pose le bandeau de texte en bas."""
    bandeau = HAUTEUR - 112
    filtres = [
        # La scène garde ses proportions ; le reste de l'image est rempli en vert.
        f"scale={LARGEUR}:{HAUTEUR}:force_original_aspect_ratio=decrease",
        f"pad={LARGEUR}:{HAUTEUR}:(ow-iw)/2:(oh-ih)/2:color={VERT}",
        f"drawbox=x=0:y={bandeau}:w=iw:h=112:color=black@0.72:t=fill",
        f"drawbox=x=0:y={bandeau}:w=iw:h=4:color={OR}@1:t=fill",
        f"drawtext=fontfile={POLICE_GRASSE}:text='{echapper(titre)}':fontcolor=white:"
        f"fontsize=27:x=40:y={bandeau + 26}",
        f"drawtext=fontfile={POLICE}:text='{echapper(sous_titre)}':fontcolor=0xc9d6cf:"
        f"fontsize=20:x=40:y={bandeau + 66}",
        "fps=25", "format=yuv420p",
    ]
    lancer(["ffmpeg", "-y", "-i", source, "-vf", ",".join(filtres),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an", chemin])


def lancer(commande) -> None:
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        sys.exit(resultat.stderr[-1500:])


def principal():
    source = sys.argv[1] if len(sys.argv) > 1 else "/tmp/video"
    sortie = sys.argv[2] if len(sys.argv) > 2 else "/tmp/demonstration.mp4"
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg est nécessaire.")
    travail = tempfile.mkdtemp(prefix="montage-")
    morceaux = []

    debut = os.path.join(travail, "00-titre.mp4")
    carton(debut, TITRE, 3.5)
    morceaux.append(debut)

    for nom, titre, sous_titre in SCENES:
        dossier = os.path.join(source, nom)
        fichiers = [f for f in sorted(os.listdir(dossier))] if os.path.isdir(dossier) else []
        if not fichiers:
            print(f"scène absente, ignorée : {nom}")
            continue
        chemin = os.path.join(travail, nom + ".mp4")
        scene(os.path.join(dossier, fichiers[0]), chemin, titre, sous_titre)
        morceaux.append(chemin)
        print("monté :", nom)

    fin = os.path.join(travail, "99-fin.mp4")
    carton(fin, FIN, 4.0)
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
