import datetime as dt
from zoneinfo import ZoneInfo
import logging
from pathlib import Path
from typing import Dict, List, Any
from urllib.parse import urlparse, parse_qs
import requests

from .market import get_open_and_last
from .state import load_state, save_state
from .ntfy import notify_ntfy
from .company import auto_keywords
from .news import fetch_headlines, build_query, filter_titles
from time import strftime

logger = logging.getLogger("stock-alerts")


def _ticker_to_query(ticker: str, override_name: str | None = None) -> str:
    """
    Return a human-friendly query term for a ticker.

    Args:
        ticker: Raw ticker symbol (e.g., "AAPL").
        override_name: Optional override (e.g., "Apple").

    Returns:
        A display/query string; override_name if provided, else the ticker.
    """
    # DONE: Return override_name if provided; otherwise return ticker
    name = (override_name or "").strip()
    if name:
        return name
    else:
        return (ticker or "").strip()
    # pass


def _ensure_https(u: str) -> str:
    """
    Ensure the given URL has a scheme. If missing, prefix with https://

    This helps when feeds provide bare domains or schemeless URLs.
    """
    # DONE: Handle empty strings
    if not u:
        return "" 
    
    # DONE: If u starts with http:// or https://, return u unchanged
    u = u.strip()
    parsed = urlparse(u)
    if parsed.scheme in ("http", "https"):
        return u
    
    # DONE: Otherwise, prefix u with "https://"
    # schemeless like "example.com/path" or "//example.com/path"
    if u.startswith("//"):
        return "https:" + u
    else:
        return "https://" + u
    # pass


def _extract_original_url(link: str, resolve_redirects: bool = True, timeout: float = 3.0) -> str:
    """
    Try to extract the original article URL from Google News redirect links.

    Strategy:
        1) If it's a news.google.com link and contains ?url=..., use that.
        2) Optionally resolve redirects via HEAD (fallback GET) to obtain the final URL.
        3) If all fails, return the input link.

    Args:
        link: Possibly a Google News RSS link.
        resolve_redirects: Whether to follow redirects to the final URL.
        timeout: Per-request timeout in seconds.

    Returns:
        A best-effort "clean" URL pointing to the original source.
    """
    if not link:
        return ""
    
    # DONE: Normalize link via _ensure_https
    link = _ensure_https(link)
    
    try:
        parsed = urlparse(link)
        host = (parsed.netloc or "").lower()

    # DONE: If link is a news.google.com URL, attempt to extract ?url= parameter
        # Case 1: Google News redirector
        if "news.google.com" in host:
            qs = parse_qs(parsed.query or "")
            if "url" in qs and qs["url"]:
                candidate = _ensure_https(qs["url"][0])
            else:
                candidate = link  # fallback
        else:
            candidate = link

    # DONE: Optionally resolve redirects via HEAD or GET
        # Case 2: Follow redirects to final URL
        if resolve_redirects and candidate:
            try:
                # Prefer HEAD to avoid downloading bodies
                r = requests.head(candidate, allow_redirects=True, timeout=timeout)
                if r.url:
                    return _ensure_https(r.url)
            except requests.RequestException:
                # Some servers don't like HEAD; try a very light GET
                try:
                    r = requests.get(candidate, allow_redirects=True, timeout=timeout, stream=True)
                    final_url = r.url or candidate
                    r.close()
                    return _ensure_https(final_url)
                except requests.RequestException:
                    return candidate  # network issue; return best effort

        return candidate
    except Exception:
    # DONE: Return cleaned URL or fallback to original link
        # Be conservative on any parsing error
        return link
    # pass


def _domain(url: str) -> str:
    """
    Extract a pretty domain (strip leading 'www.') from a URL for compact display.
    """
    if not url:
        return ""
    
    # DONE: Parse the domain with urlparse
    try:
        parsed = urlparse(url)
        host = parsed.netloc or ""
        
    # DONE: Strip leading "www." if present
        if host.startswith("www."):
            host = host[4:]
            
        return host or url
    
    # DONE: Return cleaned domain or original url on error
    except Exception:
        return url
    # pass


