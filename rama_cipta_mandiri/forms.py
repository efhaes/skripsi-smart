from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import Kriteria, SubKriteria, Absensi, Alternatif, Karyawan,Periode   

class KaryawanForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Kosongkan jika karyawan ini tidak perlu akun login."
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text=(
            "Wajib diisi saat membuat akun baru. "
            "Kosongkan saat update jika tidak ingin ganti password."
        )
    )

    class Meta:
        model = Karyawan
        fields = [
            'nama',
            'jabatan',
            'aktif',
            'tanggal_masuk'
        ]

        widgets = {
            'jabatan': forms.Select(
                attrs={'class': 'form-select'}
            ),
            'tanggal_masuk': forms.DateInput(
                attrs={'type': 'date'}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        username = (
            cleaned_data.get('username') or ''
        ).strip()

        password = cleaned_data.get('password') or ''

        punya_user = bool(
            self.instance.pk and self.instance.user_id
        )

        # Jika username diisi tetapi Karyawan belum punya akun,
        # berarti admin sedang membuat User baru.
        if username and not punya_user and not password:
            self.add_error(
                'password',
                "Password wajib diisi saat membuat akun baru."
            )

        if username:
            qs = User.objects.filter(
                username=username
            )

            # Saat edit akun existing, username miliknya sendiri
            # tidak dianggap duplikat.
            if punya_user:
                qs = qs.exclude(
                    pk=self.instance.user_id
                )

            if qs.exists():
                self.add_error(
                    'username',
                    "Username sudah dipakai, pilih yang lain."
                )

        return cleaned_data
    
class KriteriaForm(forms.ModelForm):
    class Meta:
        model = Kriteria
        fields = ['kode', 'nama', 'bobot', 'tipe', 'urutan', 'aktif']
        widgets = {
            'kode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'C1'}),
            'nama': forms.TextInput(attrs={'class': 'form-control'}),
            'bobot': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
            'tipe': forms.Select(attrs={'class': 'form-select'}),
            'urutan': forms.NumberInput(attrs={'class': 'form-control'}),
            'aktif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_bobot(self):
        bobot = self.cleaned_data['bobot']
        if bobot <= 0 or bobot > 100:
            raise ValidationError("Bobot harus di antara 0 dan 100.")
        return bobot

    def clean(self):
        """
        Cegah total bobot kriteria aktif melebihi 100%.
        Kalau masih di bawah 100%, dibiarkan lolos — itu wajar selama
        kriteria lain belum semua ditambahkan. Info total & validitasnya
        ditampilkan di halaman list (bobot_valid), bukan diblokir di sini.
        """
        cleaned = super().clean()
        aktif = cleaned.get('aktif')
        bobot = cleaned.get('bobot')

        if aktif and bobot is not None:
            qs = Kriteria.objects.filter(aktif=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            total_lain = sum(k.bobot for k in qs)
            total_baru = total_lain + bobot

            if total_baru > 100 + 0.01:  # toleransi kecil untuk floating point
                self.add_error(
                    'bobot',
                    f"Total bobot kriteria aktif akan menjadi {total_baru:.2f}%, melebihi 100%. "
                    f"Kurangi bobot kriteria ini, atau nonaktifkan/kurangi bobot kriteria lain dulu."
                )
        return cleaned


class SubKriteriaForm(forms.ModelForm):
    class Meta:
        model = SubKriteria
        fields = ['kriteria', 'nama','range_nilai', 'nilai']
        widgets = {
            'kriteria': forms.Select(attrs={'class': 'form-select'}),
            'nama': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'mis. Baik'}),
            'range_nilai': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'mis. 0-2'}),
            'nilai': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }



class PeriodeForm(forms.ModelForm):
    class Meta:
        model = Periode
        fields = ['bulan', 'tahun']
        widgets = {
            'bulan': forms.Select(
                choices=[(i, Periode.BULAN_LABEL[i]) for i in range(1, 13)],
                attrs={'class': 'form-select'}
            ),
            'tahun': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100}),
        }

    def clean(self):
        cleaned = super().clean()
        bulan = cleaned.get('bulan')
        tahun = cleaned.get('tahun')

        if bulan and tahun:
            qs = Periode.objects.filter(bulan=bulan, tahun=tahun)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('tahun', "Periode bulan & tahun ini sudah ada.")
        
        # Add server-side validation for month and year ranges
        if bulan and not (1 <= bulan <= 12):
            self.add_error('bulan', "Bulan harus antara 1 dan 12.")
        
        if tahun and not (2000 <= tahun <= 2100):
            self.add_error('tahun', "Tahun harus antara 2000 dan 2100.")
            
        return cleaned
    
class AbsensiForm(forms.ModelForm):
    class Meta:
        model = Absensi
        fields = ['alternatif', 'tanggal', 'status']
        widgets = {
            'alternatif': forms.Select(attrs={'class': 'form-select'}),
            'tanggal': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        alternatif = cleaned.get('alternatif')
        tanggal = cleaned.get('tanggal')

        if alternatif and tanggal:
            qs = Absensi.objects.filter(alternatif=alternatif, tanggal=tanggal)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Absensi untuk karyawan & tanggal ini sudah ada.")
        return cleaned