from __future__ import annotations
import datetime as dt
from typing import List, Dict, Iterable
from urllib.parse import quote_plus
import feedparser


def build_query(name: str, ticker: str) -> str:
    """
    Build a Google News search query for a company.  
    Combines company name, ticker, and finance-related keywords (EN/DE).
    """
    # DONE: Return a query combining company name, ticker, and finance keywords
    # Quote company name to prefer exact matches; include ticker as-is.
    # A small set of finance terms increases relevance.
    finance_terms = "(stock OR shares OR finance OR earnings OR results OR Aktie OR Börse OR Gewinn OR Verlust)"
    # print(f"\"{name}\" OR {ticker} {finance_terms}")
    return f"\"{name}\" OR {ticker} {finance_terms}"
    # pass


def filter_titles(items: List[Dict[str, str]], required_keywords: Iterable[str] = ()) -> List[Dict[str, str]]:
    """
    Filter news items so that only those containing required keywords
    in their title are kept (case-insensitive). If no keywords are given,
    returns the input unchanged.
    """
    # DONE: If no required keywords, return items unchanged
    req = [k.strip().lower() for k in (required_keywords or []) if k and k.strip()]
    if not req:
        return items
    else:
    # DONE: Otherwise, keep only items whose title contains any keyword (case-insensitive)
        out: List[Dict[str, str]] = []
        for it in items:
            title = (it.get("title") or "").lower()
            if any(k in title for k in req):
                out.append(it)
        return out
    # pass


def _google_news_rss_url(query: str, lang: str = "de", country: str = "DE") -> str:
    """
    Build a Google News RSS URL for a given query.
    """
    # DONE: Encode the query with quote_plus, append "when:12h" - implemented in 'fetch_headlines() params
    # DONE: Construct and return the final RSS URL
    q = quote_plus(query)
    # hl: UI language, gl/ceid: Geo edition. This is the standard pattern for Google News RSS.
    return (
        f"https://news.google.com/rss/search?"
        f"q={q}&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"
    )
    # pass


def fetch_headlines(
    query: str,
    limit: int = 2,
    lookback_hours: int = 12,
    lang: str = "de",
    country: str = "DE",
) -> List[Dict[str, str]]:
    """
    Fetch latest headlines from Google News RSS for a given query.  
    Returns a list of dicts: {"title": str, "source": str, "link": str}
    """
    # DONE: Build the RSS URL via _google_news_rss_url and parse it with feedparser
    # Add a time window hint to the query (improves freshness on Google's side)
    timed_query = f"{query} when:{int(lookback_hours)}h"
    url = _google_news_rss_url(timed_query, lang=lang, country=country)

    feed = feedparser.parse(url)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=lookback_hours)
    
    # DONE: Filter entries by publication time (lookback_hours) and collect title/source/link
    results: List[Dict[str, str]] = []
    for e in feed.entries or []:
        # published_parsed or updated_parsed → struct_time
        t = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        if t:
            published_dt = dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
            if published_dt < cutoff:
                continue
        else:
            published_dt = None # fallback
            
        title = (getattr(e, "title", "") or "").strip()
        link = (getattr(e, "link", "") or "").strip()

        # 'source' in Google News RSS is usually a dict with 'title'
        source = ""
        src = getattr(e, "source", None)
        if isinstance(src, dict):
            source = (src.get("title") or "").strip()
        elif src:
            source = str(src).strip()

    # DONE: Stop after collecting 'limit' items
        results.append({
            "title": title, 
            "source": source, 
            "link": link,
            "published": published_dt.isoformat() if published_dt else "",  # RSS feed timestamp
            })
        if len(results) >= int(limit):
            break

    return results
    # pass
