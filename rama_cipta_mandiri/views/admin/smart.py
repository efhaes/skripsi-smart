import io
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from ...decorators import superuser_required
from ...models import (
    Periode,
    Kriteria,
    Alternatif,
    Utility,
    PerhitunganSmart,
    HasilSmart,
)
from ...spk import (
    SmartCalculator,
    get_hasil_dari_db,
    get_or_create_periode,
    cek_kelengkapan_penilaian,
)

@superuser_required
def smart_pilih_periode(request):
    """
    Admin pilih bulan & tahun untuk proses SMART. Kalau periode itu
    belum punya penilaian lengkap, arahkan balik buat isi dulu.
    """
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')

    if bulan and tahun:
        periode = Periode.objects.filter(bulan=int(bulan), tahun=int(tahun)).first()
        if not periode:
            messages.warning(request, "Periode ini belum ada. Isi absensi dan penilaian terlebih dahulu.")
            return redirect('absensi_bulanan')
        
        # Cek kelengkapan penilaian
        cek = cek_kelengkapan_penilaian(periode)
        if not cek['valid']:
            messages.warning(request, cek['pesan'])
            return redirect('penilaian_list')
        
        return redirect('preview_smart', periode_id=periode.id)

    tahun_sekarang = date.today().year
    context = {
        'daftar_bulan': list(enumerate(Periode.BULAN_LABEL))[1:],
        'daftar_tahun': range(tahun_sekarang - 2, tahun_sekarang + 2),
        'bulan_default': date.today().month,
        'tahun_default': tahun_sekarang,
    }
    return render(request, 'admin_panel/smart_pilih_periode.html', context)
# ============================================================
# PROSES SMART
# ============================================================


@superuser_required
def smart_list(request):
    """
    Daftar semua periode yang sudah pernah diproses SMART-nya,
    plus tombol untuk memproses periode baru.
    """
    daftar_periode = (
        Periode.objects
        .filter(alternatif__hasil__isnull=False)
        .distinct()
        .order_by('-tahun', '-bulan')
    )
    context = {'daftar_periode': daftar_periode}
    return render(request, 'admin_panel/smart_list.html', context)


@superuser_required
def smart_proses_form(request):
    """
    Form pilih bulan & tahun, submit langsung menjalankan SmartCalculator
    untuk periode tsb (create Periode kalau belum ada).
    """
    if request.method == 'POST':
        bulan = int(request.POST.get('bulan'))
        tahun = int(request.POST.get('tahun'))

        periode = get_or_create_periode(bulan, tahun)

        # Cek kelengkapan penilaian sebelum proses SMART
        cek = cek_kelengkapan_penilaian(periode)
        if not cek['valid']:
            messages.warning(request, cek['pesan'])
            return redirect('penilaian_list')

        try:
            calc = SmartCalculator(periode_id=periode.id)
            calc.hitung()
            messages.success(request, f"Perhitungan SMART untuk {periode} berhasil diproses.")
            return redirect('smart_detail', periode_id=periode.id)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('smart_proses_form')

    tahun_sekarang = date.today().year
    context = {
        'daftar_bulan': list(enumerate(Periode.BULAN_LABEL))[1:],
        'daftar_tahun': range(tahun_sekarang - 2, tahun_sekarang + 2),
        'bulan_default': date.today().month,
        'tahun_default': tahun_sekarang,
    }
    return render(request, 'admin_panel/smart_proses_form.html', context)

@superuser_required
def smart_delete(request, periode_id):
    periode = get_object_or_404(Periode, pk=periode_id)
    if request.method == 'POST':
        alt_ids = Alternatif.objects.filter(periode=periode).values_list('id', flat=True)
        Utility.objects.filter(penilaian__alternatif_id__in=alt_ids).delete()
        PerhitunganSmart.objects.filter(alternatif_id__in=alt_ids).delete()
        HasilSmart.objects.filter(alternatif_id__in=alt_ids).delete()
        messages.success(request, f"Hasil SMART untuk {periode} berhasil dihapus.")
    return redirect('smart_list')

@superuser_required
def hasil_smart_view(request, periode_id):
    periode = get_object_or_404(Periode, pk=periode_id)
    hasil = get_hasil_dari_db(periode_id=periode.id)
    context = {'periode': periode, 'hasil': hasil}
    return render(request, 'admin_panel/hasil_smart.html', context)


@superuser_required
def preview_smart(request, periode_id):
    periode = get_object_or_404(Periode, pk=periode_id)
    try:
        calc = SmartCalculator(periode_id=periode.id)
        hasil = calc.get_tabel()
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('dashboard_admin')

    context = {'periode': periode, 'hasil': hasil, 'is_preview': True}
    return render(request, 'admin_panel/hasil_smart.html', context)


# ============================================================
# LAPORAN
# ============================================================

@superuser_required
def laporan_detail(request, periode_id):
    periode = get_object_or_404(Periode, pk=periode_id)
    hasil = get_hasil_dari_db(periode_id=periode.id)

    if not hasil:
        messages.warning(request, f"Belum ada hasil SMART untuk {periode}. Proses dulu perhitungannya.")
        return redirect('smart_list')

    daftar_kriteria = list(Kriteria.objects.filter(aktif=True).order_by('urutan', 'kode'))

    for h in hasil:
        detail_map = {d['kriteria_kode']: d for d in h['detail_kriteria']}
        h['matrix'] = [detail_map.get(k.kode) for k in daftar_kriteria]

    hasil_matrix = sorted(hasil, key=lambda h: h['nama'].lower())
    hasil_ranking = sorted(hasil, key=lambda h: h['ranking'])

    context = {
        'periode': periode,
        'hasil_matrix': hasil_matrix,
        'hasil_ranking': hasil_ranking,
        'daftar_kriteria': daftar_kriteria,
    }
    return render(request, 'admin_panel/laporan_detail.html', context)


@superuser_required
def laporan_pdf(request, periode_id):
    from xhtml2pdf import pisa
    from django.template.loader import render_to_string
    import io

    periode = get_object_or_404(Periode, pk=periode_id)
    hasil = get_hasil_dari_db(periode_id=periode.id)

    if not hasil:
        messages.warning(request, f"Belum ada hasil SMART untuk {periode}.")
        return redirect('smart_list')

    daftar_kriteria = list(Kriteria.objects.filter(aktif=True).order_by('urutan', 'kode'))

    for h in hasil:
        detail_map = {d['kriteria_kode']: d for d in h['detail_kriteria']}
        h['matrix'] = [detail_map.get(k.kode) for k in daftar_kriteria]

    hasil_matrix = sorted(hasil, key=lambda h: h['nama'].lower())
    hasil_ranking = sorted(hasil, key=lambda h: h['ranking'])

    html_string = render_to_string('admin_panel/laporan_pdf.html', {
        'periode': periode,
        'hasil_matrix': hasil_matrix,
        'hasil_ranking': hasil_ranking,
        'daftar_kriteria': daftar_kriteria,
    })

    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.StringIO(html_string), result)

    if pdf.err:
        messages.error(request, "Gagal generate PDF laporan.")
        return redirect('smart_detail', periode_id=periode.id)

    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="laporan_smart_{periode.tahun}_{periode.bulan}.pdf"'
    return response
