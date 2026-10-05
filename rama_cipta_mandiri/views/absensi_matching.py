import re

# Kata kunci buat deteksi kriteria mana yang nilainya di-generate otomatis
# dari data Absensi (Kriteria belum punya flag khusus, jadi dicocokkan dari nama).
KATA_KUNCI_KRITERIA_ABSENSI = ['hadir']  # cocok utk "Ketidakhadiran" & "Kehadiran"


def is_kriteria_otomatis_absensi(kriteria):
    nama_lower = kriteria.nama.lower()
    return any(kata in nama_lower for kata in KATA_KUNCI_KRITERIA_ABSENSI)


def parse_range_nilai(range_nilai):
    """
    Parsing field SubKriteria.range_nilai jadi (batas_bawah, batas_atas).
    Format yang didukung:
      "0"        -> (0, 0)
      "0-0"      -> (0, 0)
      "1-2"      -> (1, 2)
      "90-100"   -> (90, 100)
      "7+"       -> (7, None)   # None = tak terbatas ke atas
      ">6"       -> (7, None)

    Return None kalau range_nilai kosong atau formatnya tidak dikenali.
    """
    if not range_nilai:
        return None
    teks = range_nilai.strip().lower()

    # pola "N+" atau ">N" -> N ke atas
    match_plus = re.fullmatch(r'>?\s*(\d+)\s*\+?', teks) if teks.endswith('+') or teks.startswith('>') else None
    if match_plus:
        angka = int(match_plus.group(1))
        awal = angka if teks.endswith('+') else angka + 1
        return (awal, None)

    # pola rentang "N-M"
    match_rentang = re.fullmatch(r'(\d+)\s*-\s*(\d+)', teks)
    if match_rentang:
        a, b = int(match_rentang.group(1)), int(match_rentang.group(2))
        return (min(a, b), max(a, b))

    # angka tunggal "N"
    match_tunggal = re.fullmatch(r'(\d+)', teks)
    if match_tunggal:
        angka = int(match_tunggal.group(1))
        return (angka, angka)

    return None


def cari_subkriteria_untuk_nilai(kriteria, nilai_cek):
    """
    Cari SubKriteria di bawah `kriteria` yang range_nilai-nya mencakup nilai_cek
    (mis. jumlah hari tidak hadir). Return None kalau tidak ada yang cocok
    atau semua range_nilai kosong/format salah.
    """
    for sub in kriteria.subkriteria.all():
        rentang = parse_range_nilai(sub.range_nilai)
        if rentang is None:
            continue
        batas_bawah, batas_atas = rentang
        batas_atas_efektif = batas_atas if batas_atas is not None else float('inf')
        if batas_bawah <= nilai_cek <= batas_atas_efektif:
            return sub
    return None