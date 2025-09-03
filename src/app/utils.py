def mask_secret(s: str, keep: int = 1) -> str:
    """Maskiert sensible Strings für Logging-Ausgaben."""
    if not s:
    # DONE: Gib "(unset)" zurück, falls der String leer oder None ist
        return "(unset)"
    # DONE: Falls die Länge > keep * 2 ist, behalte jeweils die ersten/letzten
    #       'keep' Zeichen und ersetze die Mitte durch eine Ellipse
    if len(s) > keep * 2:
        return s[:keep] + "..." + s[-keep:]
    # DONE: Andernfalls gib den ersten und letzten Buchstaben mit Ellipse dazwischen aus
    else:
        return s[0] + "..." + s[-1] if len(s) > 1 else s
