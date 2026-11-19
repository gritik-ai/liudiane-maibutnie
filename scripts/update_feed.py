#!/usr/bin/env python3
"""Fetch selected public RSS feeds and append carefully labelled source cards.

No LLM, API key, database, or paid service is used. The script republishes only
metadata and short feed excerpts, with a link to the original publisher.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT / "content" / "articles.json"
MAX_AGE_DAYS = 45
MAX_NEW_ITEMS_PER_RUN = 5
MAX_TOTAL_ITEMS = 150

# These are topic-specific or institutional feeds. Add sources only after
# checking their publisher, feed URL, terms, and update frequency.
FEEDS = [
    {
        "name": "MIT News — Штучний інтелект",
        "url": "https://news.mit.edu/rss/topic/artificial-intelligence2",
        "publisher": "MIT News",
        "host": "news.mit.edu",
        "kind": "ai_topic",
        "preprint": False,
    },
    {
        "name": "arXiv — Штучний інтелект",
        "url": "https://export.arxiv.org/rss/cs.AI",
        "publisher": "arXiv",
        "host": "arxiv.org",
        "kind": "ai_topic",
        "preprint": True,
    },
    {
        "name": "arXiv — Машинне навчання",
        "url": "https://export.arxiv.org/rss/cs.LG",
        "publisher": "arXiv",
        "host": "arxiv.org",
        "kind": "ai_topic",
        "preprint": True,
    },
    {
        "name": "UNESCO-UNEVOC — Освіта і професійне навчання",
        "url": "https://connect.unevoc.unesco.org/unevoc_news.xml",
        "publisher": "UNESCO-UNEVOC",
        "host": "connect.unevoc.unesco.org",
        "kind": "institutional",
        "preprint": False,
    },
]

CATEGORY_KEYWORDS = {
    "Медицина": ["health", "medical", "medicine", "clinical", "patient", "cancer", "diagnos", "hospital", "drug", "healthcare", "медиц", "здоров", "пацієнт"],
    "Освіта": ["education", "learning", "student", "teacher", "teaching", "school", "university", "tvet", "training", "освіт", "навчан", "студент"],
    "Мир і безпека": ["peace", "safety", "security", "disaster", "emergency", "humanitarian", "conflict", "безпек", "катастроф", "гуманітар"],
    "Екологія": ["climate", "energy", "environment", "sustainab", "biodiversity", "agriculture", "crop", "food system", "water", "еколог", "клімат", "енерг", "довкіл", "сільськ", "аграр"],
    "Права людини": ["accessibility", "accessible", "assistive", "disability", "inclusion", "fairness", "bias", "human rights", "інклюз", "доступн", "безбар'єр", "права людини"],
    "Державне управління": ["government", "public service", "public sector", "governance", "civic", "policy", "державн", "уряд", "публічн послуг", "врядуван"],
    "Економіка та добробут": ["workforce", "worker", "labor", "employment", "productivity", "poverty", "wellbeing", "well-being", "економ", "праців", "зайнят", "добробут"],
}

# For non-specialist institutional feeds, require an explicit AI term and a
# human-impact topic before adding an item.
AI_TERMS = ["artificial intelligence", "machine learning", "generative ai", " ai ", "штучний інтелект", "машинне навчання"]
IMPACT_TERMS = [term for terms in CATEGORY_KEYWORDS.values() for term in terms] + [
    "robot", "robotics", "language", "translation", "speech", "agriculture",
    "public", "human", "люд", "мов", "робот", "дослідж"
]


class TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: str | None) -> str:
    if not value:
        return ""
    parser = TextOnly()
    try:
        parser.feed(value)
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        if local_name(child.tag) in names:
            if child.text and child.text.strip():
                return " ".join(t.strip() for t in child.itertext() if t.strip())
    return ""


def item_link(element: ET.Element) -> str:
    for child in list(element):
        if local_name(child.tag) == "link":
            href = child.attrib.get("href")
            rel = child.attrib.get("rel", "alternate")
            if href and rel in ("alternate", "self"):
                return href.strip()
            if child.text and child.text.strip():
                return child.text.strip()
    return ""


def parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_entries(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    elements = [e for e in root.iter() if local_name(e.tag) in ("item", "entry")]
    rows = []
    for element in elements:
        title = plain_text(child_text(element, ("title",)))
        link = item_link(element)
        description = plain_text(child_text(element, ("description", "summary", "content", "encoded")))
        published = child_text(element, ("pubdate", "published", "updated", "date", "issued"))
        if title and link and published:
            rows.append({"title": title, "link": link, "description": description, "published": published})
    return rows


def normalized_url(raw_url: str, expected_host: str) -> str:
    try:
        parsed = urlparse(raw_url.strip())
        host = (parsed.hostname or "").lower()
        if host != expected_host:
            return ""
        if parsed.scheme not in ("http", "https"):
            return ""
        path = parsed.path.rstrip("/") or "/"
        return f"https://{expected_host}{path}" + (f"?{parsed.query}" if parsed.query else "")
    except Exception:
        return ""


def classify(text: str) -> str:
    lowered = text.casefold()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Наука і технології"


def is_relevant(item: dict[str, str], feed: dict[str, object]) -> bool:
    text = f" {item['title']} {item['description']} ".casefold()
    if feed["kind"] == "ai_topic":
        # These feeds are specifically dedicated to AI research/news. Keep
        # applied or human-impact material, not every theoretical paper.
        return any(keyword in text for keyword in IMPACT_TERMS)
    has_ai = any(re.search(r"\b" + re.escape(term.strip()) + r"\b", text) for term in AI_TERMS)
    has_impact = any(term in text for term in IMPACT_TERMS)
    return has_ai and has_impact


def fetch_feed(feed: dict[str, object]) -> list[dict[str, str]]:
    request = urllib.request.Request(
        str(feed["url"]),
        headers={"User-Agent": "LiudianeMaibutnie-RSSBot/1.0 (+https://github.com/)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        content = response.read(2_500_000)
    return get_entries(content)


def article_from(item: dict[str, str], feed: dict[str, object], published: datetime) -> dict[str, object]:
    title = item["title"][:180]
    description = item["description"][:1400]
    category = classify(f"{title} {description}")
    short_summary = description[:330].rstrip()
    if len(description) > 330:
        short_summary = short_summary.rsplit(" ", 1)[0] + "…"
    if not short_summary:
        short_summary = "Відкрийте першоджерело, щоб прочитати опис матеріалу та перевірити його контекст."

    body_parts = [
        f"Цей матеріал автоматично відібрано зі стрічки {feed['publisher']}. Заголовок, дата та короткий опис отримані з RSS-каналу видавця.",
    ]
    if description:
        body_parts.append("Короткий опис від першоджерела:\n" + description)
    body_parts.append(
        "Чому матеріал у цій добірці: його тема стосується штучного інтелекту та одного з напрямів, важливих для якості життя людей. Це тематичний відбір, а не незалежна експертна оцінка результатів. Перед висновками прочитайте оригінальну публікацію."
    )
    if feed["preprint"]:
        body_parts.append(
            "Науковий статус: arXiv є репозитарієм препринтів. Розміщення роботи там саме по собі не означає, що вона пройшла незалежне рецензування. Перевіряйте розділ про публікацію та рецензування в оригіналі."
        )
    body_parts.append(
        "Редакційне застереження: автоматична система перевіряє формат стрічки, дату, домен посилання та тематичні слова. Вона не підтверджує методологію дослідження, не перевіряє незалежно всі твердження та не замінює людську редакційну перевірку."
    )

    digest = hashlib.sha256(item["link"].encode("utf-8")).hexdigest()[:12]
    published_date = published.date().isoformat()
    return {
        "id": f"rss-{published_date}-{digest}",
        "date": published_date,
        "autoPublished": True,
        "sourceType": "rss",
        "category": category,
        "title": title,
        "summary": short_summary,
        "body": "\n\n".join(body_parts),
        "sourceDate": published_date,
        "sources": [{
            "title": title,
            "publisher": str(feed["publisher"]),
            "url": item["link"],
            "publishedDate": published_date,
        }],
    }


def load_existing() -> list[dict[str, object]]:
    if not ARTICLES_FILE.exists():
        return []
    try:
        data = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Не вдалося прочитати {ARTICLES_FILE}: {exc}") from exc


def main() -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    existing = load_existing()
    seen = {
        source.get("url", "")
        for article in existing
        for source in article.get("sources", [])
        if isinstance(source, dict)
    }
    new_items: list[dict[str, object]] = []
    success_count = 0

    for feed in FEEDS:
        try:
            rows = fetch_feed(feed)
            success_count += 1
            for row in rows:
                link = normalized_url(row["link"], str(feed["host"]))
                if not link or link in seen:
                    continue
                published = parse_date(row["published"])
                if not published or published < cutoff or published > now + timedelta(days=1):
                    continue
                row["link"] = link
                if not is_relevant(row, feed):
                    continue
                if len(plain_text(row["description"])) < 40:
                    continue
                new_items.append(article_from(row, feed, published))
                seen.add(link)
        except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError, ValueError) as exc:
            print(f"[WARN] {feed['name']}: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"[WARN] {feed['name']}: unexpected error: {exc}", file=sys.stderr)

    if success_count == 0:
        print("[ERROR] Не вдалося отримати жодну RSS-стрічку.", file=sys.stderr)
        return 1

    new_items.sort(key=lambda article: str(article["date"]), reverse=True)
    additions = new_items[:MAX_NEW_ITEMS_PER_RUN]
    if not additions:
        print("Нових матеріалів, що відповідають правилам, немає. Файл не змінено.")
        return 0

    combined = (additions + existing)[:MAX_TOTAL_ITEMS]
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ARTICLES_FILE.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Додано {len(additions)} матеріал(ів). У бібліотеці тепер {len(combined)} запис(ів).")
    for article in additions:
        print(f" - {article['date']} | {article['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
