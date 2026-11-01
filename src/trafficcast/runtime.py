"""Descoperirea executabilelor și oprire coordonată pe Windows/Linux."""

import os
from pathlib import Path
import shutil
import signal
from threading import Event, Thread

DEFAULT_SCENARIO = "simulation/intersection-urban/intersection.sumocfg"


def find_binary(name):
    found = shutil.which(name)
    if found:
        return found
    roots = []
    if name in ("sumo", "sumo-gui", "netconvert"):
        homes = [os.environ.get("SUMO_HOME")]
        if os.name == "nt":
            import winreg
            for hive, key in (
                (winreg.HKEY_CURRENT_USER, "Environment"),
                (winreg.HKEY_LOCAL_MACHINE,
                 r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            ):
                try:
                    with winreg.OpenKey(hive, key) as handle:
                        homes.append(winreg.QueryValueEx(handle, "SUMO_HOME")[0])
                except OSError:
                    pass
        roots.extend(Path(home) / "bin" for home in homes if home)
    elif name.startswith("mosquitto") and os.name == "nt":
        roots.extend(Path(os.environ.get(variable, default)) / "Mosquitto"
                     for variable, default in (("ProgramFiles", "C:/Program Files"),
                                                ("ProgramFiles(x86)", "C:/Program Files (x86)")))
    for root in roots:
        candidate = root / (name + (".exe" if os.name == "nt" else ""))
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def sumo_executable(name, directory, backend="auto"):
    native = find_binary(name)
    if backend != "flatpak" and native:
        home = Path(native).resolve().parent.parent
        if (home / "tools").is_dir():
            os.environ.setdefault("SUMO_HOME", str(home))
        return [native]
    if backend != "native" and os.name != "nt" and shutil.which("flatpak"):
        return ["flatpak", "run", f"--filesystem={directory}", "--share=network",
                f"--command={name}", "org.eclipse.sumo"]
    raise RuntimeError(f"Nu am găsit {name}. Verifică PATH și SUMO_HOME sau instalarea SUMO.")


class Shutdown:
    """Semnale locale și fișier de oprire privat pentru procesele demo."""

    def __init__(self):
        self.event = Event()
        self.previous = {}

    def __enter__(self):
        signals = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGBREAK"):
            signals.append(signal.SIGBREAK)
        for sig in signals:
            self.previous[sig] = signal.signal(sig, lambda *_: self.event.set())
        if os.environ.get("TRAFFICCAST_STOP_FILE"):
            Thread(target=self._control, daemon=True).start()
        return self.event

    def _control(self):
        path = Path(os.environ["TRAFFICCAST_STOP_FILE"])
        while not self.event.wait(0.1):
            if path.exists():
                self.event.set()

    def __exit__(self, *_):
        self.event.set()
        for sig, previous in self.previous.items():
            signal.signal(sig, previous)
