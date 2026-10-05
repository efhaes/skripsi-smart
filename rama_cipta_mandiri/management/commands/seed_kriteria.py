"""
Seed data Kriteria (C1-C5) dan SubKriteria.

Letak file:
    rama_cipta_mandiri/management/commands/seed_kriteria.py

Cara pakai:
    python manage.py seed_kriteria

Aman dijalankan berulang kali (idempotent):
- Kriteria dicocokkan lewat kode (unik), SubKriteria lewat (kriteria, nama).
- Data yang sudah ada diperbarui sesuai isi file ini, tidak diduplikasi.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Kriteria, SubKriteria


# (kode, nama, bobot %, tipe, urutan, [(nama opsi, nilai, range_nilai), ...])
DATA_KRITERIA = [
    ("C1", "Kehadiran", 30.0, "benefit", 1, [
        ("Sangat Baik", 5.0, "0-1"),
        ("Baik", 4.0, "2-3"),
        ("Cukup", 3.0, "4-5"),
        ("Kurang", 2.0, "6-7"),
        ("Sangat Kurang", 1.0, "8-31"),
    ]),
    ("C2", "Pelanggaran", 25.0, "cost", 2, [
        ("Sangat Baik", 5.0, "0"),
        ("Baik", 4.0, "1-2"),
        ("Cukup", 3.0, "3-4"),
        ("Kurang", 2.0, "5-6"),
        ("Sangat Kurang", 1.0, "≥ 7"),
    ]),
    ("C3", "Kualitas Kerja", 20.0, "benefit", 3, [
        ("Sangat Baik", 5.0, "95-100"),
        ("Baik", 4.0, "90-95"),
        ("Cukup", 3.0, "85-90"),
        ("Kurang", 2.0, "80-85"),
        ("Sangat Kurang", 1.0, "0-80"),
    ]),
    ("C4", "Kerjasama TIM", 15.0, "benefit", 4, [
        ("Sangat Baik", 5.0, "95-100"),
        ("Baik", 4.0, "90-95"),
        ("Cukup", 3.0, "85-90"),
        ("Kurang", 2.0, "80-85"),
        ("Sangat Kurang", 1.0, "0-80"),
    ]),
    ("C5", "Tanggung Jawab", 10.0, "benefit", 5, [
        # ("Sangat Baik", 5.0, "95-100"),  # tidak ada di data asli; hapus tanda # jika perlu
        ("Baik", 4.0, "90-95"),
        ("Cukup", 3.0, "85-90"),
        ("Kurang", 2.0, "80-85"),
        ("Sangat Kurang", 1.0, "0-80"),
    ]),
]


class Command(BaseCommand):
    help = "Seed data Kriteria dan SubKriteria"

    @transaction.atomic
    def handle(self, *args, **options):
        n_kriteria, n_sub = 0, 0

        for kode, nama, bobot, tipe, urutan, opsi_list in DATA_KRITERIA:
            kriteria, _ = Kriteria.objects.update_or_create(
                kode=kode,
                defaults={
                    "nama": nama,
                    "bobot": bobot,
                    "tipe": tipe,
                    "urutan": urutan,
                    "aktif": True,
                },
            )
            n_kriteria += 1

            for nama_opsi, nilai, range_nilai in opsi_list:
                SubKriteria.objects.update_or_create(
                    kriteria=kriteria,
                    nama=nama_opsi,
                    defaults={"nilai": nilai, "range_nilai": range_nilai},
                )
                n_sub += 1

        total_bobot = sum(k[2] for k in DATA_KRITERIA)
        self.stdout.write(self.style.SUCCESS(
            f"Seed selesai: {n_kriteria} kriteria, {n_sub} subkriteria "
            f"(total bobot {total_bobot:g}%)."
        ))