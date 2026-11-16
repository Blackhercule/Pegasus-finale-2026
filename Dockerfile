# Application d'aide à la décision : une petite application Flask, servie par gunicorn.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /application

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY application ./application
COPY interface ./interface
COPY donnees ./donnees

# L'application tourne sans privilèges ; la base et les photos vont dans un volume.
# Le dossier personnel doit exister et lui appartenir : gunicorn y ouvre une socket de contrôle.
RUN useradd --uid 991 --create-home --home-dir /home/outil outil \
    && mkdir -p /travail && chown 991:991 /travail /home/outil
USER 991
ENV HOME=/home/outil \
    BASE_DONNEES=/travail/signalements.sqlite DOSSIER_PHOTOS=/travail/photos

EXPOSE 8000
# Un seul processus, plusieurs fils : le réseau routier (111 000 carrefours) n'est ainsi
# chargé qu'une fois en mémoire. Le délai large laisse le temps d'un gros recalcul de plan.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", \
     "--timeout", "180", "--forwarded-allow-ips", "*", "application.wsgi:app"]
