# Panduan Instalasi dan Penggunaan YTUploader di Windows

Dokumen ini menjelaskan langkah demi langkah cara memasang, menjalankan, dan membagikan aplikasi **YTUploader** kepada pengguna Windows. Seluruh instruksi ditulis agar mudah diikuti oleh pemula.

---

## 1. Persiapan Awal

1. **Unduh kode sumber**
   - Buka halaman repositori YTUploader dan tekan tombol **Code → Download ZIP**.
   - Ekstrak arsip ZIP tersebut ke folder yang mudah diakses, misalnya `C:\YTUploader`.

2. **Pasang Python 3.11 atau versi terbaru**
   - Kunjungi [python.org/downloads](https://www.python.org/downloads/).
   - Unduh installer Windows (64-bit).
   - Jalankan installer dan centang opsi **Add Python to PATH**, kemudian klik **Install Now**.

3. **Siapkan kredensial Google**
   - Buka [Google Cloud Console](https://console.cloud.google.com/) dan buat proyek baru atau gunakan proyek yang sudah ada.
   - Arahkan ke menu **APIs & Services → Library**, lalu aktifkan layanan berikut untuk proyek tersebut:
     - **YouTube Data API v3** (mengelola unggahan ke YouTube).
     - **Google Sheets API** (mengambil data dari spreadsheet penjadwalan).
     - **Google Drive API** (mengunduh berkas video dari Drive, bila digunakan).
   - Setelah semua API aktif, buka **APIs & Services → Credentials** dan pilih **Create Credentials → OAuth client ID**.
   - Jika diminta, lengkapi layar persetujuan OAuth minimal pada level **External** dengan informasi dasar (nama aplikasi dan email).
   - Pilih jenis aplikasi **Desktop app**, beri nama bebas, kemudian klik **Create**.
   - Tekan tombol **Download JSON** pada kredensial yang baru dibuat untuk mendapatkan berkas `client_secret.json`, lalu simpan file tersebut di folder proyek YTUploader.

---

## 2. Membuat Lingkungan Kerja

1. Buka **Command Prompt** atau **Windows Terminal**.
2. Pindah ke folder proyek, contohnya:
   ```powershell
   cd C:\YTUploader
   ```
3. Buat lingkungan virtual (opsional namun direkomendasikan):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
4. Instal seluruh ketergantungan aplikasi:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 3. Menyiapkan File Konfigurasi

1. Salin contoh konfigurasi:
   ```powershell
   copy config.example.yaml config.yaml
   ```
2. Sunting `config.yaml` menggunakan teks editor (misal Notepad atau VS Code).
3. Isi bagian berikut sesuai kebutuhan:
   - **Informasi spreadsheet Google Sheets** (ID sheet, nama worksheet, kolom-kolom yang digunakan).
   - **Informasi akun YouTube** dan kredensial login otomatis.
   - **Jadwal unggahan** serta pengaturan pembersihan file.
4. Simpan perubahan dan pastikan `config.yaml` berada di folder yang sama dengan aplikasi.

> **Tips:** Jika menggunakan file Google Drive, pastikan kolom `drive_file_id` atau `drive_download_url` terisi untuk setiap baris video.

---

## 4. Menjalankan Aplikasi dengan Antarmuka Grafis (GUI)

1. Pastikan lingkungan virtual (jika ada) masih aktif.
2. Jalankan perintah berikut untuk membuka tampilan GUI:
   ```powershell
   python -m yt_uploader.gui
   ```
3. Pada jendela **YTUploader**:
   - Klik **Pilih Config** dan arahkan ke `config.yaml` yang sudah Anda sunting.
   - Setelah konfigurasi berhasil dimuat, tekan tombol **Mulai** untuk menyalakan penjadwal.
4. Aplikasi akan berjalan di latar belakang menggunakan jadwal yang Anda tentukan. Status terbaru tampil pada panel informasi di jendela.
5. Untuk menghentikan sementara, tekan tombol **Berhenti**. Anda dapat menekan **Mulai** lagi kapan pun tanpa perlu memuat ulang konfigurasi.

> **Catatan:** Log aktivitas tersimpan otomatis di folder log yang ditentukan pada konfigurasi (misalnya `logs/uploader.log`).

### Mengelola Cookie Login Google/YouTube

1. Pasang ekstensi [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/) di Google Chrome.
2. Buka `https://studio.youtube.com` dan pastikan akun yang benar sudah login.
3. Klik ikon Cookie-Editor → pilih tab **Export** → tekan **Copy** untuk menyalin JSON cookie.
4. Di GUI YTUploader, buka bagian **Manajemen Cookie Google/YouTube**, pilih akun yang diinginkan, kemudian tempel JSON pada kotak yang tersedia atau tekan **Muat File Cookie** bila Anda sudah menyimpannya sebagai `.json`.
5. Klik **Simpan Cookie** untuk menulis data ke jalur `cookie_file` sesuai konfigurasi. Setelah tersimpan, aplikasi dapat langsung menggunakan sesi tersebut untuk otomatis login.

---

## 5. Menjalankan Aplikasi Melalui Command Line (Opsional)

Jika Anda lebih nyaman dengan terminal, aplikasi tetap dapat dijalankan tanpa GUI:

```powershell
python -m yt_uploader.main config.yaml
```

Tekan `Ctrl + C` untuk menghentikan program ketika sudah tidak diperlukan.

---

## 6. Membangun File `.exe` Menggunakan PyInstaller

Langkah ini memungkinkan Anda mendistribusikan aplikasi sebagai berkas tunggal yang siap dijalankan di Windows.

1. Instal **PyInstaller** di lingkungan yang sama:
   ```powershell
   pip install pyinstaller
   ```
2. Jalankan perintah berikut di folder proyek:
   ```powershell
   pyinstaller --noconfirm --noconsole --name YTUploaderGUI yt_uploader\gui.py
   ```
   - Opsi `--noconsole` menonaktifkan jendela terminal agar aplikasi terlihat seperti aplikasi desktop biasa.
   - Anda dapat menambahkan ikon khusus menggunakan `--icon path\ke\ikon.ico` bila diinginkan.
3. Setelah proses selesai, file executable berada di folder `dist\YTUploaderGUI\YTUploaderGUI.exe`.
4. Salin `config.yaml`, kredensial (`client_secret.json`), dan file pendukung lain ke folder yang sama dengan `YTUploaderGUI.exe`.
5. Distribusikan seluruh isi folder tersebut kepada pengguna akhir.

> **Saran:** Uji jalankan `YTUploaderGUI.exe` pada komputer uji sebelum dibagikan ke pengguna untuk memastikan seluruh dependensi terpenuhi.

---

## 7. Pemecahan Masalah Umum

| Permasalahan | Solusi |
| --- | --- |
| Tidak bisa login ke akun Google | Pastikan kredensial dan data login pada `config.yaml` benar, serta tidak ada verifikasi tambahan dari Google. |
| Video tidak ditemukan | Pastikan jalur file lokal benar atau kolom Google Drive terisi dengan tautan/ID yang valid. |
| Jadwal tidak berjalan | Periksa pengaturan waktu di komputer dan pastikan komputer tidak masuk mode tidur. |
| Aplikasi menutup sendiri ketika dijalankan dari `.exe` | Jalankan kembali melalui Command Prompt untuk melihat pesan error, lalu perbaiki konfigurasi sesuai pesan tersebut. |

---

Selamat! Anda sudah siap menggunakan dan membagikan aplikasi YTUploader di lingkungan Windows. Jika membutuhkan fitur tambahan, Anda dapat mengembangkan kode sumber lebih lanjut sesuai kebutuhan.

