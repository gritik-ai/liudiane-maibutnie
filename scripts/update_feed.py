#!/usr/bin/env python3
"""Curate a diverse, free RSS digest about science and its benefits to people.

Rule-based only: no paid API, LLM, database, or credentials required.
The filter labels editorial relevance; it does not certify research claims.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_FILE = ROOT / "content" / "articles.json"
MAX_AGE_DAYS = 60
MAX_NEW_ITEMS_PER_RUN = 10
MAX_ITEMS_PER_DOMAIN_PER_RUN = 3
MAX_TOTAL_ITEMS = 200
MIN_DESCRIPTION_LENGTH = 40
FILTER_VERSION = "2.6"
SOURCE_STATS_FILE = ROOT / "content" / "source_stats.json"

FEEDS: list[dict[str, object]] = [
    # MIT News — тематичні новини про науку та суспільно корисні технології.
    {"id": "mit-ai", "name": "MIT News — Штучний інтелект", "url": "https://news.mit.edu/rss/topic/artificial-intelligence2", "publisher": "MIT News", "host": "mit.edu", "domain": "mit.edu", "kind": "ai_topic", "requires_ai": True, "preprint": False},
    {"id": "mit-health", "name": "MIT News — Здоров'я і медицина", "url": "https://news.mit.edu/rss/topic/health-sciences-and-technology", "publisher": "MIT News", "host": "mit.edu", "domain": "mit.edu", "kind": "domain_topic", "requires_ai": False, "preprint": False},
    {"id": "mit-climate", "name": "MIT News — Клімат і сталість", "url": "https://news.mit.edu/rss/topic/climate-change-and-sustainability", "publisher": "MIT News", "host": "mit.edu", "domain": "mit.edu", "kind": "domain_topic", "requires_ai": False, "preprint": False},
    {"id": "mit-food-water", "name": "MIT News — Продовольство і водні ресурси", "url": "https://news.mit.edu/rss/topic/food-and-water-security", "publisher": "MIT News", "host": "mit.edu", "domain": "mit.edu", "kind": "domain_topic", "requires_ai": False, "preprint": False},
    {"id": "mit-education", "name": "MIT News — Освіта і навчання", "url": "https://news.mit.edu/rss/topic/education", "publisher": "MIT News", "host": "mit.edu", "domain": "mit.edu", "kind": "domain_topic", "requires_ai": False, "preprint": False},

    # arXiv — наукові препринти; фільтр позначає їхній статус окремо.
    {"id": "arxiv-ai", "name": "arXiv — Штучний інтелект", "url": "https://export.arxiv.org/rss/cs.AI", "publisher": "arXiv", "host": "arxiv.org", "domain": "arxiv.org", "kind": "ai_topic", "requires_ai": True, "preprint": True},
    {"id": "arxiv-ml", "name": "arXiv — Машинне навчання", "url": "https://export.arxiv.org/rss/cs.LG", "publisher": "arXiv", "host": "arxiv.org", "domain": "arxiv.org", "kind": "ai_topic", "requires_ai": True, "preprint": True},

    # UNESCO та WHO — освіта, професійний розвиток і здоров'я.
    {"id": "unevoc-news", "name": "UNESCO-UNEVOC — Освіта і професійне навчання", "url": "https://connect.unevoc.unesco.org/unevoc_news.xml", "publisher": "UNESCO-UNEVOC", "host": "unevoc.unesco.org", "domain": "unesco.org", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "who-news", "name": "WHO — Новини про здоров'я", "url": "https://www.who.int/rss-feeds/news-english.xml", "publisher": "World Health Organization (WHO)", "host": "who.int", "domain": "who.int", "kind": "institutional", "requires_ai": False, "preprint": False},

    # NASA: залишаємо стабільну загальну стрічку. JPL окрему стрічку
    # тимчасово прибрано після HTTP 403 у журналі GitHub Actions.
    {"id": "nasa-news", "name": "NASA — Наука і технології", "url": "https://www.nasa.gov/feed/", "publisher": "NASA", "host": "nasa.gov", "domain": "nasa.gov", "kind": "institutional", "requires_ai": False, "preprint": False},

    # NOAA: замінено некоректний NOS News XML на офіційну Ocean Facts RSS.
    {"id": "noaa-main", "name": "NOAA — Клімат, океани і довкілля", "url": "https://www.noaa.gov/rss.xml", "publisher": "NOAA", "host": "noaa.gov", "domain": "noaa.gov", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "noaa-ocean", "name": "NOAA National Ocean Service — Ocean Facts", "url": "https://oceanservice.noaa.gov/rss/oceanfacts.xml", "publisher": "NOAA National Ocean Service", "host": "oceanservice.noaa.gov", "domain": "noaa.gov", "kind": "institutional", "requires_ai": False, "preprint": False},

    # UN News — окремі тематичні стрічки з питань здоров'я, клімату,
    # прав людини, освіти, гуманітарної допомоги та миру.
    {"id": "un-health", "name": "UN News — Здоров'я", "url": "https://news.un.org/feed/subscribe/en/news/topic/health/feed/rss.xml", "publisher": "United Nations News", "host": "news.un.org", "domain": "un.org", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "un-climate", "name": "UN News — Клімат і довкілля", "url": "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml", "publisher": "United Nations News", "host": "news.un.org", "domain": "un.org", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "un-human-rights", "name": "UN News — Права людини", "url": "https://news.un.org/feed/subscribe/en/news/topic/human-rights/feed/rss.xml", "publisher": "United Nations News", "host": "news.un.org", "domain": "un.org", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "un-education", "name": "UN News — Культура та освіта", "url": "https://news.un.org/feed/subscribe/en/news/topic/culture-and-education/feed/rss.xml", "publisher": "United Nations News", "host": "news.un.org", "domain": "un.org", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "un-humanitarian", "name": "UN News — Гуманітарна допомога", "url": "https://news.un.org/feed/subscribe/en/news/topic/humanitarian-aid/feed/rss.xml", "publisher": "United Nations News", "host": "news.un.org", "domain": "un.org", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "un-peace-security", "name": "UN News — Мир і безпека", "url": "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/feed/rss.xml", "publisher": "United Nations News", "host": "news.un.org", "domain": "un.org", "kind": "institutional", "requires_ai": False, "preprint": False},

    # Європейський центр з профілактики та контролю захворювань.
    {"id": "ecdc-news", "name": "ECDC — Новини та пресрелізи", "url": "https://www.ecdc.europa.eu/en/taxonomy/term/1307/feed", "publisher": "European Centre for Disease Prevention and Control (ECDC)", "host": "ecdc.europa.eu", "domain": "ecdc.europa.eu", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "ecdc-publications", "name": "ECDC — Публікації та звіти", "url": "https://www.ecdc.europa.eu/en/taxonomy/term/1244/feed", "publisher": "European Centre for Disease Prevention and Control (ECDC)", "host": "ecdc.europa.eu", "domain": "ecdc.europa.eu", "kind": "institutional", "requires_ai": False, "preprint": False},

    # CDC Emerging Infectious Diseases — наукові статті про інфекційні хвороби.
    {"id": "cdc-eid-ahead", "name": "CDC — Emerging Infectious Diseases: Ahead of Print", "url": "https://wwwnc.cdc.gov/eid/rss/ahead-of-print.xml", "publisher": "CDC Emerging Infectious Diseases", "host": "wwwnc.cdc.gov", "domain": "cdc.gov", "kind": "institutional", "requires_ai": False, "preprint": False},

    # NIH/NIEHS — новини з екологічного здоров'я та досліджень.
    {"id": "niehs-news", "name": "NIEHS — Новини про екологічне здоров'я", "url": "https://www.niehs.nih.gov/news/newsroom/rssfeed/rss_news.xml", "publisher": "National Institute of Environmental Health Sciences (NIEHS)", "host": "niehs.nih.gov", "domain": "nih.gov", "kind": "institutional", "requires_ai": False, "preprint": False},

    # Copernicus Data Space — супутникові дані Землі та приклади їх застосування.
    {"id": "copernicus-general", "name": "Copernicus — Новини та оновлення", "url": "https://dataspace.copernicus.eu/rss.xml", "publisher": "Copernicus Data Space Ecosystem", "host": "dataspace.copernicus.eu", "domain": "copernicus.eu", "kind": "institutional", "requires_ai": False, "preprint": False},

    # Європейська статистика: довкілля, енергетика та наука.
    {"id": "eurostat-environment-energy", "name": "Eurostat — Довкілля та енергетика", "url": "https://ec.europa.eu/eurostat/en/search?_estatsearchportlet_WAR_estatsearchportlet_collection=CAT_EURNEW&_estatsearchportlet_WAR_estatsearchportlet_theme=PER_ENVENE&p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_mode=view&p_p_resource_id=atom&p_p_state=maximized", "publisher": "Eurostat", "host": "ec.europa.eu", "domain": "europa.eu", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "eurostat-science-tech", "name": "Eurostat — Наука і технології", "url": "https://ec.europa.eu/eurostat/en/search?_estatsearchportlet_WAR_estatsearchportlet_collection=CAT_PREREL&_estatsearchportlet_WAR_estatsearchportlet_theme=PER_RESDEV&p_p_id=estatsearchportlet_WAR_estatsearchportlet&p_p_lifecycle=2&p_p_mode=view&p_p_resource_id=atom&p_p_state=maximized", "publisher": "Eurostat", "host": "ec.europa.eu", "domain": "europa.eu", "kind": "institutional", "requires_ai": False, "preprint": False},

    # Європейська Комісія — кліматична та природоохоронна політика.
    {"id": "eu-clima-news", "name": "Європейська Комісія — Клімат", "url": "https://ec.europa.eu/newsroom/clima/feed?item_type_id=1536&lang=en&orderby=item_date", "publisher": "European Commission — Climate Action", "host": "ec.europa.eu", "domain": "europa.eu", "kind": "institutional", "requires_ai": False, "preprint": False},
    {"id": "eu-env-news", "name": "Європейська Комісія — Довкілля", "url": "https://ec.europa.eu/newsroom/env/feed?item_type_id=1041&lang=en&orderby=item_date", "publisher": "European Commission — Environment", "host": "ec.europa.eu", "domain": "europa.eu", "kind": "institutional", "requires_ai": False, "preprint": False},
]

# Strong, human-domain signals. Intentionally avoid ambiguous standalone words
# such as "learning", "environment", "governance", or "policy".
CATEGORY_TERMS: dict[str, list[str]] = {
    "Медицина": [
        "healthcare", "health care", "public health", "clinical", "patient", "medical",
        "medicine", "diagnos", "screening", "cancer", "hospital", "disease", "therapy",
        "clinical note", "medical imaging", "radiology", "rehabilitation", "drug discovery",
        "sleep apnea", "sleep disorder", "cognitive assessment", "behavioral assessment",
        "psychological assessment", "mental health assessment",
        "медиц", "здоров", "клініч", "пацієнт", "діагност", "лікуван", "реабілітац",
    ],
    "Освіта": [
        "education", "educational", "student", "students", "teacher", "teachers",
        "school", "schools", "classroom", "classrooms", "tutoring", "tutor", "pedagogy",
        "literacy", "vocational education", "teacher training", "student learning",
        "learning outcomes", "learning support", "personalized learning for students",
        "adaptive learning for students", "curriculum-aligned", "curriculum aligned",
        "curriculum development", "assessment items", "educational assessment",
        "школ", "учн", "студент", "вчител", "освіт", "навчальн програм", "педагог",
    ],
    "Мир і безпека": [
        "peacebuilding", "humanitarian", "disaster response", "emergency response",
        "early warning", "wildfire", "flood forecast", "earthquake response",
        "civil protection", "crisis response", "humanitarian relief", "гуманітар",
        "цивільний захист", "раннє попередження", "повен", "пожеж", "стихійн",
    ],
    "Екологія": [
        "climate", "environmental", "natural ecosystem", "ecosystem restoration", "ecosystem services", "sustainability", "sustainable development",
        "biodiversity", "agriculture", "crop yield", "food system", "food security",
        "water quality", "water resources", "water resource", "conservation", "pollution",
        "renewable energy", "emissions", "deforestation", "drought", "еколог", "клімат",
        "довкіл", "сільськ господар", "аграр", "біорізноман", "продоволь", "водних ресурс",
        "забруднен", "відновлювана енергетика",
    ],
    "Права людини": [
        "accessibility", "accessible", "assistive technology", "disability", "disabled people",
        "inclusion", "human rights", "equal access", "sign language", "безбар'єр",
        "доступн", "інклюз", "права людини", "рівний доступ",
    ],
    "Державне управління": [
        "government", "public service", "public services", "public sector", "public administration",
        "public governance", "public policy", "policy makers", "policymakers", "public comments",
        "regulator", "regulators", "regulatory oversight", "regulatory agency",
        "ai regulation", "державн", "уряд", "публічн послуг", "державних послуг",
        "органи влади", "регулятор",
    ],
    "Економіка та добробут": [
        "workforce", "worker wellbeing", "labor market", "labour market", "employment",
        "poverty", "wellbeing", "well-being", "quality of life", "social protection", "housing",
        "income security", "market concentration", "supply chain", "financial inclusion", "financial access", "living standards", "економ", "праців", "зайнят", "добробут", "якість життя", "соціальн захист",
    ],
    "Наука і технології": [
        "space science", "space technology", "spacecraft", "space weather", "space exploration",
        "earth observation", "satellite observation", "satellite data", "remote sensing",
        "aeronautics", "aviation technology", "robotics", "robotic system", "scientific instrument",
        "technology demonstration", "materials science", "navigation system", "solar storm",
        "planetary science", "earth science", "ocean observation", "ocean mapping",
        "наукові прилади", "космічні технології", "дистанційне зондування", "супутникові дані",
        "робототехнік", "аеронавтик", "навігаційн", "дослідження землі",
    ],
    "Надійність ШІ": [
        "ai safety", "safety alignment", "interpretability", "explainability",
        "explainable", "transparency", "auditability", "human oversight", "model reliability",
        "robustness", "hallucination", "controllability", "monitorability",
        "privacy-preserving", "algorithmic bias", "gender stereotyping", "bias detection",
        "fairness evaluation", "надійність ші", "пояснюваність", "прозорість", "людський нагляд",
        "підзвітність алгоритмів",
    ],
}

AI_TERMS = [
    "artificial intelligence", "machine learning", "generative ai", "large language model",
    "large language models", "language model", "language models", "llm", "llms",
    "deep learning", "neural network", "neural networks", "штучний інтелект",
    "машинне навчання", "генеративний ші", "модель ші", "моделі ші",
]

# These are meaningful indicators of use, evaluation or safeguards. A category
# must also be established; a generic word such as "improve" is not enough alone.
UTILITY_TERMS = [
    "clinical validation", "clinical trial", "diagnostic accuracy", "decision support",
    "forecasting", "forecast", "monitoring", "monitor", "observation", "measurements",
    "early warning", "warning system", "navigation", "mapping", "remote sensing",
    "technology demonstration", "field campaign", "data products", "earth observation",
    "public health guidance", "health guidance", "vaccination", "immunization",
    "prevention", "treatment", "health services", "training programme", "skills development",
    "controlled comparison", "comparison", "medical explanations", "clinical explanations", "information extraction",
    "early detection", "screening", "benchmark", "benchmarks", "evaluation", "evaluate",
    "evaluating", "validated", "validation", "assessment items", "curriculum-aligned",
    "field study", "real-world", "deployment", "deployed", "workflow", "dataset",
    "information retrieval", "assist", "assists", "support", "supports", "improve",
    "improves", "improvement", "reduce", "reduces", "prevent", "prevents", "protect",
    "detect", "detection", "forecast", "forecasting", "predict", "prediction", "measure",
    "measuring", "accessibility", "accessible", "human oversight", "audit", "auditable",
    "robust", "reliable", "privacy-preserving", "transparency", "public comments", "public oversight", "regulatory oversight", "evidence to regulators", "evidence-based", "accountability", "auditor", "auditors", "покращ", "допомага",
    "підтрим", "зменш", "запобіг", "захищ", "виявля", "прогноз", "оціню", "вимірю",
    "доступн", "персоналіз", "інклюз", "стал", "ефектив", "надійн", "пояснюван",
    "прозор", "справедлив", "раннього виявлення", "раннього попередження",
]

# Strongly out-of-scope harmful uses. Risks/safety research are not excluded just
# because they discuss risk; only clear harmful application signals are.
EXCLUSION_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("військове застосування або озброєння", re.compile(
        r"\b(military|warfare|weapon|weapons|combat|battlefield|missile|missiles|armed forces|lethal autonomous)\b|\btarget recognition\b|\bautonomous weapon", re.I)),
    ("відомі військові набори розпізнавання цілей", re.compile(r"\b(mstar|atrnet(?:-star)?|synthetic aperture radar)\b", re.I)),
    ("сприяння здійсненню або приховуванню саботажу", re.compile(
        r"\b(perform|execute|carry out|enable|facilitate|conceal|hide|evade detection of)\b.{0,70}\bsabotage\b", re.I)),
    ("розробка шкідливого програмного забезпечення або фішингу", re.compile(
        r"\b(build|create|generate|deploy|develop)\b.{0,50}\b(malware|ransomware|phishing kit)\b", re.I)),
    ("масове стеження або каральне розпізнавання облич", re.compile(
        r"\b(mass surveillance|covert surveillance|facial recognition.{0,40}(policing|surveillance)|surveillance.{0,40}(population|citizens))\b", re.I)),
    ("ядерна тематика без чіткого цивільного суспільного застосування", re.compile(
        r"\bnuclear domain\b|\bnuclear weapons?\b|\bnuclear arms\b", re.I)),
    ("зниження можливості контролювати ланцюжок міркувань ШІ", re.compile(
        r"reduce.{0,70}chain[- ]of[- ]thought monitorability|reduce.{0,70}monitorability", re.I)),
]

# Explicit contextual checks prevent technical "curriculum learning" or generic
# "learning" in ML papers from being mistaken for human education.
EDUCATION_STRONG = [
    "education", "educational", "student", "students", "teacher", "teachers", "school",
    "schools", "classroom", "classrooms", "pupil", "pupils", "pedagogy", "literacy program",
    "vocational education", "teacher training", "adult education", "higher education",
    "освіт", "школ", "учн", "студент", "вчител", "педагог",
]

# A technical use of "learning", "curriculum", or "assessment" does not by itself
# mean that a paper concerns education of people. These cues are deliberately human-focused.
EDUCATION_CONTEXT_TERMS = [
    "students", "student", "teachers", "teacher", "pupils", "pupil", "schools", "school",
    "classroom", "classrooms", "education", "educational", "pedagogy", "vocational education",
    "adult education", "higher education", "literacy program", "curriculum-aligned assessment",
    "curriculum aligned assessment", "school curriculum", "освіт", "школ", "учн", "студент",
    "вчител", "педагог",
]

SCIENCE_TECH_STRONG_TERMS = [
    "space science", "space technology", "spacecraft", "space weather", "space exploration",
    "earth observation", "satellite data", "remote sensing", "aeronautics", "robotics",
    "scientific instrument", "technology demonstration", "materials science", "navigation system",
    "solar storm", "planetary science", "earth science", "ocean observation", "ocean mapping",
    "космічні технології", "супутникові дані", "дистанційне зондування", "робототехнік",
]

RELIABILITY_STRONG_TERMS = [
    "ai safety", "safety alignment", "model reliability", "interpretability",
    "explainability", "explainable ai", "human oversight", "auditability", "hallucination",
    "monitorability", "controllability", "privacy-preserving", "robustness evaluation",
    "algorithmic accountability", "ai auditing", "algorithmic bias", "gender stereotyping",
    "bias detection", "fairness evaluation", "надійність ші", "пояснюваність",
    "людський нагляд", "підзвітність алгоритмів",
]

ECOLOGY_STRONG_TERMS = [
    "climate", "climate change", "environmental impact", "environmental monitoring",
    "biodiversity", "natural ecosystem", "ecosystem restoration", "ecosystem services",
    "agriculture", "crop yield", "food security", "water quality", "water resources",
    "pollution", "renewable energy", "emissions", "deforestation", "drought",
    "еколог", "клімат", "довкіл", "сільськ господар", "аграр", "біорізноман",
    "продоволь", "водних ресурс", "забруднен", "відновлювана енергетика",
]



def matching_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.casefold()
    return [term for term in terms if term.casefold() in lowered]


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
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        if local_name(child.tag) in names:
            text = " ".join(part.strip() for part in child.itertext() if part.strip())
            if text:
                return text
    return ""


def item_link(element: ET.Element) -> str:
    links = [child for child in list(element) if local_name(child.tag) == "link"]
    for child in links:
        href = child.attrib.get("href")
        rel = child.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href.strip()
    for child in links:
        href = child.attrib.get("href")
        if href:
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
    rows: list[dict[str, str]] = []
    for element in root.iter():
        if local_name(element.tag) not in ("item", "entry"):
            continue
        title = plain_text(child_text(element, ("title",)))
        link = item_link(element)
        description = plain_text(child_text(element, ("description", "summary", "content", "encoded")))
        published = child_text(element, ("pubdate", "published", "updated", "date", "issued"))
        if title and link and published:
            rows.append({"title": title, "link": link, "description": description, "published": published})
    return rows


def normalized_url(raw_url: str, expected_host: str | None = None) -> str:
    try:
        parsed = urlparse(raw_url.strip())
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not host:
            return ""
        if expected_host:
            expected = expected_host.lower().strip(".")
            if host != expected and not host.endswith("." + expected):
                return ""
        # Tracking query parameters and fragments do not identify a different article.
        kept_query = "&".join(part for part in parsed.query.split("&") if part and not part.lower().startswith(("utm_", "fbclid=", "gclid=")))
        path = re.sub(r"/+", "/", parsed.path).rstrip("/") or "/"
        return urlunparse(("https", host, path, "", kept_query, ""))
    except Exception:
        return ""


def canonical_domain(raw_url: str) -> str:
    """Return a stable publisher domain for source-diversity statistics."""
    try:
        host = (urlparse(raw_url).hostname or "").lower().strip(".")
    except Exception:
        return ""
    if not host:
        return ""
    if host.endswith(".arxiv.org") or host == "arxiv.org":
        return "arxiv.org"
    for root in (
        "mit.edu", "unesco.org", "who.int", "nasa.gov", "noaa.gov",
        "un.org", "ecdc.europa.eu", "cdc.gov", "nih.gov", "copernicus.eu", "europa.eu",
    ):
        if host == root or host.endswith("." + root):
            return root
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in {"co", "org", "gov", "ac", "com"} and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def title_key(title: str) -> str:
    folded = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.findall(r"[\w]+", folded, flags=re.UNICODE))


def doi_key(article: dict[str, object]) -> str:
    """Extract a DOI identifier from source URL/title/text for robust deduplication."""
    parts: list[str] = [str(article.get("title", "")), str(article.get("summary", "")), str(article.get("sourceDescription", ""))]
    sources = article.get("sources", [])
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict):
                parts.extend([str(source.get("url", "")), str(source.get("title", ""))])
    text = " ".join(parts)
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I)
    if not match:
        return ""
    return match.group(0).rstrip(".,;:)").casefold()


def article_keys(article: dict[str, object]) -> tuple[str, str, str]:
    return normalized_url(source_url(article)), doi_key(article), title_key(str(article.get("title", "")))


def find_exclusion(text: str) -> str | None:
    for reason, pattern in EXCLUSION_RULES:
        if pattern.search(text):
            return reason
    return None


def education_is_human_focused(title: str, combined: str) -> bool:
    """Return true only for an explicit human-education context."""
    return bool(matching_terms(combined, EDUCATION_CONTEXT_TERMS))


def category_matches(title: str, description: str) -> list[tuple[int, str, list[str]]]:
    combined = f"{title} {description}".casefold()
    title_folded = title.casefold()
    results: list[tuple[int, str, list[str]]] = []
    for category, terms in CATEGORY_TERMS.items():
        all_hits = matching_terms(combined, terms)
        if not all_hits:
            continue
        if category == "Освіта":
            # Require an explicit human-education context; technical ML learning is not enough.
            if not matching_terms(combined, EDUCATION_CONTEXT_TERMS):
                continue
        elif category == "Надійність ШІ":
            if not matching_terms(combined, RELIABILITY_STRONG_TERMS):
                continue
        elif category == "Екологія":
            if not matching_terms(combined, ECOLOGY_STRONG_TERMS):
                continue
        elif category == "Наука і технології":
            if not matching_terms(combined, SCIENCE_TECH_STRONG_TERMS):
                continue
        title_hits = matching_terms(title_folded, terms)
        score = len(set(all_hits)) + 3 * len(set(title_hits))
        results.append((score, category, all_hits))
    results.sort(key=lambda row: row[0], reverse=True)
    return results

def assess_relevance(item: dict[str, str], feed: dict[str, object]) -> dict[str, object]:
    title = item.get("title", "")
    description = item.get("description", "")
    combined = f"{title} {description}".casefold()

    exclusion = find_exclusion(combined)
    if exclusion:
        return {"accepted": False, "reason": f"відсів: {exclusion}", "category": "", "evidenceLevel": ""}

    # AI is required only for AI-specialist feeds. Institutional/domain feeds may
    # publish valuable non-AI work in health, education, environment and science.
    requires_ai = bool(feed.get("requires_ai", False))
    if requires_ai and not matching_terms(combined, AI_TERMS):
        return {"accepted": False, "reason": "немає чіткого зв'язку зі штучним інтелектом для спеціалізованої AI-стрічки", "category": "", "evidenceLevel": ""}

    matches = category_matches(title, description)
    if not matches:
        return {"accepted": False, "reason": "не виявлено достатньо чіткого напряму користі для людей", "category": "", "evidenceLevel": ""}

    # When two domains have almost equal evidence, do not guess a category.
    if len(matches) > 1 and matches[1][0] >= matches[0][0] - 1:
        names = " / ".join((matches[0][1], matches[1][1]))
        return {"accepted": False, "reason": f"неоднозначна тематика: {names}; потрібна редакційна перевірка", "category": "", "evidenceLevel": ""}

    _, category, domain_hits = matches[0]
    utility_hits = matching_terms(combined, UTILITY_TERMS)
    if not utility_hits:
        return {
            "accepted": False,
            "reason": f"визначено напрям «{category}», але немає достатніх ознак застосування, оцінювання або суспільної користі",
            "category": category,
            "evidenceLevel": "",
        }

    title_domain_hits = matching_terms(title.casefold(), CATEGORY_TERMS[category])
    if not title_domain_hits and len(set(domain_hits)) < 2:
        return {
            "accepted": False,
            "reason": f"недостатньо чіткий зв'язок із напрямом «{category}»",
            "category": category,
            "evidenceLevel": "",
        }

    concrete = [
        "clinical validation", "clinical trial", "diagnostic accuracy", "real-world",
        "deployment", "deployed", "field study", "validated", "early detection",
        "forecast", "forecasting", "monitoring", "observation", "navigation system",
        "technology demonstration", "field campaign", "earth observation", "remote sensing",
        "decision support", "curriculum-aligned", "public service", "human oversight",
        "auditable", "accessibility", "assistive technology", "renewable energy",
        "water quality", "crop yield", "disaster response", "poverty reduction",
    ]
    evaluated = [
        "benchmark", "benchmarks", "evaluation", "evaluating", "assessment", "dataset",
        "information retrieval", "measure", "measuring", "audit", "controlled comparison",
        "forecast", "forecasting", "diagnostic", "clinical note",
    ]
    if matching_terms(combined, concrete):
        evidence_level = "практичне застосування або конкретний приклад"
    elif matching_terms(combined, evaluated):
        evidence_level = "дослідження або оцінювання потенційного застосування"
    else:
        evidence_level = "перспективне дослідження; практичний ефект ще потрібно перевірити"

    reasons = ", ".join(utility_hits[:3])
    return {
        "accepted": True,
        "reason": f"напрям: {category}; ознаки користі: {reasons}",
        "category": category,
        "evidenceLevel": evidence_level,
    }

def is_relevant(item: dict[str, str], feed: dict[str, object]) -> bool:
    return bool(assess_relevance(item, feed)["accepted"])


def fetch_feed(feed: dict[str, object]) -> list[dict[str, str]]:
    request = urllib.request.Request(
        str(feed["url"]),
        headers={"User-Agent": "LiudianeMaibutnie-RSSBot/2.6 (+https://github.com/)",
                 "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        content = response.read(2_500_000)
    return get_entries(content)


def article_from(item: dict[str, str], feed: dict[str, object], published: datetime, assessment: dict[str, object]) -> dict[str, object]:
    title = item["title"][:180]
    description = item["description"][:4000]
    category = str(assessment["category"])
    short_summary = description[:360].rstrip()
    if len(description) > 360:
        short_summary = short_summary.rsplit(" ", 1)[0] + "…"
    if not short_summary:
        short_summary = "Відкрийте першоджерело, щоб прочитати опис матеріалу та перевірити його контекст."
    body_parts = [
        f"Матеріал автоматично відібрано зі стрічки {feed['publisher']}. Заголовок, дата та опис отримані з RSS-каналу видавця.",
    ]
    if description:
        body_parts.append("Короткий опис від першоджерела:\n" + description)
    body_parts.append(
        f"Редакційна класифікація: {assessment['reason']}. Рівень свідчень: {assessment['evidenceLevel']}. "
        "Це автоматичний тематичний відбір за правилами, а не підтвердження ефективності чи незалежна експертна оцінка. Прочитайте оригінальну публікацію перед висновками."
    )
    if feed.get("preprint"):
        body_parts.append("Науковий статус: arXiv є репозитарієм препринтів. Розміщення роботи там саме по собі не означає, що вона пройшла незалежне рецензування. Перевіряйте статус публікації в першоджерелі.")
    body_parts.append("Редакційне застереження: система перевіряє RSS-метадані, дату, домен посилання та тематичні сигнали. Вона не підтверджує методологію дослідження й не замінює людську редакційну перевірку.")
    digest = hashlib.sha256(normalized_url(item["link"]).encode("utf-8")).hexdigest()[:12]
    published_date = published.date().isoformat()
    return {
        "id": f"rss-{published_date}-{digest}",
        "date": published_date,
        "autoPublished": True,
        "sourceType": "rss",
        "feedName": str(feed["name"]),
        "feedId": str(feed.get("id", "")),
        "sourceDomain": str(feed.get("domain", canonical_domain(item["link"]))),
        "filterVersion": FILTER_VERSION,
        "editorialStatus": "approved",
        "editorialDecisionSource": "automatic",
        "editorialLabel": (
            "Безпека та виклики" if category == "Надійність ШІ"
            else "Позитивний вплив" if assessment.get("evidenceLevel") == "практичне застосування або конкретний приклад"
            else "Перспективний розвиток"
        ),
        "feedKind": str(feed.get("kind", "ai_topic")),
        "sourceDescription": description,
        "selectionReason": str(assessment["reason"]),
        "evidenceLevel": str(assessment["evidenceLevel"]),
        "category": category,
        "title": title,
        "summary": short_summary,
        "body": "\n\n".join(body_parts),
        "sourceDate": published_date,
        "sources": [{"title": title, "publisher": str(feed["publisher"]), "url": item["link"], "publishedDate": published_date}],
    }


def load_existing() -> list[dict[str, object]]:
    if not ARTICLES_FILE.exists():
        return []
    try:
        data = json.loads(ARTICLES_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise RuntimeError(f"Очікувався список статей у {ARTICLES_FILE}.")
        return data
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Не вдалося прочитати {ARTICLES_FILE}: {exc}") from exc


def source_url(article: dict[str, object]) -> str:
    sources = article.get("sources", [])
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and source.get("url"):
                return str(source["url"])
    return ""


def index_fetched_entries(fetched: list[tuple[dict[str, object], dict[str, str]]]) -> dict[str, tuple[dict[str, object], dict[str, str]]]:
    index: dict[str, tuple[dict[str, object], dict[str, str]]] = {}
    for feed, row in fetched:
        link = normalized_url(row.get("link", ""), str(feed["host"]))
        if link and link not in index:
            index[link] = (feed, row)
    return index


def is_auto_rss(article: dict[str, object]) -> bool:
    return article.get("autoPublished") is True and article.get("sourceType") == "rss"


def prune_existing(
    existing: list[dict[str, object]],
    fetched_index: dict[str, tuple[dict[str, object], dict[str, str]]] | None = None,
) -> tuple[list[dict[str, object]], int, int, int, int]:
    """Reassess legacy RSS cards without deleting them.

    Existing records are never removed by editorial filtering. Accepted cards are
    marked approved; uncertain or rejected cards are retained with needs_review
    and hidden from the public list by the site UI. A current feed entry is used
    as the canonical description when available, so old and new candidates receive
    the same decision during a run.
    """
    fetched_index = fetched_index or {}
    kept: list[dict[str, object]] = []
    restored = updated = review_count = 0
    for original in existing:
        article = dict(original)
        before = json.dumps(article, ensure_ascii=False, sort_keys=True)
        if not is_auto_rss(article):
            kept.append(article)
            continue

        title = str(article.get("title", ""))
        stored_description = str(article.get("sourceDescription", "") or "")
        link = normalized_url(source_url(article))
        recovered = fetched_index.get(link)

        # A human editorial decision is authoritative until an editor explicitly
        # returns the record to automatic review. Never silently overwrite it.
        human_locked = (
            article.get("editorialDecisionSource") == "human"
            and bool(article.get("editorialReviewedAt"))
            and article.get("editorialStatus") in {"approved", "rejected", "needs_review"}
        )
        if human_locked:
            if recovered:
                recovered_feed, row = recovered
                refreshed = plain_text(row.get("description", ""))[:4000]
                if len(refreshed) >= MIN_DESCRIPTION_LENGTH and refreshed != stored_description:
                    article["sourceDescription"] = refreshed
                    article["lastSourceRefreshAt"] = datetime.now(timezone.utc).isoformat()
                    article["sourceDescription"] = refreshed
                article["feedKind"] = str(recovered_feed.get("kind", article.get("feedKind", "ai_topic")))
                article["feedName"] = str(recovered_feed.get("name", article.get("feedName", "")))
                article["feedId"] = str(recovered_feed.get("id", article.get("feedId", "")))
                article["sourceDomain"] = str(recovered_feed.get("domain", canonical_domain(source_url(article))))
            article["filterVersion"] = FILTER_VERSION
            status = str(article.get("editorialStatus"))
            print(f"[HUMAN-DECISION-KEPT] {title or 'Без назви'} — {status}; рішення редактора не змінено")
            if status == "needs_review":
                review_count += 1
            kept.append(article)
            after = json.dumps(article, ensure_ascii=False, sort_keys=True)
            if after != before:
                updated += 1
            continue
        feed: dict[str, object] = {"kind": str(article.get("feedKind") or "ai_topic")}
        canonical_title = title
        description = stored_description
        if recovered:
            recovered_feed, row = recovered
            feed = recovered_feed
            canonical_title = row.get("title") or title
            current_description = plain_text(row.get("description", ""))[:4000]
            if len(current_description) >= MIN_DESCRIPTION_LENGTH:
                if current_description != stored_description:
                    article["sourceDescription"] = current_description
                    restored += 1 if len(stored_description) < MIN_DESCRIPTION_LENGTH else 0
                description = current_description
            elif stored_description:
                description = stored_description
            article["feedKind"] = str(recovered_feed.get("kind", article.get("feedKind", "ai_topic")))
            article["feedName"] = str(recovered_feed.get("name", article.get("feedName", "")))
            article["feedId"] = str(recovered_feed.get("id", article.get("feedId", "")))
            article["sourceDomain"] = str(recovered_feed.get("domain", canonical_domain(source_url(article))))

        if len(description) < MIN_DESCRIPTION_LENGTH:
            status = "needs_review"
            reason = "немає достатнього опису першоджерела для надійної перевірки"
            article["editorialStatus"] = status
            article["editorialReviewReason"] = reason
            review_count += 1
            print(f"[REVIEW] {title or 'Без назви'} — {reason}; запис збережено")
        else:
            decision = assess_relevance({"title": canonical_title, "description": description}, feed)
            article["sourceDescription"] = description
            article["filterVersion"] = FILTER_VERSION
            if decision["accepted"]:
                article["editorialStatus"] = "approved"
                article.pop("editorialReviewReason", None)
                article["selectionReason"] = str(decision["reason"])
                article["evidenceLevel"] = str(decision["evidenceLevel"])
                article["category"] = str(decision["category"])
                print(f"[RECHECK-OK] {title or 'Без назви'} — {decision['category']}")
            else:
                article["editorialStatus"] = "needs_review"
                article["editorialReviewReason"] = str(decision["reason"])
                review_count += 1
                print(f"[REVIEW] {title or 'Без назви'} — {decision['reason']}; запис збережено")

        kept.append(article)
        after = json.dumps(article, ensure_ascii=False, sort_keys=True)
        if after != before:
            updated += 1
    return kept, 0, restored, updated, review_count


def dedupe_existing(existing: list[dict[str, object]]) -> tuple[list[dict[str, object]], int, set[str], set[str], set[str]]:
    """Flag duplicate RSS cards without deleting any library record."""
    seen_urls: set[str] = set()
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    manual = [article for article in existing if not is_auto_rss(article)]
    automatic = [article for article in existing if is_auto_rss(article)]
    # Manual articles always have priority over automatic cards with matching identity.
    for article in manual:
        url, doi, title = article_keys(article)
        if url:
            seen_urls.add(url)
        if doi:
            seen_dois.add(doi)
        if title:
            seen_titles.add(title)

    kept_auto: list[dict[str, object]] = []
    duplicate_count = 0
    for original in automatic:
        article = dict(original)
        url, doi, title = article_keys(article)
        duplicate = bool((url and url in seen_urls) or (doi and doi in seen_dois) or (title and title in seen_titles))
        human_duplicate_override = (
            article.get("editorialDuplicateOverride") is True
            and article.get("editorialDecisionSource") == "human"
            and article.get("editorialStatus") == "approved"
        )
        if duplicate and human_duplicate_override:
            print(f"[DUPLICATE-OVERRIDE] {article.get('title', 'Без назви')} — редактор перевірив збіг і залишив матеріал схваленим")
        elif duplicate:
            if article.get("editorialStatus") != "duplicate":
                duplicate_count += 1
            article["editorialStatus"] = "duplicate"
            article["editorialReviewReason"] = "дублікат іншого матеріалу в бібліотеці"
            print(f"[DUPLICATE-HELD] {article.get('title', 'Без назви')} — запис збережено, приховано з публічної стрічки")
        else:
            article["editorialStatus"] = article.get("editorialStatus") or "needs_review"
            if article["editorialStatus"] == "approved":
                article.pop("editorialReviewReason", None)
        kept_auto.append(article)
        if url:
            seen_urls.add(url)
        if doi:
            seen_dois.add(doi)
        if title:
            seen_titles.add(title)

    # Preserve the original order as much as possible: manual items first, then RSS items.
    manual_ids = {id(item) for item in manual}
    _ = manual_ids
    return manual + kept_auto, duplicate_count, seen_urls, seen_titles, seen_dois

def select_diverse_candidates(
    candidates: list[dict[str, object]],
    max_total: int = MAX_NEW_ITEMS_PER_RUN,
    max_per_domain: int = MAX_ITEMS_PER_DOMAIN_PER_RUN,
) -> tuple[list[dict[str, object]], int]:
    """Select recent items by round-robin publisher domain to avoid one-source dominance."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for candidate in candidates:
        domain = str(candidate.get("sourceDomain") or "unknown")
        grouped.setdefault(domain, []).append(candidate)
    for rows in grouped.values():
        rows.sort(key=lambda row: str(row.get("date", "")), reverse=True)
    domain_order = sorted(
        grouped,
        key=lambda domain: (
            str(grouped[domain][0].get("date", "")) if grouped[domain] else "",
            domain,
        ),
        reverse=True,
    )
    selected: list[dict[str, object]] = []
    per_domain = Counter()
    offsets = {domain: 0 for domain in domain_order}
    while len(selected) < max_total:
        progressed = False
        for domain in domain_order:
            if len(selected) >= max_total:
                break
            if per_domain[domain] >= max_per_domain:
                continue
            offset = offsets[domain]
            if offset >= len(grouped[domain]):
                continue
            selected.append(grouped[domain][offset])
            offsets[domain] += 1
            per_domain[domain] += 1
            progressed = True
        if not progressed:
            break
    return selected, max(0, len(candidates) - len(selected))


