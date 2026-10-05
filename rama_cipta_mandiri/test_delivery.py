"""Delivery regression checks; all writes use Django's isolated test database."""
from datetime import date
from pathlib import Path
import re
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.template.loader import get_template

from .forms import KaryawanForm, PeriodeForm
from .models import (Karyawan, Kriteria, SubKriteria, Periode, Alternatif,
                     Absensi, Penilaian, Utility, PerhitunganSmart, HasilSmart)
from .spk import SmartCalculator, cek_kelengkapan_penilaian


class DeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('delivery_admin', password='test-pass')
        cls.user = User.objects.create_user('delivery_employee', password='test-pass')
        cls.employee = Karyawan.objects.create(nama='A', user=cls.user)
        cls.other = Karyawan.objects.create(nama='B')
        cls.period = Periode.objects.create(bulan=2, tahun=2026)
        cls.a = Alternatif.objects.create(karyawan=cls.employee, periode=cls.period)
        cls.b = Alternatif.objects.create(karyawan=cls.other, periode=cls.period)
        cls.benefit = Kriteria.objects.create(kode='C2', nama='Benefit', bobot=60, tipe='benefit')
        cls.cost = Kriteria.objects.create(kode='C3', nama='Cost', bobot=40, tipe='cost')
        cls.sub = SubKriteria.objects.create(kriteria=cls.benefit, nama='Good', nilai=8)
        cls.sub_cost = SubKriteria.objects.create(kriteria=cls.cost, nama='Low', nilai=2)
        for alt, values in [(cls.a, (8, 2)), (cls.b, (4, 6))]:
            for criterion, value in zip((cls.benefit, cls.cost), values):
                Penilaian.objects.create(alternatif=alt, kriteria=criterion, nilai_raw=value)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_anonymous_login_target_exists(self):
        self.client.logout()
        response = self.client.get(reverse('dashboard_admin'))
        self.assertTrue(response.url.startswith(reverse('login') + '?next='))

    def test_logout_requires_post_and_csrf(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(reverse('logout')).status_code, 403)
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'))

    def test_login_roles_invalid_and_no_profile(self):
        self.client.logout()
        for username, destination in [('delivery_admin', 'dashboard_admin'), ('delivery_employee', 'dashboard_karyawan')]:
            self.assertRedirects(self.client.post(reverse('login'), {'username': username, 'password': 'test-pass'}), reverse(destination))
            self.client.logout()
        self.assertEqual(self.client.post(reverse('login'), {'username': 'delivery_admin', 'password': 'wrong'}).status_code, 200)
        orphan = User.objects.create_user('orphan', password='test-pass')
        self.assertEqual(self.client.post(reverse('login'), {'username': 'orphan', 'password': 'test-pass'}).status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.force_login(orphan)
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)

    def test_admin_routes_roles_and_readonly_get(self):
        routes = [(name, []) for name in ['dashboard_admin', 'karyawan_list', 'karyawan_create', 'kriteria_list', 'kriteria_create', 'subkriteria_list', 'subkriteria_create', 'absensi_bulanan', 'penilaian_list', 'penilaian_form', 'smart_list', 'smart_proses_form']]
        routes += [(name, [pk]) for name, pk in [('karyawan_update', self.employee.pk), ('karyawan_delete', self.employee.pk), ('kriteria_update', self.benefit.pk), ('kriteria_delete', self.benefit.pk), ('subkriteria_update', self.sub.pk), ('subkriteria_delete', self.sub.pk), ('penilaian_form_periode', self.period.pk), ('penilaian_hapus', self.period.pk), ('hasil_smart', self.period.pk), ('smart_detail', self.period.pk), ('smart_pdf', self.period.pk), ('smart_delete', self.period.pk)]]
        for name, args in routes:
            with self.subTest(route=name):
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(reverse(name, args=args))
                self.assertIn(response.status_code, [200, 302])
                writes = [q['sql'] for q in queries if re.match(r'\s*(INSERT|UPDATE|DELETE|REPLACE)\b', q['sql'], re.I)]
                self.assertEqual(writes, [])
        self.client.force_login(self.user)
        for name, args in routes:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
            self.assertEqual(self.client.post(reverse(name, args=args)).status_code, 403, name)

    def test_employee_account_crud_and_protected_delete(self):
        payload = {'nama': 'New', 'jabatan': 'operator', 'aktif': 'on', 'username': 'new_account', 'password': 'initial'}
        self.assertEqual(self.client.post(reverse('karyawan_create'), payload).status_code, 302)
        employee = Karyawan.objects.get(user__username='new_account')
        self.assertTrue(employee.user.check_password('initial'))
        payload.update(nama='Updated', password='changed')
        self.assertEqual(self.client.post(reverse('karyawan_update', args=[employee.pk]), payload).status_code, 302)
        employee.refresh_from_db()
        self.assertEqual(employee.nama, 'Updated')
        self.assertTrue(User.objects.get(pk=employee.user_id).check_password('changed'))
        self.client.post(reverse('karyawan_delete', args=[self.employee.pk]))
        self.assertTrue(Karyawan.objects.filter(pk=self.employee.pk).exists())
        self.client.post(reverse('karyawan_delete', args=[employee.pk]))
        self.assertFalse(User.objects.filter(username='new_account').exists())

    def test_existing_employee_new_account_requires_password(self):
        form = KaryawanForm({'nama': 'B', 'username': 'new'}, instance=self.other)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_master_validation_and_crud(self):
        payload = {'kode': 'C4', 'nama': 'Extra', 'bobot': 10, 'tipe': 'benefit', 'urutan': 4, 'aktif': 'on'}
        response = self.client.post(reverse('kriteria_create'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Kriteria.objects.filter(kode='C4').exists())
        payload.pop('aktif')
        self.assertEqual(self.client.post(reverse('kriteria_create'), payload).status_code, 302)
        criterion = Kriteria.objects.get(kode='C4')
        payload['nama'] = 'Changed'
        self.client.post(reverse('kriteria_update', args=[criterion.pk]), payload)
        criterion.refresh_from_db()
        self.assertEqual(criterion.nama, 'Changed')
        sub_data = {'kriteria': criterion.pk, 'nama': 'Option', 'nilai': 3, 'range_nilai': '2-3'}
        self.assertEqual(self.client.post(reverse('subkriteria_create'), sub_data).status_code, 302)
        sub = SubKriteria.objects.get(kriteria=criterion)
        sub_data['nilai'] = 4
        self.client.post(reverse('subkriteria_update', args=[sub.pk]), sub_data)
        sub.refresh_from_db()
        self.assertEqual(sub.nilai, 4)
        self.client.post(reverse('subkriteria_delete', args=[sub.pk]))
        self.assertFalse(SubKriteria.objects.filter(pk=sub.pk).exists())
        self.client.post(reverse('kriteria_delete', args=[criterion.pk]))
        self.assertFalse(Kriteria.objects.filter(pk=criterion.pk).exists())
        self.client.post(reverse('kriteria_delete', args=[self.benefit.pk]))
        self.assertTrue(Kriteria.objects.filter(pk=self.benefit.pk).exists())

    def test_period_server_validation(self):
        for month, year in [(0, 2026), (13, 2026), (1, 0), (1, 10000)]:
            self.assertFalse(PeriodeForm({'bulan': month, 'tahun': year}).is_valid())
        for data in [{'bulan': 'bad', 'tahun': '2026'}, {'bulan': '13', 'tahun': '2026'}, {'bulan': '2', 'tahun': '10000'}]:
            for method, name in [('get', 'absensi_bulanan'), ('post', 'absensi_bulanan'), ('post', 'smart_proses_form')]:
                with self.subTest(data=data, name=name, method=method):
                    response = getattr(self.client, method)(reverse(name), data)
                    self.assertIn(response.status_code, [200, 302, 400])
        self.assertEqual(Periode.objects.count(), 1)

    def test_attendance_post_period_weekends_and_update(self):
        data = {'bulan': 2, 'tahun': 2026, f'absensi_{self.employee.pk}_2026-02-02': 'on'}
        self.assertEqual(self.client.post(reverse('absensi_bulanan'), data).status_code, 302)
        records = Absensi.objects.filter(alternatif=self.a)
        self.assertEqual(records.count(), 20)
        self.assertEqual(records.filter(status=True).count(), 1)
        self.assertTrue(all(a.tanggal.weekday() < 5 for a in records))
        self.client.post(reverse('absensi_bulanan'), {'bulan': 2, 'tahun': 2026})
        self.assertEqual(records.count(), 20)
        self.assertEqual(records.filter(status=True).count(), 0)

    @patch('rama_cipta_mandiri.views.admin.KARYAWAN_PER_HALAMAN', 1)
    def test_attendance_post_uses_submitted_page(self):
        self.client.post(reverse('absensi_bulanan'), {'bulan': 2, 'tahun': 2026, 'page': 2})
        self.assertFalse(Absensi.objects.filter(alternatif=self.a).exists())
        self.assertEqual(Absensi.objects.filter(alternatif=self.b).count(), 20)

    def test_assessment_validation_and_update(self):
        url = reverse('penilaian_form_periode', args=[self.period.pk])
        before = list(Penilaian.objects.values_list('pk', 'nilai_raw'))
        for bad in ['', 'abc', str(self.sub_cost.pk)]:
            response = self.client.post(url, {f'nilai_{self.employee.pk}_{self.benefit.pk}': bad})
            self.assertIn(response.status_code, [200, 302])
            self.assertEqual(list(Penilaian.objects.values_list('pk', 'nilai_raw')), before)
        payload = {f'nilai_{emp.pk}_{criterion.pk}': sub.pk for emp in [self.employee, self.other] for criterion, sub in [(self.benefit, self.sub), (self.cost, self.sub_cost)]}
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        self.assertEqual(Penilaian.objects.count(), 4)
        self.assertEqual(Penilaian.objects.get(alternatif=self.b, kriteria=self.benefit).nilai_raw, 8)
        payload[f'nilai_{self.employee.pk}_{self.benefit.pk}'] = 'abc'
        self.assertIn(self.client.post(url, payload).status_code, [200, 302])

    def test_smart_formula_and_reprocessing(self):
        self.assertTrue(cek_kelengkapan_penilaian(self.period)['valid'])
        calculator = SmartCalculator(self.period.pk)
        result = calculator.hitung()
        self.assertEqual([r['total_nilai'] for r in result], [1, 0])
        self.assertEqual([r['ranking'] for r in result], [1, 2])
        for row in PerhitunganSmart.objects.all():
            self.assertAlmostEqual(row.nilai_akhir_kriteria, row.bobot_ternormalisasi * row.nilai_utility, places=6)
        self.assertEqual(list(Utility.objects.filter(penilaian__alternatif=self.a).values_list('nilai_utility', flat=True)), [1, 1])
        calculator.hitung()
        self.assertEqual((Utility.objects.count(), PerhitunganSmart.objects.count(), HasilSmart.objects.count()), (4, 4, 2))
        self.assertEqual(self.client.post(reverse('smart_proses_form'), {'bulan': 2, 'tahun': 2026}).status_code, 302)

    def test_smart_missing_values_preserves_existing_results(self):
        SmartCalculator(self.period.pk).hitung()
        Penilaian.objects.filter(alternatif=self.b, kriteria=self.cost).delete()
        self.assertFalse(cek_kelengkapan_penilaian(self.period)['valid'])
        with self.assertRaises(ValueError):
            SmartCalculator(self.period.pk).hitung()
        self.assertEqual(HasilSmart.objects.count(), 2)

    def test_smart_equal_single_zero_weight_and_no_participants(self):
        Penilaian.objects.update(nilai_raw=0)
        self.assertEqual([r['total_nilai'] for r in SmartCalculator(self.period.pk).hitung()], [1, 1])
        self.b.delete()
        self.assertEqual(SmartCalculator(self.period.pk).hitung()[0]['total_nilai'], 1)
        Kriteria.objects.update(bobot=0)
        with self.assertRaises(ValueError):
            SmartCalculator(self.period.pk).hitung()
        self.a.delete()
        with self.assertRaises(ValueError):
            SmartCalculator(self.period.pk).hitung()

    def test_reports_keep_inactive_historical_criteria_and_pdf(self):
        SmartCalculator(self.period.pk).hitung()
        self.cost.aktif = False
        self.cost.save()
        response = self.client.get(reverse('smart_detail', args=[self.period.pk]))
        self.assertEqual(len(response.context['daftar_kriteria']), 2)
        response = self.client.get(reverse('smart_pdf', args=[self.period.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    @patch('xhtml2pdf.pisa.pisaDocument')
    def test_pdf_error_redirect(self, pdf):
        SmartCalculator(self.period.pk).hitung()
        pdf.return_value.err = 1
        self.assertRedirects(self.client.get(reverse('smart_pdf', args=[self.period.pk])), reverse('smart_detail', args=[self.period.pk]))

    def test_period_scoped_deletion_preserves_attendance(self):
        SmartCalculator(self.period.pk).hitung()
        other_period = Periode.objects.create(bulan=3, tahun=2026)
        other_alt = Alternatif.objects.create(karyawan=self.employee, periode=other_period)
        HasilSmart.objects.create(alternatif=other_alt, total_nilai=.5, ranking=1, predikat='Cukup')
        Absensi.objects.create(alternatif=self.a, tanggal=date(2026, 2, 2), status=True)
        self.client.post(reverse('smart_delete', args=[self.period.pk]))
        self.assertEqual(HasilSmart.objects.count(), 1)
        self.assertEqual(Penilaian.objects.count(), 4)
        self.client.post(reverse('penilaian_hapus', args=[self.period.pk]))
        self.assertEqual(Penilaian.objects.count(), 0)
        self.assertEqual(Absensi.objects.count(), 1)
        self.assertEqual(Alternatif.objects.count(), 3)
        self.assertEqual(HasilSmart.objects.count(), 1)

    def test_templates_compile_and_local_static_references_exist(self):
        root = Path(settings.BASE_DIR) / 'rama_cipta_mandiri' / 'templates'
        for path in root.rglob('*.html'):
            with self.subTest(template=str(path)):
                get_template(path.relative_to(root).as_posix())
                for asset in re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]", path.read_text(encoding='utf-8')):
                    self.assertIsNotNone(finders.find(asset), asset)
