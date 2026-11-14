# ==========================================================
# anpr_portail.py
# Raspberry Pi Zero 2 W - camera CSI
# Detection plaque : OpenCV
# Lecture caracteres : Tesseract / pytesseract
# Messages visibles dans le terminal SSH
# Relais GPIO prevu, desactive par defaut (SIMULATION=True)
# ==========================================================

import re
import time
from datetime import datetime
from difflib import SequenceMatcher

import cv2
import pytesseract
from picamera2 import Picamera2


# ==========================================================
# 1. CONFIGURATION
# ==========================================================

# True : aucun relais physique n'est commande.
# Passer a False uniquement apres avoir teste le cablage et la logique.
SIMULATION = True

RESOLUTION = (640, 480)

# Plaques de test/autorisées. Adapte cette liste a tes besoins.
PLAQUES_AUTORISEES = [
    "FC-118-JL",  # plaque utilisee pour les essais
    "AA-123-AA",
    "BB-456-BB",
    "CC-789-CC",
]

TOLERANCE = 0.90
VALIDATIONS = 2                 # lectures identiques consecutives
COOLDOWN = 30                   # secondes entre deux commandes d'ouverture
DUREE_IMPULSION = 0.5           # secondes
INTERVALLE_ANALYSE = 0.25       # pause entre deux analyses
DELAI_REINITIALISATION = 2.5    # absence de plaque avant de rearmer la detection
DELAI_AFFICHAGE = 1.5           # limite l'affichage repetitif pendant la lecture

PIN_RELAIS = 17
GPIO = None


# ==========================================================
# 2. AFFICHAGE DANS LE TERMINAL SSH
# ==========================================================

def afficher(message):
    heure = datetime.now().strftime("%H:%M:%S")
    print(f"[{heure}] {message}", flush=True)


# ==========================================================
# 3. INITIALISATION ET NETTOYAGE GPIO
# ==========================================================

def initialiser_gpio():
    global GPIO

    if SIMULATION:
        afficher("MODE SIMULATION : GPIO inactif, aucun relais ne sera commande")
        return

    import RPi.GPIO as module_gpio

    GPIO = module_gpio
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_RELAIS, GPIO.OUT)
    GPIO.output(PIN_RELAIS, GPIO.LOW)
    afficher(f"GPIO {PIN_RELAIS} initialise")


def nettoyer_gpio():
    global GPIO

    if GPIO is not None:
        try:
            GPIO.output(PIN_RELAIS, GPIO.LOW)
        finally:
            GPIO.cleanup()
        afficher("GPIO nettoye")


# ==========================================================
# 4. NORMALISATION ET COMPARAISON DES PLAQUES
# ==========================================================

def normaliser(texte):
    """Met en majuscules et conserve uniquement A-Z et 0-9."""
    return re.sub(r"[^A-Z0-9]", "", str(texte).upper())


def plaque_similaire(lue, reference):
    """Compare deux plaques normalisees, de meme longueur."""
    plaque_lue = normaliser(lue)
    plaque_reference = normaliser(reference)

    if len(plaque_lue) != len(plaque_reference):
        return False

    score = SequenceMatcher(None, plaque_lue, plaque_reference).ratio()
    return score >= TOLERANCE


# ==========================================================
# 5. COMMANDE DU RELAIS
# ==========================================================

def ouvrir_porte():
    afficher("OUVERTURE DE LA PORTE DEMANDEE")

    if SIMULATION:
        afficher("SIMULATION : aucune impulsion GPIO envoyee")
        return

    GPIO.output(PIN_RELAIS, GPIO.HIGH)
    try:
        time.sleep(DUREE_IMPULSION)
    finally:
        GPIO.output(PIN_RELAIS, GPIO.LOW)

    afficher("Impulsion relais terminee")


# ==========================================================
# 6. DETECTION DE LA PLAQUE AVEC OPENCV
# ==========================================================

