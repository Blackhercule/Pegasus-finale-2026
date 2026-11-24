"""
Réglages de l'application « Gestion de cave ».

Deux modes :
- en local (sur un PC) : base SQLite dans un fichier, mode debug actif ;
- en production (Render ou autre hébergeur) : base PostgreSQL donnée par la
  variable DATABASE_URL, debug désactivé, cookies réservés au HTTPS.

Tous les secrets viennent des variables d'environnement, jamais du code.
"""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Render définit toujours la variable RENDER : on sait alors qu'on est en ligne.
EN_PRODUCTION = bool(os.environ.get("RENDER")) or os.environ.get("PRODUCTION") == "1"
DEBUG = os.environ.get("DEBUG", "0" if EN_PRODUCTION else "1") == "1"

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if EN_PRODUCTION:
        raise RuntimeError("La variable d'environnement SECRET_KEY est obligatoire en production.")
    SECRET_KEY = "cle-de-developpement-uniquement-a-ne-jamais-utiliser-en-ligne"

# Noms de domaine autorisés à servir l'application
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ALLOWED_HOSTS += [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    # Adresse publique fournie automatiquement par Render (xxx.onrender.com)
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
if DEBUG:
    # En local, on accepte aussi les téléphones du réseau Wi-Fi (adresse IP du PC)
    ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("*", "localhost", "127.0.0.1")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "cave",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cave.context_processors.cave",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de données : PostgreSQL si DATABASE_URL est défini, sinon un fichier SQLite.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'cave.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Comptes : modèle d'utilisateur propre à l'application (patron ou gérant)
AUTH_USER_MODEL = "cave.Utilisateur"
LOGIN_URL = "connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "connexion"

# Règles de mot de passe de Django (longueur minimale, mots de passe trop courants…)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Une session dure au plus 12 heures (une journée de travail) : sur un appareil
# partagé au comptoir, un gérant qui oublie de se déconnecter ne reste pas
# connecté indéfiniment.
SESSION_COOKIE_AGE = 60 * 60 * 12

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if EN_PRODUCTION
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if EN_PRODUCTION:
    # L'hébergeur termine le HTTPS devant l'application et le signale par cet en-tête
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
