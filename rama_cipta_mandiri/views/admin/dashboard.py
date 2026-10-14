from django.shortcuts import render
from django.db.models import Sum

from ...decorators import superuser_required
from ...models import Periode, Kriteria, SubKriteria, Alternatif, Absensi, HasilSmart, Karyawan, Penilaian, PerhitunganSmart

@superuser_required
def dashboard_admin(request):
    # =========================================================
    # PERIODE PENILAIAN TERAKHIR YANG MEMILIKI PENILAIAN
    # =========================================================
    periode_penilaian = (
        Periode.objects
        .filter(alternatif__penilaian__isnull=False)
        .distinct()
        .order_by('-tahun', '-bulan')
        .first()
    )

    # =========================================================
    # MASTER DATA
    # =========================================================
    kriteria_aktif_qs = Kriteria.objects.filter(aktif=True)

    total_karyawan = Karyawan.objects.count()
    total_karyawan_aktif = Karyawan.objects.filter(aktif=True).count()
    total_karyawan_nonaktif = total_karyawan - total_karyawan_aktif

    total_kriteria = kriteria_aktif_qs.count()

    total_subkriteria = (
        SubKriteria.objects
        .filter(kriteria__aktif=True)
        .count()
    )

    total_bobot = (
        kriteria_aktif_qs
        .aggregate(total=Sum('bobot'))['total']
        or 0
    )

    total_bobot = round(float(total_bobot), 2)

    # Aturan yang sama dengan halaman Kriteria: total bobot harus 100.
    bobot_valid = round(abs(total_bobot - 100), 2) <= 0.01

    # =========================================================
    # DEFAULT DATA PERIODE
    # =========================================================
    total_alternatif = 0

    total_absensi = 0
    total_hadir = 0
    total_tidak_hadir = 0

    total_penilaian = 0
    total_penilaian_seharusnya = 0
    progres_penilaian = 0
    penilaian_lengkap = False

    total_perhitungan = 0

    total_hasil = 0
    sudah_diproses_smart = False
    ranking_teratas = None

    # =========================================================
    # DATA PERIODE PENILAIAN
    # =========================================================
    if periode_penilaian:
        # -----------------------------------------------------
        # ALTERNATIF
        # -----------------------------------------------------
        alternatif_qs = Alternatif.objects.filter(
            periode=periode_penilaian
        )

        total_alternatif = alternatif_qs.count()

        # -----------------------------------------------------
        # ABSENSI
        # -----------------------------------------------------
        absensi_qs = Absensi.objects.filter(
            alternatif__periode=periode_penilaian
        )

        total_absensi = absensi_qs.count()
        total_hadir = absensi_qs.filter(status=True).count()
        total_tidak_hadir = absensi_qs.filter(status=False).count()

        # -----------------------------------------------------
        # PENILAIAN
        # -----------------------------------------------------
        penilaian_qs = Penilaian.objects.filter(
            alternatif__periode=periode_penilaian,
            kriteria__aktif=True
        )

        total_penilaian = penilaian_qs.count()

        total_penilaian_seharusnya = (
            total_alternatif * total_kriteria
        )

        if total_penilaian_seharusnya > 0:
            progres_penilaian = round(
                (total_penilaian / total_penilaian_seharusnya) * 100
            )

            progres_penilaian = min(
                progres_penilaian,
                100
            )

        penilaian_lengkap = (
            total_penilaian_seharusnya > 0
            and total_penilaian >= total_penilaian_seharusnya
        )

        # -----------------------------------------------------
        # PERHITUNGAN SMART
        # -----------------------------------------------------
        total_perhitungan = (
            PerhitunganSmart.objects
            .filter(
                alternatif__periode=periode_penilaian
            )
            .count()
        )

        # -----------------------------------------------------
        # HASIL SMART
        # -----------------------------------------------------
        hasil_qs = (
            HasilSmart.objects
            .filter(
                alternatif__periode=periode_penilaian
            )
            .select_related(
                'alternatif',
                'alternatif__karyawan',
                'alternatif__periode'
            )
            .order_by('ranking')
        )

        total_hasil = hasil_qs.count()

        sudah_diproses_smart = (
            total_hasil > 0
        )

        ranking_teratas = (
            hasil_qs
            .filter(ranking=1)
            .first()
        )

    # =========================================================
    # KARYAWAN TERBAIK SETIAP BULAN
    # =========================================================
    karyawan_terbaik_bulanan = (
        HasilSmart.objects
        .filter(ranking=1)
        .select_related(
            'alternatif',
            'alternatif__karyawan',
            'alternatif__periode'
        )
        .order_by(
            '-alternatif__periode__tahun',
            '-alternatif__periode__bulan'
        )[:6]
    )

    # =========================================================
    # CONTEXT
    # =========================================================
    context = {
        'periode_penilaian': periode_penilaian,

        'total_karyawan': total_karyawan,
        'total_karyawan_aktif': total_karyawan_aktif,
        'total_karyawan_nonaktif': total_karyawan_nonaktif,

        'total_kriteria': total_kriteria,
        'total_subkriteria': total_subkriteria,
        'total_bobot': total_bobot,
        'bobot_valid': bobot_valid,

        'total_alternatif': total_alternatif,

        'total_absensi': total_absensi,
        'total_hadir': total_hadir,
        'total_tidak_hadir': total_tidak_hadir,

        'total_penilaian': total_penilaian,
        'total_penilaian_seharusnya': total_penilaian_seharusnya,
        'progres_penilaian': progres_penilaian,
        'penilaian_lengkap': penilaian_lengkap,

        'total_perhitungan': total_perhitungan,

        'total_hasil': total_hasil,
        'sudah_diproses_smart': sudah_diproses_smart,
        'ranking_teratas': ranking_teratas,

        'karyawan_terbaik_bulanan': karyawan_terbaik_bulanan,
    }

    return render(
        request,
        'admin_panel/dashboard.html',
        context
    )