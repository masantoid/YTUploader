"""Graphical interface for the YTUploader application."""
from __future__ import annotations

import json
import re
import tempfile
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

import yaml

from .config import AccountConfig, AppConfig
from .google_drive import GoogleDriveDownloader
from .google_sheets import GoogleSheetClient
from .service import UploaderService


class UploaderGUI:
    """Tkinter based desktop interface for YTUploader."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YTUploader")
        self.root.geometry("920x780")
        self.root.minsize(820, 720)

        self.service = UploaderService()
        self._lock = threading.Lock()

        self.status_var = tk.StringVar(value="Silakan buat atau muat file konfigurasi sebelum mulai.")
        self.config_info_var = tk.StringVar(value="Belum ada file konfigurasi dipilih.")
        self.unsaved_info_var = tk.StringVar(value="")
        self.sheet_status_var = tk.StringVar(value="Tekan tombol untuk menguji koneksi Google Sheets.")
        self.drive_status_var = tk.StringVar(value="Masukkan File ID atau URL untuk menguji akses Google Drive.")

        self.config_path: Path | None = None
        self.accounts: list[AccountConfig] = []
        self.accounts_data: list[dict[str, Any]] = []
        self.unsaved_changes = False
        self._loading_form = False
        self._current_account_index: int | None = None

        self._create_config_variables()
        self._build_widgets()
        self._set_default_form()

    def _build_widgets(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", padding=6)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TLabelframe", padding=12)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=6)

        header = ttk.Frame(self.root, padding=20)
        header.pack(fill=tk.X)

        title = ttk.Label(header, text="YTUploader", font=("Segoe UI", 22, "bold"))
        title.grid(row=0, column=0, sticky="w")

        control_frame = ttk.Frame(header)
        control_frame.grid(row=0, column=1, sticky="e")

        self.start_button = ttk.Button(
            control_frame,
            text="Mulai",
            command=self.start_service,
            state=tk.DISABLED,
            style="Accent.TButton",
        )
        self.start_button.grid(row=0, column=0, padx=(0, 8))

        self.stop_button = ttk.Button(control_frame, text="Berhenti", command=self.stop_service, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1)

        header.grid_columnconfigure(0, weight=1)

        info_frame = ttk.Frame(self.root, padding=(20, 0))
        info_frame.pack(fill=tk.X)

        ttk.Label(info_frame, textvariable=self.config_info_var, font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        ttk.Label(info_frame, textvariable=self.unsaved_info_var, foreground="#cc6600").pack(anchor="w", pady=(2, 0))

        status_label = ttk.Label(
            self.root,
            textvariable=self.status_var,
            padding=12,
            wraplength=760,
            relief=tk.GROOVE,
        )
        status_label.pack(fill=tk.X, padx=20, pady=10)

        self._build_content_area()

    def _create_config_variables(self) -> None:
        self.google_service_file_var = tk.StringVar()
        self.google_spreadsheet_var = tk.StringVar()
        self.google_worksheet_var = tk.StringVar()

        self.sheet_mapping_vars: dict[str, tk.StringVar] = {
            "title": tk.StringVar(),
            "description": tk.StringVar(),
            "hashtags": tk.StringVar(),
            "tags": tk.StringVar(),
            "filename": tk.StringVar(),
            "drive_file_id": tk.StringVar(),
            "drive_download_url": tk.StringVar(),
            "drive_view_url": tk.StringVar(),
            "created_time": tk.StringVar(),
            "final_output": tk.StringVar(),
            "status": tk.StringVar(),
            "youtube_url": tk.StringVar(),
            "altered_content": tk.StringVar(),
            "made_for_kids": tk.StringVar(),
        }

        self.schedule_times_var = tk.StringVar()
        self.schedule_timezone_var = tk.StringVar()
        self.schedule_randomize_var = tk.BooleanVar()

        self.selenium_driver_var = tk.StringVar()
        self.selenium_headless_var = tk.BooleanVar()
        self.selenium_user_agent_var = tk.StringVar()
        self.selenium_download_dir_var = tk.StringVar()

        self.cleanup_log_dir_var = tk.StringVar()
        self.cleanup_retention_var = tk.StringVar()
        self.cleanup_remove_uploaded_var = tk.BooleanVar()

        self.max_retries_var = tk.StringVar()
        self.retry_interval_var = tk.StringVar()

        self.drive_file_id_var = tk.StringVar()
        self.drive_url_var = tk.StringVar()

        for var in [
            self.google_service_file_var,
            self.google_spreadsheet_var,
            self.google_worksheet_var,
            self.schedule_times_var,
            self.schedule_timezone_var,
            self.selenium_driver_var,
            self.selenium_user_agent_var,
            self.selenium_download_dir_var,
            self.cleanup_log_dir_var,
            self.cleanup_retention_var,
            self.max_retries_var,
            self.retry_interval_var,
            self.drive_file_id_var,
            self.drive_url_var,
        ]:
            var.trace_add("write", self._mark_dirty)

        self.schedule_randomize_var.trace_add("write", self._mark_dirty)
        self.selenium_headless_var.trace_add("write", self._mark_dirty)
        self.cleanup_remove_uploaded_var.trace_add("write", self._mark_dirty)

        for var in self.sheet_mapping_vars.values():
            var.trace_add("write", self._mark_dirty)

    def _build_content_area(self) -> None:
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_header_section(scroll_frame)
        self._build_account_section(scroll_frame)
        self._build_google_section(scroll_frame)
        self._build_sheet_mapping_section(scroll_frame)
        self._build_schedule_section(scroll_frame)
        self._build_selenium_section(scroll_frame)
        self._build_cleanup_section(scroll_frame)
        self._build_retry_section(scroll_frame)

    def _build_header_section(self, parent: ttk.Frame) -> None:
        intro = ttk.LabelFrame(parent, text="Panduan Langkah Demi Langkah")
        intro.pack(fill=tk.X, padx=4, pady=(0, 12))

        intro_text = (
            "Ikuti urutan langkah di bawah ini untuk mengatur otomatisasi upload: \n"
            "1. Tambah akun YouTube dan simpan cookie.\n"
            "2. Hubungkan ke Google Service Account serta Spreadsheet.\n"
            "3. Tentukan kolom pada Spreadsheet yang harus diupdate otomatis.\n"
            "4. Atur jadwal dan opsi lanjutan jika diperlukan, lalu simpan konfigurasi."
        )
        ttk.Label(intro, text=intro_text, justify=tk.LEFT, wraplength=760).pack(anchor="w", padx=12, pady=(8, 4))

        file_frame = ttk.LabelFrame(parent, text="File Konfigurasi")
        file_frame.pack(fill=tk.X, padx=4, pady=(0, 12))

        self.config_path_var = tk.StringVar()

        entry = ttk.Entry(file_frame, textvariable=self.config_path_var, state="readonly")
        entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)

        ttk.Button(file_frame, text="Konfigurasi Baru", command=self._create_new_config).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(file_frame, text="Muat…", command=self.load_config_dialog).grid(row=0, column=2, padx=4)
        ttk.Button(file_frame, text="Simpan", command=self.save_config).grid(row=0, column=3, padx=4)
        ttk.Button(file_frame, text="Simpan Sebagai…", command=self.save_config_as).grid(row=0, column=4, padx=4)

        file_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(
            file_frame,
            text="Setelah selesai mengisi langkah-langkah di bawah, gunakan tombol Simpan untuk membuat file YAML.",
            foreground="#444444",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=12, pady=(0, 12))

    def _build_account_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Langkah 1 · Kelola Akun YouTube")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text=(
                "Tambahkan setiap akun YouTube yang ingin Anda otomasi. Isi nama mudah dibaca, URL channel, dan lokasi file "
                "cookie. Anda dapat langsung menempel JSON cookie ke editor di bagian bawah lalu simpan."
            ),
            wraplength=760,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.account_listbox = tk.Listbox(list_frame, height=5)
        self.account_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.account_listbox.bind("<<ListboxSelect>>", self._on_account_select)

        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))

        ttk.Button(btn_frame, text="Tambah Akun", command=self._add_account).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(btn_frame, text="Hapus Akun", command=self._remove_account).pack(fill=tk.X)

        form = ttk.Frame(frame)
        form.pack(fill=tk.X, padx=12)

        self.account_name_var = tk.StringVar()
        self.account_cookie_var = tk.StringVar()
        self.account_channel_var = tk.StringVar()

        for var in [self.account_name_var, self.account_cookie_var, self.account_channel_var]:
            var.trace_add("write", self._mark_dirty)

        self._labeled_entry(form, "Nama Akun", self.account_name_var, 0)
        cookie_entry = self._labeled_entry(form, "Lokasi File Cookie", self.account_cookie_var, 1)
        ttk.Button(form, text="Pilih…", command=self._browse_cookie_file).grid(row=1, column=2, padx=(8, 0))
        cookie_entry.configure(state="readonly")
        ttk.Label(
            form,
            text="File cookie akan dibuat otomatis ketika Anda menyimpan cookie dari editor di bawah.",
            foreground="#555555",
            wraplength=520,
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 8))

        self._labeled_entry(form, "URL Channel", self.account_channel_var, 3)

        ttk.Button(
            form,
            text="Simpan Perubahan Akun",
            command=self._apply_account_changes,
            style="Accent.TButton",
        ).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        form.grid_columnconfigure(1, weight=1)

        cookie_frame = ttk.LabelFrame(frame, text="Cookie JSON untuk Akun Terpilih")
        cookie_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(16, 12))
        cookie_frame.columnconfigure(0, weight=1)
        cookie_frame.rowconfigure(2, weight=1)

        ttk.Label(
            cookie_frame,
            text=(
                "Tempel cookie hasil ekspor dari browser (misal menggunakan ekstensi Cookie-Editor). "
                "Klik Simpan untuk membuat/menimpa file cookie akun ini."
            ),
            wraplength=720,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        self.cookie_text = scrolledtext.ScrolledText(cookie_frame, wrap=tk.WORD, height=10, font=("Consolas", 10))
        self.cookie_text.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(8, 12))
        self.cookie_text.insert(tk.END, "Pilih atau buat akun terlebih dahulu untuk mengelola cookie.")
        self.cookie_text.config(state=tk.DISABLED)

        button_bar = ttk.Frame(cookie_frame)
        button_bar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        button_bar.columnconfigure((0, 1, 2, 3), weight=1)

        self.load_cookie_button = ttk.Button(
            button_bar,
            text="Muat dari File",
            command=self.load_cookie_file,
            state=tk.DISABLED,
        )
        self.load_cookie_button.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.paste_cookie_button = ttk.Button(
            button_bar,
            text="Tempel Clipboard",
            command=self.paste_cookie_from_clipboard,
            state=tk.DISABLED,
        )
        self.paste_cookie_button.grid(row=0, column=1, padx=6, sticky="ew")

        self.clear_cookie_button = ttk.Button(
            button_bar,
            text="Kosongkan",
            command=self.clear_cookie_editor,
            state=tk.DISABLED,
        )
        self.clear_cookie_button.grid(row=0, column=2, padx=6, sticky="ew")

        self.save_cookie_button = ttk.Button(
            button_bar,
            text="Simpan Cookie",
            command=self.save_cookie_data,
            state=tk.DISABLED,
            style="Accent.TButton",
        )
        self.save_cookie_button.grid(row=0, column=3, padx=(6, 0), sticky="ew")
        self._update_cookie_editor_state()

    def _build_google_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Langkah 2 · Hubungkan Google")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text=(
                "Gunakan credential Service Account Google untuk mengakses Spreadsheet dan Drive. "
                "Spreadsheet ID dapat diambil dari URL Google Sheets."
            ),
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))

        self._labeled_entry(frame, "Service Account JSON", self.google_service_file_var, 1)
        ttk.Button(frame, text="Pilih…", command=self._browse_service_account).grid(row=1, column=2, padx=(8, 0))

        self._labeled_entry(frame, "Spreadsheet ID", self.google_spreadsheet_var, 2)
        self._labeled_entry(frame, "Worksheet", self.google_worksheet_var, 3)

        ttk.Label(
            frame,
            text="Masukkan nama worksheet persis seperti yang muncul di spreadsheet.",
            foreground="#555555",
        ).grid(row=4, column=1, columnspan=2, sticky="w", padx=12, pady=(0, 8))

        test_frame = ttk.LabelFrame(frame, text="Tes Koneksi Google", padding=12)
        test_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8))
        test_frame.columnconfigure(1, weight=1)

        ttk.Label(
            test_frame,
            text="Uji koneksi Spreadsheet dan Drive setelah mengisi credential.",
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Button(test_frame, text="Tes Spreadsheet", command=self.test_google_sheets).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Label(test_frame, textvariable=self.sheet_status_var, foreground="#0b5394", wraplength=520).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(12, 0)
        )

        ttk.Label(test_frame, text="Drive File ID").grid(row=2, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(test_frame, textvariable=self.drive_file_id_var).grid(
            row=2, column=1, sticky="ew", pady=(12, 0), padx=(8, 0)
        )
        ttk.Label(test_frame, text="atau URL Unduhan").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(test_frame, textvariable=self.drive_url_var).grid(
            row=3, column=1, sticky="ew", pady=(6, 0), padx=(8, 0)
        )
        ttk.Button(test_frame, text="Tes Google Drive", command=self.test_google_drive).grid(
            row=2, column=2, rowspan=2, padx=(12, 0), sticky="ns"
        )
        ttk.Label(test_frame, textvariable=self.drive_status_var, foreground="#38761d", wraplength=520).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        frame.grid_columnconfigure(1, weight=1)

    def _build_sheet_mapping_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Langkah 3 · Pemetaan Kolom Spreadsheet")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text=(
                "Tentukan nama kolom di Google Sheet untuk setiap data. Kolom status akan diperiksa untuk nilai "
                "'UploadYT'. Setelah video terunggah, kolom status diupdate menjadi 'Done' dan kolom YouTube URL "
                "diisi otomatis."
            ),
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=12, pady=(8, 4))

        ttk.Label(
            frame,
            text="Gunakan nama kolom persis seperti di spreadsheet (misal: UploadYT, YTUrl).",
            foreground="#555555",
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=(0, 12))

        fields = [
            ("Judul", "title"),
            ("Deskripsi", "description"),
            ("Hashtag", "hashtags"),
            ("Tag", "tags"),
            ("Nama File", "filename"),
            ("Drive File ID", "drive_file_id"),
            ("Drive Download URL", "drive_download_url"),
            ("Drive View URL", "drive_view_url"),
            ("Created Time", "created_time"),
            ("Final Output", "final_output"),
            ("Status (misal UploadYT)", "status"),
            ("YouTube URL (misal YTUrl)", "youtube_url"),
            ("Altered Content", "altered_content"),
            ("Made For Kids", "made_for_kids"),
        ]

        for idx, (label, key) in enumerate(fields):
            row = idx // 2 + 2
            column = (idx % 2) * 2
            self._labeled_entry(frame, label, self.sheet_mapping_vars[key], row, column)

        for idx in range(0, 4, 2):
            frame.grid_columnconfigure(idx + 1, weight=1)

    def _build_schedule_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Langkah 4 · Jadwal Upload")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text="Masukkan jam upload (format HH:MM) dipisahkan koma. Sistem akan menjalankan upload sesuai jadwal dan zona waktu yang dipilih.",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))

        self._labeled_entry(frame, "Jam Upload", self.schedule_times_var, 1)
        self._labeled_entry(frame, "Zona Waktu", self.schedule_timezone_var, 2)

        randomize_check = ttk.Checkbutton(frame, text="Acak urutan jam setiap hari", variable=self.schedule_randomize_var)
        randomize_check.grid(row=3, column=1, sticky="w", pady=(4, 0))

        frame.grid_columnconfigure(1, weight=1)

    def _build_selenium_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Pengaturan Browser (Opsional)")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text="Bagian ini dapat dibiarkan kosong bila Anda menggunakan pengaturan standar. Isi hanya jika perlu mengganti driver atau user agent.",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))

        self._labeled_entry(frame, "Path Driver", self.selenium_driver_var, 1)
        ttk.Button(frame, text="Pilih…", command=self._browse_driver_path).grid(row=1, column=2, padx=(8, 0))

        headless_check = ttk.Checkbutton(frame, text="Jalankan browser dalam mode headless", variable=self.selenium_headless_var)
        headless_check.grid(row=2, column=1, sticky="w", pady=(4, 0))

        self._labeled_entry(frame, "User Agent", self.selenium_user_agent_var, 3)
        self._labeled_entry(frame, "Folder Unduhan", self.selenium_download_dir_var, 4)
        ttk.Button(frame, text="Pilih…", command=self._browse_download_dir).grid(row=4, column=2, padx=(8, 0))

        frame.grid_columnconfigure(1, weight=1)

    def _build_cleanup_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Perawatan & Log (Opsional)")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text="Atur lokasi penyimpanan log serta kebijakan penghapusan file setelah upload selesai.",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))

        self._labeled_entry(frame, "Folder Log", self.cleanup_log_dir_var, 1)
        ttk.Button(frame, text="Pilih…", command=self._browse_log_dir).grid(row=1, column=2, padx=(8, 0))

        self._labeled_entry(frame, "Retensi Log (hari)", self.cleanup_retention_var, 2)

        remove_check = ttk.Checkbutton(
            frame,
            text="Hapus video dari komputer setelah berhasil diunggah",
            variable=self.cleanup_remove_uploaded_var,
        )
        remove_check.grid(row=3, column=1, sticky="w", pady=(4, 0))

        frame.grid_columnconfigure(1, weight=1)

    def _build_retry_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Pengaturan Retry (Opsional)")
        frame.pack(fill=tk.X, padx=4, pady=6)

        ttk.Label(
            frame,
            text="Sesuaikan jumlah percobaan ulang dan jeda antar percobaan jika upload gagal.",
            wraplength=760,
            justify=tk.LEFT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 4))

        self._labeled_entry(frame, "Maksimum Percobaan", self.max_retries_var, 1)
        self._labeled_entry(frame, "Jeda Antar Percobaan (detik)", self.retry_interval_var, 2)

        frame.grid_columnconfigure(1, weight=1)

    def _labeled_entry(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.Variable,
        row: int,
        column_offset: int = 0,
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=column_offset, sticky="w", padx=(12, 8), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=column_offset + 1, sticky="ew", pady=4)
        return entry

    # ------------------------------------------------------------------
    # Config handling helpers
    # ------------------------------------------------------------------
    def _set_default_form(self) -> None:
        default_mapping = {
            "title": "video_title",
            "description": "video_description",
            "hashtags": "video_hashtags",
            "tags": "video_tags",
            "filename": "video_filename",
            "drive_file_id": "drive_file_id",
            "drive_download_url": "drive_download_url",
            "drive_view_url": "drive_view_url",
            "created_time": "created_time",
            "final_output": "final_output",
            "status": "UploadYT",
            "youtube_url": "YTUrl",
            "altered_content": "altered_content",
            "made_for_kids": "made_for_kids",
        }

        self._loading_form = True
        self.accounts_data = []
        self._refresh_account_list()
        self.google_service_file_var.set("")
        self.google_spreadsheet_var.set("")
        self.google_worksheet_var.set("Sheet1")
        for key, value in default_mapping.items():
            self.sheet_mapping_vars[key].set(value)
        self.schedule_times_var.set("09:00, 15:00, 21:00")
        self.schedule_timezone_var.set("Asia/Jakarta")
        self.schedule_randomize_var.set(False)
        self.selenium_driver_var.set("")
        self.selenium_headless_var.set(False)
        self.selenium_user_agent_var.set("")
        self.selenium_download_dir_var.set("")
        self.cleanup_log_dir_var.set("logs")
        self.cleanup_retention_var.set("1")
        self.cleanup_remove_uploaded_var.set(True)
        self.max_retries_var.set("3")
        self.retry_interval_var.set("60")
        self._loading_form = False
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")

    def load_config_dialog(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Pilih file konfigurasi YTUploader",
            filetypes=[("Berkas YAML", "*.yaml *.yml"), ("Semua berkas", "*.*")],
        )
        if file_path:
            self._load_config(Path(file_path))

    def _load_config(self, path: Path) -> None:
        try:
            config = self.service.load_config(path)
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Memuat Config", str(exc))
            return

        self.config_path = Path(path)
        self.config_path_var.set(str(self.config_path))
        self.config_info_var.set(f"Config: {self.config_path}")

        self.accounts = list(config.accounts)
        self.accounts_data = [
            {
                "name": acc.name,
                "cookie_file": self._display_path(acc.cookie_file),
                "channel_url": acc.channel_url or "",
            }
            for acc in config.accounts
        ]

        self._loading_form = True
        self.google_service_file_var.set(self._display_path(config.google.service_account_file))
        self.google_spreadsheet_var.set(config.google.spreadsheet_id)
        self.google_worksheet_var.set(config.google.worksheet_name)

        for key, var in self.sheet_mapping_vars.items():
            value = getattr(config.sheet_mapping, key)
            var.set(value or "")

        self.schedule_times_var.set(", ".join(config.schedule.times))
        self.schedule_timezone_var.set(config.schedule.timezone)
        self.schedule_randomize_var.set(config.schedule.randomize)

        self.selenium_driver_var.set(self._display_optional_path(config.selenium.driver_path))
        self.selenium_headless_var.set(config.selenium.headless)
        self.selenium_user_agent_var.set(config.selenium.user_agent or "")
        self.selenium_download_dir_var.set(self._display_optional_path(config.selenium.download_directory))

        self.cleanup_log_dir_var.set(self._display_path(config.cleanup.log_directory))
        self.cleanup_retention_var.set(str(config.cleanup.retention_days))
        self.cleanup_remove_uploaded_var.set(config.cleanup.remove_uploaded_videos)

        self.max_retries_var.set(str(config.max_retries))
        self.retry_interval_var.set(str(config.retry_interval_seconds))
        self._loading_form = False

        self.unsaved_changes = False
        self.unsaved_info_var.set("")
        self.status_var.set("Konfigurasi berhasil dimuat. Simpan perubahan jika Anda mengedit pengaturan.")

        self._refresh_account_list()
        self._refresh_cookie_accounts()
        self.start_button.config(state=tk.NORMAL)

    def save_config(self) -> bool:
        if self.config_path is None:
            return self.save_config_as()
        return self._write_config(self.config_path)

    def save_config_as(self) -> bool:
        file_path = filedialog.asksaveasfilename(
            title="Simpan konfigurasi",
            defaultextension=".yaml",
            filetypes=[("Berkas YAML", "*.yaml *.yml"), ("Semua berkas", "*.*")],
        )
        if not file_path:
            return False
        return self._write_config(Path(file_path))

    def _write_config(self, path: Path) -> bool:
        try:
            data = self._collect_config_data()
        except ValueError as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Konfigurasi Tidak Valid", str(exc))
            return False

        try:
            with open(path, "w", encoding="utf-8") as fh:
                yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
        except OSError as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Menyimpan Config", f"Tidak dapat menulis file konfigurasi: {exc}")
            return False

        self.config_path = Path(path)
        self.config_path_var.set(str(self.config_path))
        self.config_info_var.set(f"Config: {self.config_path}")

        try:
            config = self.service.load_config(self.config_path)
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Config Tidak Dapat Dimuat", str(exc))
            return False

        self.accounts = list(config.accounts)
        self.unsaved_changes = False
        self.unsaved_info_var.set("")
        self.status_var.set(f"Konfigurasi tersimpan di {self.config_path}.")
        self.start_button.config(state=tk.NORMAL)
        self._refresh_cookie_accounts()
        return True

    def _collect_config_data(self) -> dict[str, Any]:
        accounts = []
        for account in self.accounts_data:
            name = account.get("name", "").strip()
            cookie_file = account.get("cookie_file", "").strip()
            if not name or not cookie_file:
                raise ValueError("Setiap akun harus memiliki nama dan path cookie.")
            entry: dict[str, Any] = {
                "name": name,
                "cookie_file": cookie_file,
            }
            channel_url = account.get("channel_url", "").strip()
            if channel_url:
                entry["channel_url"] = channel_url
            accounts.append(entry)
        if not accounts:
            raise ValueError("Tambahkan minimal satu akun YouTube sebelum menyimpan konfigurasi.")

        service_account = self.google_service_file_var.get().strip()
        spreadsheet_id = self.google_spreadsheet_var.get().strip()
        worksheet = self.google_worksheet_var.get().strip()
        if not service_account or not spreadsheet_id or not worksheet:
            raise ValueError("Isi credential Google dan informasi Spreadsheet dengan lengkap.")

        mapping = {key: var.get().strip() for key, var in self.sheet_mapping_vars.items() if var.get().strip()}
        required_mapping = ("title", "description", "filename", "status", "youtube_url")
        for key in required_mapping:
            if key not in mapping:
                raise ValueError("Lengkapi pemetaan kolom utama pada bagian Google Sheet.")

        times_raw = [item.strip() for item in self.schedule_times_var.get().split(",") if item.strip()]
        if not times_raw:
            raise ValueError("Masukkan minimal satu jam penjadwalan.")

        try:
            retention = int(self.cleanup_retention_var.get().strip())
            max_retries = int(self.max_retries_var.get().strip())
            retry_interval = int(self.retry_interval_var.get().strip())
        except ValueError as exc:
            raise ValueError("Nilai numerik (retensi, retry, interval) harus berupa angka.") from exc

        selenium_data: dict[str, Any] = {
            "headless": bool(self.selenium_headless_var.get()),
        }
        if driver := self.selenium_driver_var.get().strip():
            selenium_data["driver_path"] = driver
        if user_agent := self.selenium_user_agent_var.get().strip():
            selenium_data["user_agent"] = user_agent
        if download_dir := self.selenium_download_dir_var.get().strip():
            selenium_data["download_directory"] = download_dir

        cleanup_data: dict[str, Any] = {
            "log_directory": self.cleanup_log_dir_var.get().strip() or "logs",
            "retention_days": retention,
            "remove_uploaded_videos": bool(self.cleanup_remove_uploaded_var.get()),
        }

        data: dict[str, Any] = {
            "accounts": accounts,
            "google": {
                "service_account_file": service_account,
                "spreadsheet_id": spreadsheet_id,
                "worksheet_name": worksheet,
            },
            "sheet_mapping": mapping,
            "schedule": {
                "times": times_raw,
                "randomize": bool(self.schedule_randomize_var.get()),
                "timezone": self.schedule_timezone_var.get().strip() or "UTC",
            },
            "selenium": selenium_data,
            "cleanup": cleanup_data,
            "max_retries": max_retries,
            "retry_interval_seconds": retry_interval,
        }
        return data

    def _display_path(self, path: Path) -> str:
        if self.config_path:
            try:
                return str(path.relative_to(self.config_path.parent))
            except ValueError:
                return str(path)
        return str(path)

    def _display_optional_path(self, path: Path | None) -> str:
        if not path:
            return ""
        return self._display_path(path)

    def _resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            base = self.config_path.parent if self.config_path else Path.cwd()
            path = (base / path).resolve()
        return path

    def _generate_cookie_path(self, account_name: str) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", account_name.strip()) or uuid.uuid4().hex
        base = self.config_path.parent if self.config_path else Path.cwd()
        return (base / "cookies" / f"{safe_name}.json").resolve()

    def _create_new_config(self) -> None:
        if self.unsaved_changes and not messagebox.askyesno(
            "Konfirmasi", "Perubahan yang belum disimpan akan hilang. Lanjutkan?"
        ):
            return
        self.config_path = None
        self.config_path_var.set("")
        self.config_info_var.set("Belum ada file konfigurasi dipilih.")
        self.accounts = []
        self._set_default_form()
        self._refresh_cookie_accounts()
        self.start_button.config(state=tk.DISABLED)
        self.status_var.set("Konfigurasi baru siap diedit. Simpan untuk mulai menggunakan.")

    def _refresh_account_list(self) -> None:
        previous_index = self._current_account_index
        self.account_listbox.delete(0, tk.END)
        for account in self.accounts_data:
            self.account_listbox.insert(tk.END, account.get("name", "(akun baru)"))
        if not self.accounts_data:
            self._clear_account_form()
            return

        if previous_index is None or previous_index >= len(self.accounts_data):
            previous_index = len(self.accounts_data) - 1
        self.account_listbox.selection_set(previous_index)
        self.account_listbox.activate(previous_index)
        self.account_listbox.see(previous_index)
        self._on_account_select()

    def _clear_account_form(self) -> None:
        self._current_account_index = None
        self.account_name_var.set("")
        self.account_cookie_var.set("")
        self.account_channel_var.set("")
        self._update_cookie_editor_state()

    def _get_current_account_data(self) -> dict[str, Any] | None:
        if self._current_account_index is None:
            return None
        if 0 <= self._current_account_index < len(self.accounts_data):
            return self.accounts_data[self._current_account_index]
        return None

    def _update_cookie_editor_state(self) -> None:
        if not hasattr(self, "cookie_text"):
            return

        account = self._get_current_account_data()
        if account is None:
            self.cookie_text.config(state=tk.NORMAL)
            self.cookie_text.delete("1.0", tk.END)
            self.cookie_text.insert(tk.END, "Pilih atau buat akun terlebih dahulu untuk mengelola cookie.")
            self.cookie_text.config(state=tk.DISABLED)
            for button in (
                self.load_cookie_button,
                self.save_cookie_button,
                self.paste_cookie_button,
                self.clear_cookie_button,
            ):
                button.config(state=tk.DISABLED)
            return

        path_str = account.get("cookie_file", "").strip()
        self.account_cookie_var.set(path_str)

        for button in (
            self.load_cookie_button,
            self.save_cookie_button,
            self.paste_cookie_button,
            self.clear_cookie_button,
        ):
            button.config(state=tk.NORMAL)

        self.cookie_text.config(state=tk.NORMAL)
        self.cookie_text.delete("1.0", tk.END)

        if path_str:
            cookie_path = self._resolve_path(path_str)
            display_path = self._display_path(cookie_path)
            if cookie_path.exists():
                try:
                    with open(cookie_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except json.JSONDecodeError as exc:  # pragma: no cover - UI feedback
                    messagebox.showwarning(
                        "Cookie Tidak Valid",
                        f"File cookie '{display_path}' tidak berisi JSON yang valid: {exc}",
                    )
                    self.status_var.set(
                        f"File cookie '{display_path}' tidak valid. Tempel atau muat ulang data cookie."
                    )
                except OSError as exc:  # pragma: no cover - UI feedback
                    messagebox.showwarning(
                        "Cookie Tidak Dapat Dibuka",
                        f"File cookie '{display_path}' tidak dapat dibaca: {exc}",
                    )
                    self.status_var.set(
                        f"File cookie '{display_path}' tidak dapat dibuka. Tempel atau muat ulang data cookie."
                    )
                else:
                    formatted = json.dumps(data, ensure_ascii=False, indent=2)
                    self.cookie_text.insert(tk.END, formatted)
                    self.cookie_text.focus_set()
                    self.status_var.set(
                        f"Cookie untuk akun '{account.get('name', '') or 'tanpa nama'}' dimuat dari {display_path}."
                    )
                    return

        self.cookie_text.insert(
            tk.END,
            "Tempel JSON cookie baru kemudian klik Simpan Cookie untuk membuat file secara otomatis.",
        )
        self.cookie_text.focus_set()
        if path_str:
            self.status_var.set(
                f"File cookie '{path_str}' belum ditemukan. Tempel cookie baru dan simpan untuk membuatnya."
            )
        else:
            self.status_var.set("Belum ada file cookie. Tempel cookie lalu simpan untuk membuat file secara otomatis.")

    def _ensure_account_selected(self) -> dict[str, Any] | None:
        account = self._get_current_account_data()
        if account is None:
            messagebox.showinfo("Pilih Akun", "Pilih atau buat akun terlebih dahulu sebelum mengelola cookie.")
            return None
        return account

    def _on_account_select(self, event: Any | None = None) -> None:
        selection = self.account_listbox.curselection()
        if not selection:
            self._clear_account_form()
            return
        index = selection[0]
        self._current_account_index = index
        data = self.accounts_data[index]
        self._loading_form = True
        self.account_name_var.set(data.get("name", ""))
        self.account_cookie_var.set(data.get("cookie_file", ""))
        self.account_channel_var.set(data.get("channel_url", ""))
        self._loading_form = False
        self._update_cookie_editor_state()

    def _add_account(self) -> None:
        self.accounts_data.append({"name": "", "cookie_file": "", "channel_url": ""})
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")
        self._current_account_index = len(self.accounts_data) - 1
        self._refresh_account_list()
        self._update_cookie_editor_state()

    def _remove_account(self) -> None:
        selection = self.account_listbox.curselection()
        if not selection:
            messagebox.showinfo("Pilih Akun", "Pilih akun yang ingin dihapus dari daftar.")
            return
        index = selection[0]
        del self.accounts_data[index]
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")
        if self.accounts_data:
            self._current_account_index = min(index, len(self.accounts_data) - 1)
        else:
            self._current_account_index = None
        self._refresh_account_list()
        self._update_cookie_editor_state()

    def _apply_account_changes(self) -> None:
        if self._current_account_index is None:
            messagebox.showinfo("Pilih Akun", "Pilih akun yang ingin diperbarui dari daftar.")
            return
        name = self.account_name_var.get().strip()
        cookie = self.account_cookie_var.get().strip()
        if not name or not cookie:
            messagebox.showerror("Data Tidak Lengkap", "Nama akun dan file cookie wajib diisi.")
            return
        self.accounts_data[self._current_account_index] = {
            "name": name,
            "cookie_file": cookie,
            "channel_url": self.account_channel_var.get().strip(),
        }
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")
        self._refresh_account_list()
        self._update_cookie_editor_state()

    def _browse_cookie_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Pilih file cookie JSON",
            filetypes=[("File JSON", "*.json"), ("Semua berkas", "*.*")],
        )
        if file_path:
            self.account_cookie_var.set(file_path)
            if self._current_account_index is not None:
                self.accounts_data[self._current_account_index]["cookie_file"] = file_path
            self._update_cookie_editor_state()

    def _browse_service_account(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Pilih credential Service Account",
            filetypes=[("File JSON", "*.json"), ("Semua berkas", "*.*")],
        )
        if file_path:
            self.google_service_file_var.set(file_path)

    def _browse_driver_path(self) -> None:
        file_path = filedialog.askopenfilename(title="Pilih executable driver browser")
        if file_path:
            self.selenium_driver_var.set(file_path)

    def _browse_download_dir(self) -> None:
        directory = filedialog.askdirectory(title="Pilih folder unduhan")
        if directory:
            self.selenium_download_dir_var.set(directory)

    def _browse_log_dir(self) -> None:
        directory = filedialog.askdirectory(title="Pilih folder log")
        if directory:
            self.cleanup_log_dir_var.set(directory)

    def _refresh_cookie_accounts(self) -> None:
        self._update_cookie_editor_state()

    def paste_cookie_from_clipboard(self) -> None:
        if not self._ensure_account_selected():
            return
        try:
            clipboard_data = self.root.clipboard_get()
        except tk.TclError:  # pragma: no cover - UI feedback
            messagebox.showwarning("Clipboard Kosong", "Tidak ada data yang dapat ditempel dari clipboard.")
            return

        text = clipboard_data.strip()
        self.cookie_text.config(state=tk.NORMAL)
        self.cookie_text.delete("1.0", tk.END)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            self.cookie_text.insert(tk.END, text)
            messagebox.showwarning(
                "Format Clipboard Tidak Valid",
                "Data clipboard bukan JSON yang valid. Data tetap ditempel, periksa kembali sebelum menyimpan.",
            )
        else:
            formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
            self.cookie_text.insert(tk.END, formatted)

        self.cookie_text.focus_set()
        self.status_var.set(
            "Data cookie ditempel dari clipboard. Simpan untuk menyimpannya ke file akun."
        )
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")

    def clear_cookie_editor(self) -> None:
        if not self._ensure_account_selected():
            return
        self.cookie_text.config(state=tk.NORMAL)
        self.cookie_text.delete("1.0", tk.END)
        self.cookie_text.focus_set()
        self.status_var.set("Editor cookie dikosongkan. Tempel atau muat cookie baru sebelum menyimpan.")
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")

    # ------------------------------------------------------------------
    # Cookie management
    # ------------------------------------------------------------------
    def load_cookie_file(self) -> None:
        if not self._ensure_account_selected():
            return
        file_path = filedialog.askopenfilename(
            title="Pilih file cookie JSON",
            filetypes=[("File JSON", "*.json"), ("Semua berkas", "*.*")],
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Memuat Cookie", f"Tidak dapat membaca file cookie: {exc}")
            return
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        self.cookie_text.config(state=tk.NORMAL)
        self.cookie_text.delete("1.0", tk.END)
        self.cookie_text.insert(tk.END, formatted)
        self.cookie_text.config(state=tk.NORMAL)
        self.status_var.set(f"Cookie dari {file_path} siap disimpan ke akun terpilih.")
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")

    def save_cookie_data(self) -> None:
        account = self._ensure_account_selected()
        if account is None:
            return
        raw_data = self.cookie_text.get("1.0", tk.END).strip()
        if not raw_data:
            messagebox.showwarning("Cookie Kosong", "Tempel JSON cookie atau muat dari file terlebih dahulu.")
            return
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Cookie Tidak Valid", f"Data cookie bukan JSON yang valid: {exc}")
            return

        path_str = account.get("cookie_file", "").strip()
        account_name = (account.get("name") or self.account_name_var.get() or "akun").strip()
        if not path_str:
            cookie_path = self._generate_cookie_path(account_name or "akun")
        else:
            cookie_path = self._resolve_path(path_str)

        try:
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cookie_path, "w", encoding="utf-8") as fh:
                json.dump(parsed, fh, ensure_ascii=False, indent=2)
        except OSError as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Menyimpan Cookie", f"Tidak dapat menulis file cookie: {exc}")
            return

        formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
        self.cookie_text.config(state=tk.NORMAL)
        self.cookie_text.delete("1.0", tk.END)
        self.cookie_text.insert(tk.END, formatted)
        self.cookie_text.config(state=tk.NORMAL)

        display_path = self._display_path(cookie_path)
        account["cookie_file"] = display_path
        if self._current_account_index is not None:
            self.accounts_data[self._current_account_index]["cookie_file"] = display_path
        self.account_cookie_var.set(display_path)

        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")
        self.status_var.set(
            f"Cookie untuk akun '{account.get('name', '') or account_name}' berhasil disimpan ke {display_path}."
        )

    # ------------------------------------------------------------------
    # Testing utilities
    # ------------------------------------------------------------------
    def test_google_sheets(self) -> None:
        try:
            config = self._build_config_object()
        except ValueError as exc:
            self.sheet_status_var.set(f"Konfigurasi tidak valid: {exc}")
            return
        try:
            client = GoogleSheetClient(config)
            worksheet_title = client.worksheet.title
        except Exception as exc:  # pragma: no cover - UI feedback
            self.sheet_status_var.set(f"Gagal terhubung ke Google Sheets: {exc}")
            return
        self.sheet_status_var.set(
            f"Berhasil terhubung ke spreadsheet '{worksheet_title}'. Data siap digunakan."
        )

    def test_google_drive(self) -> None:
        file_id = self.drive_file_id_var.get().strip()
        url = self.drive_url_var.get().strip()
        if not file_id and not url:
            self.drive_status_var.set("Masukkan File ID atau URL untuk melakukan pengujian.")
            return
        downloader = GoogleDriveDownloader()
        temp_path = Path(tempfile.gettempdir()) / f"ytuploader-test-{uuid.uuid4().hex}.tmp"
        try:
            downloader.download(file_id=file_id or None, download_url=url or None, destination=temp_path)
        except Exception as exc:  # pragma: no cover - UI feedback
            self.drive_status_var.set(f"Gagal mengakses file Google Drive: {exc}")
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return
        temp_path.unlink(missing_ok=True)
        self.drive_status_var.set("File dapat diunduh dari Google Drive. Koneksi berhasil.")

    def _build_config_object(self) -> AppConfig:
        data = self._collect_config_data()
        base_path = self.config_path.parent if self.config_path else Path.cwd()
        return AppConfig.from_dict(data, base_path=base_path)

    # ------------------------------------------------------------------
    # Service controls
    # ------------------------------------------------------------------
    def start_service(self) -> None:
        with self._lock:
            if self.service.is_running:
                return
            if self.unsaved_changes:
                if not messagebox.askyesno(
                    "Konfigurasi Belum Disimpan",
                    "Terdapat perubahan yang belum disimpan. Simpan sekarang?",
                ):
                    messagebox.showinfo("Informasi", "Simpan konfigurasi sebelum menjalankan uploader.")
                    return
                if not self.save_config():
                    return
            if not self.service.config_path:
                if not self.save_config():
                    return
            try:
                self.service.start()
            except Exception as exc:  # pragma: no cover - UI feedback
                messagebox.showerror("Gagal Menjalankan", str(exc))
                return
            self.status_var.set(
                "Uploader berjalan di latar belakang. Jadwal akan dipantau sesuai konfigurasi."
            )
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

    def stop_service(self) -> None:
        with self._lock:
            if not self.service.is_running:
                return
            self.service.stop()
            self.status_var.set("Uploader dihentikan. Anda dapat menjalankannya kembali kapan saja.")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Utility callbacks
    # ------------------------------------------------------------------
    def _mark_dirty(self, *_: Any) -> None:
        if self._loading_form:
            return
        self.unsaved_changes = True
        self.unsaved_info_var.set("Perubahan konfigurasi belum disimpan.")


def main() -> None:
    root = tk.Tk()
    UploaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
