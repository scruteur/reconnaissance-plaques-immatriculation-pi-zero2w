- Toute la communication est faite en ssh
- 
- Étape 1 — Installer Picamera2
- sudo apt install python3-picamera2
- 
- Étape 2 — Vérifier dans notre environnement Python
- ~/anpr-env/bin/python -c 'from picamera2 import Picamera2; print('PICAMERA2 FONCTIONNE !')'
- 
- tape 1 — Installer les outils nécessaires
- sudo apt update
- sudo apt install python3-venv

- Étape 2 — Créer un environnement Python
- python3 -m venv --system-site-packages ~/anpr-env
- 
- Étape 3 — Installer pytesseract
- ~/anpr-env/bin/python -m pip install pytesseract
- 
- Étape 4 — Vérifier
- ~/anpr-env/bin/python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
- 
- Étape 5 — Lancer notre programme
- ~/anpr-env/bin/python anpr_portail.py
- 
- # envoyer un programme au pi 
-  scp mon_programme.py utilisateur@ADRESSE_IP_DU_PI:/home/utilisateur/

-  # 1. Installer pip et venv
- sudo apt install -y python3-pip python3-venv

- # 2. Créer un environnement virtuel pour ton projet
- python3 -m venv ~/env_anpr

- # 3. L'activer
- source ~/env_anpr/bin/activate

- # 4. Ton prompt change → tu es dans l'environnement :
- # (env_anpr) pi@pi:~ $

- pip install pytesseract

- pour supprimer l'ancienne clée
- # avec adresse du pi

- ssh-keygen -f '/home/jean/.ssh/known_hosts' -R '192.168.1.45'

- 