def _format_headlines(items: List[Dict[str, Any]]) -> str:
    """
    Build a compact Markdown block for headlines.  

    - Web (ntfy web app): Markdown will be rendered (nice links)
    - Mobile (ntfy apps): Markdown shows as plain text, so we also include
      a short, real URL line that remains clickable on phones.  
    
    Each item is expected to have: {"title": str, "source": str, "link": str}  

    - First line: "- [Title](url) — **Source**"
    - Second line: "  url" (plain, for mobile clients that don't render Markdown)


    Returns:
        A multi-line string ready to embed into the notification body.
        str: Multi-line Markdown text or empty string if no items.
    """
    
    # DONE: Handle empty list case
    if not items:
        return ""
    
    # DONE: Build Markdown lines with titles, sources and cleaned links
    lines: list[str] = []
    for item in items:
        title = (item.get("title") or "").strip() or "(untitled)"
        raw_link = item.get("link") or ""
        link = _extract_original_url(raw_link)  # best-effort clean URL
        source = (item.get("source") or "").strip() or _domain(link)
        domain = _domain(link)
        
        # Smart short link for mobile: domain only or trimmed
        short_url = (
            link if len(link) <= 60 else f"https://{domain}"
        )
        
        # Format timestamp
        t_raw = item.get("published", "")
        if t_raw:
            try:
                dt_obj = dt.datetime.fromisoformat(t_raw)
                ts = dt_obj.strftime("%H:%M")
                clock = f"🕒 {ts} "
            except Exception:
                clock = ""
        else:
            clock = ""
        
        # Markdown line + plain URL line
        # lines.append(f"• [{title}]({link}) — {source}\n   🔗 {short_url}")
        lines.append(f"• {clock}{title}\n 🔗 {short_url}")
    
    # DONE: Join lines with newline characters and return the result
    return "\n".join(lines)
    # pass


def now_tz(tz: str) -> dt.datetime:
    """
    Get current date/time in a specific timezone (e.g., 'Europe/Berlin').

    Using timezone-aware datetimes avoids DST pitfalls and makes logging consistent.
    """
    # DONE: Use dt.datetime.now with ZoneInfo to return timezone-aware datetime
    try:
        return dt.datetime.now(ZoneInfo(tz))
    except Exception as e:
        logger.warning("Invalid timezone %s, falling back to UTC: %s", tz, e)
        return dt.datetime.now(dt.timezone.utc)

    # pass


def is_market_hours(cfg_mh: dict) -> bool:
    """
    Heuristic market-hours check (simple window, no holidays).

    Args:
        cfg_mh: Market hours config with keys:
            - enabled (bool)
            - tz (str)
            - start_hour (int)
            - end_hour (int)
            - days_mon_to_fri_only (bool)

    Returns:
        True if within the configured hours, else False.
    """
    # DONE: If checking is disabled, return True
    if not cfg_mh.get("enabled", True):
        return True  # disabled → always allow
    
    # DONE: Obtain current time via now_tz(cfg_mh["tz"])
    now = now_tz(cfg_mh.get("tz", "UTC"))
    weekday = now.weekday()  # 0=Mon, 6=Sun
    
    # DONE: Optionally limit to Monday–Friday
    if cfg_mh.get("days_mon_to_fri_only", True) and weekday > 4:
        logger.debug("Market closed (weekend): weekday=%d", weekday)
        return False
    
    # DONE: Compare current hour with start_hour/end_hour
    start_hour = cfg_mh.get("start_hour", 8)
    end_hour = cfg_mh.get("end_hour", 22)

    if not (start_hour <= now.hour < end_hour):
        logger.debug(
            "Market closed (outside hours): now=%s start=%d end=%d",
            now.strftime("%H:%M"),
            start_hour,
            end_hour,
        )
        return False

    return True
    # pass


