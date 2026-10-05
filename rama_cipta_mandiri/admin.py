from django.contrib import admin
from .models import (
    Karyawan, Kriteria, SubKriteria,
    Periode, Alternatif, Penilaian, Absensi,
    Utility, PerhitunganSmart, HasilSmart,
)


@admin.register(Karyawan)
class KaryawanAdmin(admin.ModelAdmin):
    list_display = ['nama', 'jabatan', 'aktif', 'user', 'tanggal_masuk']
    list_filter = ['aktif', 'jabatan']
    search_fields = ['nama', 'user__username']
    autocomplete_fields = ['user']


@admin.register(SubKriteria)
class SubKriteriaAdmin(admin.ModelAdmin):
    list_display = ['kriteria', 'nama', 'nilai']
    list_filter = ['kriteria']
    search_fields = ['nama', 'kriteria__nama', 'kriteria__kode']


class SubKriteriaInline(admin.TabularInline):
    model = SubKriteria
    extra = 0
    fields = ['nama', 'nilai']


@admin.register(Kriteria)
class KriteriaAdmin(admin.ModelAdmin):
    list_display = ['kode', 'nama', 'bobot', 'tipe', 'urutan', 'aktif']
    list_editable = ['bobot', 'urutan', 'aktif']
    list_filter = ['tipe', 'aktif']
    ordering = ['urutan', 'kode']
    search_fields = ['kode', 'nama']
    inlines = [SubKriteriaInline]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        total = sum(k.bobot for k in Kriteria.objects.filter(aktif=True))
        extra_context['total_bobot_aktif'] = round(total, 2)
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Periode)
class PeriodeAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'bulan', 'tahun']
    list_filter = ['tahun']
    search_fields = ['tahun']



class PenilaianInline(admin.TabularInline):
    model = Penilaian
    extra = 0
    autocomplete_fields = ['kriteria', 'subkriteria']


@admin.register(Alternatif)
class AlternatifAdmin(admin.ModelAdmin):
    list_display = ['kode', 'karyawan', 'periode']
    list_filter = ['periode']
    search_fields = ['kode', 'karyawan__nama']
    autocomplete_fields = ['karyawan', 'periode']
    inlines = [PenilaianInline]


@admin.register(Penilaian)
class PenilaianAdmin(admin.ModelAdmin):
    list_display = ['alternatif', 'kriteria', 'nilai_raw', 'subkriteria']
    list_filter = ['kriteria', 'alternatif__periode']
    autocomplete_fields = ['alternatif', 'kriteria', 'subkriteria']
    search_fields = ['alternatif__karyawan__nama']


@admin.register(Absensi)
class AbsensiAdmin(admin.ModelAdmin):
    list_display = ['alternatif', 'tanggal', 'status']
    list_filter = ['status', 'tanggal']
    autocomplete_fields = ['alternatif']


@admin.register(HasilSmart)
class HasilSmartAdmin(admin.ModelAdmin):
    list_display = ['ranking', 'alternatif', 'total_nilai', 'predikat']
    list_filter = ['predikat', 'alternatif__periode']
    ordering = ['ranking']
    readonly_fields = ['alternatif', 'total_nilai', 'ranking', 'predikat']

    def has_add_permission(self, request):
        return False


@admin.register(Utility)
class UtilityAdmin(admin.ModelAdmin):
    list_display = ['penilaian', 'nilai_utility', 'nilai_min', 'nilai_max']

    def has_add_permission(self, request):
        return False


@admin.register(PerhitunganSmart)
class PerhitunganSmartAdmin(admin.ModelAdmin):
    list_display = ['alternatif', 'kriteria', 'bobot_ternormalisasi', 'nilai_utility', 'nilai_akhir_kriteria']
    list_filter = ['alternatif__periode']

    def has_add_permission(self, request):
        return False