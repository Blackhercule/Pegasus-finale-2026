"""Qui a le droit de voir quoi."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def patron_requis(vue):
    """La page n'est accessible qu'au patron. Un gérant reçoit « Accès refusé »."""

    @login_required
    @wraps(vue)
    def vue_protegee(request, *args, **kwargs):
        if not request.user.est_patron:
            raise PermissionDenied
        return vue(request, *args, **kwargs)

    return vue_protegee
