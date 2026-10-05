from django.db import models
from django.contrib.auth.models import User

# ============================================================
# MASTER DATA
# ============================================================

class Karyawan(models.Model):
    """
    Profil karyawan (data master), terpisah dari User (akun login)
    dan dari Alternatif (data yang dinilai per periode).
    """
    JABATAN_CHOICES = [
        ('kabag_ga_personalia', 'Kabag. GA dan Personalia'),
        ('kabag_administrasi', 'Kabag. Administrasi'),
        ('kabag_gudang', 'Kabag. Gudang'),
        ('kabag_rnd_qc', 'Kabag. R&D dan QC'),
        ('kabag_produksi', 'Kabag. Produksi'),
        ('staff_produksi', 'Staff Produksi'),
        ('staff_rnd_qc', 'Staff R&D dan QC'),
        ('kabag_maintenance', 'Kabag. Maintenance'),
        ('operator', 'Operator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nama = models.CharField(max_length=100)
    jabatan = models.CharField(max_length=30, choices=JABATAN_CHOICES, blank=True)
    aktif = models.BooleanField(default=True)
    tanggal_masuk = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Karyawan"
        verbose_name_plural = "Karyawan"
        ordering = ['nama']

    def __str__(self):
        return self.nama


class Kriteria(models.Model):
    """
    Master kriteria penilaian untuk metode SMART.
    bobot disimpan dalam skala PERSEN (0-100), total idealnya = 100.
    """
    TIPE_CHOICES = [
        ('benefit', 'Benefit'),
        ('cost', 'Cost'),
    ]
    kode = models.CharField(max_length=10, unique=True, help_text="Kode singkat, mis. C1, C2")
    nama = models.CharField(max_length=100)
    bobot = models.FloatField(help_text="Bobot kriteria dalam persen (0-100), total semua kriteria aktif idealnya = 100")
    tipe = models.CharField(max_length=10, choices=TIPE_CHOICES)
    urutan = models.PositiveIntegerField(default=0, help_text="Urutan tampil kriteria")
    aktif = models.BooleanField(default=True, help_text="Nonaktifkan kriteria tanpa menghapus data historisnya")

    class Meta:
        verbose_name = "Kriteria"
        verbose_name_plural = "Kriteria"
        ordering = ['urutan', 'kode']

    def __str__(self):
        return f"{self.kode} - {self.nama}"


class SubKriteria(models.Model):

    kriteria = models.ForeignKey(Kriteria, on_delete=models.CASCADE, related_name='subkriteria')
    nama = models.CharField(max_length=100)
    range_nilai = models.CharField(max_length=50, blank=True, help_text="Opsional: range nilai yang diwakili subkriteria ini, mis. 90-100")
    nilai = models.FloatField(help_text="Nilai raw yang akan dipakai sebagai Penilaian.nilai_raw")

    class Meta:
        verbose_name = "Sub Kriteria"
        verbose_name_plural = "Sub Kriteria"

    def __str__(self):
        return f"{self.kriteria.kode} - {self.nama} ({self.nilai})"


# ============================================================
# PERIODE & DATA PENILAIAN
# ============================================================

class Periode(models.Model):
    bulan = models.IntegerField()
    tahun = models.IntegerField()

    BULAN_LABEL = [
        '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
    ]

    class Meta:
        verbose_name = "Periode"
        verbose_name_plural = "Periode"
        unique_together = ['bulan', 'tahun']
        ordering = ['-tahun', '-bulan']

    def __str__(self):
        return f"{self.BULAN_LABEL[self.bulan]} {self.tahun}"


class Alternatif(models.Model):
    """
    Karyawan yang dinilai pada Periode tertentu.
    """
    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name='alternatif')
    karyawan = models.ForeignKey(Karyawan, on_delete=models.CASCADE)
    kode = models.CharField(max_length=20, blank=True, help_text="Kode alternatif, mis. A1, A2 (opsional, auto jika kosong)")

    class Meta:
        verbose_name = "Alternatif"
        verbose_name_plural = "Alternatif"
        unique_together = ['karyawan', 'periode']
        ordering = ['kode']

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and not self.kode:
            self.kode = f"A{self.pk}"
            super().save(update_fields=['kode'])

    def __str__(self):
        return f"{self.karyawan.nama} ({self.periode})"


class Penilaian(models.Model):
    alternatif = models.ForeignKey(Alternatif, on_delete=models.CASCADE, related_name='penilaian')
    kriteria = models.ForeignKey(Kriteria, on_delete=models.CASCADE)
    subkriteria = models.ForeignKey(SubKriteria, on_delete=models.SET_NULL, null=True, blank=True,
                                     help_text="Diisi otomatis jika kriteria bertipe kualitatif")
    nilai_raw = models.FloatField(help_text="Nilai mentah sebelum dinormalisasi (input asli)")

    class Meta:
        verbose_name = "Penilaian"
        verbose_name_plural = "Penilaian"
        unique_together = ['alternatif', 'kriteria']

    def __str__(self):
        return f"{self.alternatif} - {self.kriteria.kode}: {self.nilai_raw}"


class Absensi(models.Model):
    alternatif = models.ForeignKey(Alternatif, on_delete=models.CASCADE, related_name='absensi')
    tanggal = models.DateField()
    status = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Absensi"
        verbose_name_plural = "Absensi"
        unique_together = ['alternatif', 'tanggal']

    def __str__(self):
        return f"{self.alternatif} - {self.tanggal}"


# ============================================================
# HASIL PERHITUNGAN SMART
# ============================================================

class Utility(models.Model):
    """
    Nilai utility per Penilaian (normalisasi min-max).
    Rumus Benefit : u(ai) = (nilai - min) / (max - min)
    Rumus Cost    : u(ai) = (max - nilai) / (max - min)
    """
    penilaian = models.OneToOneField(Penilaian, on_delete=models.CASCADE, related_name='utility')
    nilai_max = models.FloatField(help_text="Nilai maksimum pada kriteria & periode ybs")
    nilai_min = models.FloatField(help_text="Nilai minimum pada kriteria & periode ybs")
    nilai_utility = models.FloatField(help_text="Hasil normalisasi utility (0-1)")

    class Meta:
        verbose_name = "Utility"
        verbose_name_plural = "Utility"

    def __str__(self):
        return f"Utility {self.penilaian}: {self.nilai_utility:.4f}"


class PerhitunganSmart(models.Model):
    """
    bobot_ternormalisasi x nilai_utility per alternatif per kriteria per periode.
    """
    alternatif = models.ForeignKey(Alternatif, on_delete=models.CASCADE, related_name='perhitungan')
    kriteria = models.ForeignKey(Kriteria, on_delete=models.CASCADE)
    bobot_ternormalisasi = models.FloatField(help_text="Bobot kriteria ternormalisasi (0-1)")
    nilai_utility = models.FloatField()
    nilai_akhir_kriteria = models.FloatField(help_text="bobot_ternormalisasi x nilai_utility")

    class Meta:
        verbose_name = "Perhitungan SMART"
        verbose_name_plural = "Perhitungan SMART"
        unique_together = ['alternatif', 'kriteria']

    def __str__(self):
        return f"SMART {self.alternatif} - {self.kriteria.kode}: {self.nilai_akhir_kriteria:.4f}"


class HasilSmart(models.Model):
    """
    Hasil akhir ranking per alternatif per periode.
    total_nilai = SUM(nilai_akhir_kriteria) semua kriteria pada periode ybs.
    """
    alternatif = models.OneToOneField(Alternatif, on_delete=models.CASCADE, related_name='hasil')
    total_nilai = models.FloatField()
    ranking = models.PositiveIntegerField()
    predikat = models.CharField(max_length=20)

    class Meta:
        verbose_name = "Hasil SMART"
        verbose_name_plural = "Hasil SMART"
        ordering = ['ranking']

    def __str__(self):
        return f"Rank {self.ranking} - {self.alternatif}: {self.total_nilai:.4f} ({self.predikat})"