"""Rapport de projet en PDF : une plateforme pour toute la population (18/11/2026).

    python outils/rapport_inclusion.py <dossier des captures> <police Lato .ttf> livrables/Rapport-projet-Pegasus.pdf

Le texte est écrit ici ; les captures d'écran sont prises sur notre propre plateforme.
"""

import os
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

CAPTURES, POLICES, SORTIE = sys.argv[1], sys.argv[2], sys.argv[3]
pdfmetrics.registerFont(TTFont("Lato", os.path.join(POLICES, "lato-400.ttf")))
pdfmetrics.registerFont(TTFont("Lato-Gras", os.path.join(POLICES, "lato-700.ttf")))
pdfmetrics.registerFontFamily("Lato", normal="Lato", bold="Lato-Gras", italic="Lato", boldItalic="Lato-Gras")

VERT, VERT_CLAIR, FOND, ENCRE, GRIS = (colors.HexColor(c) for c in
                                       ("#0b5e47", "#12805f", "#e6f4ee", "#1b2033", "#5f6680"))
ROUGE = colors.HexColor("#c8102e")

corps = ParagraphStyle("corps", fontName="Lato", fontSize=10.5, leading=15.5, textColor=ENCRE, spaceAfter=7)
titre1 = ParagraphStyle("t1", fontName="Lato-Gras", fontSize=17, leading=21, textColor=VERT,
                        spaceBefore=12, spaceAfter=8)
titre2 = ParagraphStyle("t2", fontName="Lato-Gras", fontSize=12.5, leading=16, textColor=VERT,
                        spaceBefore=8, spaceAfter=4)
puce = ParagraphStyle("puce", parent=corps, leftIndent=14, bulletIndent=2, spaceAfter=3)
legende = ParagraphStyle("legende", parent=corps, fontSize=8.5, leading=11, textColor=GRIS,
                         alignment=TA_CENTER, spaceAfter=10)
encadre = ParagraphStyle("encadre", parent=corps, fontSize=11, leading=16, textColor=VERT)
cellule = ParagraphStyle("cellule", parent=corps, fontSize=9.5, leading=13, spaceAfter=0)
cellule_gras = ParagraphStyle("cellule_gras", parent=cellule, fontName="Lato-Gras", textColor=VERT)


def p(texte, style=corps):
    return Paragraph(texte, style)


def puces(*lignes):
    return [Paragraph(l, puce, bulletText="•") for l in lignes]


def image(nom, largeur_mm, texte=None, recadre=None):
    chemin = os.path.join(CAPTURES, nom)
    if recadre:
        from PIL import Image as Pil
        rogne = os.path.join(CAPTURES, "rogne-" + nom)
        Pil.open(chemin).crop(recadre).save(rogne)
        chemin = rogne
    from PIL import Image as Pil
    l, h = Pil.open(chemin).size
    elements = [Image(chemin, width=largeur_mm * mm, height=largeur_mm * mm * h / l)]
    if texte:
        elements.append(p(texte, legende))
    return KeepTogether(elements)


def boite(texte):
    t = Table([[p(texte, encadre)]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FOND), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 9),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, VERT)]))
    return t


def tableau(lignes, largeurs):
    donnees = [[p(c, cellule_gras if i == 0 else cellule) for c in ligne] for i, ligne in enumerate(lignes)]
    t = Table(donnees, colWidths=[l * mm for l in largeurs], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), FOND), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9dce6")),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def decor(canevas, document):
    """Bandeau aux couleurs du drapeau en haut de chaque page, numéro en bas."""
    largeur, hauteur = A4
    canevas.saveState()
    pas = 60
    for i in range(pas):                      # dégradé rouge → vert
        t = i / (pas - 1)
        canevas.setFillColorRGB((0xc8 * (1 - t) + 0x00 * t) / 255, (0x10 * (1 - t) + 0x9a * t) / 255,
                                (0x2e * (1 - t) + 0x44 * t) / 255)
        canevas.rect(largeur * i / pas, hauteur - 6 * mm, largeur / pas + 1, 6 * mm, stroke=0, fill=1)
    canevas.setFont("Lato", 8)
    canevas.setFillColor(GRIS)
    canevas.drawString(20 * mm, 10 * mm, "Groupe Pegasus · Assainissement de Ouaga · rapport de projet")
    canevas.drawRightString(largeur - 20 * mm, 10 * mm, "page %d" % document.page)
    canevas.restoreState()


