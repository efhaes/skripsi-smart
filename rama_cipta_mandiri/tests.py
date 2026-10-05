from datetime import date

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from .models import (Absensi, Alternatif, HasilSmart, Karyawan, Kriteria,
                     Penilaian, PerhitunganSmart, Periode, SubKriteria)


class KaryawanPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('pegawai_a')
        cls.karyawan = Karyawan.objects.create(user=cls.user, nama='Pegawai A')
        cls.other_user = User.objects.create_user('pegawai_b')
        cls.other = Karyawan.objects.create(user=cls.other_user, nama='Rahasia Pegawai B')
        cls.admin = User.objects.create_superuser('admin', password='test-only')
        cls.no_profile = User.objects.create_user('tanpa_profil')
        cls.empty_user = User.objects.create_user('tanpa_hasil')
        Karyawan.objects.create(user=cls.empty_user, nama='Tanpa Hasil')
        cls.previous_period = Periode.objects.create(bulan=12, tahun=2025)
        cls.period = Periode.objects.create(bulan=2, tahun=2026)
        cls.pending_period = Periode.objects.create(bulan=1, tahun=2026)
        cls.previous = Alternatif.objects.create(karyawan=cls.karyawan, periode=cls.previous_period)
        cls.selected = Alternatif.objects.create(karyawan=cls.karyawan, periode=cls.period)
        cls.pending = Alternatif.objects.create(karyawan=cls.karyawan, periode=cls.pending_period)
        cls.foreign = Alternatif.objects.create(karyawan=cls.other, periode=cls.period)
        HasilSmart.objects.create(alternatif=cls.previous, total_nilai=.4, ranking=5, predikat='Cukup')
        HasilSmart.objects.create(alternatif=cls.selected, total_nilai=.6, ranking=2, predikat='Baik')
        HasilSmart.objects.create(alternatif=cls.foreign, total_nilai=.9876, ranking=1, predikat='Rahasia')
        cls.criterion = Kriteria.objects.create(kode='C2', nama='Kualitas', bobot=100, tipe='benefit')
        sub = SubKriteria.objects.create(kriteria=cls.criterion, nama='Sesuai target', nilai=80)
        Penilaian.objects.create(alternatif=cls.selected, kriteria=cls.criterion, subkriteria=sub, nilai_raw=80)
        PerhitunganSmart.objects.create(alternatif=cls.selected, kriteria=cls.criterion,
                                       bobot_ternormalisasi=1, nilai_utility=.6, nilai_akhir_kriteria=.6)
        for day, status in [(2, True), (3, False), (7, True)]:
            Absensi.objects.create(alternatif=cls.selected, tanggal=date(2026, 2, day), status=status)
        Absensi.objects.create(alternatif=cls.selected, tanggal=date(2026, 3, 2), status=True)
        Absensi.objects.create(alternatif=cls.previous, tanggal=date(2025, 12, 1), status=True)

    def setUp(self):
        self.client.force_login(self.user)

    def dashboard(self, **params):
        return self.client.get(reverse('dashboard_karyawan'), params or {'bulan': 2, 'tahun': 2026})

    def test_dashboard_stored_results_and_previous_available(self):
        response = self.dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['hasil_dipilih'].total_nilai, .6)
        self.assertEqual(response.context['hasil_sebelumnya'].alternatif_id, self.previous.pk)
        self.assertEqual(response.context['perbandingan']['selisih_nilai'], .2)
        self.assertEqual(response.context['perbandingan']['perubahan_ranking'], 'Naik 3 posisi')
        self.assertEqual(response.context['perbandingan']['selisih_kehadiran'], -50)
        self.assertContains(response, '0.6000')
        self.assertNotContains(response, 'Rahasia')
        self.assertEqual(len(response.context['riwayat_terbaru']), 2)

    def test_attendance_consistent_and_missing_days_are_not_absent(self):
        urls = [reverse('dashboard_karyawan'), reverse('absensi_saya'),
                reverse('detail_penilaian', args=[self.selected.pk])]
        for url in urls:
            response = self.client.get(url, {'bulan': 2, 'tahun': 2026})
            self.assertEqual(response.context['ringkasan_absensi'], {
                'total': 2, 'hadir': 1, 'tidak_hadir': 1, 'persen_hadir': 50,
            })
        self.assertContains(self.client.get(urls[1], {'bulan': 2, 'tahun': 2026}), 'Belum Dicatat')
        self.assertContains(self.client.get(urls[1], {'bulan': 2, 'tahun': 2026}), 'Libur')

    def test_empty_states_and_one_result(self):
        response = self.dashboard(bulan=12, tahun=2025)
        self.assertIsNone(response.context['perbandingan'])
        self.assertEqual(len(response.context['tren_tahun_ini']), 1)
        response = self.dashboard(bulan=1, tahun=2026)
        self.assertContains(response, 'belum diproses')
        response = self.dashboard(bulan=1, tahun=2030)
        self.assertContains(response, 'Belum ada data periode')
        self.assertEqual(response.context['tren_tahun_ini'], [])
        self.client.force_login(self.empty_user)
        for name in ['dashboard_karyawan', 'riwayat_penilaian', 'absensi_saya']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_attendance_visible_without_smart_and_without_records(self):
        Absensi.objects.create(alternatif=self.pending, tanggal=date(2026, 1, 1), status=True)
        response = self.dashboard(bulan=1, tahun=2026)
        self.assertIsNone(response.context['hasil_dipilih'])
        self.assertEqual(response.context['ringkasan_absensi']['hadir'], 1)
        response = self.client.get(reverse('detail_penilaian', args=[self.pending.pk]))
        self.assertContains(response, 'Ringkasan Kehadiran')
        Absensi.objects.filter(alternatif=self.pending).delete()
        self.assertIsNone(self.dashboard(bulan=1, tahun=2026).context['ringkasan_absensi'])

    def test_zero_result_retains_breakdown_and_zero_average(self):
        HasilSmart.objects.filter(alternatif=self.selected).update(total_nilai=0)
        response = self.dashboard()
        self.assertEqual(len(response.context['breakdown_kriteria']), 1)
        self.assertContains(response, 'Rata-rata nilai: 0.0000')
        self.assertEqual(response.context['perbandingan']['selisih_nilai'], -.4)

    def test_history_cross_year_delta_and_pending(self):
        response = self.client.get(reverse('riwayat_penilaian'), {'tahun': 2026})
        self.assertEqual(response.context['daftar_alternatif'][0].selisih_nilai, .2)
        self.assertContains(response, 'Desember 2025')
        self.assertContains(response, 'Belum diproses')
        self.assertNotContains(response, 'Rahasia')
        self.assertContains(self.client.get(reverse('riwayat_penilaian'), {'tahun': 2030}), 'Belum ada riwayat')

    def test_detail_ownership_and_original_values(self):
        response = self.client.get(reverse('detail_penilaian', args=[self.selected.pk]))
        self.assertContains(response, 'Sesuai target')
        self.assertContains(response, '80.00')
        self.assertEqual(self.client.get(reverse('detail_penilaian', args=[self.foreign.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('detail_penilaian', args=[999999])).status_code, 404)

    def test_filters_reject_invalid_dates(self):
        for name in ['dashboard_karyawan', 'absensi_saya', 'riwayat_penilaian']:
            for value in ['abc', '', '0', '-1', '10000', '9999999999999999999999']:
                with self.subTest(name=name, value=value):
                    self.assertEqual(self.client.get(reverse(name), {'bulan': value, 'tahun': value}).status_code, 200)

    def test_gets_issue_no_database_writes(self):
        requests = [(reverse(name), params) for name in
                    ['dashboard_karyawan', 'absensi_saya', 'riwayat_penilaian']
                    for params in [{'bulan': 2, 'tahun': 2026}, {'bulan': 1, 'tahun': 2030}]]
        requests += [(reverse('detail_penilaian', args=[alt.pk]), {})
                     for alt in [self.selected, self.pending, self.foreign]]
        for url, params in requests:
            with CaptureQueriesContext(connection) as queries:
                self.client.get(url, params)
            writes = [q['sql'] for q in queries if q['sql'].lstrip().split()[0].upper()
                      in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE'}]
            self.assertEqual(writes, [], url)

    def test_role_permissions_and_routes(self):
        names = ['dashboard_karyawan', 'absensi_saya', 'riwayat_penilaian']
        urls = [reverse(name) for name in names] + [reverse('detail_penilaian', args=[self.selected.pk])]
        for name in names:
            self.assertEqual(resolve(reverse(name)).url_name, name)
        self.assertEqual(self.client.get(reverse('dashboard_admin')).status_code, 403)
        for user in [self.admin, self.no_profile]:
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_latest_history_limited_and_queries_do_not_grow_per_result(self):
        with CaptureQueriesContext(connection) as initial:
            self.dashboard()
        for month in range(3, 10):
            period = Periode.objects.create(bulan=month, tahun=2026)
            alt = Alternatif.objects.create(karyawan=self.karyawan, periode=period)
            HasilSmart.objects.create(alternatif=alt, total_nilai=.5, ranking=3, predikat='Cukup')
        with CaptureQueriesContext(connection) as expanded:
            response = self.dashboard()
        self.assertEqual(len(response.context['riwayat_terbaru']), 5)
        self.assertEqual(response.context['riwayat_terbaru'][0].alternatif.periode.bulan, 9)
        self.assertEqual(len(initial), len(expanded))

    def test_admin_pages_still_render(self):
        self.client.force_login(self.admin)
        for name in ['dashboard_admin', 'karyawan_list', 'kriteria_list',
                     'subkriteria_list', 'penilaian_list', 'smart_list', 'absensi_bulanan']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name), {'bulan': 2, 'tahun': 2026}).status_code, 200)

    def test_previous_result_skips_unprocessed_month_in_same_year(self):
        self.previous_period.tahun = 2026
        self.previous_period.bulan = 8
        self.previous_period.save()
        self.period.bulan = 10
        self.period.save()
        self.pending_period.bulan = 9
        self.pending_period.save()
        HasilSmart.objects.filter(alternatif=self.selected).update(ranking=7)
        response = self.dashboard(bulan=10, tahun=2026)
        self.assertEqual(response.context['hasil_sebelumnya'].alternatif_id, self.previous.pk)
        self.assertEqual(response.context['perbandingan']['perubahan_ranking'], 'Turun 2 posisi')
        self.assertIsNone(response.context['perbandingan']['selisih_kehadiran'])
        HasilSmart.objects.filter(alternatif=self.selected).update(ranking=5, total_nilai=.4)
        response = self.dashboard(bulan=10, tahun=2026)
        self.assertEqual(response.context['perbandingan']['perubahan_ranking'], 'Tetap')
        self.assertEqual(response.context['perbandingan']['selisih_nilai'], 0)

    def test_visible_dashboard_sections_and_comparison_pairs(self):
        response = self.dashboard()
        for label in ['Halo, Pegawai A', 'Perbandingan Periode Sebelumnya',
                      'Rincian Kriteria', 'Ringkasan Kehadiran', 'Tren Penilaian',
                      'Riwayat Penilaian Terbaru', 'Persentase Kehadiran']:
            self.assertContains(response, label)
        for pair in ['Desember 2025 &rarr; Februari 2026',
                     '0.4000 &rarr; 0.6000', '#5 &rarr; #2', '100.0% &rarr; 50.0%']:
            self.assertContains(response, pair)
        self.assertContains(response, 'Perubahan: +0.2000')
        self.assertContains(response, 'Naik 3 posisi')
        self.assertContains(response, '-50.0 poin persentase')
        self.assertContains(response, reverse('absensi_saya') + '?bulan=2&amp;tahun=2026')

    def test_missing_attendance_is_not_displayed_as_zero(self):
        Absensi.objects.filter(alternatif=self.selected).delete()
        response = self.dashboard()
        self.assertContains(response, '100.0% &rarr; Belum tersedia')
        self.assertContains(response, 'Perubahan belum dapat dibandingkan')
        self.assertNotContains(response, '100.0% &rarr; 0.0%')

    def test_all_four_attendance_statuses_are_visible(self):
        response = self.client.get(reverse('absensi_saya'), {'bulan': 2, 'tahun': 2026})
        for label in ['Hadir', 'Tidak Hadir', 'Belum Dicatat', 'Libur', 'Hari kerja tercatat']:
            self.assertContains(response, label)

    def test_history_and_detail_query_counts_do_not_grow_per_row(self):
        history_url = reverse('riwayat_penilaian')
        detail_url = reverse('detail_penilaian', args=[self.selected.pk])
        with CaptureQueriesContext(connection) as history_before:
            self.client.get(history_url, {'tahun': 2026})
        with CaptureQueriesContext(connection) as detail_before:
            self.client.get(detail_url)
        for month in range(3, 7):
            period = Periode.objects.create(bulan=month, tahun=2026)
            alt = Alternatif.objects.create(karyawan=self.karyawan, periode=period)
            HasilSmart.objects.create(alternatif=alt, total_nilai=.5, ranking=3, predikat='Cukup')
            criterion = Kriteria.objects.create(kode=f'C{month}', nama=f'Kriteria {month}', bobot=0, tipe='benefit')
            Penilaian.objects.create(alternatif=self.selected, kriteria=criterion, nilai_raw=0)
            PerhitunganSmart.objects.create(alternatif=self.selected, kriteria=criterion,
                                           bobot_ternormalisasi=0, nilai_utility=0, nilai_akhir_kriteria=0)
        with CaptureQueriesContext(connection) as history_after:
            self.client.get(history_url, {'tahun': 2026})
        with CaptureQueriesContext(connection) as detail_after:
            self.client.get(detail_url)
        self.assertEqual(len(history_before), len(history_after))
        self.assertEqual(len(detail_before), len(detail_after))