def trouver_plaque(image):
    """Repere une zone allongee par fermeture morphologique, puis la recadre."""
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gris = cv2.bilateralFilter(gris, 9, 75, 75)
    bords = cv2.Canny(gris, 50, 150)

    hauteur, largeur = gris.shape

    largeur_noyau = max(15, int(largeur * 0.08))
    hauteur_noyau = max(3, int(hauteur * 0.015))
    noyau = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (largeur_noyau, hauteur_noyau),
    )

    contours_fermes = cv2.morphologyEx(
        bords,
        cv2.MORPH_CLOSE,
        noyau,
    )

    contours, _ = cv2.findContours(
        contours_fermes,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    candidates = []

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        if h == 0:
            continue

        ratio = w / float(h)
        aire = w * h

        if 2.0 <= ratio <= 5.5 and aire > 2000:
            candidates.append((aire, (x, y, w, h)))

    if not candidates:
        return None

    # Conserve la plus grande zone candidate.
    candidates.sort(key=lambda element: element[0], reverse=True)
    x, y, w, h = candidates[0][1]

    # Petite marge autour de la zone detectee.
    marge_x = int(w * 0.04)
    marge_y = int(h * 0.12)

    x1 = max(0, x - marge_x)
    y1 = max(0, y - marge_y)
    x2 = min(largeur, x + w + marge_x)
    y2 = min(hauteur, y + h + marge_y)

    plaque = image[y1:y2, x1:x2]

    if plaque.size == 0:
        return None

    return plaque


# ==========================================================
# 7. LECTURE OCR AVEC TESSERACT
# ==========================================================

def lire_plaque(plaque_img):
    if plaque_img is None:
        return None

    gris = cv2.cvtColor(plaque_img, cv2.COLOR_BGR2GRAY)

    _, seuil = cv2.threshold(
        gris,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    config = (
        "--psm 7 "
        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    )

    texte = pytesseract.image_to_string(seuil, config=config).strip()
    texte = normaliser(texte)

    return texte if len(texte) >= 5 else None


# ==========================================================
# 8. IDENTIFICATION ET DECISION D'ACCES
# ==========================================================

def identifier_plaque(lue, derniere_ouverture):
    afficher("IDENTIFICATION : comparaison avec la liste autorisee")

    for reference in PLAQUES_AUTORISEES:
        if plaque_similaire(lue, reference):
            afficher(f"PLAQUE AUTORISEE : {reference}")

            maintenant = time.time()

            if maintenant - derniere_ouverture > COOLDOWN:
                afficher("ACCES AUTORISE")
                ouvrir_porte()
                return maintenant

            afficher(
                "PLAQUE AUTORISEE, MAIS NOUVELLE OUVERTURE BLOQUEE "
                f"(cooldown de {COOLDOWN} secondes)"
            )
            return derniere_ouverture

    afficher(f"ACCES REFUSE : plaque non autorisee ({lue})")
    return derniere_ouverture


# ==========================================================
# 9. BOUCLE PRINCIPALE - CAMERA CSI
# ==========================================================

def main():
    derniere_ouverture = 0.0
    dernieres_lectures = []

    # Verrou : apres traitement, la meme plaque n'est plus traitee
    # tant qu'elle reste devant la camera.
    plaque_verrouillee = None

    derniere_lecture_affichee = None
    dernier_temps_affichage = 0.0
    dernier_temps_detection = 0.0

    picam2 = None
    camera_demarre = False

    try:
        afficher("INITIALISATION CAMERA CSI")

        picam2 = Picamera2()
        configuration = picam2.create_video_configuration(
            main={
                "size": RESOLUTION,
                "format": "RGB888",
            },
            display=None,
        )

        picam2.configure(configuration)
        picam2.start()
        camera_demarre = True
        time.sleep(2)

        afficher("CAMERA CSI DEMARREE")
        afficher("SYSTEME ANPR OPERATIONNEL")
        afficher("EN ATTENTE D'UNE PLAQUE...")

        while True:
            # Capture de l'image depuis la camera CSI.
            frame = picam2.capture_array()
            maintenant = time.monotonic()

            plaque_img = trouver_plaque(frame)
            lue = lire_plaque(plaque_img)

            if lue:
                # Une plaque est presente : actualise le dernier instant detecte.
                # Cela empeche de liberer le verrou tant que la plaque reste visible.
                if (
                    dernier_temps_detection == 0.0
                    or maintenant - dernier_temps_detection > DELAI_REINITIALISATION
                ):
                    dernieres_lectures.clear()
                    plaque_verrouillee = None
                    derniere_lecture_affichee = None

                dernier_temps_detection = maintenant
                lue_normalisee = normaliser(lue)

                # IMPORTANT : verifier le verrou AVANT d'afficher l'OCR.
                # La meme plaque deja traitee est ignoree silencieusement.
                if (
                    plaque_verrouillee is not None
                    and lue_normalisee == plaque_verrouillee
                ):
                    # Efface une eventuelle lecture parasite entre deux images.
                    dernieres_lectures.clear()
                    time.sleep(INTERVALLE_ANALYSE)
                    continue

                # Affiche occasionnellement la lecture, sans inonder le terminal.
                if (
                    lue != derniere_lecture_affichee
                    or maintenant - dernier_temps_affichage >= DELAI_AFFICHAGE
                ):
                    afficher(f"LECTURE OCR EN COURS : {lue}")
                    derniere_lecture_affichee = lue
                    dernier_temps_affichage = maintenant

                # Validation de plusieurs lectures identiques consecutives.
                dernieres_lectures.append(lue_normalisee)
                dernieres_lectures = dernieres_lectures[-VALIDATIONS:]

                if len(dernieres_lectures) == VALIDATIONS:
                    if len(set(dernieres_lectures)) == 1:
                        afficher("VALIDATION CONFIRMEE")

                        derniere_ouverture = identifier_plaque(
                            lue_normalisee,
                            derniere_ouverture,
                        )

                        # Verrouille la plaque traitee, autorisee ou non.
                        plaque_verrouillee = lue_normalisee
                        dernieres_lectures.clear()

                    else:
                        afficher(
                            "LECTURES DIFFERENTES : "
                            "nouvelle verification necessaire"
                        )
                        # La derniere lecture devient le debut de la validation suivante.
                        dernieres_lectures = [dernieres_lectures[-1]]

            else:
                # Pas de plaque lisible. Apres un delai, le systeme se rearme.
                if (
                    dernier_temps_detection != 0.0
                    and maintenant - dernier_temps_detection > DELAI_REINITIALISATION
                ):
                    if plaque_verrouillee is not None or dernieres_lectures:
                        afficher("PLAQUE DISPARUE : detection rearmee")

                    dernieres_lectures.clear()
                    plaque_verrouillee = None
                    derniere_lecture_affichee = None
                    dernier_temps_detection = 0.0

            time.sleep(INTERVALLE_ANALYSE)

    finally:
        if picam2 is not None:
            try:
                if camera_demarre:
                    picam2.stop()
            finally:
                picam2.close()
            afficher("CAMERA CSI ARRETEE")


# ==========================================================
# 10. DEMARRAGE
# ==========================================================

if __name__ == "__main__":
    try:
        initialiser_gpio()
        main()
    except KeyboardInterrupt:
        afficher("ARRET DEMANDE PAR L'UTILISATEUR")
    finally:
        nettoyer_gpio()
        afficher("SYSTEME ANPR ARRETE")
