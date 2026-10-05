from .dashboard import dashboard_admin

from .karyawan import (
    karyawan_list,
    karyawan_create,
    karyawan_update,
    karyawan_delete,
)

from .kriteria_subkriteria import (
    kriteria_list,
    kriteria_create,
    kriteria_update,
    kriteria_delete,
    subkriteria_list,
    subkriteria_create,
    subkriteria_update,
    subkriteria_delete,
)

from .absensi_penilaian import (
    absensi_bulanan,
    penilaian_list,
    penilaian_form,
    penilaian_hapus,
)

from .smart import (
    smart_pilih_periode,
    smart_list,
    smart_proses_form,
    smart_delete,
    hasil_smart_view,
    preview_smart,
    laporan_detail,
    laporan_pdf,
)