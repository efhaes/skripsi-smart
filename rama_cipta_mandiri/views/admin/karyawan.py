from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from django.db.models import ProtectedError

from ...decorators import superuser_required
from ...models import Karyawan
from ...forms import KaryawanForm

# ============================================================
# CRUD KARYAWAN (+ AKUN LOGIN)
# ============================================================


def _cek_akun_login(form, karyawan=None):
    """
    Validasi tambahan untuk username & password akun login.
    Kesalahan ditambahkan ke form, sehingga tampil sebagai pesan
    di bawah field (bukan halaman error Django).
    """
    username = form.cleaned_data.get('username')
    password = form.cleaned_data.get('password')

    if not username:
        return

    user_id_sendiri = karyawan.user_id if karyawan else None

    username_dipakai = User.objects.filter(username=username)

    if user_id_sendiri:
        username_dipakai = username_dipakai.exclude(pk=user_id_sendiri)

    if username_dipakai.exists():
        form.add_error('username', 'Username sudah digunakan oleh akun lain.')

    # Akun baru tanpa password tidak akan bisa login.
    if not user_id_sendiri and not password:
        form.add_error('password', 'Password wajib diisi untuk membuat akun login.')


@superuser_required
def karyawan_list(request):
    daftar_karyawan = Karyawan.objects.select_related('user').order_by('nama', 'id')
    context = {'daftar_karyawan': daftar_karyawan}
    return render(request, 'admin_panel/karyawan_list.html', context)


@superuser_required
def karyawan_create(request):
    if request.method == 'POST':
        form = KaryawanForm(request.POST)

        if form.is_valid():
            _cek_akun_login(form)

            if not form.errors:
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')

                try:
                    with transaction.atomic():
                        karyawan = form.save(commit=False)

                        if username:
                            user = User.objects.create_user(username=username, password=password)
                            karyawan.user = user

                        karyawan.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "Karyawan gagal disimpan karena ada data yang sama dengan data yang sudah ada."
                    )
                else:
                    messages.success(request, "Karyawan berhasil ditambahkan.")
                    return redirect('karyawan_list')
    else:
        form = KaryawanForm()

    return render(request, 'admin_panel/karyawan_form.html', {
        'form': form,
        'mode': 'create',
    })


@superuser_required
def karyawan_update(request, pk):
    karyawan = get_object_or_404(Karyawan, pk=pk)

    if request.method == 'POST':
        form = KaryawanForm(request.POST, instance=karyawan)

        if form.is_valid():
            _cek_akun_login(form, karyawan)

            if not form.errors:
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')

                try:
                    with transaction.atomic():
                        karyawan = form.save(commit=False)

                        if username:
                            if karyawan.user_id:
                                user = karyawan.user
                                user.username = username

                                if password:
                                    user.set_password(password)

                                user.save()
                            else:
                                user = User.objects.create_user(username=username, password=password)
                                karyawan.user = user

                        karyawan.save()
                except IntegrityError:
                    messages.error(
                        request,
                        "Perubahan gagal disimpan karena ada data yang sama dengan data yang sudah ada."
                    )
                else:
                    messages.success(request, "Karyawan berhasil diperbarui.")
                    return redirect('karyawan_list')
    else:
        initial = {
            'username': karyawan.user.username if karyawan.user_id else ''
        }
        form = KaryawanForm(instance=karyawan, initial=initial)

    return render(request, 'admin_panel/karyawan_form.html', {
        'form': form,
        'mode': 'update',
        'karyawan': karyawan,
    })


@superuser_required
def karyawan_delete(request, pk):
    karyawan = get_object_or_404(Karyawan, pk=pk)

    if request.method != 'POST':
        return redirect('karyawan_list')

    if karyawan.alternatif_set.exists():
        messages.error(
            request,
            "Karyawan ini sudah memiliki data absensi atau penilaian. Karyawan tidak dapat dihapus, silakan nonaktifkan saja."
        )
        return redirect('karyawan_list')

    try:
        with transaction.atomic():
            user = karyawan.user if karyawan.user_id else None
            karyawan.delete()

            # Akun superuser tidak ikut dihapus supaya admin tidak terkunci.
            if user and not user.is_superuser:
                user.delete()
    except (ProtectedError, IntegrityError):
        messages.error(
            request,
            "Karyawan tidak dapat dihapus karena masih terhubung dengan data lain. Silakan nonaktifkan saja."
        )
        return redirect('karyawan_list')

    messages.success(request, "Karyawan berhasil dihapus.")
    return redirect('karyawan_list')