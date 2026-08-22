"""The menu window: pick a listed program, run it in a terminal.

This is what the Raspberry Pi menu entry starts. It reads the app
registry, shows what is on offer, and hands the chosen command to
:mod:`pi_menu.terminal`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from . import __version__
from .config import AppEntry, ConfigError, apps_path, load_apps
from .palette import BG, FG, GRID_LINE, MUTED, PANEL_BG
from .terminal import NoTerminalFound, find_terminal, launch

POLL_MS = 1000


class MenuApp:
    """Lists the registered apps and launches the selected one."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.apps: list[AppEntry] = []
        self._running: list[tuple[str, subprocess.Popen]] = []
        self._status = tk.StringVar()
        self._description = tk.StringVar()

        self._build_ui()
        self.reload()
        self._poll()

    # -- construction ----------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title("Pi Menu")
        self.root.configure(bg=BG)
        self.root.minsize(560, 380)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:  # pragma: no cover - theme availability varies
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=FG, font=("", 15, "bold"))
        style.configure("TButton", padding=(12, 7))

        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="Choose an application", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        self.listbox = tk.Listbox(
            outer,
            bg=PANEL_BG,
            fg=FG,
            selectbackground="#3355aa",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=GRID_LINE,
            borderwidth=0,
            activestyle="none",
            font=("", 12),
        )
        self.listbox.grid(row=1, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", lambda _e: self._on_select())
        self.listbox.bind("<Double-Button-1>", lambda _e: self.run_selected())
        self.listbox.bind("<Return>", lambda _e: self.run_selected())

        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        description = ttk.Label(
            outer,
            textvariable=self._description,
            style="Muted.TLabel",
            wraplength=520,
            justify="left",
        )
        description.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(outer)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.run_button = ttk.Button(buttons, text="Run", command=self.run_selected)
        self.run_button.pack(side="left")
        ttk.Button(buttons, text="Reload list", command=self.reload).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Quit", command=self.quit).pack(side="right")

        ttk.Label(outer, textvariable=self._status, style="Muted.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

    # -- registry --------------------------------------------------------

    def reload(self) -> None:
        """Re-read the app registry and rebuild the list."""
        self.listbox.delete(0, tk.END)
        try:
            self.apps = [app for app in load_apps() if app.enabled]
        except ConfigError as exc:
            self.apps = []
            self._description.set("")
            self._status.set(str(exc))
            self.run_button.state(["disabled"])
            return

        for app in self.apps:
            self.listbox.insert(tk.END, f"  {app.name}")

        if self.apps:
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.run_button.state(["!disabled"])
        else:
            self.run_button.state(["disabled"])

        self._on_select()
        self._report_environment()

    def _report_environment(self) -> None:
        terminal = find_terminal()
        where = terminal[0].rsplit("/", 1)[-1] if terminal else "none found"
        self._status.set(
            f"{len(self.apps)} app(s) from {apps_path()}  ·  terminal: {where}"
        )

    def _selected(self) -> AppEntry | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.apps[selection[0]]

    def _on_select(self) -> None:
        app = self._selected()
        self._description.set(app.description if app else "")

    # -- launching -------------------------------------------------------

    def run_selected(self) -> None:
        app = self._selected()
        if app is None:
            self._status.set("Select an application first.")
            return

        command = app.resolved_command()
        try:
            process = launch(
                command, title=app.name, hold=app.hold, in_terminal=app.terminal
            )
        except NoTerminalFound as exc:
            self._status.set(f"{exc} — running without a terminal instead.")
            try:
                process = launch(command, title=app.name, in_terminal=False)
            except OSError as fallback_exc:
                self._status.set(f"Could not start {app.name}: {fallback_exc}")
                return
        except OSError as exc:
            self._status.set(f"Could not start {app.name}: {exc}")
            return

        self._running.append((app.name, process))
        self._status.set(f"Started {app.name} (pid {process.pid}).")

    def _poll(self) -> None:
        """Notice apps that exit straight away, which usually means a crash."""
        still_running = []
        for name, process in self._running:
            code = process.poll()
            if code is None:
                still_running.append((name, process))
            elif code != 0:
                self._status.set(
                    f"{name} exited with status {code} — see its terminal window."
                )
        self._running = still_running
        self.root.after(POLL_MS, self._poll)

    def quit(self) -> None:
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pi-menu", description="Menu of Stellar Unicorn applications."
    )
    parser.add_argument("--version", action="version", version=f"pi-menu {__version__}")
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the registered apps and exit, without opening a window",
    )
    args = parser.parse_args(argv)

    if args.list:
        try:
            apps = load_apps()
        except ConfigError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"# {apps_path()}")
        for app in apps:
            flag = "" if app.enabled else "  (disabled)"
            print(f"{app.id:12} {app.name}{flag}")
            print(f"{'':12} {' '.join(app.resolved_command())}")
        return 0

    root = tk.Tk()
    MenuApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
