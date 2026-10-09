"""
main.py
--------
Entry point for the packaged desktop app.

Run during development:
    python main.py

Build to a single EXE (Windows) with PyInstaller, from the project root:
    pyinstaller --noconfirm --onefile --windowed ^
        --add-data "frontend;frontend" ^
        --name ClubLedger main.py

(See README.md for the full build instructions.)

Why this file has a lot of try/except: when a script is launched by
double-clicking on Windows (or run as a --windowed PyInstaller EXE with no
console at all), any unhandled exception just closes the window instantly
with NOTHING shown to the user — the classic "flashes and disappears"
symptom. Every failure path below is caught, written to a log file, and
also shown in a native message box so it's actually visible.
"""
import os
import sys
import traceback
import logging
from pathlib import Path


def resource_path(relative: str) -> str:
    """Resolve a path to a bundled resource, working both when run from
    source and when frozen into a PyInstaller onefile EXE (which unpacks
    bundled data into a temp dir referenced by sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None) or str(Path(__file__).parent)
    return str(Path(base) / relative)


def get_log_dir() -> Path:
    """Same per-user data folder the ledgers live in, so logs survive
    even if the EXE itself is reinstalled/replaced. Falls back to the
    folder next to the script/EXE if that's ever unwritable."""
    try:
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = str(Path.home() / "Library" / "Application Support")
        else:
            base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        d = Path(base) / "ClubLedger"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        return Path(getattr(sys, "_MEIPASS", None) or Path(__file__).parent)


def show_fatal_error(title: str, message: str):
    """Best-effort native message box so the error is visible even when
    there is no console window at all (--windowed EXE builds)."""
    print(f"\n=== {title} ===\n{message}\n", file=sys.stderr)
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
        elif sys.platform == "darwin":
            os.system(
                'osascript -e \'display dialog "%s" with title "%s" buttons {"OK"} '
                "default button 1 with icon stop'"
                % (message.replace('"', "'").replace("\n", "\\n"), title)
            )
        # On Linux we just rely on the log file + stderr; a GTK/QT message box
        # would need the same toolkit that may itself be missing.
    except Exception:
        pass  # message box is a nice-to-have; the log file is the real record


def main():
    log_dir = get_log_dir()
    log_file = log_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    log = logging.getLogger("club_ledger.main")
    log.info("=== ClubLedger starting ===")
    log.info("Python: %s", sys.version)
    log.info("Platform: %s", sys.platform)
    log.info("Frozen (PyInstaller): %s", bool(getattr(sys, "_MEIPASS", None)))
    log.info("Log file: %s", log_file)

    try:
        import webview
    except ImportError as e:
        msg = (
            "缺少必要套件 pywebview，無法啟動。\n\n"
            "請先在專案資料夾開啟命令提示字元，執行：\n"
            "    pip install -r requirements.txt\n\n"
            f"詳細錯誤：{e}\n\n"
            f"完整記錄檔位置：{log_file}"
        )
        log.exception("Failed to import webview")
        show_fatal_error("ClubLedger 啟動失敗", msg)
        sys.exit(1)

    try:
        from backend.api import Api
        from backend.ledger_manager import LedgerManager

        ledger_manager = LedgerManager()
        api = Api(ledger_manager)

        index_path = resource_path(os.path.join("frontend", "index.html"))
        if not Path(index_path).exists():
            raise FileNotFoundError(f"找不到介面檔案：{index_path}")

        window = webview.create_window(
            "社團帳本",
            url=index_path,
            js_api=api,
            width=1180,
            height=820,
            min_size=(960, 640),
        )
        api.set_window(window)
        debug = "--debug" in sys.argv
        log.info("Opening window (debug=%s)...", debug)
        webview.start(debug=debug)
        log.info("Window closed normally, exiting.")
    except Exception as e:
        msg = (
            "程式發生未預期的錯誤，已自動關閉。\n\n"
            f"錯誤內容：{e}\n\n"
            f"完整記錄檔位置：{log_file}\n"
            "（若是「WebView2」相關錯誤，通常代表這台電腦缺少 Microsoft Edge "
            "WebView2 Runtime，請搜尋「WebView2 Runtime 下載」安裝後再試一次。）"
        )
        log.exception("Fatal error during startup")
        show_fatal_error("ClubLedger 發生錯誤", msg)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # absolute last-resort net, in case something above main() itself
        # (e.g. logging setup) is what failed
        traceback.print_exc()
        try:
            input("\n發生錯誤（詳見上方訊息）。按 Enter 鍵關閉視窗...")
        except Exception:
            pass
        sys.exit(1)
