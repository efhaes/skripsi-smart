"""
Seed data Karyawan + akun login dari AUDY.xlsx (32 karyawan).

Letak file:
    rama_cipta_mandiri/management/commands/seed_karyawan.py

Cara pakai:
    python manage.py seed_karyawan

Akun:
- Username = nama depan (huruf kecil), mis. marendra. Jika bentrok: ari, ari2, ari3, ...
- Password semua akun = karyawan12345

Aman dijalankan berulang kali (idempotent): karyawan/akun yang sudah ada tidak diduplikasi.
"""
import re

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Karyawan


PASSWORD = "karyawan12345"

DATA_KARYAWAN = [
    ("Marendra Saptia Darma", "Kabag. GA dan Personalia"),
    ("Siti Khairani Ustra", "Kabag. Administrasi"),
    ("Suci Maulida", "Kabag. Gudang"),
    ("Rizka Ridatil Rahmi", "Kabag. R&D dan QC"),
    ("Muhammad Naufal Razak Nasir", "Kabag. Produksi"),
    ("Ari Franando Fahmi", "Staff Produksi"),
    ("Reska Febioleni Putri", "Staff R&D dan QC"),
    ("Kuntum Khaira", "Staff R&D dan QC"),
    ("Amelia Zelissa", "Staff R&D dan QC"),
    ("Dinda Three Wahyuni", "Staff R&D dan QC"),
    ("Rindu Nayla Velisya", "Staff R&D dan QC"),
    ("Yulia Dewi Safitri", "Staff R&D dan QC"),
    ("Arfan Johansyah", "Kabag. Maintenance"),
    ("Dedi Febrianto", "Operator"),
    ("Ridho Restu Alamsyah", "Operator"),
    ("Rendi Agustin", "Operator"),
    ("Yusril Abdul Kohar", "Operator"),
    ("Sekar Octaviani", "Operator"),
    ("Muhammad Rofi Affan", "Operator"),
    ("Imron Mubarok", "Operator"),
    ("Suryana", "Operator"),
    ("Apudin", "Operator"),
    ("Muhamad Fikri Haikal", "Operator"),
    ("Mukidin", "Operator"),
    ("Ari Nur Fadillah", "Operator"),
    ("Anita", "Operator"),
    ("Agus Fikri", "Operator"),
    ("Muhamad Hasanudin", "Operator"),
    ("Resky Putra", "Operator"),
    ("Resti Febriyanti", "Operator"),
    ("Aditya Liano Putra", "Operator"),
    ("Manto", "Operator"),
]


def username_unik(nama):
    dasar = re.sub(r"[^a-z0-9]", "", nama.split()[0].lower()) or "user"
    username = dasar
    i = 2
    while User.objects.filter(username=username).exists():
        username = f"{dasar}{i}"
        i += 1
    return username


class Command(BaseCommand):
    help = "Seed data Karyawan + akun login dari AUDY.xlsx"

    @transaction.atomic
    def handle(self, *args, **options):
        label_to_key = {label: key for key, label in Karyawan.JABATAN_CHOICES}
        dibuat, akun_baru = 0, []

        for nama, jabatan_label in DATA_KARYAWAN:
            jabatan = label_to_key[jabatan_label.strip()]

            obj, is_created = Karyawan.objects.get_or_create(
                nama=nama.strip(),
                defaults={"jabatan": jabatan, "aktif": True},
            )
            dibuat += is_created

            if obj.user_id is None:
                user = User.objects.create_user(
                    username=username_unik(nama),
                    password=PASSWORD,
                    first_name=nama[:150],
                )
                obj.user = user
                obj.save(update_fields=["user"])
                akun_baru.append((user.username, nama))

        self.stdout.write(self.style.SUCCESS(
            f"Selesai: {dibuat} karyawan baru, {len(akun_baru)} akun baru "
            f"(total data: {len(DATA_KARYAWAN)})."
        ))
        for username, nama in akun_baru:
            self.stdout.write(f"  {username:<12} <- {nama}")
        if akun_baru:
            self.stdout.write(f"Password semua akun: {PASSWORD}")