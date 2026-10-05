from datetime import date
import calendar

from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from ..decorators import karyawan_required
from ..models import Absensi, Alternatif, HasilSmart, Periode


BULAN_LABEL = Periode.BULAN_LABEL


def _tahun_tersedia(karyawan):
    return list(Alternatif.objects.filter(karyawan=karyawan)
                .order_by('-periode__tahun')
                .values_list('periode__tahun', flat=True).distinct())


def _angka_filter(request, nama, default, minimum, maximum):
    try:
        nilai = int(request.GET.get(nama, default))
    except (TypeError, ValueError):
        return default
    return nilai if minimum <= nilai <= maximum else default


def _filter_periode(request, karyawan):
    today = date.today()
    bulan = _angka_filter(request, 'bulan', today.month, 1, 12)
    tahun = _angka_filter(request, 'tahun', today.year, 1, 9999)
    return {
        'bulan_dipilih': bulan,
        'tahun_dipilih': tahun,
        'label_periode': f'{BULAN_LABEL[bulan]} {tahun}',
        'daftar_bulan': list(enumerate(BULAN_LABEL))[1:],
        'daftar_tahun': sorted(set(_tahun_tersedia(karyawan)) | {today.year, tahun}, reverse=True),
    }


def _data_absensi(alternatif):
    """Read only: weekend dan tanggal di luar periode tidak masuk ringkasan."""
    if alternatif is None:
        return {}, None
    periode = alternatif.periode
    catatan = dict(Absensi.objects.filter(
        alternatif=alternatif, tanggal__year=periode.tahun,
        tanggal__month=periode.bulan,
    ).values_list('tanggal', 'status'))
    hari_kerja = [status for tanggal, status in catatan.items() if tanggal.weekday() < 5]
    if not hari_kerja:
        return catatan, None
    hadir = sum(hari_kerja)
    return catatan, {
        'total': len(hari_kerja), 'hadir': hadir,
        'tidak_hadir': len(hari_kerja) - hadir,
        'persen_hadir': hadir / len(hari_kerja) * 100,
    }


def _hasil_karyawan(karyawan):
    return HasilSmart.objects.filter(alternatif__karyawan=karyawan).select_related(
        'alternatif__periode').order_by('-alternatif__periode__tahun', '-alternatif__periode__bulan')


def _rincian_kriteria(alternatif):
    return alternatif.perhitungan.select_related('kriteria').order_by(
        'kriteria__urutan', 'kriteria__kode')


@karyawan_required
def dashboard_karyawan(request):
    karyawan = request.user.karyawan
    context = _filter_periode(request, karyawan)
    bulan, tahun = context['bulan_dipilih'], context['tahun_dipilih']
    periode = Periode.objects.filter(bulan=bulan, tahun=tahun).first()
    alternatif = Alternatif.objects.filter(
        karyawan=karyawan, periode=periode).select_related('periode', 'hasil').first() if periode else None
    hasil = getattr(alternatif, 'hasil', None)
    _, ringkasan = _data_absensi(alternatif)
    hasil_qs = _hasil_karyawan(karyawan)
    hasil_sebelumnya = None
    perbandingan = None
    if hasil is not None:
        hasil_sebelumnya = hasil_qs.filter(
            Q(alternatif__periode__tahun__lt=tahun) |
            Q(alternatif__periode__tahun=tahun, alternatif__periode__bulan__lt=bulan)
        ).first()
        if hasil_sebelumnya:
            _, absensi_sebelumnya = _data_absensi(hasil_sebelumnya.alternatif)
            gerak = hasil_sebelumnya.ranking - hasil.ranking
            perbandingan = {
                'selisih_nilai': round(hasil.total_nilai - hasil_sebelumnya.total_nilai, 4),
                'perubahan_ranking': f'Naik {gerak} posisi' if gerak > 0 else (
                    f'Turun {abs(gerak)} posisi' if gerak < 0 else 'Tetap'),
                'absensi_sebelumnya': absensi_sebelumnya,
                'selisih_kehadiran': round(ringkasan['persen_hadir'] - absensi_sebelumnya['persen_hadir'], 1)
                    if ringkasan and absensi_sebelumnya else None,
            }
    breakdown = []
    if hasil is not None:
        breakdown = [{
            'kode': p.kriteria.kode, 'nama': p.kriteria.nama,
            'bobot_ternormalisasi': p.bobot_ternormalisasi,
            'nilai_utility': p.nilai_utility, 'nilai_akhir': p.nilai_akhir_kriteria,
            'kontribusi_persen': p.nilai_akhir_kriteria / hasil.total_nilai * 100 if hasil.total_nilai else None,
        } for p in _rincian_kriteria(alternatif)]
    tren = list(hasil_qs.filter(alternatif__periode__tahun=tahun).order_by('alternatif__periode__bulan'))
    today = date.today()
    context.update({
        'karyawan': karyawan, 'periode_dipilih': periode,
        'is_bulan_berjalan': (bulan, tahun) == (today.month, today.year),
        'alternatif_dipilih': alternatif, 'hasil_dipilih': hasil,
        'breakdown_kriteria': breakdown, 'ringkasan_absensi': ringkasan,
        'hasil_sebelumnya': hasil_sebelumnya, 'perbandingan': perbandingan,
        'tahun_ini': tahun,
        'tren_tahun_ini': [{
            'bulan': h.alternatif.periode.bulan, 'bulan_label': BULAN_LABEL[h.alternatif.periode.bulan],
            'total_nilai': h.total_nilai, 'ranking': h.ranking, 'predikat': h.predikat,
            'is_dipilih': h.alternatif.periode.bulan == bulan,
        } for h in tren],
        'rata_rata_tahun_ini': sum(h.total_nilai for h in tren) / len(tren) if tren else None,
        'riwayat_terbaru': list(hasil_qs[:5]),
    })
    return render(request, 'karyawan/dashboard.html', context)


