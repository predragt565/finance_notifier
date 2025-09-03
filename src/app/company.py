from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import json
import time
import yfinance as yf

# DONE: Create with 'Path' class the 'CACHE_FILE' object which stores location to 'company_cache.json'
# CACHE_FILE =
CACHE_FILE: Path = Path(__file__).resolve().parent / "company_cache.json"

# DONE: # Common legal suffixes often found in company names (ADD MORE),
# which we remove to get a cleaner keyword (e.g., "Apple Inc." -> "Apple"). 
LEGAL_SUFFIXES = {
    "inc", "inc.", "incorporated",
    "corp", "corp.", "corporation",
    "co", "co.",
    "ltd", "ltd.", "limited",
    "plc",
    "ag",
    "se",
    "sa", "s.a.",
    "nv",
    "oyj",
    "ab",
    "spa", "s.p.a.",
    "kgaa",
    "sas",
    "gmbh",
    "kg",
    "pte", "pte.",
    "bv",
    "as",
    "oy",
}

# DONE: Add class attributes like in the class description

@dataclass
class CompanyMeta:
    """
    Represents metadata about a company/ticker.
    
    Attributes:
        ticker (str): The full ticker symbol, e.g., "SAP.DE".
        name (Optional[str]): Cleaned company name without legal suffixes, e.g., "Apple".
        raw_name (Optional[str]): Original company name as returned by Yahoo Finance, e.g., "Apple Inc.".
        source (str): Source of the name (e.g., "info.longName", "info.shortName", "fallback").
        base_ticker (str): Simplified ticker without suffixes, e.g., "SAP" for "SAP.DE".
    """
    ticker: str
    name: Optional[str]
    raw_name: Optional[str]
    source: str
    base_ticker: str
    # pass

# DONE: Finish this function:

def _load_cache() -> Dict[str, Any]:
    """Load cached company metadata from JSON file."""
    if CACHE_FILE.exists():
        try:
            # Return content of file
            return json.loads(CACHE_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            # Return empty dictionary
            return {}
    else:
        # Return empty dictionary
        return {}

def _save_cache(cache: Dict[str, Any]) -> None:
    """Save company metadata to local cache file."""
    # DONE: What parameters are missing?
    # CACHE_FILE.write_text(json.dumps(), encoding="utf-8")
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# DONE: Finish the function logic    
def _strip_legal_suffixes(name: str) -> str:
    """
    Remove common legal suffixes from a company name.

    Example:
        "Apple Inc." -> "Apple"
        "SAP SE" -> "SAP"
    """
    if not name:
        return ""
    parts: List[str] = [p.strip(",. ") for p in name.split()]
    while parts and parts[-1].lower() in LEGAL_SUFFIXES:
        parts.pop()
        
    return " ".join(parts) if parts else name.strip()

# DONE: Finish the function logic
def _base_ticker(symbol: str) -> str:
    """
    Extract the base ticker symbol.

    Examples:
        "SAP.DE" -> "SAP"
        "BRK.B"  -> "BRK"
        "^GDAXI" -> "^GDAXI" (indices remain unchanged)
    """
    if not symbol:
        return ""
    if symbol.startswith("^"):  # Index tickers like ^GDAXI
        return symbol
    if "." in symbol:
        return symbol.split(".", 1)[0]
    if "-" in symbol:
        return symbol.split("-", 1)[0]
    return symbol

# DONE: Finish the try and except block
def _fetch_yf_info(symbol: str, retries: int = 2, delay: float = 0.4) -> Dict[str, Any]:
    """
    Fetch company information from Yahoo Finance.

    Args:
        symbol (str): Ticker symbol.
        retries (int): Number of retries if request fails.
        delay (float): Delay between retries in seconds.

    Returns:
        dict: Yahoo Finance info dictionary (may be empty if lookup fails).
    """
    last_exc = None
    for _ in range(retries + 1):
        try:
            t = yf.Ticker(symbol)
            # Try the modern accessor first; fallback to legacy .info if needed
            info = {}
            try:
                info = t.get_info()  # yfinance >= 0.2.x
            except Exception:
                # Some versions or symbols may fail with get_info(); try .info
                info = getattr(t, "info", {}) or {}
            if info:
                return info
        except Exception as e:
            last_exc = e
            time.sleep(delay)
    return {}


def get_company_meta(symbol: str) -> CompanyMeta:
    """
    Retrieve company metadata (name, base ticker, etc.) with caching and fallbacks.
    """
    # DONE: Load the cache with _load_cache() and return early if the symbol exists
    cache = _load_cache()
    if symbol in cache:
        try:
            c = cache[symbol]
            return CompanyMeta(
                ticker=c.get("ticker", symbol),
                name=c.get("name"),
                raw_name=c.get("raw_name"),
                source=c.get("source", "cache"),
                base_ticker=c.get("base_ticker", _base_ticker(symbol)),
            )
        except Exception:
            # fall through to refetch
            pass

    # DONE: Fetch raw company information via _fetch_yf_info
    info = _fetch_yf_info(symbol)

    # DONE: Extract a potential company name from info ("longName", "shortName", "displayName")
    raw_name: Optional[str] = None
    source = "fallback"
    for key in ("longName", "shortName", "displayName"):
        if info.get(key):
            raw_name = str(info.get(key))
            source = f"info.{key}"
            break

    # DONE: Clean the extracted name with _strip_legal_suffixes and handle fallback to _base_ticker
    clean = _strip_legal_suffixes(raw_name) if raw_name else ""
    base = _base_ticker(symbol)
    if not clean:
        clean = base

    # DONE: Create a CompanyMeta instance and cache the result using _save_cache
    meta = CompanyMeta(
        ticker=symbol,
        name=clean or None,
        raw_name=raw_name,
        source=source,
        base_ticker=base,
    )

    # DONE: Save the constructed metadata back into the cache
    cache[symbol] = asdict(meta)
    _save_cache(cache)

    return meta

    # pass  # Remove this once the function is implemented


def auto_keywords(symbol: str) -> Tuple[str, list[str]]:
    """
    Generate a company search keyword set based on symbol.
    """
    # DONE: Fetch the CompanyMeta for the symbol
    meta = get_company_meta(symbol)

    # DONE: Determine the display name and construct the keyword list
    name = meta.name or meta.raw_name or meta.base_ticker or symbol
    base = meta.base_ticker or symbol
    primary = name

    # Build a small, unique set of keywords to match titles (case-insensitive match later)
    req_set = []
    for k in [primary, base, symbol]:
        if k and k not in req_set:
            req_set.append(k)

    # DONE: Return the cleaned name and the list of required keywords
    return primary, req_set

    # pass  # Remove this once the function is implemented