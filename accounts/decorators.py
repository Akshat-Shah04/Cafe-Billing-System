from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view):
    """Logged in and an admin; staff get a 403 instead of a silent redirect."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied("Only administrators can do this.")
        return view(request, *args, **kwargs)

    return wrapper
