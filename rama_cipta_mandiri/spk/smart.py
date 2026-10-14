"""
spk/smart.py
============================================================
Engine perhitungan metode SMART
(Simple Multi-Attribute Rating Technique)

Alur:
  1. Kumpulkan nilai raw semua alternatif per kriteria
  2. Hitung nilai utility  →  normalisasi min-max
       Benefit : u(ai) = (xi - x_min) / (x_max - x_min)
       Cost    : u(ai) = (x_max - xi) / (x_max - x_min)
       Edge case: x_max == x_min → u(ai) = 1.0  (semua sama, semua unggul)
  3. Normalisasi bobot kriteria  →  wj = bobot_j / total_bobot
  4. Hitung nilai akhir per kriteria  →  wj × u(ai)
  5. Total nilai alternatif  →  sum semua nilai akhir kriteria
  6. Ranking & predikat
  7. Simpan ke DB: Utility, PerhitunganSmart, HasilSmart

Penggunaan:
  from apps.spk.smart import SmartCalculator
  calc = SmartCalculator(periode_id=1)
  hasil = calc.hitung()        # hitung + simpan ke DB
  tabel = calc.get_tabel()     # ambil hasil sebagai dict (tanpa simpan)
============================================================
"""

from django.db import transaction
from django.db.models import Max, Min

from rama_cipta_mandiri.models import Kriteria, Alternatif, Penilaian , Utility, PerhitunganSmart, HasilSmart, Periode

# ============================================================
# Konfigurasi predikat berdasarkan range total nilai (0–1)
# ============================================================
PREDIKAT_RANGE = [
    (0.80, 1.00, 'Sangat Baik'),
    (0.60, 0.80, 'Baik'),
    (0.40, 0.60, 'Cukup'),
    (0.20, 0.40, 'Kurang'),
    (0.00, 0.20, 'Sangat Kurang'),
]


def get_predikat(nilai: float) -> str:
    for batas_bawah, batas_atas, label in PREDIKAT_RANGE:
        if batas_bawah <= nilai <= batas_atas:
            return label
    return 'Sangat Kurang'


# ============================================================
# Core Calculator
# ============================================================

