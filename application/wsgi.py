"""Point d'entrée pour gunicorn : gunicorn 'application.wsgi:app'."""
from . import creer_application

app = creer_application()