def couverture(canevas, document):
    decor(canevas, document)
    largeur, hauteur = A4
    canevas.saveState()
    canevas.setFillColor(VERT)
    canevas.rect(0, hauteur - 120 * mm, largeur, 114 * mm, stroke=0, fill=1)
    canevas.setFillColor(colors.white)
    canevas.setFont("Lato", 11)
    canevas.drawString(20 * mm, hauteur - 30 * mm, "HACKATHON DES UNIVERSITÉS 2026 · CHALLENGE 01")
    canevas.setFont("Lato-Gras", 30)
    canevas.drawString(20 * mm, hauteur - 52 * mm, "Assainissement de Ouaga")
    canevas.setFont("Lato", 16)
    canevas.drawString(20 * mm, hauteur - 66 * mm, "Une plateforme pour toute la population,")
    canevas.drawString(20 * mm, hauteur - 75 * mm, "même pour ceux qui ne savent ni lire ni écrire")
    canevas.setFont("Lato", 11)
    canevas.drawString(20 * mm, hauteur - 100 * mm, "Groupe Pegasus · Université Joseph Ki-Zerbo · Ouagadougou")
    canevas.drawString(20 * mm, hauteur - 108 * mm, "Rapport de projet · 18 novembre 2026 · logiciel libre (AGPL-3.0)")
    canevas.restoreState()


