"""
ledger_manager.py
------------------
Manages MULTIPLE ledgers (club account books), each backed by its own
SQLite file under the app's data directory. A small JSON "registry" file
tracks which ledgers exist, their display names, and which one (if any)
is the default that should auto-open on launch.

    <app_data_dir>/
        registry.json
        ledgers/
            <ledger_id>.db
            <ledger_id>.db
            ...

This directly implements the "多帳本管理頁面 + 預設開啟帳本" request:
- list_ledgers()        -> for the ledger-picker screen
- create_ledger(name)   -> "+ 新增帳本"
- set_default(id)       -> "設為預設帳本，以後都直接進入"
- delete_ledger(id)     -> remove a ledger (file + registry entry)
"""
import json
import os
import sys
import uuid
from pathlib import Path

REGISTRY_FILENAME = "registry.json"
LEDGERS_DIRNAME = "ledgers"


def get_app_data_dir(app_name: str = "ClubLedger") -> Path:
    """Cross-platform per-user writable data directory.
    Using a real user-profile location (not a folder next to the EXE) so the
    data survives reinstalls/updates and works even if the EXE sits in a
    read-only location (e.g. Program Files)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / app_name
    d.mkdir(parents=True, exist_ok=True)
    (d / LEDGERS_DIRNAME).mkdir(parents=True, exist_ok=True)
    return d


class LedgerManager:
    def __init__(self, app_data_dir: Path = None):
        # mkdir regardless of whether app_data_dir came from get_app_data_dir()
        # (which already creates it) or was passed in explicitly (e.g. by a
        # test or a future caller) — previously a caller-supplied path that
        # didn't exist yet would make every later file op fail.
        self.app_dir = Path(app_data_dir) if app_data_dir else get_app_data_dir()
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.ledgers_dir = self.app_dir / LEDGERS_DIRNAME
        self.ledgers_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.app_dir / REGISTRY_FILENAME
        self._registry = self._load_registry()

    # ---- registry persistence ----
    def _load_registry(self):
        if self.registry_path.exists():
            try:
                return json.loads(self.registry_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"ledgers": [], "default_ledger_id": None}

    def _save_registry(self):
        """Write registry.json atomically (write to a temp file, then
        os.replace()) so a crash/power-loss mid-write can't leave a
        truncated or corrupted registry.json behind."""
        payload = json.dumps(self._registry, ensure_ascii=False, indent=2)
        tmp = self.registry_path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        try:
            os.replace(tmp, self.registry_path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    # ---- public API ----
    def list_ledgers(self):
        default_id = self._registry.get("default_ledger_id")
        return [
            {**l, "is_default": l["id"] == default_id}
            for l in self._registry["ledgers"]
        ]

    def get_ledger(self, ledger_id: str):
        for l in self._registry["ledgers"]:
            if l["id"] == ledger_id:
                return l
        return None

    def db_path_for(self, ledger_id: str) -> Path:
        return self.ledgers_dir / f"{ledger_id}.db"

    def create_ledger(self, name: str) -> dict:
        name = (name or "未命名帳本").strip() or "未命名帳本"
        ledger_id = uuid.uuid4().hex[:12]
        entry = {"id": ledger_id, "name": name}
        self._registry["ledgers"].append(entry)
        # first-ever ledger automatically becomes the default for convenience
        if self._registry.get("default_ledger_id") is None:
            self._registry["default_ledger_id"] = ledger_id
        self._save_registry()
        return {**entry, "is_default": self._registry["default_ledger_id"] == ledger_id}

    def rename_ledger(self, ledger_id: str, new_name: str) -> bool:
        for l in self._registry["ledgers"]:
            if l["id"] == ledger_id:
                l["name"] = (new_name or l["name"]).strip() or l["name"]
                self._save_registry()
                return True
        return False

    def set_default(self, ledger_id: str) -> bool:
        if not self.get_ledger(ledger_id):
            return False
        self._registry["default_ledger_id"] = ledger_id
        self._save_registry()
        return True

    def clear_default(self) -> bool:
        self._registry["default_ledger_id"] = None
        self._save_registry()
        return True

    def get_default_ledger_id(self):
        return self._registry.get("default_ledger_id")

    def delete_ledger(self, ledger_id: str) -> bool:
        found = self.get_ledger(ledger_id)
        if not found:
            return False
        # 刪實體檔案一定要排在改 registry 之前：如果檔案刪除失敗（例如 Windows
        # 上檔案還被鎖住），這裡要整個中止、registry（記憶體內的跟存在磁碟上的）
        # 都完全不動，維持跟刪除前一致的狀態，讓使用者可以重試；不要先把
        # 記憶體裡的清單改掉，不然這次執行期間 list_ledgers() 會顯示「已刪除」，
        # 但磁碟上的 .db 檔案跟 registry.json 其實都還在，兩邊會對不起來。
        db_file = self.db_path_for(ledger_id)
        try:
            for suffix in ("", "-wal", "-shm"):
                extra = db_file if suffix == "" else Path(str(db_file) + suffix)
                if extra.exists():
                    extra.unlink()
        except OSError:
            return False
        self._registry["ledgers"] = [
            l for l in self._registry["ledgers"] if l["id"] != ledger_id
        ]
        if self._registry.get("default_ledger_id") == ledger_id:
            self._registry["default_ledger_id"] = None
        try:
            self._save_registry()
        except Exception:
            return False
        return True
