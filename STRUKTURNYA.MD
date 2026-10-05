## Struktur dan Fungsi Folder Project

Berikut gambaran singkat struktur project dan fungsi dari masing-masing bagian:

```text
skripsismart/
│
├── manage.py
├── requirements.txt
├── db.sqlite3
│
├── rama_cipta_mandiri/
│   ├── migrations/
│   ├── spk/
│   ├── static/
│   ├── templates/
│   ├── views/
│   │   ├── admin/
│   │   │   ├── dashboard.py
│   │   │   ├── karyawan.py
│   │   │   ├── kriteria_subkriteria.py
│   │   │   ├── absensi_penilaian.py
│   │   │   └── smart.py
│   │   ├── auth.py
│   │   ├── karyawan.py
│   │   └── absensi_matching.py
│   │
│   ├── admin.py
│   ├── decorators.py
│   ├── forms.py
│   ├── models.py
│   └── urls.py
│
└── konfigurasi_project/
    ├── settings.py
    ├── urls.py
    ├── asgi.py
    └── wsgi.py
```

> Nama folder konfigurasi project bisa berbeda, tetapi biasanya merupakan folder yang berisi `settings.py`.

### File Utama

**`manage.py`**  
File utama untuk menjalankan perintah Django.

Contoh:

```bash
python manage.py runserver
python manage.py check
python manage.py migrate
```

**`requirements.txt`**  
Berisi daftar library Python yang dibutuhkan aplikasi.

Untuk menginstall seluruh kebutuhan aplikasi:

```bash
pip install -r requirements.txt
```

**`db.sqlite3`**  
Database aplikasi. Data karyawan, penilaian, absensi, hasil SMART, akun, dan data lainnya tersimpan di sini.

File ini jangan dihapus apabila masih menggunakan database yang sudah tersedia.

---

## Folder `rama_cipta_mandiri`

Folder ini merupakan bagian utama aplikasi SPK.

### `models.py`

Berisi struktur/model database aplikasi.

Beberapa data utama yang dikelola antara lain:

- Karyawan
- Kriteria
- Sub Kriteria
- Periode
- Alternatif
- Absensi
- Penilaian
- Utility
- Perhitungan SMART
- Hasil SMART

Kalau ingin melihat struktur data yang digunakan sistem, file utamanya ada di sini.

### `forms.py`

Berisi form Django yang digunakan untuk menerima dan memvalidasi input dari halaman aplikasi.

Contohnya form untuk:

- Data karyawan
- Kriteria
- Sub Kriteria
- Data lainnya yang menggunakan Django Form

### `urls.py`

Berisi daftar URL aplikasi dan menentukan function/view yang dijalankan ketika suatu halaman dibuka.

Contohnya:

```text
/admin-panel/
/admin-panel/karyawan/
/admin-panel/absensi/
/admin-panel/penilaian/
/admin-panel/smart/
```

### `decorators.py`

Berisi pembatasan akses berdasarkan jenis pengguna.

Digunakan agar halaman tertentu hanya dapat diakses oleh user yang memiliki hak akses sesuai.

---

## Folder `views`

Folder `views` berisi proses utama yang menghubungkan halaman, database, dan logic aplikasi.

### `views/auth.py`

Mengatur proses autentikasi seperti:

- Login
- Logout
- Pengalihan halaman berdasarkan hak akses

### `views/karyawan.py`

Mengatur halaman yang digunakan oleh karyawan, seperti:

- Dashboard karyawan
- Riwayat penilaian
- Detail hasil penilaian
- Absensi karyawan

### `views/absensi_matching.py`

Berisi helper untuk mencocokkan data absensi dengan Sub Kriteria yang digunakan dalam proses penilaian.

---

## Folder `views/admin`

Berisi seluruh proses logic halaman yang digunakan oleh Admin.

### `dashboard.py`

Mengatur Dashboard Admin dan menampilkan ringkasan data aplikasi.

### `karyawan.py`

Mengatur data karyawan, seperti:

- Daftar karyawan
- Tambah karyawan
- Edit karyawan
- Hapus karyawan
- Akun login karyawan

### `kriteria_subkriteria.py`

Mengatur data Kriteria dan Sub Kriteria yang digunakan dalam perhitungan SMART.

### `absensi_penilaian.py`

Mengatur:

- Absensi bulanan karyawan
- Input penilaian
- Penilaian otomatis berdasarkan absensi
- Data penilaian setiap periode

Data absensi digunakan sebagai salah satu sumber nilai dalam proses penilaian.

### `smart.py`

Berisi proses yang berhubungan dengan hasil SMART dan laporan, seperti:

- Memilih periode SMART
- Menjalankan proses SMART
- Menampilkan hasil SMART
- Menghapus hasil SMART
- Menampilkan detail laporan
- Generate laporan PDF

---

## Folder `spk`

Folder ini berisi logic utama Sistem Pendukung Keputusan.

Di bagian ini terdapat proses perhitungan metode SMART, mulai dari pengambilan nilai, utility, normalisasi bobot, nilai akhir, hingga ranking.

Secara sederhana alurnya:

```text
Data Karyawan
      ↓
Absensi & Penilaian
      ↓
Nilai Kriteria
      ↓
Utility
      ↓
Normalisasi Bobot
      ↓
Perhitungan SMART
      ↓
Nilai Akhir
      ↓
Ranking
```

Kalau ingin mengecek atau mengubah rumus/perhitungan SMART, bagian utamanya ada di folder ini.

---

## Folder `templates`

Berisi seluruh file HTML yang digunakan sebagai tampilan aplikasi.

Contohnya:
pyth
├── admin_panel/
└── karyawan/
```

`admin_panel` digunakan untuk halaman Admin, sedangkan halaman karyawan digunakan untuk tampilan akun karyawan.

Kalau ingin mengubah struktur atau isi tampilan halaman, biasanya file yang dicari ada di folder ini.

---

## Folder `static`

Berisi file pendukung tampilan aplikasi yang tidak berubah secara dinamis, seperti:

- CSS
- JavaScript
- Gambar
- Logo

Kalau ingin mengubah desain, ukuran, warna, atau styling halaman, sebagian besar pengaturannya ada di folder ini.

---

## Folder `migrations`

Berisi riwayat perubahan struktur database Django.

Folder ini digunakan Django ketika menjalankan:

```bash
python manage.py migrate
```

Sebaiknya file migration tidak dihapus atau diubah secara manual jika tidak diperlukan.

---

## Folder Konfigurasi Project

Folder yang berisi `settings.py`, `urls.py`, `wsgi.py`, dan `asgi.py` merupakan konfigurasi utama Django.

### `settings.py`

Berisi konfigurasi aplikasi, seperti:

- Database
- Installed apps
- Template
- Static files
- Bahasa dan timezone
- Konfigurasi Django lainnya

### `urls.py`

Merupakan URL utama project yang menghubungkan Django dengan URL aplikasi `rama_cipta_mandiri`.

### `wsgi.py` dan `asgi.py`

Digunakan sebagai konfigurasi ketika aplikasi dijalankan melalui server/deployment.

Untuk penggunaan aplikasi secara lokal dengan:

```bash
python manage.py runserver
```

biasanya file ini tidak perlu diubah.

---

## Alur Singkat Aplikasi

Secara umum alur aplikasi adalah:

```text
Login
  ↓
Data Karyawan
  ↓
Kriteria & Sub Kriteria
  ↓
Absensi
  ↓
Penilaian
  ↓
Perhitungan SMART
  ↓
Hasil & Ranking
  ↓
Laporan / PDF
```

Untuk penggunaan normal, tidak perlu mengubah source code pada folder-folder di atas.