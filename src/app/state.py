import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("stock-alerts")


def load_state(path: Path) -> Dict[str, str]:
    """
    Load the last alert "state" from a JSON file.

    The state keeps track of which direction (up/down/none) a stock
    has already triggered an alert for. This prevents sending duplicate
    notifications every run.
    """
    # DONE: Prüfen, ob die Datei existiert und deren Inhalt als JSON laden
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))    
            # DONE: Bei Erfolg den geladenen Zustand zurückgeben und einen Debug-Log schreiben
            if isinstance(data, dict):
                logger.debug("Loaded state from %s: %s", path, data)
                return data
            logger.warning("State file %s did not contain a dict; resetting.", path)
        return {}
    except Exception as e:
    # DONE: Bei Fehlern eine Warnung loggen und ein leeres Dict zurückgeben
        logger.warning("Could not read state file %s: %s", path, e)
        return {}
    
    # pass


def save_state(path: Path, state: Dict[str, str]) -> None:
    """
    Save the current alert state to disk.
    """
    # DONE: Den Zustand als JSON (UTF-8) in die Datei schreiben
    try:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved state to %s: %s", path, state)
    except Exception as e:
    # DONE: Einen Debug-Log mit dem gespeicherten Zustand ausgeben
        logger.warning("Could not write state file %s: %s", path, e)
    
    # pass
