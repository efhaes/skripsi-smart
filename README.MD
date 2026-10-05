# Panduan Menjalankan Aplikasi SPK Penilaian Karyawan

Halo Mas Audi, berikut langkah untuk setup dan menjalankan aplikasi di laptop.

## 1. Install Python

Kalau Python belum terinstall, download terlebih dahulu melalui:

https://www.python.org/downloads/

Saat proses instalasi, pastikan centang:

`Add Python to PATH`

Setelah instalasi selesai, buka VS Code lalu buka folder project aplikasi.

Untuk memastikan Python sudah terinstall, buka terminal VS Code dengan:

`Ctrl + J`

Kemudian pilih tab **Terminal** dan jalankan:

```bash
python --version
```

Kalau muncul versi Python, misalnya:

```text
Python 3.x.x
```

berarti Python sudah berhasil terinstall.

Cek juga pip:

```bash
pip --version
```

Kalau versi pip muncul, lanjut ke langkah berikutnya.

## 2. Install Library Project

Pastikan folder project sudah dibuka di VS Code.

Buka terminal dengan:

`Ctrl + J`

Kemudian install semua library yang dibutuhkan aplikasi dengan:

```bash
pip install -r requirements.txt
```

Tunggu sampai proses instalasi selesai.

Perintah tersebut akan otomatis menginstall Django dan library lain yang dibutuhkan aplikasi.

Untuk memastikan Django sudah terinstall:

```bash
python -m django --version
```

Kalau muncul versi Django, berarti instalasi berhasil.

## 3. Cek Project

Sebelum menjalankan aplikasi, jalankan:

```bash
python manage.py check
```

Kalau tidak ada error, berarti project sudah siap dijalankan.

## 4. Jalankan Aplikasi

Di terminal VS Code, jalankan:

```bash
python manage.py runserver
```

Kalau berhasil, akan muncul:

```text
Starting development server at http://127.0.0.1:8000/
```

Setelah itu buka browser dan akses:

```text
http://127.0.0.1:8000/
```

Aplikasi sudah bisa digunakan.

Selama aplikasi digunakan, terminal yang menjalankan server jangan ditutup.

## 5. Menjalankan Aplikasi Selanjutnya

Kalau Python dan semua library sudah pernah diinstall, tidak perlu melakukan instalasi ulang.

Cukup buka folder project di VS Code, tekan:

`Ctrl + J`

Lalu jalankan:

```bash
python manage.py runserver
```

Kemudian buka:

```text
http://127.0.0.1:8000/
```

## 6. Menghentikan Server

Untuk menghentikan aplikasi, klik terminal yang sedang menjalankan server lalu tekan:

`Ctrl + C`

Server akan berhenti dan terminal bisa digunakan kembali.

## Catatan

- Jangan hapus file `db.sqlite3` karena berisi database aplikasi.
- Jangan menghapus atau mengubah file project jika tidak diperlukan.
- Jika muncul error saat instalasi atau menjalankan aplikasi, screenshot bagian error di terminal lalu kirim ke saya ya Mas.