import calendar
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction

from ...decorators import superuser_required
from ...models import (
    Periode,
    Kriteria,
    SubKriteria,
    Alternatif,
    Absensi,
    HasilSmart,
    Karyawan,
    Penilaian,
    Utility,
    PerhitunganSmart,
)
from ...spk import get_or_create_periode, get_periode_if_exists
from ..absensi_matching import cari_subkriteria_untuk_nilai

KARYAWAN_PER_HALAMAN = 100
NAMA_HARI = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']


# ============================================================
# HELPER
# ============================================================
def _ambil_bulan_tahun(request):
    """
    Membaca ?bulan= dan ?tahun= dari URL.
    Mengembalikan (bulan, tahun), atau None kalau nilainya tidak valid.
    """
    hari_ini = date.today()

    try:
        bulan = int(request.GET.get('bulan', hari_ini.month))
        tahun = int(request.GET.get('tahun', hari_ini.year))
    except (TypeError, ValueError):
        return None

    if not 1 <= bulan <= 12:
        return None

    if not 2000 <= tahun <= 2100:
        return None

    return bulan, tahun


# ============================================================
# CRUD ABSENSI KARYAWAN
# ============================================================
@superuser_required
def absensi_bulanan(request):
    """
    Halaman Absensi Bulanan berupa matriks Karyawan x Tanggal.
    Data karyawan dipaginasi untuk menjaga performa halaman.
    GET hanya membaca data, sedangkan penyimpanan dilakukan melalui POST.
    """
    hasil_parse = _ambil_bulan_tahun(request)

    if hasil_parse is None:
        messages.error(request, 'Bulan atau tahun tidak valid.')
        return redirect('absensi_bulanan')

    bulan, tahun = hasil_parse
    page_number = request.GET.get('page', 1)

    # GET hanya mencari periode yang sudah ada.
    periode = get_periode_if_exists(bulan, tahun)

    jumlah_hari = calendar.monthrange(tahun, bulan)[1]
    daftar_tanggal = [
        date(tahun, bulan, d)
        for d in range(1, jumlah_hari + 1)
    ]

    # Karyawan aktif pada halaman saat ini.
    # Urutan memakai id sebagai pembeda supaya nama kembar tidak
    # tertukar atau hilang antar halaman.
    semua_karyawan = Karyawan.objects.filter(
        aktif=True
    ).order_by('nama', 'id')

    paginator = Paginator(
        semua_karyawan,
        KARYAWAN_PER_HALAMAN
    )

    page_obj = paginator.get_page(page_number)
    karyawan_halaman_ini = list(page_obj.object_list)

    # ========================================================
    # POST — SIMPAN ABSENSI
    # ========================================================
    if request.method == 'POST':
        posted_page = request.POST.get('page', page_number)

        with transaction.atomic():
            # Periode baru dibuat hanya ketika admin menyimpan absensi.
            if not periode:
                periode = get_or_create_periode(bulan, tahun)

            for karyawan in karyawan_halaman_ini:
                # Alternatif baru dibuat hanya saat proses penyimpanan.
                alternatif, _ = Alternatif.objects.get_or_create(
                    periode=periode,
                    karyawan=karyawan
                )

                for tgl in daftar_tanggal:
                    # Sabtu dan Minggu merupakan hari libur.
                    if tgl.weekday() >= 5:
                        Absensi.objects.filter(
                            alternatif=alternatif,
                            tanggal=tgl
                        ).delete()
                        continue

                    field_name = (
                        f"absensi_{karyawan.id}_{tgl.isoformat()}"
                    )

                    hadir = field_name in request.POST

                    Absensi.objects.update_or_create(
                        alternatif=alternatif,
                        tanggal=tgl,
                        defaults={
                            'status': hadir
                        }
                    )

        messages.success(
            request,
            f"Absensi {periode} (halaman {posted_page}) "
            f"berhasil disimpan."
        )

        # Nilai C1 pada penilaian disimpan sebagai salinan, jadi tidak
        # ikut berubah otomatis ketika absensi diubah.
        if Penilaian.objects.filter(alternatif__periode=periode).exists():
            messages.warning(
                request,
                f"Periode {periode} sudah memiliki data penilaian. "
                f"Simpan ulang penilaian agar nilai C1 diperbarui, "
                f"lalu proses ulang SMART jika hasilnya sudah ada."
            )

        return redirect(
            f"{request.path}"
            f"?bulan={bulan}"
            f"&tahun={tahun}"
            f"&page={posted_page}"
        )

    # ========================================================
    # GET — AMBIL ABSENSI YANG SUDAH TERSIMPAN
    # ========================================================
    existing = {}

    if periode:
        existing = {
            (a.alternatif.karyawan_id, a.tanggal): a.status
            for a in Absensi.objects.filter(
                alternatif__periode=periode,
                alternatif__karyawan__in=karyawan_halaman_ini,
            ).select_related('alternatif')
        }

    # ========================================================
    # DATA BARIS KARYAWAN
    # ========================================================
    rows = []

    for karyawan in karyawan_halaman_ini:
        cells = [
            {
                'checked': existing.get(
                    (karyawan.id, tgl),
                    False
                ),
                'name': (
                    f"absensi_{karyawan.id}_{tgl.isoformat()}"
                ),
                'is_weekend': tgl.weekday() >= 5,
                'is_libur': tgl.weekday() >= 5,
            }
            for tgl in daftar_tanggal
        ]

        rows.append({
            'karyawan': karyawan,
            'cells': cells
        })

    # ========================================================
    # HEADER KALENDER
    # ========================================================
    header_hari = [
        {
            'tanggal': tgl.day,
            'nama_hari': NAMA_HARI[tgl.weekday()],
            'is_weekend': tgl.weekday() >= 5,
            'is_libur': tgl.weekday() >= 5,
        }
        for tgl in daftar_tanggal
    ]

    context = {
        'periode': periode,
        'rows': rows,
        'header_hari': header_hari,
        'page_obj': page_obj,
        'daftar_bulan': list(
            enumerate(Periode.BULAN_LABEL)
        )[1:],
        'bulan_dipilih': bulan,
        'tahun_dipilih': tahun,
        'daftar_tahun': range(
            date.today().year - 2,
            date.today().year + 2
        ),
    }

    return render(
        request,
        'admin_panel/absensi_bulanan.html',
        context
    )


