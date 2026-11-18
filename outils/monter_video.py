"""Monte la vidéo de démonstration à partir des scènes filmées dans le navigateur.

    node outils/filmer.mjs           (filme les scènes dans /tmp/video)
    python outils/monter_video.py [scènes] [vidéo.mp4] [--voix modele.onnx] [--sans-musique]

Avec --voix, une voix de synthèse (Piper, hors ligne) lit le bandeau de chaque scène, sans le
changer. La musique de fond est fabriquée par outils/musique_de_fond.py ; elle baisse d'elle-même
quand la voix parle.

Chaque scène reçoit un bandeau avec sa phrase, et la vidéo s'ouvre et se ferme sur un carton.
Tout est fait avec ffmpeg : aucun service en ligne, aucun montage à la main.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# Dans l'ordre imposé par l'énoncé : « du signalement à la tournée, puis un changement de
# paramètres et le plan recalculé ».
SCENES = [
    ("00-accueil", "Une plateforme pour toute la population",
     "Signaler sans savoir lire, trouver son collecteur, voir les quartiers les plus propres"),
    ("01-signaler", "1. Un habitant signale un dépotoir depuis son téléphone",
     "Accueil parlé en mooré, menu 1-2-3, mesure du tas, message vocal — sans compte, même sans réseau"),
    ("02-appel", "Touche 2 ou 3 : l'habitant appelle la mairie",
     "L'agent décroche dans la plateforme et voit la position de l'habitant en direct"),
    ("04-pieges", "2. Le jury injecte 42 signalements piégés",
     "Chacun est écarté avec son motif, aucun n'entre dans le plan, le serveur tient"),
    ("05-verifier", "3. La mairie vérifie le signalement",
     "Le nom de l'agent qui a vérifié reste attaché à sa décision"),
    ("06-chaine", "4. Le dossier passe de poste en poste",
     "Photo en grand, position sur la carte, et pour chaque étape : qui a fait quoi, et quand"),
    ("065-zones", "Zones à risque : où agir en premier",
     "Carte thermique, quartiers les plus touchés, caniveaux à curer avant la saison des pluies"),
    ("07-tournee", "5. Jusqu'à la tournée : le camion passe par le dépotoir",
     "Points de regroupement et tournées optimisées, tracées rue par rue"),
    ("08-parametres", "6. Le jury change les paramètres : 8 camions en panne, saison des pluies",
     "Le plan se recalcule en quelques secondes et affiche ses contrôles de cohérence"),
    ("09-scenarios", "7. Comparer des scénarios",
     "Camions, fréquence de passage, abonnements : chaque levier chiffré côte à côte"),
    ("10-simulation", "8. Simulation multi-agents de la filière",
     "Ménages, pré-collecteurs, brigade Laabal et mairie, un jour par pas de temps"),
]

TITRE = ("Assainissement de Ouaga", "Du signalement d'un dépotoir au plan de gestion de la ville",
         "Équipe PEGASUS — Université Joseph Ki-Zerbo")
FIN = ("Code libre, données ouvertes", "AGPL-3.0 · OpenStreetMap (ODbL) · aucune dépendance à Internet",
       "279 tests automatisés · déploiement en une commande")

# Une scène qui attend un long calcul commence AVANT_RESULTAT secondes avant que le résultat
# s'affiche (moment noté par filmer.mjs dans coupes.json) : on ne montre pas l'attente.
AVANT_RESULTAT = 2.0

# Début coupé (secondes) des scènes de carte : la connexion y a déjà été montrée (scènes 3 et
# 4), et la page clignote le temps que la barre se pose.
COUPER_LE_DEBUT = {"07-tournee": 4.0, "08-parametres": 4.0}

# L'énoncé demande 3 minutes : les scènes où l'on tape et où l'on attend sont accélérées
# (1,5 = une fois et demie plus vite). Les gestes restent lisibles ; rien n'est coupé.
ACCELERER = {"00-accueil": 1.35, "01-signaler": 1.35, "02-appel": 1.25, "04-pieges": 1.5,
             "05-verifier": 1.2, "06-chaine": 1.7, "065-zones": 1.1, "07-tournee": 1.7,
             "08-parametres": 1.9, "09-scenarios": 1.8, "10-simulation": 1.4}

POLICE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
POLICE_GRASSE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LARGEUR, HAUTEUR = 1280, 720
# Vert foncé et vert clair, comme l'interface depuis C11.
VERT, OR = "0x0b5e47", "0x8ee0bd"


def echapper(texte: str) -> str:
    """ffmpeg lit le texte dans un filtre : les deux-points et les apostrophes doivent être protégés."""
    return texte.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def carton(chemin: str, lignes, secondes: float = 3.0) -> None:
    """Un carton de texte, sur fond vert foncé."""
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


def scene(source: str, chemin: str, titre: str, sous_titre: str, debut: float = 0,
          vitesse: float = 1.0) -> None:
    """Met la scène au format, puis pose le bandeau de texte en bas. `debut` coupe l'attente,
    `vitesse` accélère la scène (le bandeau, lui, est posé après : il reste net)."""
    bandeau = HAUTEUR - 112
    filtres = [f"setpts=PTS/{vitesse}",
        # La scène garde ses proportions ; le reste de l'image est rempli en vert foncé.
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


def pour_la_voix(*lignes) -> str:
    """Le texte du bandeau, tel que la voix doit le lire : mêmes mots, ponctuation parlée.

    Le numéro de scène (« 1. ») n'est pas lu, les tirets et les points médians deviennent des
    pauses, et quelques sigles sont épelés pour que la voix ne les prononce pas comme un mot."""
    texte = ". ".join(re.sub(r"^\d+\. ", "", ligne) for ligne in lignes) + "."
    for ecrit, dit in ((" — ", ", "), (" · ", ", "), (" : ", ", "), ("GPS", "gé pé esse"),
                       ("AGPL-3.0", "A G P L 3"), ("(ODbL)", ""), ("PEGASUS", "Pégasus"),
                       ("Ki-Zerbo", "Ki Zerbo")):
        texte = texte.replace(ecrit, dit)
    return texte


def dire(texte: str, modele: str, chemin: str) -> float:
    """Fait lire le texte par Piper et renvoie la durée de l'enregistrement, en secondes."""
    piper = shutil.which("piper") or os.path.join(os.path.dirname(sys.executable), "piper")
    resultat = subprocess.run([piper, "-m", modele, "-f", chemin], input=texte, text=True,
                              capture_output=True)
    if resultat.returncode != 0:
        sys.exit("Piper a échoué : " + resultat.stderr[-800:])
    return duree(chemin)


