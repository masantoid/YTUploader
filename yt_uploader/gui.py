"""Graphical interface for the YTUploader application."""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from .service import UploaderService


class UploaderGUI:
    """Tkinter based desktop interface for YTUploader."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YTUploader")
        self.root.geometry("520x320")
        self.root.resizable(False, False)

        self.service = UploaderService()
        self._lock = threading.Lock()

        self.status_var = tk.StringVar(value="Silakan pilih file konfigurasi YAML sebelum mulai.")
        self.config_var = tk.StringVar(value="Belum ada file konfigurasi dipilih.")

        self._build_widgets()

    def _build_widgets(self) -> None:
        padding = {"padx": 16, "pady": 8}

        title = tk.Label(self.root, text="YTUploader", font=("Segoe UI", 18, "bold"))
        title.pack(**padding)

        desc = tk.Label(
            self.root,
            text=(
                "Aplikasi otomatis untuk mengunggah video ke YouTube berdasarkan data Google Sheets.\n"
                "Gunakan tombol di bawah ini untuk menyiapkan konfigurasi dan menjalankan uploader."
            ),
            justify=tk.CENTER,
            wraplength=460,
        )
        desc.pack(**padding)

        config_frame = tk.Frame(self.root)
        config_frame.pack(fill=tk.X, padx=16, pady=4)

        config_label = tk.Label(config_frame, textvariable=self.config_var, anchor="w", justify=tk.LEFT)
        config_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        choose_button = tk.Button(config_frame, text="Pilih Config", command=self.choose_config)
        choose_button.pack(side=tk.RIGHT)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=12)

        self.start_button = tk.Button(button_frame, text="Mulai", command=self.start_service, state=tk.DISABLED)
        self.start_button.pack(side=tk.LEFT, padx=6)

        self.stop_button = tk.Button(button_frame, text="Berhenti", command=self.stop_service, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=6)

        status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            wraplength=460,
            justify=tk.LEFT,
            relief=tk.GROOVE,
            anchor="w",
            padx=10,
            pady=10,
        )
        status_label.pack(fill=tk.X, padx=16, pady=8)

        info = tk.Label(
            self.root,
            text=(
                "Log aplikasi akan tersimpan pada folder log yang ditentukan di file konfigurasi.\n"
                "Pastikan komputer tetap menyala agar unggahan terjadwal berjalan sesuai rencana."
            ),
            justify=tk.LEFT,
            wraplength=460,
        )
        info.pack(**padding)

    def choose_config(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Pilih file konfigurasi YTUploader",
            filetypes=[("Berkas YAML", "*.yaml *.yml"), ("Semua berkas", "*.*")],
        )
        if not file_path:
            return
        try:
            self.service.load_config(Path(file_path))
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Memuat Config", str(exc))
            return
        self.config_var.set(f"Config: {file_path}")
        self.status_var.set("Konfigurasi berhasil dimuat. Tekan Mulai untuk menjalankan uploader.")
        self.start_button.config(state=tk.NORMAL)

    def start_service(self) -> None:
        with self._lock:
            if self.service.is_running:
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


def main() -> None:
    root = tk.Tk()
    UploaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

