"""Fabrique la musique de fond de la vidéo : une boucle calme, entièrement synthétisée ici.

    python outils/musique_de_fond.py sortie.wav [secondes]

Aucun morceau n'est emprunté : chaque son est calculé par ce fichier (sinusoïdes et bruit
filtré). La musique est donc à nous, publiée sous la même licence que le code, et la vidéo ne
risque aucun blocage pour droits d'auteur.

Composition : 82 battements par minute, quatre accords (la mineur 7, fa majeur 7, do majeur 7,
sol 6) de deux mesures chacun ; une nappe douce, une basse, un piano qui égrène l'accord, une
grosse caisse feutrée et un léger charleston.
"""

import sys
import wave

import numpy as np

TAUX = 44100
TEMPO = 82
TEMPS = 60 / TEMPO                       # durée d'un battement, en secondes

# Les accords, en numéros de notes MIDI (60 = do du milieu du piano).
ACCORDS = [
    [57, 60, 64, 67],                    # la mineur 7
    [53, 57, 60, 64],                    # fa majeur 7
    [48, 52, 55, 59],                    # do majeur 7
    [55, 59, 62, 64],                    # sol 6
]
BATTEMENTS_PAR_ACCORD = 8                # deux mesures de quatre temps


def frequence(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def enveloppe(n, attaque, extinction):
    """Monte doucement, puis s'éteint : évite les clics au début et à la fin d'une note."""
    t = np.arange(n) / TAUX
    montee = np.clip(t / attaque, 0, 1)
    descente = np.exp(-t / extinction)
    return montee * descente


def nappe(note, n):
    """Son tenu et doux : trois harmoniques, légèrement désaccordées pour qu'il respire."""
    t = np.arange(n) / TAUX
    f = frequence(note)
    son = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2.003 * f * t)
           + 0.12 * np.sin(2 * np.pi * 3.01 * f * t))
    volume = np.clip(t / 1.2, 0, 1) * np.clip((n / TAUX - t) / 1.0, 0, 1)
    return son * volume


def piano(note, n):
    """Note frappée qui s'éteint : sinusoïde et son octave, attaque rapide."""
    t = np.arange(n) / TAUX
    f = frequence(note)
    son = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    return son * enveloppe(n, 0.005, 0.6)


def grosse_caisse(n):
    t = np.arange(n) / TAUX
    hauteur = 110 * np.exp(-t * 18) + 45          # un « boum » qui descend
    phase = 2 * np.pi * np.cumsum(hauteur) / TAUX
    return np.sin(phase) * np.exp(-t * 9)


def charleston(n, hasard):
    bruit = hasard.standard_normal(n)
    aigu = bruit - np.convolve(bruit, np.ones(8) / 8, mode="same")   # on garde les aigus
    aigu = np.convolve(aigu, np.ones(3) / 3, mode="same")            # sans les plus stridents
    return aigu * enveloppe(n, 0.003, 0.02)                          # attaque douce, bref


def poser(piste, son, debut):
    """Ajoute un son dans la piste à partir de l'échantillon `debut`, sans déborder."""
    fin = min(len(piste), debut + len(son))
    if debut < fin:
        piste[debut:fin] += son[:fin - debut]


def composer(secondes):
    hasard = np.random.default_rng(2026)                 # même musique à chaque fois
    n = int(secondes * TAUX)
    gauche, droite = np.zeros(n), np.zeros(n)
    battement = int(TEMPS * TAUX)
    nb_battements = n // battement + 1
    for b in range(nb_battements):
        debut = b * battement
        accord = ACCORDS[(b // BATTEMENTS_PAR_ACCORD) % len(ACCORDS)]
        if b % BATTEMENTS_PAR_ACCORD == 0:              # nouvel accord : nappe et basse
            duree = BATTEMENTS_PAR_ACCORD * battement
            for i, note in enumerate(accord):
                son = 0.07 * nappe(note, duree)
                poser(gauche if i % 2 else droite, son, debut)
                poser(droite if i % 2 else gauche, 0.6 * son, debut)
            basse = 0.22 * nappe(accord[0] - 12, duree)
            poser(gauche, basse, debut); poser(droite, basse, debut)
        # Le piano égrène l'accord, une note par demi-temps, en montant puis en descendant.
        for demi in range(2):
            ordre = [0, 1, 2, 3, 2, 1][(2 * b + demi) % 6]
            note = accord[ordre] + 12
            son = 0.09 * piano(note, int(1.2 * TAUX))
            pos = debut + demi * battement // 2
            poser(gauche, son * (0.6 + 0.4 * (ordre % 2)), pos)
            poser(droite, son * (1.0 - 0.4 * (ordre % 2)), pos)
        # Batterie feutrée : grosse caisse aux temps 1 et 3, charleston à chaque demi-temps.
        if b % 2 == 0:
            boum = 0.35 * grosse_caisse(int(0.4 * TAUX))
            poser(gauche, boum, debut); poser(droite, boum, debut)
        for demi in range(2):
            tss = 0.012 * charleston(int(0.08 * TAUX), hasard)
            pos = debut + demi * battement // 2
            poser(gauche, tss, pos); poser(droite, 0.8 * tss, pos)
    stereo = np.stack([gauche, droite], axis=1)
    # Fondu à l'entrée et à la sortie, puis volume ramené sous le maximum.
    fondu = np.ones(n)
    entree, sortie = int(2 * TAUX), int(4 * TAUX)
    fondu[:entree] = np.linspace(0, 1, entree)
    fondu[-sortie:] = np.linspace(1, 0, sortie)
    stereo *= fondu[:, None]
    return stereo / np.max(np.abs(stereo)) * 0.8


def ecrire(chemin, stereo):
    donnees = (stereo * 32767).astype("<i2")
    with wave.open(chemin, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(TAUX)
        f.writeframes(donnees.tobytes())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    secondes = float(sys.argv[2]) if len(sys.argv) > 2 else 180
    ecrire(sys.argv[1], composer(secondes))
    print(f"Musique écrite : {sys.argv[1]} ({secondes:.0f} s)")