def duree(chemin: str) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", chemin], capture_output=True, text=True).stdout)


# La voix commence un peu après le début de la scène, et la musique ne descend que de quoi
# laisser la voix au premier plan.
DECALAGE_VOIX = 0.6
VOLUME_MUSIQUE = 0.32


def bande_son(travail, paroles, total, musique, sortie):
    """Assemble la voix (chaque phrase à sa place) et la musique, baissée sous la voix."""
    entrees, filtres, etiquettes = [], [], []
    for numero, (chemin, debut) in enumerate(paroles):
        entrees += ["-i", chemin]
        ms = int((debut + DECALAGE_VOIX) * 1000)
        filtres.append(f"[{numero}:a]aresample=44100,aformat=channel_layouts=stereo,"
                       f"adelay={ms}|{ms}[v{numero}]")
        etiquettes.append(f"[v{numero}]")
    voix = (f"{''.join(etiquettes)}amix=inputs={len(etiquettes)}:normalize=0,"
            f"apad=whole_dur={total:.2f},atrim=0:{total:.2f}" if etiquettes
            else f"anullsrc=r=44100:cl=stereo,atrim=0:{total:.2f}")
    if musique:
        chemin_musique = os.path.join(travail, "musique.wav")
        lancer([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "musique_de_fond.py"), chemin_musique, f"{total:.2f}"])
        entrees += ["-i", chemin_musique]
        m = len(paroles)
        filtres.append(voix + ",asplit=2[voix][cle]")
        filtres.append(f"[{m}:a]volume={VOLUME_MUSIQUE}[musique]")
        # La voix sert de « clé » : quand elle parle, la musique est comprimée (baissée).
        filtres.append("[musique][cle]sidechaincompress=threshold=0.02:ratio=6:attack=30:"
                       "release=500[sous]")
        filtres.append("[sous][voix]amix=inputs=2:normalize=0,alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[sortie]")
    else:
        filtres.append(voix + "[sortie]")
    lancer(["ffmpeg", "-y", *entrees, "-filter_complex", ";".join(filtres), "-map", "[sortie]",
            "-c:a", "pcm_s16le", sortie])