# ===========================================================================
# 1. LIST PENILAIAN
# ===========================================================================
@superuser_required
def penilaian_list(request):

    periode_ids = (
        Penilaian.objects
        .values_list('alternatif__periode_id', flat=True)
        .distinct()
    )

    daftar_periode = (
        Periode.objects
        .filter(id__in=periode_ids)
        .order_by('-tahun', '-bulan')
    )

    # Hitung karyawan yang benar-benar mempunyai Penilaian.
    for periode in daftar_periode:
        periode.jumlah_karyawan = (
            Penilaian.objects
            .filter(alternatif__periode=periode)
            .values('alternatif__karyawan_id')
            .distinct()
            .count()
        )

    return render(
        request,
        'admin_panel/penilaian_list.html',
        {
            'daftar_periode': daftar_periode,
        }
    )


# ===========================================================================
# 2. FORM PENILAIAN
# ===========================================================================
@superuser_required
def penilaian_form(request, periode_id=None):
    hari_ini = date.today()
    periode = None

    # ============================================================
    # AMBIL PERIODE
    # ============================================================
    if periode_id is not None:
        periode = get_object_or_404(Periode, pk=periode_id)

    bulan_get = request.GET.get('bulan')
    tahun_get = request.GET.get('tahun')

    if bulan_get and tahun_get:
        try:
            bulan = int(bulan_get)
            tahun = int(tahun_get)
        except (TypeError, ValueError):
            messages.error(request, 'Bulan atau tahun tidak valid.')
            return redirect('penilaian_form')

        if not 1 <= bulan <= 12:
            messages.error(request, 'Bulan tidak valid.')
            return redirect('penilaian_form')

        periode = get_periode_if_exists(bulan, tahun)

        if not periode:
            messages.warning(
                request,
                f'Periode {Periode.BULAN_LABEL[bulan]} {tahun} belum ada. Silakan isi absensi terlebih dahulu.'
            )
            return redirect('penilaian_form')

        return redirect('penilaian_form_periode', periode_id=periode.id)

    # ============================================================
    # HALAMAN AWAL
    # ============================================================
    if periode is None:
        context = {
            'periode': None,
            'daftar_bulan': list(enumerate(Periode.BULAN_LABEL))[1:],
            'bulan_dipilih': hari_ini.month,
            'tahun_dipilih': hari_ini.year,
            'daftar_tahun': range(hari_ini.year - 2, hari_ini.year + 2),
            'daftar_kriteria': [],
            'rows': [],
            'page_obj': None,
        }
        return render(request, 'admin_panel/penilaian_form.html', context)

    # ============================================================
    # KRITERIA AKTIF
    # ============================================================
    daftar_kriteria = list(
        Kriteria.objects
        .filter(aktif=True)
        .prefetch_related('subkriteria')
        .order_by('urutan', 'kode')
    )

    # ============================================================
    # HITUNG HARI KERJA
    # ============================================================
    jumlah_hari_bulan = calendar.monthrange(periode.tahun, periode.bulan)[1]

    daftar_tanggal_kerja = [
        date(periode.tahun, periode.bulan, hari)
        for hari in range(1, jumlah_hari_bulan + 1)
        if date(periode.tahun, periode.bulan, hari).weekday() < 5
    ]

    jumlah_hari_kerja = len(daftar_tanggal_kerja)

    # ============================================================
    # KARYAWAN + PAGINATION
    # ============================================================
    semua_karyawan = Karyawan.objects.filter(aktif=True).order_by('nama', 'id')
    page_number = request.GET.get('page', 1)

    paginator = Paginator(semua_karyawan, KARYAWAN_PER_HALAMAN)
    page_obj = paginator.get_page(page_number)
    karyawan_halaman_ini = list(page_obj.object_list)

    # ============================================================
    # ALTERNATIF YANG SUDAH ADA
    # ============================================================
    alternatif_map = {
        alternatif.karyawan_id: alternatif
        for alternatif in Alternatif.objects.filter(
            periode=periode,
            karyawan__in=karyawan_halaman_ini
        ).select_related('karyawan')
    }

    # ============================================================
    # HELPER ABSENSI
    # ============================================================
    def get_data_absensi(alternatif):
        if alternatif is None:
            return {
                'sudah_diisi': False,
                'jumlah_hadir': 0,
                'jumlah_tidak_hadir': None,
            }

        absensi_qs = Absensi.objects.filter(
            alternatif=alternatif,
            tanggal__year=periode.tahun,
            tanggal__month=periode.bulan
        )

        if not absensi_qs.exists():
            return {
                'sudah_diisi': False,
                'jumlah_hadir': 0,
                'jumlah_tidak_hadir': None,
            }

        jumlah_hadir = absensi_qs.filter(status=True).count()
        jumlah_tidak_hadir = max(jumlah_hari_kerja - jumlah_hadir, 0)

        return {
            'sudah_diisi': True,
            'jumlah_hadir': jumlah_hadir,
            'jumlah_tidak_hadir': jumlah_tidak_hadir,
        }

    # ============================================================
    # POST - SIMPAN PENILAIAN
    # ============================================================
    if request.method == 'POST':
        posted_page = request.POST.get('page', page_number)
        errors = []

        # Validasi seluruh input sebelum menyimpan
        for karyawan in karyawan_halaman_ini:
            alternatif = alternatif_map.get(karyawan.id)

            for kriteria in daftar_kriteria:
                kode = str(kriteria.kode).strip().upper()

                # C1 otomatis dari absensi
                if kode == 'C1':
                    data_absensi = get_data_absensi(alternatif)

                    if not data_absensi['sudah_diisi']:
                        errors.append(
                            f'{karyawan.nama} belum memiliki data absensi.'
                        )
                        continue

                    sub_otomatis = cari_subkriteria_untuk_nilai(
                        kriteria,
                        data_absensi['jumlah_tidak_hadir']
                    )

                    if not sub_otomatis:
                        errors.append(
                            f'Nilai absensi {karyawan.nama} tidak memiliki sub kriteria yang sesuai.'
                        )

                    continue

                # C2-C5 manual
                field_name = f'nilai_{karyawan.id}_{kriteria.id}'
                subkriteria_id = request.POST.get(field_name)

                if not subkriteria_id:
                    errors.append(
                        f'{karyawan.nama} pada {kriteria.kode} - {kriteria.nama} belum diisi.'
                    )
                    continue

                # isdigit() mencegah error 500 kalau nilai bukan angka.
                if (
                    not subkriteria_id.isdigit()
                    or not SubKriteria.objects.filter(
                        pk=subkriteria_id,
                        kriteria=kriteria
                    ).exists()
                ):
                    errors.append(
                        f'Pilihan {kriteria.kode} untuk {karyawan.nama} tidak valid.'
                    )

        if errors:
            messages.error(
                request,
                'Penilaian belum lengkap. ' + ' '.join(errors[:3])
            )

            if len(errors) > 3:
                messages.error(
                    request,
                    f'Dan {len(errors) - 3} lainnya.'
                )

            return redirect(f'{request.path}?page={posted_page}')

        # ========================================================
        # SIMPAN SETELAH SEMUA DATA VALID
        # ========================================================
        with transaction.atomic():
            for karyawan in karyawan_halaman_ini:
                alternatif, _ = Alternatif.objects.get_or_create(
                    periode=periode,
                    karyawan=karyawan
                )

                for kriteria in daftar_kriteria:
                    kode = str(kriteria.kode).strip().upper()

                    # C1 otomatis dari absensi
                    if kode == 'C1':
                        data_absensi = get_data_absensi(alternatif)

                        sub_otomatis = cari_subkriteria_untuk_nilai(
                            kriteria,
                            data_absensi['jumlah_tidak_hadir']
                        )

                        Penilaian.objects.update_or_create(
                            alternatif=alternatif,
                            kriteria=kriteria,
                            defaults={
                                'subkriteria': sub_otomatis,
                                'nilai_raw': sub_otomatis.nilai,
                            }
                        )
                        continue

                    # C2-C5 manual
                    field_name = f'nilai_{karyawan.id}_{kriteria.id}'
                    subkriteria_id = request.POST.get(field_name)

                    subkriteria = SubKriteria.objects.get(
                        pk=subkriteria_id,
                        kriteria=kriteria
                    )

                    Penilaian.objects.update_or_create(
                        alternatif=alternatif,
                        kriteria=kriteria,
                        defaults={
                            'subkriteria': subkriteria,
                            'nilai_raw': subkriteria.nilai,
                        }
                    )

        messages.success(
            request,
            f'Penilaian {periode} berhasil disimpan.'
        )

        # Hasil SMART yang sudah ada dihitung dari penilaian yang lama.
        if HasilSmart.objects.filter(alternatif__periode=periode).exists():
            messages.warning(
                request,
                f'Hasil SMART {periode} masih memakai penilaian lama. '
                f'Proses ulang SMART agar hasilnya diperbarui.'
            )

        return redirect(f'{request.path}?page={posted_page}')

    # ============================================================
    # GET - PENILAIAN YANG SUDAH TERSIMPAN
    # ============================================================
    existing = {
        (penilaian.alternatif.karyawan_id, penilaian.kriteria_id): penilaian
        for penilaian in Penilaian.objects.filter(
            alternatif__periode=periode,
            alternatif__karyawan__in=karyawan_halaman_ini
        ).select_related(
            'alternatif',
            'alternatif__karyawan',
            'kriteria',
            'subkriteria'
        )
    }

    # ============================================================
    # SUSUN MATRIX KARYAWAN × KRITERIA
    # ============================================================
    rows = []

    for karyawan in karyawan_halaman_ini:
        alternatif = alternatif_map.get(karyawan.id)
        cells = []

        for kriteria in daftar_kriteria:
            kode = str(kriteria.kode).strip().upper()
            penilaian_ada = existing.get((karyawan.id, kriteria.id))

            # C1 otomatis dari absensi
            if kode == 'C1':
                data_absensi = get_data_absensi(alternatif)

                if not data_absensi['sudah_diisi']:
                    cells.append({
                        'kriteria': kriteria,
                        'otomatis': True,
                        'ada_data_absensi': False,
                        'ada_data': False,
                        'jumlah_hadir': None,
                        'jumlah_tidak_hadir': None,
                        'subkriteria_nama': None,
                        'nilai': None,
                    })
                    continue

                jumlah_tidak_hadir = data_absensi['jumlah_tidak_hadir']

                sub_otomatis = cari_subkriteria_untuk_nilai(
                    kriteria,
                    jumlah_tidak_hadir
                )

                cells.append({
                    'kriteria': kriteria,
                    'otomatis': True,
                    'ada_data_absensi': True,
                    'ada_data': sub_otomatis is not None,
                    'jumlah_hadir': data_absensi['jumlah_hadir'],
                    'jumlah_tidak_hadir': jumlah_tidak_hadir,
                    'subkriteria_nama': sub_otomatis.nama if sub_otomatis else None,
                    'nilai': sub_otomatis.nilai if sub_otomatis else None,
                })
                continue

            # C2-C5 manual
            cells.append({
                'kriteria': kriteria,
                'otomatis': False,
                'field_name': f'nilai_{karyawan.id}_{kriteria.id}',
                'opsi': kriteria.subkriteria.all(),
                'selected_id': penilaian_ada.subkriteria_id if penilaian_ada else None,
            })

        rows.append({
            'karyawan': karyawan,
            'cells': cells,
        })

    context = {
        'periode': periode,
        'daftar_bulan': list(enumerate(Periode.BULAN_LABEL))[1:],
        'bulan_dipilih': periode.bulan,
        'tahun_dipilih': periode.tahun,
        'daftar_tahun': range(hari_ini.year - 2, hari_ini.year + 2),
        'daftar_kriteria': daftar_kriteria,
        'rows': rows,
        'page_obj': page_obj,
    }

    return render(request, 'admin_panel/penilaian_form.html', context)


# ===========================================================================
# 3. HAPUS PENILAIAN
# ===========================================================================
@superuser_required
def penilaian_hapus(request, periode_id):
    periode = get_object_or_404(
        Periode,
        pk=periode_id
    )

    if request.method != 'POST':
        return redirect(
            'penilaian_list'
        )

    label = str(periode)

    with transaction.atomic():
        # Hapus data penilaian dan hasil SMART, pertahankan Absensi dan Periode
        alt_ids = Alternatif.objects.filter(periode=periode).values_list('id', flat=True)

        # Hapus dalam urutan yang aman terhadap FK
        Utility.objects.filter(penilaian__alternatif_id__in=alt_ids).delete()
        PerhitunganSmart.objects.filter(alternatif_id__in=alt_ids).delete()
        HasilSmart.objects.filter(alternatif_id__in=alt_ids).delete()
        Penilaian.objects.filter(alternatif_id__in=alt_ids).delete()

        # Alternatif tetap dipertahankan karena masih bisa digunakan untuk Absensi
        # Periode tetap dipertahankan

    messages.success(
        request,
        (
            f'Data penilaian {label} berhasil dihapus. '
            f'Data absensi tetap dipertahankan.'
        )
    )

    return redirect(
        'penilaian_list'
    )