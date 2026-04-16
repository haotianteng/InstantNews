"""RSS feed fetching and XML parsing."""

import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from app.services.sentiment import score_sentiment


def strip_html(text):
    """Remove HTML tags and entities, truncate to 500 chars."""
    if not text:
        return ""
    text = re.sub(r'<(br|p|div|li|h[1-6]|tr|td|th)[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()[:500]


def utc_iso(dt):
    """Format a datetime as UTC ISO 8601 with +00:00 suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def parse_date(date_str):
    """Parse a date string into UTC ISO 8601 format. Falls back to now."""
    if not date_str:
        return utc_iso(datetime.now(timezone.utc))
    cleaned = date_str.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%d %b %Y %H:%M:%S %z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return utc_iso(dt)
        except ValueError:
            continue
    return utc_iso(datetime.now(timezone.utc))


def fetch_feed(source_name, url, user_agent, timeout):
    """Fetch and parse a single RSS/Atom feed. Returns list of item dicts."""
    items = []
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        root = ET.fromstring(data)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}

        # RSS 2.0
        for item in root.findall('.//item'):
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            pub_date = item.findtext('pubDate', '') or item.findtext('published', '')
            description = item.findtext('description', '')
            if not title or not link:
                continue
            summary = strip_html(description)
            combined = f"{title} {summary}"
            score, label = score_sentiment(combined)
            items.append({
                "title": title, "link": link, "source": source_name,
                "published": parse_date(pub_date), "summary": summary,
                "sentiment_score": score, "sentiment_label": label,
            })

        # Atom
        for entry in root.findall('atom:entry', ns):
            title = entry.findtext('atom:title', '', ns).strip()
            link_el = entry.find('atom:link', ns)
            link = link_el.get('href', '') if link_el is not None else ''
            pub_date = entry.findtext('atom:published', '', ns) or entry.findtext('atom:updated', '', ns)
            description = entry.findtext('atom:summary', '', ns) or entry.findtext('atom:content', '', ns)
            if not title or not link:
                continue
            summary = strip_html(description)
            combined = f"{title} {summary}"
            score, label = score_sentiment(combined)
            items.append({
                "title": title, "link": link, "source": source_name,
                "published": parse_date(pub_date), "summary": summary,
                "sentiment_score": score, "sentiment_label": label,
            })
    except Exception:
        pass
    return items