histoire = [Spacer(1, 112 * mm)]
histoire += [
    p("En une phrase", titre1),
    boite("Un habitant qui ne sait ni lire ni écrire peut signaler un dépotoir sauvage : la page lui "
          "parle en mooré, lui montre trois grandes touches numérotées, et la touche 2 ou 3 l'appelle "
          "directement à la mairie, depuis la plateforme. L'agent qui décroche voit en direct, sur la "
          "carte, où se trouve l'habitant. Aucun compte, aucun mot à écrire, aucun crédit d'appel."),
    Spacer(1, 6),
    p("Ce rapport explique pourquoi nous avons construit l'outil autour de cette idée, comment chaque "
      "habitant y trouve sa place, et ce qui reste à faire. Le détail technique (architecture, plan de "
      "gestion, scénarios) est dans le rapport technique du dépôt (<b>RAPPORT.md</b>)."),
    PageBreak(),

    p("1. Le constat : signaler ne doit pas exiger de savoir lire", titre1),
    p("Les applications de signalement supposent presque toujours un habitant qui lit les menus, écrit "
      "une description, crée un compte et sait se servir d'une carte. À Ouagadougou, ce n'est pas le cas "
      "de tout le monde. Selon l'enquête multisectorielle continue de l'INSD (2014), <b>34,5 %</b> des "
      "personnes de 15 ans et plus savent lire et écrire au Burkina Faso, et <b>65,2 %</b> dans la région "
      "du Centre, celle de Ouagadougou : environ <b>un adulte sur trois</b> de la capitale ne peut donc pas "
      "utiliser un formulaire écrit."),
    p("Or ce sont souvent ces habitants qui vivent à côté des dépotoirs : commerçantes des marchés, "
      "ménagères, personnes âgées, vendeurs ambulants. Un outil qui les exclut voit moins de dépotoirs, "
      "et surtout pas ceux des quartiers où il en faudrait le plus."),
    boite("Notre règle de conception : <b>chaque action importante doit pouvoir se faire sans lire</b> — "
          "par la voix, par une image, par un chiffre de 1 à 3, ou en parlant à quelqu'un."),

    p("2. Un chemin pour chaque habitant", titre1),
    tableau([
        ["L'habitant…", "Ce qu'il fait sur la plateforme"],
        ["sait lire et écrire", "Touche 1 : il remplit lui-même le signalement (photo, taille du tas, type d'ordures), en moins d'une minute."],
        ["ne sait ni lire ni écrire", "La page lui parle en mooré. Il touche <b>2</b> ou <b>3</b> : un agent de la mairie décroche, l'écoute et voit sa position en direct."],
        ["préfère parler", "Dans le formulaire, il enregistre un message vocal au lieu d'écrire."],
        ["n'a pas de GPS", "Il choisit un lieu connu dans une liste : marché, école, centre de santé, mosquée, église."],
        ["n'a pas de réseau", "Le signalement est gardé dans le téléphone et part tout seul au retour du réseau."],
        ["ne veut pas se faire connaître", "Aucun compte ; le nom n'est jamais exigé. Seul l'habitant qui accepte d'être témoin le donne, et il est effacé à la clôture du dossier. Les visages et les plaques sont floutés à la réception."],
    ], [45, 125]),
    PageBreak(),

    p("3. Pour ceux qui ne savent ni lire ni écrire", titre1),
    p("3.1 La page parle, et montre", titre2),
    p("Dès l'ouverture de la page Signaler, un message de bienvenue est lu à voix haute en mooré. Tout "
      "ce qui compte est porté par une image : de grandes icônes dessinées en trait (tas d'ordures, "
      "goutte d'eau, caniveau, téléphone), et non par du texte. Il n'y a ni menu déroulant, ni petit "
      "bouton : chaque choix est une grande carte qu'on touche du doigt."),
    p("3.2 Trois touches, comme sur un téléphone", titre2),
    p("Après le message d'accueil, la page propose trois grandes touches numérotées, que tout le monde "
      "connaît depuis le clavier d'un téléphone :"),
    *puces("<b>1 — Je signale moi-même</b> : le formulaire, pour ceux qui savent s'en servir ;",
           "<b>2 et 3 — Parler à la mairie</b> : l'appel part tout de suite vers un agent."),
    image("menu.png", 62, "La page Signaler : le message en mooré, puis les touches 1, 2 et 3.",
          recadre=(0, 0, 412, 760)),
    p("3.3 L'appel direct, sans crédit et sans Internet", titre2),
    p("Quand l'habitant touche 2 ou 3, son téléphone appelle la mairie <b>par la plateforme elle-même</b>, "
      "pas par le réseau téléphonique : l'appel ne coûte rien et passe même si la ville n'a pas Internet, "
      "tant que le téléphone et le poste de l'agent sont sur le même réseau local (Wi-Fi de la mairie, "
      "d'un point d'accès de quartier, ou partage de connexion)."),
    *puces("Le poste de l'agent <b>sonne</b>, avec un bandeau « Un habitant appelle ».",
           "L'agent décroche ; ils se parlent, en mooré, en dioula ou en français.",
           "Sur la carte de l'agent, un point montre <b>en direct</b> où se trouve l'habitant, et le suit "
           "s'il marche jusqu'au tas : l'agent sait exactement où envoyer l'équipe.",
           "L'agent crée le signalement à sa place, avec la position reçue."),
    image("appel-video.png", 165, "À gauche le téléphone de l'habitant, à droite le poste de l'agent : "
          "le point vert suit l'habitant sur la carte (extrait de notre vidéo de démonstration)."),
    p("3.4 Ce qui protège l'habitant pendant l'appel", titre2),
    *puces("La voix va directement d'un appareil à l'autre, chiffrée par le protocole standard des "
           "navigateurs (WebRTC, DTLS-SRTP) : <b>aucune cryptographie écrite par l'équipe</b>.",
           "<b>Rien n'est enregistré</b> : ni la voix, ni le numéro, ni l'historique des positions. "
           "L'appel vit en mémoire et disparaît quand on raccroche.",
           "Chaque appel a un code secret ; un même téléphone ne peut pas appeler plus de 5 fois en 10 "
           "minutes, et pas plus de 3 appels peuvent sonner en même temps.",
           "Si le micro est refusé, si personne ne répond ou si le réseau coupe, l'habitant n'est pas "
           "abandonné : la page le ramène au signalement par photo."),
    PageBreak(),

    p("4. Inclure aussi ceux qui agissent", titre1),
    p("Inclure la population, c'est aussi donner une place à ceux qui nettoient la ville : brigade "
      "Laabal, équipes de collecte, associations et entreprises de pré-collecte, ONEA. Chacun a son "
      "poste dans la plateforme, et chaque dossier passe de main en main jusqu'à l'enlèvement."),
    *puces("<b>Qui a fait quoi</b> : chaque vérification et chaque étape portent le nom de l'agent et "
           "l'heure. Personne ne peut dire « ce n'est pas moi ».",
           "<b>Les collecteurs</b> : entreprises et associations, leurs tricycles et camions, leurs "
           "quartiers et leurs jours de passage, les quantités qu'ils évacuent.",
           "<b>L'habitant voit qui passe chez lui</b> : sur la page d'accueil, il choisit son quartier et "
           "voit les collecteurs et leurs jours. Si l'un d'eux n'est pas passé, il le dit en un choix, sans "
           "écrire et sans donner son nom.",
           "<b>Les zones à risque</b> : une carte thermique montre où les signalements se concentrent ; "
           "les dépôts qui reviennent sont repérés ; les caniveaux à curer avant la saison des pluies "
           "sont classés, pour agir avant l'inondation.",
           "<b>Encourager</b> : 10 points par signalement vérifié, le classement des quartiers les plus "
           "propres, les résultats des campagnes de salubrité et des challenges entre écoles."),
    image("pc.png", 120, "Page d'accueil : un habitant choisit son quartier et voit qui ramasse les "
          "ordures, et quel jour.", recadre=(100, 0, 560, 400)),

    p("5. Ce que nous ne faisons pas, exprès", titre1),
    *puces("<b>Pas de compte pour l'habitant</b> : un compte demande de lire, d'écrire et de retenir un mot "
           "de passe. Le téléphone est reconnu par un nombre tiré au hasard ; le nom et le numéro ne sont "
           "demandés qu'à celui qui accepte d'être témoin, et effacés à la clôture du dossier.",
           "<b>Pas de dépendance à Internet</b> : la plateforme tourne sur une machine de la mairie ; "
           "cartes, polices et icônes sont dans l'outil. Une coupure d'Internet n'arrête rien.",
           "<b>Pas de forum public</b> : sans modérateur, il exposerait des noms et des accusations. Nous "
           "avons préféré des choix fermés (motif d'une plainte), qui ne contiennent aucune donnée personnelle.",
           "<b>Jamais de modification automatique d'OpenStreetMap</b> : un membre de l'équipe relit l'export "
           "avant de le verser."),

    p("6. Ce qui reste à faire", titre1),
    p("Nous préférons le dire nous-mêmes :"),
    *puces("<b>Les messages en mooré</b> : le message d'accueil est enregistré ; les messages de chaque "
           "étape et celui du menu 1-2-3 restent à enregistrer avec des locuteurs. Le dioula et le "
           "fulfuldé suivront de la même façon : il suffit de déposer les fichiers audio.",
           "<b>Les téléphones simples</b> (sans écran tactile ni navigateur) ne sont pas encore couverts. "
           "La suite naturelle est un numéro court, relié au même poste d'agent.",
           "<b>Les limites officielles des quartiers et des 12 arrondissements</b> manquent dans "
           "OpenStreetMap : la plateforme range aujourd'hui un signalement dans le quartier dont le nom "
           "est le plus proche. Nous remplacerons ces repères dès que la mairie nous transmettra les "
           "limites.",
           "<b>L'appel suppose un réseau local commun</b> au téléphone et au poste de l'agent ; dans la ville, "
           "il faudra des points d'accès de quartier ou un relais (serveur TURN) de la mairie."),

    p("7. Vérifié, pas seulement écrit", titre1),
    tableau([
        ["Vérification", "Résultat (18/11/2026)"],
        ["Tests automatisés (pytest)", "279 réussis, 0 échec"],
        ["Essai automatique de l'appel (deux navigateurs qui s'appellent)", "30 vérifications réussies sur 30 : voix dans les deux sens, position suivie, retour au formulaire en cas d'échec"],
        ["Parcours de 8 pages, sur grand écran et sur téléphone", "29 vérifications réussies, aucune requête vers Internet"],
        ["42 signalements piégés injectés", "Tous écartés avec leur motif ; aucun n'entre dans le plan"],
    ], [75, 95]),
    Spacer(1, 10),
    p("Sources : INSD, <i>Enquête multisectorielle continue 2014 — Alphabétisation et scolarisation</i>, "
      "tableaux 1 et 2 (taux d'alphabétisation des 15 ans et plus : 34,5 % au niveau national, 65,2 % "
      "dans la région du Centre). Code, données et documents : dépôt public Blackhercule/Pegasus-finale-2026, "
      "licence AGPL-3.0.", legende),
]

document = SimpleDocTemplate(SORTIE, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                             topMargin=16 * mm, bottomMargin=18 * mm,
                             title="Assainissement de Ouaga — une plateforme pour toute la population",
                             author="Groupe Pegasus")
document.build(histoire, onFirstPage=couverture, onLaterPages=decor)
print("écrit :", SORTIE)
