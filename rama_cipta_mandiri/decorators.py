from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def superuser_required(view_func):
    """
    Hanya superuser yang dapat mengakses halaman admin.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied(
                "Halaman ini khusus untuk admin."
            )

        return view_func(request, *args, **kwargs)

    return _wrapped


def karyawan_required(view_func):
    """
    Hanya user non-superuser yang terhubung dengan profil
    Karyawan yang dapat mengakses portal karyawan.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser:
            raise PermissionDenied(
                "Halaman ini khusus untuk karyawan."
            )

        if not hasattr(request.user, 'karyawan'):
            raise PermissionDenied(
                "Akun ini tidak terhubung ke profil karyawan."
            )

        return view_func(request, *args, **kwargs)

    return _wrapped