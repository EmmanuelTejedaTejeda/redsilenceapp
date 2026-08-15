import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime

class TelemetryLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, log_path: str, rotation_mb: int = 5):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TelemetryLogger, cls).__new__(cls)
                cls._instance.log_path = Path(log_path)
                cls._instance.rotation_mb = rotation_mb
                cls._instance._ensure_log_dir()
            return cls._instance

    def _ensure_log_dir(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.touch(exist_ok=True)

    def _rotate_if_needed(self):
        if self.log_path.stat().st_size >= self.rotation_mb * 1024 * 1024:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            rotated = self.log_path.with_name(f"{self.log_path.stem}_{timestamp}{self.log_path.suffix}")
            self.log_path.rename(rotated)
            self.log_path.touch()

    def record(self, entry: dict):
        """Append a JSON line to the log, rotating if needed."""
        self._rotate_if_needed()
        with self.log_path.open("a", encoding="utf-8") as f:
            json.dump(entry, f)
            f.write("\n")

class TimerContext:
    def __init__(self, name: str, output_path: str):
        self.name = name
        self.output_path = output_path
        self.start = None
        self.logger = TelemetryLogger(log_path=os.path.join(os.getcwd(), "render_telemetry.log"))
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    def __exit__(self, exc_type, exc, tb):
        duration = time.perf_counter() - self.start
        entry = {
            "function": self.name,
            "output_path": self.output_path,
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.record(entry)
        return False
