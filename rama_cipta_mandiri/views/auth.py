from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST


def _redirect_sesuai_role(user):
    if user.is_superuser:
        return redirect('dashboard_admin')

    if hasattr(user, 'karyawan'):
        return redirect('dashboard_karyawan')

    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return _redirect_sesuai_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:
            messages.error(
                request,
                "Username atau password salah."
            )
            return render(request, 'auth/login.html')

        # authenticate() Django default backend umumnya sudah menolak
        # user inactive, tetapi pengecekan ini tetap aman dipertahankan.
        if not user.is_active:
            messages.error(
                request,
                "Akun Anda tidak aktif. Hubungi admin."
            )
            return render(request, 'auth/login.html')

        # User biasa wajib terhubung ke Karyawan.
        if not user.is_superuser and not hasattr(user, 'karyawan'):
            messages.error(
                request,
                "Akun ini belum terhubung ke profil karyawan. Hubungi admin."
            )
            return render(request, 'auth/login.html')

        login(request, user)

        messages.success(
            request,
            f"Selamat datang, "
            f"{user.get_full_name() or user.username}!"
        )

        return _redirect_sesuai_role(user)

    return render(request, 'auth/login.html')


@login_required
@require_POST
def logout_view(request):
    logout(request)

    messages.success(
        request,
        "Anda berhasil logout."
    )

    return redirect('login')