class SmartCalculator:
    """
    Kalkulator SMART untuk satu periode.

    Parameters
    ----------
    periode_id : int
        ID Periode yang akan dihitung.
    """

    def __init__(self, periode_id: int):
        self.periode_id = periode_id
        self._kriteria = None
        self._alternatif = None
        self._matrix = {}          # {alt_id: {kriteria_id: nilai_raw}}
        self._utility_matrix = {}  # {alt_id: {kriteria_id: nilai_utility}}
        self._bobot_norm = {}      # {kriteria_id: bobot_ternormalisasi}
        self._total_nilai = {}     # {alt_id: total_nilai}
        self._detail = {}          # untuk tabel debug / tampilan

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def hitung(self) -> list[dict]:
        """
        Jalankan perhitungan SMART penuh dan simpan hasilnya ke database.
        Mengembalikan list hasil ranking (sama seperti get_tabel()).

        Raises
        ------
        ValueError
            Jika tidak ada alternatif / kriteria / penilaian yang cukup.
        """
        self._validasi()
        self._load_data()
        self._hitung_utility()
        self._normalisasi_bobot()
        self._hitung_nilai_akhir()

        with transaction.atomic():
            self._simpan_ke_db()

        return self._build_hasil()

    def get_tabel(self) -> list[dict]:
        """
        Hitung SMART tanpa menyimpan ke DB.
        Berguna untuk preview / simulasi.
        """
        self._validasi()
        self._load_data()
        self._hitung_utility()
        self._normalisasi_bobot()
        self._hitung_nilai_akhir()
        return self._build_hasil()

    # ----------------------------------------------------------
    # Step 0 – Validasi
    # ----------------------------------------------------------

    def _validasi(self):
        if not Alternatif.objects.filter(periode_id=self.periode_id).exists():
            raise ValueError("Tidak ada alternatif pada periode ini.")

        kriteria_aktif = Kriteria.objects.filter(aktif=True)
        if not kriteria_aktif.exists():
            raise ValueError("Tidak ada kriteria aktif.")

        total_bobot = sum(k.bobot for k in kriteria_aktif)

        # Aturan yang sama dengan halaman Kriteria dan dashboard:
        # total bobot kriteria aktif harus 100% (toleransi 0,01).
        if round(abs(total_bobot - 100), 2) > 0.01:
            raise ValueError(
                f"Total bobot kriteria = {total_bobot:.2f}%. Harus 100%."
            )
        
        # Validasi kelengkapan penilaian total
        kriteria_ids = set(k.id for k in kriteria_aktif)
        total_kriteria = len(kriteria_ids)
        total_alternatif = Alternatif.objects.filter(periode_id=self.periode_id).count()
        expected = total_alternatif * total_kriteria
        
        actual = Penilaian.objects.filter(
            alternatif__periode_id=self.periode_id,
            kriteria__aktif=True
        ).count()
        
        if actual != expected:
            periode = Periode.objects.get(id=self.periode_id)
            raise ValueError(
                f"Penilaian periode {periode} belum lengkap ({actual}/{expected} nilai). "
                f"Lengkapi penilaian terlebih dahulu."
            )

    # ----------------------------------------------------------
    # Step 1 – Load data dari DB
    # ----------------------------------------------------------

    def _load_data(self):
        self._kriteria = list(Kriteria.objects.filter(aktif=True).order_by('urutan', 'kode'))
        self._alternatif = list(
            Alternatif.objects
            .filter(periode_id=self.periode_id)
            .select_related('karyawan')
            .order_by('kode')
        )

        # Bangun matrix nilai raw: {alt_id: {kriteria_id: nilai_raw}}
        penilaian_qs = (
            Penilaian.objects
            .filter(alternatif__periode_id=self.periode_id)
            .values('alternatif_id', 'kriteria_id', 'nilai_raw')
        )

        for p in penilaian_qs:
            alt_id = p['alternatif_id']
            kr_id = p['kriteria_id']
            if alt_id not in self._matrix:
                self._matrix[alt_id] = {}
            self._matrix[alt_id][kr_id] = p['nilai_raw']

    # ----------------------------------------------------------
    # Step 2 – Hitung nilai utility (normalisasi min-max)
    # ----------------------------------------------------------

    def _hitung_utility(self):
        for kriteria in self._kriteria:
            kr_id = kriteria.id

            # Kumpulkan semua nilai raw untuk kriteria ini
            nilai_list = [
                self._matrix.get(alt.id, {}).get(kr_id)
                for alt in self._alternatif
            ]
            nilai_list = [v for v in nilai_list if v is not None]

            if not nilai_list:
                # Tidak ada penilaian untuk kriteria ini, skip
                continue

            x_max = max(nilai_list)
            x_min = min(nilai_list)
            rentang = x_max - x_min

            for alt in self._alternatif:
                xi = self._matrix.get(alt.id, {}).get(kr_id)
                if xi is None:
                    utility = 0.0   # penilaian belum diisi = 0
                elif rentang == 0:
                    utility = 1.0   # semua nilai sama → semua bernilai penuh
                elif kriteria.tipe == 'benefit':
                    utility = (xi - x_min) / rentang
                else:  # cost
                    utility = (x_max - xi) / rentang

                if alt.id not in self._utility_matrix:
                    self._utility_matrix[alt.id] = {}

                self._utility_matrix[alt.id][kr_id] = {
                    'utility': round(utility, 6),
                    'nilai_max': x_max,
                    'nilai_min': x_min,
                    'nilai_raw': xi,
                    'tipe': kriteria.tipe,
                }

    # ----------------------------------------------------------
    # Step 3 – Normalisasi bobot kriteria
    # ----------------------------------------------------------

    def _normalisasi_bobot(self):
        total_bobot = sum(k.bobot for k in self._kriteria)
        for kriteria in self._kriteria:
            self._bobot_norm[kriteria.id] = kriteria.bobot / total_bobot

    # ----------------------------------------------------------
    # Step 4 & 5 – Hitung nilai akhir & total
    # ----------------------------------------------------------

    def _hitung_nilai_akhir(self):
        for alt in self._alternatif:
            total = 0.0
            detail_kriteria = []

            for kriteria in self._kriteria:
                kr_id = kriteria.id
                bobot_w = self._bobot_norm.get(kr_id, 0)
                utility_data = self._utility_matrix.get(alt.id, {}).get(kr_id, {})
                u = utility_data.get('utility', 0.0)
                nilai_akhir = bobot_w * u
                total += nilai_akhir

                detail_kriteria.append({
                    'kriteria_id': kr_id,
                    'kriteria_kode': kriteria.kode,
                    'kriteria_nama': kriteria.nama,
                    'tipe': kriteria.tipe,
                    'bobot_persen': kriteria.bobot,
                    'bobot_ternormalisasi': round(bobot_w, 6),
                    'nilai_raw': utility_data.get('nilai_raw'),
                    'nilai_max': utility_data.get('nilai_max'),
                    'nilai_min': utility_data.get('nilai_min'),
                    'nilai_utility': round(u, 6),
                    'nilai_akhir_kriteria': round(nilai_akhir, 6),
                })

            self._total_nilai[alt.id] = round(total, 6)
            self._detail[alt.id] = detail_kriteria

    # ----------------------------------------------------------
    # Step 6 – Build hasil (ranking + predikat)
    # ----------------------------------------------------------

    def _build_hasil(self) -> list[dict]:
        # Urutkan berdasarkan total nilai descending. Nilai yang sama
        # diurutkan menurut nama supaya urutannya selalu konsisten.
        ranking_list = sorted(
            self._alternatif,
            key=lambda a: (
                -self._total_nilai.get(a.id, 0),
                a.karyawan.nama.lower(),
            ),
        )

        hasil = []
        rank = 0
        total_sebelumnya = None

        for urutan, alt in enumerate(ranking_list, start=1):
            total = self._total_nilai.get(alt.id, 0)

            # Total nilai sama -> ranking sama (mis. 1, 1, 3, 4),
            # bukan ranking berbeda yang ditentukan secara acak.
            if total != total_sebelumnya:
                rank = urutan
                total_sebelumnya = total

            hasil.append({
                'ranking': rank,
                'alternatif_id': alt.id,
                'kode': alt.kode,
                'nama': alt.karyawan.nama,
                'jabatan': alt.karyawan.jabatan,
                'jabatan_label': alt.karyawan.get_jabatan_display(),
                'total_nilai': total,
                'predikat': get_predikat(total),
                'detail_kriteria': self._detail.get(alt.id, []),
            })

        return hasil

    # ----------------------------------------------------------
    # Step 7 – Simpan ke DB
    # ----------------------------------------------------------

    def _simpan_ke_db(self):
        hasil = self._build_hasil()

        # Hapus data lama untuk periode ini
        alt_ids = [alt.id for alt in self._alternatif]

        Utility.objects.filter(penilaian__alternatif_id__in=alt_ids).delete()
        PerhitunganSmart.objects.filter(alternatif_id__in=alt_ids).delete()
        HasilSmart.objects.filter(alternatif_id__in=alt_ids).delete()

        # Simpan Utility
        # Ambil semua Penilaian periode ini sekaligus (bukan satu per satu).
        penilaian_map = {
            (p.alternatif_id, p.kriteria_id): p
            for p in Penilaian.objects.filter(alternatif_id__in=alt_ids)
        }

        utility_bulk = []
        for alt in self._alternatif:
            for kr_id, data in self._utility_matrix.get(alt.id, {}).items():
                penilaian = penilaian_map.get((alt.id, kr_id))

                if penilaian is None:
                    continue

                utility_bulk.append(
                    Utility(
                        penilaian=penilaian,
                        nilai_max=data['nilai_max'],
                        nilai_min=data['nilai_min'],
                        nilai_utility=data['utility'],
                    )
                )

        Utility.objects.bulk_create(utility_bulk)

        # Simpan PerhitunganSmart
        perhitungan_bulk = []
        for alt in self._alternatif:
            for detail in self._detail.get(alt.id, []):
                perhitungan_bulk.append(
                    PerhitunganSmart(
                        alternatif=alt,
                        kriteria_id=detail['kriteria_id'],
                        bobot_ternormalisasi=detail['bobot_ternormalisasi'],
                        nilai_utility=detail['nilai_utility'],
                        nilai_akhir_kriteria=detail['nilai_akhir_kriteria'],
                    )
                )

        PerhitunganSmart.objects.bulk_create(perhitungan_bulk)

        # Simpan HasilSmart
        hasil_bulk = []
        for h in hasil:
            hasil_bulk.append(
                HasilSmart(
                    alternatif_id=h['alternatif_id'],
                    total_nilai=h['total_nilai'],
                    ranking=h['ranking'],
                    predikat=h['predikat'],
                )
            )

        HasilSmart.objects.bulk_create(hasil_bulk)


