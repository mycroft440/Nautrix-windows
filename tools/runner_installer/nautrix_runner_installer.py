from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

APP_TITLE = "Nautrix Build Runner"
REPOSITORY = "mycroft440/Nautrix-windows"
ACTIONS_URL = f"https://github.com/{REPOSITORY}/actions/workflows/full-chromium-build.yml"
RUNNERS_URL = f"https://github.com/{REPOSITORY}/settings/actions/runners"


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative


def embedded_setup_script() -> Path:
    packaged = resource_path("tools/setup_nautrix_runner.ps1")
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[1] / "setup_nautrix_runner.ps1"


def powershell_path() -> str:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidate = Path(windir) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(candidate if candidate.exists() else "powershell.exe")


def is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate_self() -> bool:
    if is_admin():
        return True
    if "--elevated" in sys.argv:
        return False

    extra = [arg for arg in sys.argv[1:] if arg != "--elevated"] + ["--elevated"]
    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = subprocess.list2cmdline(extra)
    else:
        executable = sys.executable
        params = subprocess.list2cmdline([str(Path(__file__).resolve()), *extra])

    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    if result <= 32:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Não foi possível solicitar privilégios de administrador.",
            APP_TITLE,
            0x10,
        )
    return False


def run_self_test() -> int:
    script = embedded_setup_script()
    if not script.exists():
        print(f"embedded setup script missing: {script}", file=sys.stderr)
        return 2
    text = script.read_text(encoding="utf-8-sig")
    required = [
        "mycroft440/Nautrix-windows",
        "nautrix-chromium",
        "registration-token",
        "config.cmd",
        "svc.cmd",
        "Microsoft.VisualStudio.2022.BuildTools",
        "Wait-RunnerOnline",
        "LongPathsEnabled",
    ]
    missing = [token for token in required if token not in text]
    if missing:
        print("setup script missing markers: " + ", ".join(missing), file=sys.stderr)
        return 3
    escaped = str(script).replace("'", "''")
    command = [
        powershell_path(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"$null=[scriptblock]::Create((Get-Content -Raw -LiteralPath '{escaped}')); exit 0",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        print(completed.stdout, file=sys.stderr)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    print("NautrixRunnerInstaller self-test passed")
    return 0


class InstallerApp:
    BG = "#0b0f14"
    PANEL = "#111821"
    PANEL_2 = "#161f2a"
    TEXT = "#eef4fb"
    MUTED = "#8fa2b7"
    ACCENT = "#65d6f2"
    SUCCESS = "#70db9a"
    ERROR = "#ff7b86"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.running = False

        root.title(APP_TITLE)
        root.geometry("820x610")
        root.minsize(760, 560)
        root.configure(bg=self.BG)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Nautrix.Horizontal.TProgressbar",
            troughcolor=self.PANEL_2,
            background=self.ACCENT,
            bordercolor=self.PANEL_2,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
            thickness=12,
        )
        self._build_ui()
        self.root.after(100, self._drain_events)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=self.BG)
        header.pack(fill="x", padx=34, pady=(30, 16))
        tk.Label(
            header,
            text="N",
            font=("Segoe UI Semibold", 22),
            fg=self.BG,
            bg=self.ACCENT,
            width=2,
            height=1,
        ).pack(side="left", padx=(0, 16))
        titles = tk.Frame(header, bg=self.BG)
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(
            titles,
            text="Nautrix Build Runner",
            font=("Segoe UI Semibold", 22),
            fg=self.TEXT,
            bg=self.BG,
        ).pack(anchor="w")
        tk.Label(
            titles,
            text="Configura este Windows para compilar o Nautrix exclusivamente pelo GitHub Actions.",
            font=("Segoe UI", 10),
            fg=self.MUTED,
            bg=self.BG,
        ).pack(anchor="w", pady=(4, 0))

        card = tk.Frame(self.root, bg=self.PANEL, highlightthickness=1, highlightbackground="#223040")
        card.pack(fill="x", padx=34, pady=(0, 14))
        tk.Label(
            card,
            text=(
                "O instalador verifica espaço em disco, Git, GitHub CLI, suporte a caminhos longos e "
                "Visual Studio C++ Build Tools; depois registra este computador como runner "
                "‘nautrix-chromium’, inicia o serviço e confirma que ele ficou online no GitHub."
            ),
            wraplength=730,
            justify="left",
            font=("Segoe UI", 10),
            fg=self.TEXT,
            bg=self.PANEL,
        ).pack(anchor="w", padx=20, pady=(18, 8))
        tk.Label(
            card,
            text=(
                "Pode ser necessário autorizar o GitHub no navegador. O instalador usa um token de registro "
                "temporário e não salva esse token no aplicativo."
            ),
            wraplength=730,
            justify="left",
            font=("Segoe UI", 9),
            fg=self.MUTED,
            bg=self.PANEL,
        ).pack(anchor="w", padx=20, pady=(0, 18))

        status_card = tk.Frame(self.root, bg=self.PANEL, highlightthickness=1, highlightbackground="#223040")
        status_card.pack(fill="x", padx=34, pady=(0, 14))
        self.status = tk.Label(
            status_card,
            text="Pronto para configurar",
            font=("Segoe UI Semibold", 11),
            fg=self.TEXT,
            bg=self.PANEL,
        )
        self.status.pack(anchor="w", padx=20, pady=(15, 8))
        self.progress = ttk.Progressbar(
            status_card,
            style="Nautrix.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate",
            maximum=100,
            value=0,
        )
        self.progress.pack(fill="x", padx=20, pady=(0, 16))

        log_card = tk.Frame(self.root, bg=self.PANEL, highlightthickness=1, highlightbackground="#223040")
        log_card.pack(fill="both", expand=True, padx=34, pady=(0, 14))
        tk.Label(
            log_card,
            text="Detalhes da instalação",
            font=("Segoe UI Semibold", 10),
            fg=self.TEXT,
            bg=self.PANEL,
        ).pack(anchor="w", padx=16, pady=(12, 6))
        self.log = tk.Text(
            log_card,
            height=12,
            bg="#0d131b",
            fg="#cbd7e4",
            insertbackground=self.TEXT,
            relief="flat",
            font=("Cascadia Mono", 9),
            padx=12,
            pady=10,
            wrap="word",
            state="disabled",
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        buttons = tk.Frame(self.root, bg=self.BG)
        buttons.pack(fill="x", padx=34, pady=(0, 28))
        self.install_button = self._button(buttons, "Instalar e ativar runner", self.start_install, self.ACCENT, self.BG)
        self.install_button.pack(side="left")
        self.actions_button = self._button(
            buttons, "Abrir Full Chromium Build", lambda: webbrowser.open(ACTIONS_URL), self.PANEL_2, self.TEXT
        )
        self.actions_button.pack(side="left", padx=(10, 0))
        self.runners_button = self._button(buttons, "Ver runners", lambda: webbrowser.open(RUNNERS_URL), self.PANEL_2, self.TEXT)
        self.runners_button.pack(side="left", padx=(10, 0))
        self.close_button = self._button(buttons, "Fechar", self.on_close, self.PANEL_2, self.TEXT)
        self.close_button.pack(side="right")

    def _button(self, parent: tk.Widget, text: str, command, bg: str, fg: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=("Segoe UI Semibold", 9),
            cursor="hand2",
        )

    def _append_log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, text: str, progress: int | None = None, color: str | None = None) -> None:
        self.status.configure(text=text, fg=color or self.TEXT)
        if progress is not None:
            self.progress.configure(value=max(0, min(100, progress)))

    @staticmethod
    def _progress_for_line(line: str) -> tuple[str, int] | None:
        lowered = line.lower()
        phases = [
            ("runner drive", "Verificando espaço e selecionando disco", 8),
            ("long-path support", "Ativando suporte a caminhos longos", 14),
            ("git:", "Preparando Git", 20),
            ("github cli:", "Preparando GitHub CLI", 28),
            ("visual studio", "Preparando Visual Studio C++ Build Tools", 42),
            ("checking github authentication", "Verificando autenticação do GitHub", 54),
            ("requesting a short-lived", "Solicitando credencial temporária do runner", 62),
            ("resolving the latest", "Baixando GitHub Actions Runner", 70),
            ("extracting github actions runner", "Instalando GitHub Actions Runner", 78),
            ("registering runner", "Registrando runner nautrix-chromium", 86),
            ("starting the github actions runner", "Iniciando serviço do runner", 92),
            ("waiting for runner", "Confirmando conexão com GitHub", 96),
            ("runner is online", "Runner conectado ao GitHub", 99),
            ("runner is installed and running", "Configuração concluída", 100),
        ]
        for marker, title, value in phases:
            if marker in lowered:
                return title, value
        return None

    def start_install(self) -> None:
        if self.running:
            return
        script = embedded_setup_script()
        if not script.exists():
            messagebox.showerror(APP_TITLE, f"O componente de instalação não foi encontrado:\n{script}")
            return
        self.running = True
        self.install_button.configure(state="disabled")
        self.close_button.configure(state="disabled")
        self._set_status("Iniciando configuração...", 2)
        self._append_log(f"Componente: {script}")
        self.worker = threading.Thread(target=self._install_worker, args=(script,), daemon=True)
        self.worker.start()

    def _install_worker(self, script: Path) -> None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command = [powershell_path(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
            assert process.stdout is not None
            for raw in process.stdout:
                line = raw.rstrip("\r\n")
                self.events.put(("log", line))
                phase = self._progress_for_line(line)
                if phase:
                    self.events.put(("phase", phase))
            self.events.put(("done", process.wait()))
        except Exception as exc:
            self.events.put(("fatal", str(exc)))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "phase":
                    title, value = payload
                    self._set_status(str(title), int(value))
                elif kind == "done":
                    self._finish(int(payload))
                elif kind == "fatal":
                    self._fail(str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _finish(self, exit_code: int) -> None:
        self.running = False
        self.close_button.configure(state="normal")
        if exit_code == 0:
            self._set_status("Runner instalado e conectado. O build pode começar.", 100, self.SUCCESS)
            self._append_log("[Nautrix] Instalação finalizada com sucesso.")
            messagebox.showinfo(
                APP_TITLE,
                "O runner nautrix-chromium foi instalado, iniciado e confirmado como online.\n\n"
                "O Full Chromium Build mais recente deve ser assumido automaticamente pelo GitHub Actions.",
            )
        else:
            self.install_button.configure(state="normal")
            self._set_status(f"Falha na configuração (código {exit_code})", int(self.progress["value"]), self.ERROR)
            messagebox.showerror(APP_TITLE, "A configuração não foi concluída. Veja o log para identificar a etapa que falhou.")

    def _fail(self, message: str) -> None:
        self.running = False
        self.install_button.configure(state="normal")
        self.close_button.configure(state="normal")
        self._set_status("Falha inesperada", int(self.progress["value"]), self.ERROR)
        self._append_log("[ERRO] " + message)
        messagebox.showerror(APP_TITLE, message)

    def on_close(self) -> None:
        if self.running:
            messagebox.showwarning(APP_TITLE, "A configuração está em andamento. Aguarde a conclusão antes de fechar.")
            return
        self.root.destroy()


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_test()
    if os.name != "nt":
        print("NautrixRunnerInstaller requires Windows", file=sys.stderr)
        return 1
    if not elevate_self():
        return 0 if "--elevated" not in sys.argv else 5
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
