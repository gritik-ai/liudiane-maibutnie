#!/usr/bin/env python3
"""Build a free, rule-based RSS digest about socially beneficial AI applications.

No LLM, API key, database, or paid service is used. The script republishes only
RSS metadata and short excerpts, with a link to the original publisher.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
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
MAX_AGE_DAYS = 60
MAX_NEW_ITEMS_PER_RUN = 10
MAX_TOTAL_ITEMS = 200
FILTER_VERSION = "2.0"

# Broad, reputable feeds are narrowed by the rules below. Domain-specific MIT
# feeds increase the chance of finding practical health, education and climate
# applications instead of unrelated AI benchmarks.
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
        "name": "MIT News — Здоров'я і медицина",
        "url": "https://news.mit.edu/rss/topic/health-sciences-and-technology",
        "publisher": "MIT News",
        "host": "news.mit.edu",
        "kind": "domain_topic",
        "preprint": False,
    },
    {
        "name": "MIT News — Клімат і сталість",
        "url": "https://news.mit.edu/rss/topic/climate-change-and-sustainability",
        "publisher": "MIT News",
        "host": "news.mit.edu",
        "kind": "domain_topic",
        "preprint": False,
    },
    {
        "name": "MIT News — Продовольство і водні ресурси",
        "url": "https://news.mit.edu/rss/topic/food-and-water-security",
        "publisher": "MIT News",
        "host": "news.mit.edu",
        "kind": "domain_topic",
        "preprint": False,
    },
    {
        "name": "MIT News — Освіта і навчання",
        "url": "https://news.mit.edu/rss/topic/education",
        "publisher": "MIT News",
        "host": "news.mit.edu",
        "kind": "domain_topic",
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
    {
        "name": "WHO — Новини про здоров'я",
        "url": "https://www.who.int/rss-feeds/news-english.xml",
        "publisher": "World Health Organization (WHO)",
        "host": "www.who.int",
        "kind": "institutional",
        "preprint": False,
    },
]

# Categories already used by the website are retained. A new category for
# trustworthy and accountable AI is added to support the project's mission.
CATEGORY_KEYWORDS = {
    "Медицина": [
        "health", "medical", "medicine", "clinical", "patient", "cancer",
        "diagnos", "hospital", "drug discovery", "healthcare", "public health",
        "mental health", "rehabilitation", "терап", "медиц", "здоров",
        "пацієнт", "діагност", "лікуван", "реабілітац",
    ],
    "Освіта": [
        "education", "learning", "student", "teacher", "teaching", "school",
        "university", "tvet", "training", "tutor", "literacy", "освіт",
        "навчан", "студент", "вчител", "школ", "університет",
    ],
    "Мир і безпека": [
        "peacebuilding", "humanitarian", "disaster response", "emergency response",
        "early warning", "wildfire", "flood forecast", "earthquake response",
        "civil protection", "crisis response", "гуманітар", "цивільний захист",
        "раннє попередження", "повен", "пожеж", "стихійн",
    ],
    "Екологія": [
        "climate", "environment", "sustainab", "biodiversity", "agriculture",
        "crop", "food system", "food security", "water quality", "water resource",
        "conservation", "pollution", "еколог", "клімат", "довкіл", "сільськ",
        "аграр", "біорізноман", "продоволь", "водних ресурс", "забруднен",
    ],
    "Права людини": [
        "accessibility", "accessible", "assistive", "disability", "inclusion",
        "fairness", "human rights", "equal access", "sign language", "безбар'єр",
        "доступн", "інклюз", "права людини", "рівний доступ",
    ],
    "Державне управління": [
        "government", "public service", "public sector", "public administration",
        "governance", "civic", "policy", "public services", "державн",
        "уряд", "публічн послуг", "врядуван", "державних послуг",
    ],
    "Економіка та добробут": [
        "workforce", "worker wellbeing", "labor market", "employment", "poverty",
        "wellbeing", "well-being", "quality of life", "social protection", "housing",
        "економ", "праців", "зайнят", "добробут", "якість життя", "соціальн захист",
    ],
    "Надійність ШІ": [
        "ai safety", "alignment", "interpretability", "explainability", "explainable",
        "transparency", "auditability", "human oversight", "model reliability",
        "robustness", "hallucination", "trustworthy ai", "controllability",
        "monitorability", "надійність ші", "пояснюваність", "прозорість",
        "людський нагляд", "підзвітність алгоритмів",
    ],
}

AI_TERMS = [
    "artificial intelligence", "machine learning", "generative ai", "large language model",
    "large language models", "language model", "language models", "llm", "llms",
    "deep learning", "neural network", "neural networks", "штучний інтелект",
    "машинне навчання", "генеративний ші",
]

# A positive editorial direction does not mean that every paper must claim a
# proven benefit. These signals identify practical application, evaluation,
# access, protection or measurable improvement. The article itself remains the
# source of evidence; this filter does not certify its conclusions.
EDITORIAL_SIGNALS = [
    "improv", "help", "support", "assist", "enable", "benefit", "reduce",
    "prevent", "protect", "detect", "screen", "diagnos", "predict", "forecast",
    "evaluate", "evaluation", "measure", "assess", "optimi", "accessib",
    "personaliz", "inclus", "sustainab", "efficient", "reliab", "trustworth",
    "explainab", "transparen", "fairness", "privacy-preserving", "human oversight",
    "early warning", "early detection", "cost-effective", "resource-efficient",
    "вдосконал", "допомага", "підтрим", "сприя", "забезпеч", "зменш",
    "запобіг", "захищ", "виявля", "прогноз", "оціню", "вимірю", "доступн",
    "персоналіз", "інклюз", "стал", "ефектив", "надійн", "пояснюван",
    "прозор", "справедлив", "раннього виявлення", "раннього попередження",
]

# Clear exclusions focus on harmful applications, not on all articles that
# merely discuss risks. A separate risk-analysis section may be added later.
EXCLUSION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("військове застосування або озброєння", re.compile(
        r"\b(military|warfare|weapon|weapons|combat|battlefield|missile|missiles|armed forces|lethal autonomous)\b|\btarget recognition\b|\bautonomous weapon", re.I)),
    ("відомі військові набори розпізнавання цілей", re.compile(
        r"\b(mstar|atrnet(?:-star)?|synthetic aperture radar)\b", re.I)),
    ("саботаж", re.compile(r"\bsabotage\b|саботаж", re.I)),
    ("розробка шкідливого програмного забезпечення або фішингу", re.compile(
        r"\b(build|create|generate|deploy|develop)\b.{0,50}\b(malware|ransomware|phishing kit)\b", re.I)),
    ("масове стеження або каральне розпізнавання облич", re.compile(
        r"\b(mass surveillance|covert surveillance|facial recognition.{0,40}(policing|surveillance)|surveillance.{0,40}(population|citizens))\b", re.I)),
    ("ядерна тематика без чіткого цивільного суспільного застосування", re.compile(
        r"\bnuclear domain\b|\bnuclear weapons?\b|\bnuclear arms\b", re.I)),
    ("зниження можливості контролювати ланцюжок міркувань ШІ", re.compile(
        r"reduce.{0,70}chain[- ]of[- ]thought monitorability|reduce.{0,70}monitorability", re.I)),
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
    rows: list[dict[str, str]] = []
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


def matching_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.casefold()
    return [term for term in terms if term.casefold() in lowered]


def find_exclusion(text: str) -> str | None:
    for reason, pattern in EXCLUSION_RULES:
        if pattern.search(text):
            return reason
    return None


def assess_relevance(item: dict[str, str], feed: dict[str, object]) -> dict[str, object]:
    """Return a transparent rule-based editorial decision for one RSS item."""
    title = item.get("title", "")
    description = item.get("description", "")
    combined = f"{title} {description}".casefold()

    exclusion = find_exclusion(combined)
    if exclusion:
        return {"accepted": False, "reason": f"відсів: {exclusion}", "category": ""}

    if feed.get("kind") != "ai_topic":
        ai_hits = matching_terms(combined, AI_TERMS)
        if not ai_hits:
            return {"accepted": False, "reason": "немає чіткого зв'язку зі штучним інтелектом", "category": ""}

    category_scores: list[tuple[int, str, list[str]]] = []
    title_folded = title.casefold()
    for category, terms in CATEGORY_KEYWORDS.items():
        title_hits = matching_terms(title_folded, terms)
        all_hits = matching_terms(combined, terms)
        if all_hits:
            score = len(all_hits) + (2 * len(title_hits))
            category_scores.append((score, category, all_hits))
    if not category_scores:
        return {"accepted": False, "reason": "не виявлено визначеного напряму користі для людей", "category": ""}

    category_scores.sort(key=lambda row: row[0], reverse=True)  # stable ties preserve mission-oriented category priority
    _, category, category_hits = category_scores[0]
    signal_hits = matching_terms(combined, EDITORIAL_SIGNALS)
    if not signal_hits:
        return {
            "accepted": False,
            "reason": f"тема «{category}» є, але немає ознак практичного застосування, оцінювання або суспільної користі",
            "category": category,
        }

    # Avoid weak accidental matches from a single generic word in a long
    # abstract: require either a domain term in the title or two domain terms.
    title_category_hits = matching_terms(title_folded, CATEGORY_KEYWORDS[category])
    if not title_category_hits and len(category_hits) < 2:
        return {
            "accepted": False,
            "reason": f"недостатньо чіткий зв'язок із напрямом «{category}»",
            "category": category,
        }

    signals_for_reason = ", ".join(signal_hits[:3])
    return {
        "accepted": True,
        "reason": f"напрям: {category}; прикладні сигнали: {signals_for_reason}",
        "category": category,
    }


def is_relevant(item: dict[str, str], feed: dict[str, object]) -> bool:
    """Backward-compatible boolean helper used by tests and simple callers."""
    return bool(assess_relevance(item, feed)["accepted"])


def fetch_feed(feed: dict[str, object]) -> list[dict[str, str]]:
    request = urllib.request.Request(
        str(feed["url"]),
        headers={
            "User-Agent": "LiudianeMaibutnie-RSSBot/2.0 (+https://github.com/)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        content = response.read(2_500_000)
    return get_entries(content)


def article_from(
    item: dict[str, str], feed: dict[str, object], published: datetime,
    assessment: dict[str, object],
) -> dict[str, object]:
    title = item["title"][:180]
    description = item["description"][:1400]
    category = str(assessment["category"])
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
        f"Чому матеріал потрапив до добірки: {assessment['reason']}. Це автоматичний тематичний відбір за ключовими словами, а не підтвердження ефективності чи незалежна експертна оцінка. Перед висновками прочитайте оригінальну публікацію."
    )
    if feed["preprint"]:
        body_parts.append(
            "Науковий статус: arXiv є репозитарієм препринтів. Розміщення роботи там саме по собі не означає, що вона пройшла незалежне рецензування. Перевіряйте розділ про публікацію та рецензування в оригіналі."
        )
    body_parts.append(
        "Редакційне застереження: автоматична система перевіряє формат стрічки, дату, домен посилання та тематичні сигнали. Вона не підтверджує методологію дослідження, не перевіряє незалежно всі твердження та не замінює людську редакційну перевірку."
    )

    digest = hashlib.sha256(item["link"].encode("utf-8")).hexdigest()[:12]
    published_date = published.date().isoformat()
    return {
        "id": f"rss-{published_date}-{digest}",
        "date": published_date,
        "autoPublished": True,
        "sourceType": "rss",
        "feedName": str(feed["name"]),
        "filterVersion": FILTER_VERSION,
        "selectionReason": str(assessment["reason"]),
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


def prune_existing(existing: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    """Remove only old auto-RSS cards that fail the current editorial filter.

    Manually authored seed content is never changed. arXiv is known to be an
    AI-specific source in the previous version; other sources must still show
    an explicit AI connection when re-evaluated.
    """
    kept: list[dict[str, object]] = []
    removed = 0
    for article in existing:
        if not (article.get("autoPublished") is True and article.get("sourceType") == "rss"):
            kept.append(article)
            continue
        sources = article.get("sources", [])
        source = sources[0] if isinstance(sources, list) and sources and isinstance(sources[0], dict) else {}
        publisher = str(source.get("publisher", ""))
        old_feed_kind = "ai_topic" if publisher.casefold() == "arxiv" else "institutional"
        item = {
            "title": str(article.get("title", "")),
            # Re-check only the publisher's short excerpt, not our own
            # automatically generated explanatory paragraphs.
            "description": str(article.get("summary", "")),
        }
        decision = assess_relevance(item, {"kind": old_feed_kind})
        if decision["accepted"]:
            kept.append(article)
        else:
            removed += 1
            print(f"[PRUNE] {article.get('title', 'Без назви')} — {decision['reason']}")
    return kept, removed


def main() -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    existing_original = load_existing()
    existing, removed_existing = prune_existing(existing_original)
    seen = {
        source.get("url", "")
        for article in existing
        for source in article.get("sources", [])
        if isinstance(source, dict)
    }

    new_items: list[dict[str, object]] = []
    success_count = 0
    fetched_count = 0
    rejected_count = 0
    rejection_reasons: dict[str, int] = {}

    for feed in FEEDS:
        try:
            rows = fetch_feed(feed)
            success_count += 1
            fetched_count += len(rows)
            for row in rows:
                link = normalized_url(row["link"], str(feed["host"]))
                if not link or link in seen:
                    continue
                published = parse_date(row["published"])
                if not published or published < cutoff or published > now + timedelta(days=1):
                    continue
                row["link"] = link
                if len(plain_text(row["description"])) < 40:
                    rejected_count += 1
                    reason = "короткий або відсутній опис"
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                    continue

                assessment = assess_relevance(row, feed)
                if not assessment["accepted"]:
                    rejected_count += 1
                    reason = str(assessment["reason"])
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                    continue

                new_items.append(article_from(row, feed, published, assessment))
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
    print(f"Перевірено RSS-стрічок: {success_count}/{len(FEEDS)}; записів у стрічках: {fetched_count}.")
    print(f"Відхилено за редакційними правилами: {rejected_count}.")
    for reason, count in sorted(rejection_reasons.items(), key=lambda pair: pair[1], reverse=True)[:8]:
        print(f" - Відхилено {count}: {reason}")

    if not additions and removed_existing == 0:
        print("Нових матеріалів, що відповідають редакційним правилам, немає. Файл не змінено.")
        return 0

    combined = (additions + existing)[:MAX_TOTAL_ITEMS]
    ARTICLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ARTICLES_FILE.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if removed_existing:
        print(f"Вилучено {removed_existing} старих RSS-матеріал(ів), що не відповідають новим правилам.")
    print(f"Додано {len(additions)} нових матеріал(ів). У бібліотеці тепер {len(combined)} запис(ів).")
    for article in additions:
        print(f" - {article['date']} | [{article['category']}] {article['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