# ============================================================
# Helper: Ambil hasil yang sudah tersimpan di DB
# ============================================================

def get_hasil_dari_db(periode_id: int) -> list[dict]:
    hasil_qs = (
        HasilSmart.objects
        .filter(alternatif__periode_id=periode_id)
        .select_related(
            'alternatif',
            'alternatif__karyawan',
            'alternatif__karyawan__user',
        )
        .prefetch_related(
            'alternatif__perhitungan',
            'alternatif__perhitungan__kriteria',
            'alternatif__penilaian',   # <-- tambahan: buat ambil nilai_raw asli
        )
        .order_by('ranking', 'alternatif__karyawan__nama')
    )

    hasil = []
    for h in hasil_qs:
        alt = h.alternatif

        # map kriteria_id -> nilai_raw dari Penilaian, karena PerhitunganSmart
        # tidak menyimpan nilai_raw
        nilai_raw_map = {p.kriteria_id: p.nilai_raw for p in alt.penilaian.all()}

        detail_kriteria = []
        for p in alt.perhitungan.all():
            detail_kriteria.append({
                'kriteria_kode': p.kriteria.kode,
                'kriteria_nama': p.kriteria.nama,
                'bobot_ternormalisasi': p.bobot_ternormalisasi,
                'nilai_raw': nilai_raw_map.get(p.kriteria_id),   # <-- ditambahkan
                'nilai_utility': p.nilai_utility,
                'nilai_akhir_kriteria': p.nilai_akhir_kriteria,
            })

        hasil.append({
            'ranking': h.ranking,
            'alternatif_id': alt.id,
            'kode': alt.kode,
            'nama': alt.karyawan.nama,
            'jabatan': alt.karyawan.jabatan,
            'jabatan_label': alt.karyawan.get_jabatan_display(),
            'total_nilai': h.total_nilai,
            'predikat': h.predikat,
            'detail_kriteria': detail_kriteria,
        })

    return hasil