def build_source_stats(
    combined: list[dict[str, object]],
    feed_runs: list[dict[str, object]],
    totals: dict[str, int],
) -> dict[str, object]:
    """Create public, factual source statistics for the analytics dashboard."""
    by_domain: dict[str, dict[str, object]] = {}
    for article in combined:
        if not isinstance(article, dict):
            continue
        if article.get("autoPublished") and article.get("editorialStatus") != "approved":
            continue
        domain = str(article.get("sourceDomain") or canonical_domain(source_url(article)))
        if not domain:
            continue
        row = by_domain.setdefault(domain, {"domain": domain, "count": 0, "publishers": set()})
        row["count"] = int(row["count"]) + 1
        sources = article.get("sources", [])
        if isinstance(sources, list):
            for source in sources:
                if isinstance(source, dict) and source.get("publisher"):
                    row["publishers"].add(str(source["publisher"]))
    library_domains = []
    for domain, row in sorted(by_domain.items(), key=lambda item: (-int(item[1]["count"]), item[0])):
        publishers = sorted(row["publishers"])
        library_domains.append({
            "domain": domain,
            "count": int(row["count"]),
            "publishers": publishers,
        })
    return {
        "schemaVersion": 1,
        "filterVersion": FILTER_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "feedRuns": feed_runs,
        "libraryByDomain": library_domains,
        "libraryDomainCount": len(library_domains),
        "library": {
            "totalRecords": len(combined),
            "publicRecords": sum(
                1 for article in combined
                if isinstance(article, dict)
                and isinstance(article.get("title"), str)
                and isinstance(article.get("body"), str)
                and (not article.get("autoPublished") or article.get("editorialStatus") == "approved")
            ),
            "needsReview": sum(
                1 for article in combined
                if isinstance(article, dict) and article.get("editorialStatus") == "needs_review"
            ),
            "manualRecords": sum(1 for article in combined if isinstance(article, dict) and not is_auto_rss(article)),
        },
        "methodology": (
            "Кількість доменів обчислюється за першоджерелами схвалених матеріалів. "
            "Статистика RSS показує результати останнього запуску, а не доведений суспільний ефект."
        ),
    }


