"""Folded debug logging for agent session 67a564. Remove after confirmed fix."""
import json
import logging
import time
from pathlib import Path

_LOGGER = logging.getLogger("custom_components.nissan_leaf_obd_ble")

# Set from async_setup_entry (HA config dir is writable in Docker/Core/supervised).
_config_dir: str | None = None
_warned_primary: bool = False

# Try project .cursor path when HA runs on same machine as this repo.
_WORKSPACE_LOG = "/Users/paulbutterworth/Projects/nissan_leaf/.cursor/debug-67a564.log"
_FALLBACK_LOG = str(Path(__file__).resolve().parent / "debug-67a564-fallback.log")


def set_debug_log_config_dir(config_dir: str) -> None:
    """Call once at integration setup so logs land under the HA configuration directory."""
    global _config_dir
    _config_dir = config_dir


def _candidate_paths() -> list[str]:
    paths: list[str] = []
    if _config_dir:
        paths.append(str(Path(_config_dir) / "nissan_leaf_debug_67a564.ndjson"))
    paths.append(_WORKSPACE_LOG)
    paths.append(_FALLBACK_LOG)
    return paths


def agent_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    global _warned_primary
    line = (
        json.dumps(
            {
                "sessionId": "67a564",
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000),
                "hypothesisId": hypothesis_id,
            },
            default=str,
        )
        + "\n"
    )
    wrote_any = False
    first_path: str | None = None
    for path in _candidate_paths():
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            wrote_any = True
            if first_path is None:
                first_path = path
        except OSError:
            continue
    if wrote_any and first_path and not _warned_primary:
        _warned_primary = True
        _LOGGER.warning(
            "Debug session 67a564: writing NDJSON to %s (and any other writable paths)",
            first_path,
        )
    if not wrote_any and not _warned_primary:
        _warned_primary = True
        _LOGGER.warning(
            "Debug session 67a564: could not write NDJSON (tried HA config dir, workspace, "
            "and custom_components). Check permissions."
        )
    # #endregion