def run_once(
    tickers: List[str],
    threshold_pct: float,
    ntfy_server: str,
    ntfy_topic: str,
    state_file: Path,
    market_hours_cfg: dict,
    test_cfg: dict,
    news_cfg: dict | None,
) -> None:
    """
    Execute one monitoring cycle:
      - Check market hours (with optional test bypass)
      - For each ticker:
          * Fetch open & last price (intraday preferred)
          * Compute Δ% vs. open
          * Trigger ntfy push if |Δ%| ≥ threshold (with de-bounce via state file)
          * Optionally attach compact news headlines (with cleaned source URLs)

    Side effects:
      - Sends an HTTP POST to ntfy (unless dry_run)
      - Reads/writes the alert state JSON (anti-spam)
      - Writes logs according to logging setup
    """
    
    # DONE: Log job start and determine market-hours eligibility
    logger.info("=== Monitoring cycle started ===")

    # 1) Market hours check
    if test_cfg.get("enabled") and not test_cfg.get("bypass_market_hours", False):
        if not is_market_hours(market_hours_cfg):
            logger.info("Outside market hours → skipping alerts")
            return

    # DONE: Load alert state from state_file
    # 2) Load state
    state = load_state(state_file)

    # DONE: Iterate over tickers and fetch open/last prices
    # 3) Iterate over tickers
    for symbol in tickers:
        try:
            open_p, last_p = get_open_and_last(symbol)
            delta_pct = ((last_p - open_p) / open_p) * 100.0
        except Exception as e:
            logger.warning("Could not fetch prices for %s: %r", symbol, e)
            continue

    # DONE: Compute Δ% and apply test overrides if needed
        # Apply test override
        if test_cfg.get("enabled") and test_cfg.get("force_delta_pct") is not None:
            delta_pct = test_cfg["force_delta_pct"]

        direction = "up" if delta_pct >= threshold_pct else "down" if delta_pct <= -threshold_pct else "none"
        logger.info("%s Δ=%.2f%% (dir=%s)", symbol, delta_pct, direction)

    # DONE: Decide whether to send alerts and prepare notification body
        # Skip if below threshold or duplicate
        if direction == "none":
            continue
        if state.get(symbol) == direction:
            logger.debug("Skipping duplicate alert for %s (already %s)", symbol, direction)
            continue

    # DONE: Optionally fetch and format news headlines
        # 4) Optional: fetch news
        headlines_text = ""
        if news_cfg.get("enabled", False):
            try:
                name, keywords = auto_keywords(symbol)
                q = build_query(name, symbol)
                headlines = fetch_headlines(
                    q,
                    limit=news_cfg.get("limit", 2),
                    lookback_hours=news_cfg.get("lookback_hours", 12),
                    lang=news_cfg.get("lang", "de"),
                    country=news_cfg.get("country", "DE"),
                )
                filtered = filter_titles(headlines, keywords)
                headlines_text = _format_headlines(filtered)
            except Exception as e:
                logger.debug("News fetch/format failed for %s: %s", symbol, e)
                headlines_text = ""

    # DONE: Send notification via notify_ntfy and persist state via save_state
        # 5) Send notification
        arrow = "🟢 ▲" if delta_pct >= 0 else "🔴 ▼"    
        body_lines = [f"{arrow} {symbol} Δ={delta_pct:.2f}% vs. Open"]
        
        # .append for one-line, .extend for multiple lines - list
        body_lines.extend([
            f"Open: {open_p:.4f}",
            f"Last: {last_p:.4f}",
        ])
        if headlines_text:
            # Force clean formatting, split into lines and re-assemble
            headlines_lines = headlines_text.strip().splitlines()
            body_lines.append("")  # blank line before headlines
            body_lines.append("📰 News:")
            body_lines.extend(headlines_lines)
        body = "\n".join(body_lines)
        # print("body:\n")
        # print(body)
        
        
        try:
            notify_ntfy(
                ntfy_server,
                ntfy_topic,
                f"Stock Alert: {symbol}",
                body,
                dry_run=test_cfg.get("dry_run", False),
                markdown=True,
                click_url=f"https://finance.yahoo.com/quote/{symbol}",
            )
        except Exception as e:
            logger.warning("Notification failed for %s: %s", symbol, e)
            continue

        # 6) Update state
        state[symbol] = direction

    # Save state
    save_state(state_file, state)

    logger.info("=== Monitoring cycle finished ===")
    
    # pass
