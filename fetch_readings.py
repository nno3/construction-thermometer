#!/usr/bin/env python3
"""Build thermometer readings from public construction headlines."""

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "readings.json"

QUERIES = {
    "Residential": 'UK (housebuilding OR "residential construction" OR "housing development" OR "house builder")',
    "Industrial": 'UK ("warehouse construction" OR "industrial construction" OR "factory construction" OR "logistics development")',
    "Commercial": 'UK ("office construction" OR "commercial construction" OR "retail construction" OR "office development")',
    "Leisure": 'UK construction (hotel OR stadium OR arena) (build OR building OR development)',
    "Healthcare": 'UK ("hospital construction" OR "new hospital" OR "hospital build" OR "NHS construction" OR "healthcare construction")',
    "Education": 'UK ("school building" OR "school construction" OR "university construction" OR "college construction")',
    "Infrastructure": 'UK (HS2 OR "rail construction" OR "road construction" OR "infrastructure project") (construction OR build OR building)',
}

CONSTRUCTION_WORDS = [
    "construction", "housebuilding", "housebuilder", "contractor", "contractors",
    "infrastructure", "refurbishment", "rebuild", "warehouse", "housing",
    "house builder", "building project", "building work", "built", "hs2",
]

SECTOR_WORDS = {
    "Residential": ["housebuilding", "housing", "homes", "residential", "apartment"],
    "Industrial": ["warehouse", "industrial", "factory", "logistics"],
    "Commercial": ["office", "retail", "commercial"],
    "Leisure": ["hotel", "stadium", "leisure", "arena"],
    "Healthcare": ["hospital", "nhs", "healthcare", "clinic"],
    "Education": ["school", "university", "college"],
    "Infrastructure": ["infrastructure", "railway", "rail", "road", "bridge", "hs2"],
}

POSITIVE = [
    "green light", "record", "boost", "growth", "boom", "recover", "recovery",
    "surge", "expand", "expansion", "profit", "approved", "approval", "invest",
    "investment", "funding", "wins", "win", "award", "complete", "completed",
    "opens", "opening", "upgrade", "jobs", "hiring", "strong", "higher",
    "pipeline", "groundbreaking", "consent",
]
NEGATIVE = [
    "profit warning", "cost pressure", "insolvency", "administration",
    "collapse", "collapsed", "cancelled", "canceled", "delay", "delays",
    "delayed", "shortage", "dispute", "strike", "warning", "crisis",
    "inflation", "overrun", "halt", "halted", "pause", "paused", "decline",
    "redundancies", "loss", "losses", "cut", "cuts", "fall", "falls",
    "falling", "drop", "weak", "mothballed", "risk",
]
STOP = {
    "about", "after", "again", "against", "construction", "could", "from",
    "have", "into", "more", "news", "over", "says", "that", "their", "there",
    "this", "with", "would", "year", "years", "uk", "united", "kingdom",
}

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def google_items(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query,
        "hl": "en-GB",
        "gl": "GB",
        "ceid": "GB:en",
    })
    root = ET.fromstring(fetch(url))
    items = []
    for item in root.findall("./channel/item")[:20]:
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)].strip()
        items.append({
            "title": title,
            "source": source or "Google News",
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
        })
    return items


def enquirer_items():
    root = ET.fromstring(fetch("https://www.constructionenquirer.com/feed/"))
    items = []
    for item in root.findall("./channel/item")[:40]:
        title = re.sub(r"<[^>]+>", "", item.findtext("title") or "").strip()
        items.append({
            "title": title,
            "source": "Construction Enquirer",
            "link": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
        })
    return items


def classify(title):
    text = title.lower()
    scores = {}
    for sector, words in SECTOR_WORDS.items():
        scores[sector] = sum(1 for word in words if re.search(rf"\b{re.escape(word)}\b", text))
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def relevant(title):
    text = title.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in CONSTRUCTION_WORDS)


def recent(item):
    try:
        when = parsedate_to_datetime(item["published"])
    except (TypeError, ValueError, IndexError):
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).days <= 540


def tone(title):
    text = title.lower()
    pos = sum(1 for word in POSITIVE if re.search(rf"\b{re.escape(word)}\b", text))
    neg = sum(1 for word in NEGATIVE if re.search(rf"\b{re.escape(word)}\b", text))
    if pos == neg:
        return 0
    return (pos - neg) / (pos + neg)


def temperature(scores):
    if not scores:
        return 0
    average = sum(scores) / len(scores)
    return round(-40 + (average + 1) / 2 * 120)


def words_from(sectors):
    counts = {}
    for sector, info in sectors.items():
        for headline in info["headlines"]:
            for word in re.findall(r"[A-Za-z][A-Za-z']{3,}", headline["title"]):
                key = word.lower()
                if key in STOP:
                    continue
                bucket = counts.setdefault(key, {"value": 0, "sectors": {}})
                bucket["value"] += 1
                bucket["sectors"][sector] = bucket["sectors"].get(sector, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1]["value"], reverse=True)[:30]
    return [
        {
            "x": word.title(),
            "value": info["value"],
            "category": max(info["sectors"], key=info["sectors"].get),
        }
        for word, info in ranked
    ]


def main():
    extra = []
    try:
        extra = enquirer_items()
    except Exception as error:
        print("Construction Enquirer skipped:", error)

    sectors = {}
    for name, query in QUERIES.items():
        headlines = [item for item in google_items(query) if relevant(item["title"]) and recent(item)]
        seen = {item["title"].lower() for item in headlines}
        for item in extra:
            if classify(item["title"]) == name and relevant(item["title"]) and recent(item) and item["title"].lower() not in seen:
                headlines.append(item)
                seen.add(item["title"].lower())
        scores = [tone(item["title"]) for item in headlines]
        sectors[name] = {
            "temperature": temperature(scores),
            "headlineCount": len(headlines),
            "headlines": headlines[:6],
        }
        print(f"{name:16} {sectors[name]['temperature']:4}°C  {len(headlines)} headlines")

    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "method": "Average tone of recent headlines. -40°C is the most downbeat mix and 80°C is the most upbeat.",
        "sectors": sectors,
        "words": words_from(sectors),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
