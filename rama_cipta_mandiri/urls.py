from django.urls import path
from django.views.generic import RedirectView

from .views import admin, karyawan, auth, absensi_matching

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),

    path('admin-panel/', admin.dashboard_admin, name='dashboard_admin'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),

    path('admin-panel/karyawan/', admin.karyawan_list, name='karyawan_list'),
    path('admin-panel/karyawan/tambah/', admin.karyawan_create, name='karyawan_create'),
    path('admin-panel/karyawan/<int:pk>/edit/', admin.karyawan_update, name='karyawan_update'),
    path('admin-panel/karyawan/<int:pk>/hapus/', admin.karyawan_delete, name='karyawan_delete'),
    # Kriteria
    path('admin-panel/kriteria/', admin.kriteria_list, name='kriteria_list'),
    path('admin-panel/kriteria/tambah/', admin.kriteria_create, name='kriteria_create'),
    path('admin-panel/kriteria/<int:pk>/edit/', admin.kriteria_update, name='kriteria_update'),
    path('admin-panel/kriteria/<int:pk>/hapus/', admin.kriteria_delete, name='kriteria_delete'),

    # SubKriteria
    path('admin-panel/subkriteria/', admin.subkriteria_list, name='subkriteria_list'),
    path('admin-panel/subkriteria/tambah/', admin.subkriteria_create, name='subkriteria_create'),
    path('admin-panel/subkriteria/<int:pk>/edit/', admin.subkriteria_update, name='subkriteria_update'),
    path('admin-panel/subkriteria/<int:pk>/hapus/', admin.subkriteria_delete, name='subkriteria_delete'),

    # Penilaian
    path('admin-panel/penilaian/', admin.penilaian_list, name='penilaian_list'),
    path('admin-panel/penilaian/form/',admin.penilaian_form,name='penilaian_form'),
    path('admin-panel/penilaian/form/<int:periode_id>/',admin.penilaian_form,name='penilaian_form_periode'),
    path('admin-panel/penilaian/<int:periode_id>/hapus/',admin.penilaian_hapus,name='penilaian_hapus'),
    # Absensi
    path('admin-panel/absensi/', admin.absensi_bulanan , name='absensi_bulanan'),
    path('absensi-saya/', karyawan.absensi_saya, name='absensi_saya'),


    # Proses SMART
    path('admin-panel/smart/', admin.smart_list, name='smart_list'),
    path('admin-panel/smart/tambah/', admin.smart_proses_form, name='smart_proses_form'),
    path('admin-panel/smart/<int:periode_id>/hasil/', admin.hasil_smart_view, name='hasil_smart'),
    path('admin-panel/smart/<int:periode_id>/hapus/', admin.smart_delete, name='smart_delete'),
    # Laporan
    path('admin-panel/smart/<int:periode_id>/', admin.laporan_detail, name='smart_detail'),
    path('admin-panel/smart/<int:periode_id>/pdf/', admin.laporan_pdf, name='smart_pdf'),
    #karyawan
    path('dashboard/', karyawan.dashboard_karyawan, name='dashboard_karyawan'),
    path('riwayat/', karyawan.riwayat_penilaian, name='riwayat_penilaian'),
    path('riwayat/<int:alternatif_id>/', karyawan.detail_penilaian, name='detail_penilaian'),
]