@karyawan_required
def riwayat_penilaian(request):
    karyawan = request.user.karyawan
    daftar_tahun = _tahun_tersedia(karyawan)
    tahun = _angka_filter(request, 'tahun', daftar_tahun[0] if daftar_tahun else date.today().year, 1, 9999)
    daftar_alternatif = list(Alternatif.objects.filter(
        karyawan=karyawan, periode__tahun=tahun).select_related('periode', 'hasil')
        .order_by('-periode__tahun', '-periode__bulan'))
    # Satu hasil sebelum tahun terpilih cukup untuk perbandingan lintas tahun.
    sebelumnya = _hasil_karyawan(karyawan).filter(alternatif__periode__tahun__lt=tahun).first()
    for alternatif in reversed(daftar_alternatif):
        hasil = getattr(alternatif, 'hasil', None)
        alternatif.selisih_nilai = None
        alternatif.periode_sebelumnya = None
        if hasil is not None:
            if sebelumnya is not None:
                alternatif.selisih_nilai = round(hasil.total_nilai - sebelumnya.total_nilai, 4)
                alternatif.periode_sebelumnya = sebelumnya.alternatif.periode
            sebelumnya = hasil
    return render(request, 'karyawan/riwayat.html', {
        'karyawan': karyawan, 'daftar_alternatif': daftar_alternatif,
        'daftar_tahun': sorted(set(daftar_tahun) | {tahun}, reverse=True), 'tahun_dipilih': tahun,
    })


@karyawan_required
def detail_penilaian(request, alternatif_id):
    alternatif = get_object_or_404(
        Alternatif.objects.select_related('periode', 'hasil'),
        pk=alternatif_id, karyawan=request.user.karyawan,
    )
    hasil = getattr(alternatif, 'hasil', None)
    detail = list(_rincian_kriteria(alternatif)) if hasil is not None else []
    penilaian = {p.kriteria_id: p for p in alternatif.penilaian.select_related('subkriteria')} if detail else {}
    for rincian in detail:
        rincian.penilaian_asli = penilaian.get(rincian.kriteria_id)
    _, ringkasan = _data_absensi(alternatif)
    return render(request, 'karyawan/detail.html', {
        'karyawan': request.user.karyawan, 'alternatif': alternatif, 'hasil': hasil,
        'detail_kriteria': detail, 'ringkasan_absensi': ringkasan,
        'bulan_dipilih': alternatif.periode.bulan, 'tahun_dipilih': alternatif.periode.tahun,
    })


@karyawan_required
def absensi_saya(request):
    karyawan = request.user.karyawan
    context = _filter_periode(request, karyawan)
    bulan, tahun = context['bulan_dipilih'], context['tahun_dipilih']
    periode = Periode.objects.filter(bulan=bulan, tahun=tahun).first()
    alternatif = Alternatif.objects.filter(karyawan=karyawan, periode=periode).select_related('periode').first() if periode else None
    catatan, ringkasan = _data_absensi(alternatif)
    jumlah_hari = calendar.monthrange(tahun, bulan)[1]
    daftar_absensi = []
    if alternatif:
        for hari in range(1, jumlah_hari + 1):
            tanggal = date(tahun, bulan, hari)
            daftar_absensi.append({
                'tanggal': tanggal, 'hadir': catatan.get(tanggal),
                'tercatat': tanggal in catatan, 'is_weekend': tanggal.weekday() >= 5,
                'nama_hari': ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'][tanggal.weekday()],
            })
    context.update({
        'karyawan': karyawan, 'periode': periode, 'daftar_absensi': daftar_absensi,
        'ringkasan_absensi': ringkasan,
        'jumlah_hadir': ringkasan['hadir'] if ringkasan else 0,
        'jumlah_tidak_hadir': ringkasan['tidak_hadir'] if ringkasan else 0,
        'jumlah_hari_bulan': jumlah_hari, 'ada_data': alternatif is not None,
    })
    return render(request, 'karyawan/absensi_saya.html', context)
