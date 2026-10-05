from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction

from ...decorators import superuser_required
from ...models import Karyawan
from ...forms import KaryawanForm

# ============================================================
# CRUD KARYAWAN (+ AKUN LOGIN)
# ============================================================

@superuser_required
def karyawan_list(request):
    daftar_karyawan = Karyawan.objects.select_related('user').order_by('nama')
    context = {'daftar_karyawan': daftar_karyawan}
    return render(request, 'admin_panel/karyawan_list.html', context)


@superuser_required
def karyawan_create(request):
    if request.method == 'POST':
        form = KaryawanForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                karyawan = form.save(commit=False)
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')

                if username:
                    user = User.objects.create_user(username=username, password=password)
                    karyawan.user = user

                karyawan.save()

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
            with transaction.atomic():
                karyawan = form.save(commit=False)
                username = form.cleaned_data.get('username')
                password = form.cleaned_data.get('password')

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
            "Karyawan ini sudah memiliki data penilaian. Karyawan tidak dapat dihapus, silakan nonaktifkan saja."
        )
        return redirect('karyawan_list')

    with transaction.atomic():
        user = karyawan.user if karyawan.user_id else None
        karyawan.delete()

        if user:
            user.delete()

    messages.success(request, "Karyawan berhasil dihapus.")
    return redirect('karyawan_list')