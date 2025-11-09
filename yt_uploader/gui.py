"""Graphical interface for the YTUploader application."""
from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

from .config import AccountConfig
from .service import UploaderService


class UploaderGUI:
    """Tkinter based desktop interface for YTUploader."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YTUploader")
        self.root.geometry("560x620")
        self.root.resizable(False, False)

        self.service = UploaderService()
        self._lock = threading.Lock()

        self.status_var = tk.StringVar(value="Silakan pilih file konfigurasi YAML sebelum mulai.")
        self.config_var = tk.StringVar(value="Belum ada file konfigurasi dipilih.")
        self.account_var = tk.StringVar(value="Muat konfigurasi untuk melihat akun.")
        self.accounts: list[AccountConfig] = []

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

        cookie_frame = tk.LabelFrame(self.root, text="Manajemen Cookie Google/YouTube")
        cookie_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        cookie_desc = tk.Label(
            cookie_frame,
            text=(
                "Tempelkan JSON cookie dari browser atau muat dari file, lalu simpan ke akun yang dipilih.\n"
                "Cookie dapat diekspor menggunakan ekstensi seperti Cookie-Editor di Google Chrome."
            ),
            justify=tk.LEFT,
            wraplength=500,
        )
        cookie_desc.pack(anchor="w", pady=(8, 4))

        instruction_text = (
            "Cara mendapatkan cookie:\n"
            "1. Buka Chrome dan masuk ke https://studio.youtube.com.\n"
            "2. Klik ikon ekstensi Cookie-Editor → tab Export → Copy untuk menyalin JSON.\n"
            "3. Tempel JSON tersebut ke kotak di bawah atau simpan sebagai file .json untuk dimuat."
        )
        cookie_instr = tk.Label(cookie_frame, text=instruction_text, justify=tk.LEFT, wraplength=500)
        cookie_instr.pack(anchor="w", pady=(0, 8))

        account_row = tk.Frame(cookie_frame)
        account_row.pack(fill=tk.X, pady=(0, 6))

        account_label = tk.Label(account_row, text="Akun YouTube:")
        account_label.pack(side=tk.LEFT)

        self.account_menu = tk.OptionMenu(account_row, self.account_var, self.account_var.get())
        self.account_menu.config(width=35)
        self.account_menu.pack(side=tk.LEFT, padx=(8, 0))

        text_frame = tk.Frame(cookie_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.cookie_text = scrolledtext.ScrolledText(text_frame, height=10, wrap=tk.WORD)
        self.cookie_text.pack(fill=tk.BOTH, expand=True)
        self.cookie_text.config(state=tk.DISABLED)

        cookie_button_frame = tk.Frame(cookie_frame)
        cookie_button_frame.pack(pady=8)

        self.load_cookie_button = tk.Button(
            cookie_button_frame,
            text="Muat File Cookie",
            command=self.load_cookie_file,
            state=tk.DISABLED,
        )
        self.load_cookie_button.pack(side=tk.LEFT, padx=6)

        self.save_cookie_button = tk.Button(
            cookie_button_frame,
            text="Simpan Cookie",
            command=self.save_cookie_data,
            state=tk.DISABLED,
        )
        self.save_cookie_button.pack(side=tk.LEFT, padx=6)

        self._refresh_account_options()

    def choose_config(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Pilih file konfigurasi YTUploader",
            filetypes=[("Berkas YAML", "*.yaml *.yml"), ("Semua berkas", "*.*")],
        )
        if not file_path:
            return
        try:
            config = self.service.load_config(Path(file_path))
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Memuat Config", str(exc))
            return
        self.config_var.set(f"Config: {file_path}")
        self.status_var.set("Konfigurasi berhasil dimuat. Tekan Mulai untuk menjalankan uploader.")
        self.accounts = list(config.accounts)
        self._refresh_account_options()
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

    def _refresh_account_options(self) -> None:
        menu = self.account_menu["menu"]
        menu.delete(0, "end")
        if not self.accounts:
            self.cookie_text.config(state=tk.NORMAL)
            self.account_var.set("Tidak ada akun pada konfigurasi.")
            self.load_cookie_button.config(state=tk.DISABLED)
            self.save_cookie_button.config(state=tk.DISABLED)
            self.cookie_text.delete("1.0", tk.END)
            self.cookie_text.insert(
                tk.END,
                "Muat file konfigurasi dengan daftar akun untuk mengelola cookie di sini.",
            )
            self.cookie_text.config(state=tk.DISABLED)
            return

        self.cookie_text.config(state=tk.NORMAL)
        self.cookie_text.delete("1.0", tk.END)
        self.account_var.set(self.accounts[0].name)
        for account in self.accounts:
            menu.add_command(label=account.name, command=lambda value=account.name: self.account_var.set(value))
        self.load_cookie_button.config(state=tk.NORMAL)
        self.save_cookie_button.config(state=tk.NORMAL)

    def load_cookie_file(self) -> None:
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
        self.cookie_text.delete("1.0", tk.END)
        self.cookie_text.insert(tk.END, formatted)
        self.status_var.set(f"Cookie dari {file_path} siap disimpan ke akun terpilih.")

    def save_cookie_data(self) -> None:
        if not self.accounts:
            messagebox.showwarning("Belum Ada Akun", "Muat konfigurasi yang berisi daftar akun terlebih dahulu.")
            return
        account_name = self.account_var.get()
        account = next((acc for acc in self.accounts if acc.name == account_name), None)
        if account is None:
            messagebox.showerror("Akun Tidak Ditemukan", "Pilih akun yang valid sebelum menyimpan cookie.")
            return
        raw_data = self.cookie_text.get("1.0", tk.END).strip()
        if not raw_data:
            messagebox.showwarning("Cookie Kosong", "Tempel JSON cookie atau muat dari file terlebih dahulu.")
            return
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Format Cookie Tidak Valid", f"Cookie harus berupa JSON yang valid: {exc}")
            return
        cookie_path = Path(account.cookie_file)
        try:
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cookie_path, "w", encoding="utf-8") as fh:
                json.dump(parsed, fh, ensure_ascii=False, indent=2)
        except Exception as exc:  # pragma: no cover - UI feedback
            messagebox.showerror("Gagal Menyimpan Cookie", f"Tidak dapat menulis file cookie: {exc}")
            return
        messagebox.showinfo(
            "Cookie Tersimpan",
            f"Cookie untuk akun '{account.name}' berhasil disimpan ke {cookie_path}.",
        )
        self.status_var.set(
            f"Cookie untuk akun '{account.name}' tersimpan. Anda dapat langsung menjalankan uploader."
        )


def main() -> None:
    root = tk.Tk()
    UploaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