def write_json_atomic(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    existing_original = load_existing()
    initial_count = len(existing_original)
    manual_count = sum(1 for article in existing_original if not is_auto_rss(article))
    rss_count = initial_count - manual_count

    fetched: list[tuple[dict[str, object], dict[str, str]]] = []
    feed_runs: list[dict[str, object]] = []
    feed_run_by_id: dict[str, dict[str, object]] = {}
    success_count = fetched_count = 0
    for feed in FEEDS:
        feed_id = str(feed.get("id", feed["name"]))
        run = {
            "id": feed_id,
            "name": str(feed["name"]),
            "publisher": str(feed["publisher"]),
            "domain": str(feed.get("domain") or canonical_domain(str(feed["url"]))),
            "url": str(feed["url"]),
            "status": "error",
            "itemsFetched": 0,
            "acceptedCandidates": 0,
            "added": 0,
            "rejected": 0,
            "duplicates": 0,
            "tooOld": 0,
            "shortDescriptions": 0,
            "deferredByDiversityCap": 0,
            "rejectionReasons": {},
            "error": "",
        }
        feed_runs.append(run)
        feed_run_by_id[feed_id] = run
        try:
            rows = fetch_feed(feed)
            success_count += 1
            fetched_count += len(rows)
            run["status"] = "ok"
            run["itemsFetched"] = len(rows)
            fetched.extend((feed, row) for row in rows)
        except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError, ValueError) as exc:
            run["error"] = str(exc)[:240]
            print(f"[WARN] {feed['name']}: {exc}", file=sys.stderr)
        except Exception as exc:
            run["error"] = str(exc)[:240]
            print(f"[WARN] {feed['name']}: unexpected error: {exc}", file=sys.stderr)

    if success_count == 0:
        print("[ERROR] Не вдалося отримати жодну RSS-стрічку. Бібліотеку не змінено.", file=sys.stderr)
        return 1

    fetched_index = index_fetched_entries(fetched)
    existing, removed_existing, restored_existing, metadata_updated, review_existing = prune_existing(existing_original, fetched_index)
    existing, duplicate_existing, seen_urls, seen_titles, seen_dois = dedupe_existing(existing)

    candidates: list[dict[str, object]] = []
    rejected_count = duplicate_count = too_old_count = short_count = 0
    rejection_reasons: Counter[str] = Counter()
    # Candidate identities are reserved while scanning all feeds to prevent the same
    # article being counted twice even when it appears in more than one RSS channel.
    candidate_seen_urls = set(seen_urls)
    candidate_seen_titles = set(seen_titles)
    candidate_seen_dois = set(seen_dois)

    for feed, row_original in fetched:
        feed_id = str(feed.get("id", feed["name"]))
        feed_stats = feed_run_by_id[feed_id]
        row = dict(row_original)
        link = normalized_url(row.get("link", ""), str(feed["host"]))
        if not link:
            continue
        row["link"] = link
        row["description"] = plain_text(row.get("description", ""))
        title = row.get("title", "")
        title_fingerprint = title_key(title)
        doi = doi_key({"title": title, "summary": row.get("description", ""), "sources": [{"url": link}]})
        if link in candidate_seen_urls or (doi and doi in candidate_seen_dois) or (title_fingerprint and title_fingerprint in candidate_seen_titles):
            duplicate_count += 1
            feed_stats["duplicates"] = int(feed_stats["duplicates"]) + 1
            continue
        published = parse_date(row.get("published", ""))
        if not published or published < cutoff or published > now + timedelta(days=1):
            too_old_count += 1
            feed_stats["tooOld"] = int(feed_stats["tooOld"]) + 1
            continue
        if len(row["description"]) < MIN_DESCRIPTION_LENGTH:
            short_count += 1
            feed_stats["shortDescriptions"] = int(feed_stats["shortDescriptions"]) + 1
            reason = "короткий або відсутній опис"
            rejection_reasons[reason] += 1
            feed_reasons = feed_stats["rejectionReasons"]
            feed_reasons[reason] = int(feed_reasons.get(reason, 0)) + 1
            continue

        decision = assess_relevance(row, feed)
        # This feed row has now been assessed; reserve its identity regardless of result.
        candidate_seen_urls.add(link)
        if doi:
            candidate_seen_dois.add(doi)
        if title_fingerprint:
            candidate_seen_titles.add(title_fingerprint)
        if not decision["accepted"]:
            rejected_count += 1
            reason = str(decision["reason"])
            rejection_reasons[reason] += 1
            feed_stats["rejected"] = int(feed_stats["rejected"]) + 1
            feed_reasons = feed_stats["rejectionReasons"]
            feed_reasons[reason] = int(feed_reasons.get(reason, 0)) + 1
            continue

        article = article_from(row, feed, published, decision)
        article["sourceDomain"] = str(feed.get("domain") or canonical_domain(link))
        article["feedId"] = feed_id
        candidates.append(article)
        feed_stats["acceptedCandidates"] = int(feed_stats["acceptedCandidates"]) + 1

    selected, deferred_count = select_diverse_candidates(candidates)
    selected_ids = {str(article.get("id", "")) for article in selected}
    for article in candidates:
        if str(article.get("id", "")) not in selected_ids:
            feed_stats = feed_run_by_id[str(article.get("feedId", ""))]
            feed_stats["deferredByDiversityCap"] = int(feed_stats["deferredByDiversityCap"]) + 1
    for article in selected:
        feed_stats = feed_run_by_id[str(article.get("feedId", ""))]
        feed_stats["added"] = int(feed_stats["added"]) + 1

    additions = sorted(selected, key=lambda article: str(article["date"]), reverse=True)
    capacity = max(0, MAX_TOTAL_ITEMS - len(existing))
    if len(additions) > capacity:
        print(f"[LIMIT] Додатків скорочено з {len(additions)} до {capacity}: досягнуто ліміту бібліотеки.")
        dropped = additions[capacity:]
        deferred_count += len(dropped)
        for article in dropped:
            feed_stats = feed_run_by_id[str(article.get("feedId", ""))]
            feed_stats["added"] = max(0, int(feed_stats["added"]) - 1)
            feed_stats["deferredByDiversityCap"] = int(feed_stats["deferredByDiversityCap"]) + 1
        additions = additions[:capacity]

    combined = additions + existing
    expected_count = initial_count + len(additions)
    if len(combined) != expected_count:
        print(
            f"[ERROR] Контроль цілісності не пройдено: було {initial_count}, "
            f"додано {len(additions)}, очікується {expected_count}, отримано {len(combined)}. "
            "Бібліотеку не змінено.",
            file=sys.stderr,
        )
        return 2

    original_manual_ids = [str(a.get("id", "")) for a in existing_original if not is_auto_rss(a)]
    final_manual_ids = [str(a.get("id", "")) for a in combined if not is_auto_rss(a)]
    if sorted(original_manual_ids) != sorted(final_manual_ids):
        print("[ERROR] Контроль ручних матеріалів не пройдено. Бібліотеку не змінено.", file=sys.stderr)
        return 3

    # Build source-by-source counters from this run and the approved library.
    totals = {
        "successfulFeeds": success_count,
        "totalFeeds": len(FEEDS),
        "itemsFetched": fetched_count,
        "acceptedCandidates": len(candidates),
        "added": len(additions),
        "rejected": rejected_count,
        "duplicates": duplicate_count,
        "tooOld": too_old_count,
        "shortDescriptions": short_count,
        "deferredByDiversityCap": max(0, deferred_count),
    }
    source_stats = build_source_stats(combined, feed_runs, totals)

    print(f"Версія редакційного фільтра: {FILTER_VERSION}.")
    print(f"Перевірено RSS-стрічок: {success_count}/{len(FEEDS)}; записів у стрічках: {fetched_count}.")
    print(f"Початковий склад бібліотеки: {initial_count} (ручних: {manual_count}; автоматичних RSS: {rss_count}).")
    print(f"Оновлено редакційні метадані існуючих матеріалів: {metadata_updated}.")
    print(f"Матеріалів залишено на редакційній перевірці: {review_existing}.")
    human_decisions = sum(1 for a in existing if a.get("editorialDecisionSource") == "human")
    approved_count = sum(1 for a in existing if is_auto_rss(a) and a.get("editorialStatus") == "approved")
    rejected_library_count = sum(1 for a in existing if is_auto_rss(a) and a.get("editorialStatus") == "rejected")
    print(f"Людських редакційних рішень збережено: {human_decisions}.")
    print(f"Автоматично схвалених RSS-матеріалів у бібліотеці: {approved_count}.")
    print(f"Відхилених редактором RSS-матеріалів у бібліотеці: {rejected_library_count}.")
    print(f"Відхилено нових кандидатів за редакційними правилами: {rejected_count}.")
    print(f"Пропущено дублікатів у стрічках/бібліотеці: {duplicate_count}; позначено дублікатів у бібліотеці: {duplicate_existing}.")
    print(f"Пропущено за датою: {too_old_count}; без достатнього опису: {short_count}.")
    print(f"Відкладено через ліміт різноманітності: {max(0, deferred_count)}; максимум {MAX_ITEMS_PER_DOMAIN_PER_RUN} матеріалів на домен за запуск.")
    for reason, count in rejection_reasons.most_common(8):
        print(f" - Відхилено {count}: {reason}")

    for run in feed_runs:
        status = "OK" if run["status"] == "ok" else "ERROR"
        print(
            f"[FEED] {run['name']} | {status} | отримано: {run['itemsFetched']} | "
            f"схвалено кандидатів: {run['acceptedCandidates']} | додано: {run['added']} | "
            f"відхилено: {run['rejected']} | дублікати: {run['duplicates']}"
        )
        if run.get("error"):
            print(f"[FEED-ERROR] {run['name']}: {run['error']}")

    print(f"[SOURCES] У бібліотеці схвалених матеріалів: {source_stats['libraryDomainCount']} унікальних доменів першоджерел.")
    for domain_row in source_stats["libraryByDomain"]:
        pubs = ", ".join(domain_row["publishers"]) or domain_row["domain"]
        print(f"[SOURCE-DOMAIN] {domain_row['domain']} | {domain_row['count']} матеріал(ів) | {pubs}")

    articles_changed = combined != existing_original
    write_json_atomic(SOURCE_STATS_FILE, source_stats)
    if articles_changed:
        write_json_atomic(ARTICLES_FILE, combined)
    else:
        print(f"Бібліотека без змін: {len(combined)} запис(ів).")

    print(f"Додано {len(additions)} нових матеріал(ів). У бібліотеці тепер {len(combined)} запис(ів).")
    print(f"[INTEGRITY] Було {initial_count}; додано {len(additions)}; вилучено 0; стало {len(combined)}.")
    print(f"[INTEGRITY] Ручних матеріалів збережено: {manual_count}; жоден існуючий запис автоматично не видалено.")
    print(f"[SOURCE-STATS] Оновлено {SOURCE_STATS_FILE.relative_to(ROOT)}.")
    for article in additions:
        print(f" - {article['date']} | [{article['category']}] {article['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