def lancer(commande) -> None:
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        sys.exit(resultat.stderr[-1500:])


def principal():
    arguments = argparse.ArgumentParser(description="Monte la vidéo de démonstration.")
    arguments.add_argument("source", nargs="?", default="/tmp/video")
    arguments.add_argument("sortie", nargs="?", default="/tmp/Demonstration-Assainissement-de-Ouaga.mp4")
    arguments.add_argument("--voix", help="modèle de voix Piper (.onnx) qui lit les bandeaux")
    arguments.add_argument("--sans-musique", action="store_true")
    options = arguments.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg est nécessaire.")
    travail = tempfile.mkdtemp(prefix="montage-")
    morceaux, paroles, position = [], [], 0.0

    def ajouter(chemin, texte_lu):
        """Range un morceau monté et, si la voix est demandée, sa phrase à son instant."""
        nonlocal position
        if texte_lu is not None:
            paroles.append((texte_lu, position))
        morceaux.append(chemin)
        position += duree(chemin)

    def voix_du_carton(nom, lignes, secondes):
        """Un carton dure au moins le temps que la voix le lise."""
        if not options.voix:
            return secondes, None
        chemin = os.path.join(travail, nom + ".wav")
        return max(secondes, dire(pour_la_voix(*lignes), options.voix, chemin) + 0.9), chemin

    secondes, lu = voix_du_carton("00-titre", TITRE, 4.0)
    debut_video = os.path.join(travail, "00-titre.mp4")
    carton(debut_video, TITRE, secondes)
    ajouter(debut_video, lu)

    for nom, titre, sous_titre in SCENES:
        dossier = os.path.join(options.source, nom)
        fichiers = ([f for f in sorted(os.listdir(dossier)) if f.endswith((".webm", ".mp4"))]
                    if os.path.isdir(dossier) else [])
        if not fichiers:
            print(f"scène absente, ignorée : {nom}")
            continue
        chemin = os.path.join(travail, nom + ".mp4")
        coupe = COUPER_LE_DEBUT.get(nom, 0.0)
        coupes = os.path.join(dossier, "coupes.json")
        if os.path.exists(coupes):
            with open(coupes, encoding="utf-8") as f:
                coupe = max(0.0, float(json.load(f)["resultat"]) - AVANT_RESULTAT)
        scene(os.path.join(dossier, fichiers[0]), chemin, titre, sous_titre, coupe,
              ACCELERER.get(nom, 1.0))
        lu = None
        if options.voix:
            lu = os.path.join(travail, nom + ".wav")
            parole = dire(pour_la_voix(titre, sous_titre), options.voix, lu)
            if parole + DECALAGE_VOIX + 0.5 > duree(chemin):
                print(f"attention : la voix de {nom} ({parole:.1f} s) dépasse la scène")
        ajouter(chemin, lu)
        print("monté :", nom)

    secondes, lu = voix_du_carton("99-fin", FIN, 5.0)
    fin_video = os.path.join(travail, "99-fin.mp4")
    carton(fin_video, FIN, secondes)
    ajouter(fin_video, lu)

    liste = os.path.join(travail, "morceaux.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for chemin in morceaux:
            f.write(f"file '{chemin}'\n")
    image = os.path.join(travail, "image.mp4")
    lancer(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", liste,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", image])
    total = duree(image)
    if options.voix or not options.sans_musique:
        son = os.path.join(travail, "son.wav")
        bande_son(travail, paroles, total, not options.sans_musique, son)
        lancer(["ffmpeg", "-y", "-i", image, "-i", son, "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                "-movflags", "+faststart", options.sortie])
    else:
        shutil.copy(image, options.sortie)
    print(f"\nVidéo écrite : {options.sortie} ({duree(options.sortie):.0f} s, "
          f"{os.path.getsize(options.sortie) / 1e6:.1f} Mo)")
    shutil.rmtree(travail, ignore_errors=True)


if __name__ == "__main__":
    principal()
