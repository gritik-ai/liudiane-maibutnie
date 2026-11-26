#!/usr/bin/env python3
"""Regression tests for static SEO pages, sitemap and robots.txt."""

import unittest
import xml.etree.ElementTree as ET

from build_site import (
    SITE_URL,
    article_slug,
    article_url,
    build_outputs,
    is_public_article,
    public_articles,
    render_article_page,
    render_robots,
    render_sitemap,
    safe_source_url,
    ARCHIVE_PAGE_SIZE,
    TOPIC_GUIDES,
    render_archive_page,
    render_topics_index,
    topic_articles,
    topic_for_category,
)

class BuildSiteSeoTests(unittest.TestCase):
    def sample(self, **overrides):
        article = {
            "id": "rss-2026-11-26-abcdef123456",
            "date": "2026-11-26",
            "autoPublished": True,
            "editorialStatus": "approved",
            "category": "Освіта",
            "title": "Штучний інтелект допомагає освіті",
            "summary": "Опис матеріалу для пошукової видачі.",
            "body": "Перший абзац.\n\nДругий абзац.",
            "sources": [{
                "title": "Першоджерело",
                "publisher": "Видавець",
                "url": "https://example.org/article",
            }],
        }
        article.update(overrides)
        return article

    def test_public_filter_matches_automatic_publication_policy(self):
        self.assertTrue(is_public_article(self.sample()))
        self.assertFalse(is_public_article(self.sample(editorialStatus="needs_review")))
        self.assertFalse(is_public_article(self.sample(editorialStatus="rejected")))
        self.assertTrue(is_public_article(self.sample(autoPublished=False, editorialStatus="manual")))

    def test_public_articles_excludes_hidden_rss_records(self):
        rows = [
            self.sample(id="public"),
            self.sample(id="hidden", editorialStatus="needs_review"),
            self.sample(id="manual", autoPublished=False, editorialStatus="manual"),
        ]
        self.assertEqual([row["id"] for row in public_articles(rows)], ["public", "manual"])

    def test_slug_is_ascii_readable_and_stable(self):
        article = self.sample()
        slug = article_slug(article)
        self.assertTrue(slug.startswith("shtuchnyi-intelekt-dopomahaye-osviti-"))
        self.assertTrue(slug.endswith("abcdef123456"))
        self.assertRegex(slug, r"^[a-z0-9-]+$")
        self.assertEqual(slug, article_slug(article))

    def test_article_page_has_unique_canonical_and_open_graph(self):
        article = self.sample()
        page = render_article_page(article)
        url = article_url(article)
        self.assertIn(f'<link rel="canonical" href="{url}">', page)
        self.assertIn(f'<meta property="og:url" content="{url}">', page)
        self.assertIn('property="og:type" content="article"', page)
        self.assertIn('"@type":"Article"', page)

    def test_article_page_escapes_untrusted_text(self):
        article = self.sample(title='Назва <script>alert("x")</script>', summary='Опис <b>не HTML</b>')
        page = render_article_page(article)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;b&gt;не HTML&lt;/b&gt;", page)

    def test_article_page_uses_only_https_source_links(self):
        article = self.sample(sources=[
            {"title": "Good", "url": "https://example.org/good"},
            {"title": "Bad", "url": "javascript:alert(1)"},
        ])
        page = render_article_page(article)
        self.assertIn("https://example.org/good", page)
        self.assertNotIn("javascript:alert", page)

    def test_sitemap_contains_only_public_canonical_urls(self):
        rows = [
            self.sample(id="public-one"),
            self.sample(id="hidden-one", editorialStatus="needs_review"),
        ]
        sitemap = render_sitemap(rows)
        root = ET.fromstring(sitemap)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text for node in root.findall("sm:url/sm:loc", ns)]
        self.assertIn(SITE_URL + "/", urls)
        self.assertIn(SITE_URL + "/analytics.html", urls)
        self.assertIn(SITE_URL + "/action-lab.html", urls)
        self.assertIn(article_url(rows[0]), urls)
        self.assertNotIn(article_url(rows[1]), urls)
        self.assertEqual(len(urls), len(set(urls)))

    def test_robots_points_to_absolute_sitemap(self):
        robots = render_robots()
        self.assertIn("User-agent: *", robots)
        self.assertIn("Allow: /", robots)
        self.assertIn(f"Sitemap: {SITE_URL}/sitemap.xml", robots)

    def test_build_outputs_contains_generated_page_for_each_public_article(self):
        rows = [
            self.sample(id="visible-one"),
            self.sample(id="visible-two", title="Інша стаття"),
            self.sample(id="hidden-one", editorialStatus="needs_review"),
        ]
        outputs = build_outputs(rows)
        self.assertIn("sitemap.xml", outputs)
        self.assertIn("robots.txt", outputs)
        self.assertEqual(len([key for key in outputs if key.startswith("articles/")]), 2)


    def test_topic_hubs_are_generated_only_for_categories_with_enough_articles(self):
        rows = [
            self.sample(id="one", category="Медицина"),
            self.sample(id="two", category="Медицина", title="Інша медична стаття"),
            self.sample(id="three", category="Медицина", title="Третя медична стаття"),
            self.sample(id="four", category="Медицина", title="Четверта медична стаття"),
            self.sample(id="thin", category="Права людини"),
        ]
        outputs = build_outputs(rows)
        self.assertIn("topics/medytsyna/index.html", outputs)
        self.assertNotIn("topics/prava-lyudyny/index.html", outputs)
        self.assertIn("штучний інтелект у медицині", outputs["topics/medytsyna/index.html"])

    def test_article_page_links_to_topic_hub_and_shows_semantic_terms(self):
        page = render_article_page(self.sample(category="Медицина"))
        self.assertIn('/topics/medytsyna/', page)
        self.assertIn("цифрова медицина", page)

    def test_sitemap_contains_topic_hubs(self):
        rows = [self.sample(id=str(i), category="Медицина", title=f"Медична стаття {i}") for i in range(4)]
        self.assertIn(SITE_URL + "/topics/medytsyna/", render_sitemap(rows))

    def test_source_url_validation(self):
        self.assertEqual(safe_source_url("https://example.org/path"), "https://example.org/path")
        self.assertEqual(safe_source_url("http://example.org/path"), "")
        self.assertEqual(safe_source_url("javascript:alert(1)"), "")


    def test_broad_topics_map_existing_categories_without_renaming_them(self):
        self.assertEqual(topic_for_category("Міський розвиток"), "mista-arkhitektura")
        self.assertEqual(topic_for_category("Міська мобільність"), "mista-arkhitektura")
        self.assertEqual(topic_for_category("Надійність ШІ"), "shi")
        self.assertEqual(topic_for_category("Медицина"), "medytsyna")
        self.assertEqual(topic_for_category("Невідома категорія"), "")

    def test_topics_index_and_hub_group_related_categories(self):
        rows = [
            self.sample(id="city-a", category="Міський розвиток"),
            self.sample(id="city-b", category="Міська мобільність", title="Транспорт для людей"),
            self.sample(id="ai-a", category="Надійність ШІ"),
        ]
        grouped = topic_articles("mista-arkhitektura", rows)
        self.assertEqual({a["id"] for a in grouped}, {"city-a", "city-b"})
        index = render_topics_index(rows)
        self.assertIn("/topics/mista-arkhitektura/", index)
        self.assertIn("2 матеріалів", index)

    def test_archive_pages_are_static_crawlable_and_paginated(self):
        rows = [self.sample(id=f"article-{i}", title=f"Матеріал {i}") for i in range(ARCHIVE_PAGE_SIZE + 1)]
        first = render_archive_page(rows, 1, 2)
        second = render_archive_page(rows, 2, 2)
        self.assertIn('rel="next" href="/articles/page/2/"', first)
        self.assertIn('rel="prev" href="/articles/"', second)
        self.assertIn('href="' + article_url(rows[0]) + '"', first)
        self.assertIn('href="' + article_url(rows[-1]) + '"', second)
        self.assertIn('<link rel="canonical" href="' + SITE_URL + '/articles/page/2/">', second)

    def test_build_outputs_generates_topic_overview_and_archive_pages(self):
        rows = [self.sample(id=f"entry-{i}", title=f"Стаття {i}") for i in range(ARCHIVE_PAGE_SIZE + 2)]
        outputs = build_outputs(rows)
        self.assertIn("topics/index.html", outputs)
        self.assertIn("topics/osvita/index.html", outputs)
        self.assertIn("articles/index.html", outputs)
        self.assertIn("articles/page/2/index.html", outputs)
        self.assertIn(SITE_URL + "/articles/page/2/", outputs["sitemap.xml"])


if __name__ == "__main__":
    unittest.main()
