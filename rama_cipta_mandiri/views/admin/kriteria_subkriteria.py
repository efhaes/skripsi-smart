from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from ...decorators import superuser_required
from ...models import Kriteria, SubKriteria, Penilaian
from ...forms import KriteriaForm, SubKriteriaForm

# ============================================================
# KELOLA KRITERIA
# ============================================================

@superuser_required
def kriteria_list(request):
    daftar_kriteria = Kriteria.objects.all().order_by('urutan', 'kode')
    total_bobot_aktif = sum(k.bobot for k in daftar_kriteria if k.aktif)

    context = {
        'daftar_kriteria': daftar_kriteria,
        'total_bobot_aktif': round(total_bobot_aktif, 2),
        'bobot_valid': abs(total_bobot_aktif - 100) <= 0.01,
    }
    return render(request, 'admin_panel/kriteria_list.html', context)


@superuser_required
def kriteria_create(request):
    if request.method == 'POST':
        form = KriteriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Kriteria berhasil ditambahkan.")
            return redirect('kriteria_list')
    else:
        form = KriteriaForm()
    return render(request, 'admin_panel/kriteria_form.html', {'form': form, 'mode': 'create'})


@superuser_required
def kriteria_update(request, pk):
    kriteria = get_object_or_404(Kriteria, pk=pk)
    if request.method == 'POST':
        form = KriteriaForm(request.POST, instance=kriteria)
        if form.is_valid():
            form.save()
            messages.success(request, "Kriteria berhasil diperbarui.")
            return redirect('kriteria_list')
    else:
        form = KriteriaForm(instance=kriteria)
    return render(request, 'admin_panel/kriteria_form.html', {'form': form, 'mode': 'update', 'kriteria': kriteria})


@superuser_required
def kriteria_delete(request, pk):
    kriteria = get_object_or_404(Kriteria, pk=pk)

    if request.method != 'POST':
        return redirect('kriteria_list')

    if kriteria.penilaian_set.exists():
        messages.error(
            request,
            "Kriteria ini sudah memiliki data penilaian. Kriteria tidak dapat dihapus, silakan nonaktifkan saja."
        )
        return redirect('kriteria_list')

    kriteria.delete()
    messages.success(request, "Kriteria berhasil dihapus.")
    return redirect('kriteria_list')

# ============================================================
# KELOLA SUBKRITERIA
# ============================================================

@superuser_required
def subkriteria_list(request):
    daftar_subkriteria = (
        SubKriteria.objects
        .select_related('kriteria')
        .order_by('kriteria__urutan', '-nilai')
    )

    kelompok_subkriteria = {}

    for subkriteria in daftar_subkriteria:
        kriteria_id = subkriteria.kriteria_id

        if kriteria_id not in kelompok_subkriteria:
            kelompok_subkriteria[kriteria_id] = {
                'kriteria': subkriteria.kriteria,
                'subkriteria': [],
            }

        kelompok_subkriteria[kriteria_id]['subkriteria'].append(subkriteria)

    context = {
        'kelompok_subkriteria': kelompok_subkriteria.values(),
    }
    return render(request, 'admin_panel/subkriteria_list.html', context)


@superuser_required
def subkriteria_create(request):
    if request.method == 'POST':
        form = SubKriteriaForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Sub kriteria berhasil ditambahkan.")
            return redirect('subkriteria_list')
    else:
        form = SubKriteriaForm()

    return render(request, 'admin_panel/subkriteria_form.html', {
        'form': form,
        'mode': 'create',
    })


@superuser_required
def subkriteria_update(request, pk):
    subkriteria = get_object_or_404(SubKriteria, pk=pk)

    if request.method == 'POST':
        form = SubKriteriaForm(request.POST, instance=subkriteria)

        if form.is_valid():
            form.save()
            messages.success(request, "Sub kriteria berhasil diperbarui.")
            return redirect('subkriteria_list')
    else:
        form = SubKriteriaForm(instance=subkriteria)

    return render(request, 'admin_panel/subkriteria_form.html', {
        'form': form,
        'mode': 'update',
        'subkriteria': subkriteria,
    })


@superuser_required
def subkriteria_delete(request, pk):
    subkriteria = get_object_or_404(SubKriteria, pk=pk)

    if request.method != 'POST':
        return redirect('subkriteria_list')

    if Penilaian.objects.filter(subkriteria=subkriteria).exists():
        messages.error(
            request,
            "Sub kriteria ini sudah digunakan dalam data penilaian dan tidak dapat dihapus."
        )
        return redirect('subkriteria_list')

    subkriteria.delete()
    messages.success(request, "Sub kriteria berhasil dihapus.")
    return redirect('subkriteria_list')
