# rama_cipta_mandiri/spk/__init__.py

from .smart import SmartCalculator, get_hasil_dari_db, get_predikat
from ..models import Periode, Kriteria, Penilaian, Alternatif


def get_or_create_periode(bulan, tahun):
    periode, _ = Periode.objects.get_or_create(bulan=bulan, tahun=tahun)
    return periode


def get_periode_if_exists(bulan, tahun):
    """
    Ambil Periode jika sudah ada di database, tanpa membuat baru.
    Return None jika belum ada.
    Digunakan untuk GET request yang hanya membaca data.
    """
    return Periode.objects.filter(bulan=bulan, tahun=tahun).first()


def cek_kelengkapan_penilaian(periode):
    """
    Cek kelengkapan penilaian untuk suatu periode.
    
    Returns:
        dict: {
            'valid': bool,
            'total_alternatif': int,
            'total_kriteria': int,
            'expected': int,
            'actual': int,
            'pesan': str
        }
    """
    kriteria_aktif = Kriteria.objects.filter(aktif=True)
    total_kriteria = kriteria_aktif.count()
    
    if total_kriteria == 0:
        return {
            'valid': False,
            'total_alternatif': 0,
            'total_kriteria': 0,
            'expected': 0,
            'actual': 0,
            'pesan': 'Tidak ada kriteria aktif.'
        }
    
    alternatif_qs = Alternatif.objects.filter(periode=periode)
    total_alternatif = alternatif_qs.count()
    
    if total_alternatif == 0:
        return {
            'valid': False,
            'total_alternatif': 0,
            'total_kriteria': total_kriteria,
            'expected': 0,
            'actual': 0,
            'pesan': 'Tidak ada alternatif (karyawan) pada periode ini.'
        }
    
    expected = total_alternatif * total_kriteria
    
    penilaian_qs = Penilaian.objects.filter(
        alternatif__periode=periode,
        kriteria__aktif=True
    )
    actual = penilaian_qs.count()
    
    valid = actual == expected
    
    if valid:
        pesan = f'Penilaian lengkap ({actual}/{expected} nilai).'
    else:
        pesan = f'Penilaian belum lengkap ({actual}/{expected} nilai). Lengkapi penilaian terlebih dahulu.'
    
    return {
        'valid': valid,
        'total_alternatif': total_alternatif,
        'total_kriteria': total_kriteria,
        'expected': expected,
        'actual': actual,
        'pesan': pesan
    }


__all__ = ['SmartCalculator', 'get_hasil_dari_db', 'get_predikat', 'get_or_create_periode', 'get_periode_if_exists', 'cek_kelengkapan_penilaian']