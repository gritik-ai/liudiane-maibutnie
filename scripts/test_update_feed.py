#!/usr/bin/env python3
"""Offline regression tests for the editorial RSS filter v2.7 and expanded source diversity."""
import unittest
from urllib.parse import urlparse

from update_feed import (
    assess_relevance,
    dedupe_existing,
    doi_key,
    normalized_url,
    prune_existing,
    title_key,
    canonical_domain,
    select_diverse_candidates,
    build_source_stats,
    FEEDS,
    get_entries,
    FILTER_VERSION,
    validate_feed_payload,
)

AI_FEED = {"kind": "ai_topic"}
DOMAIN_FEED = {"kind": "domain_topic", "requires_ai": True}


class EditorialFilterV27Tests(unittest.TestCase):
    def check(self, title: str, description: str = "", feed=AI_FEED):
        return assess_relevance({"title": title, "description": description}, feed)

    def test_accepts_human_education_assessment(self):
        result = self.check(
            "VeriMath: Human-in-the-Loop Generation and Verification of Curriculum-Aligned Mathematics Assessment Items",
            "The system generates and verifies curriculum-aligned mathematics assessment items for school students and teachers.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Освіта")

    def test_does_not_classify_open_world_machine_learning_as_education(self):
        result = self.check(
            "OpenKAGE: Open-Ended Lifelong Learning in the Open World via Knowledge-Sharing Agent-Group Evolution",
            "This paper studies lifelong learning in autonomous machine-learning agents and knowledge sharing between models.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Освіта")

    def test_does_not_classify_curriculum_learning_for_llm_as_human_education(self):
        result = self.check(
            "Depth Before Breadth: Reverse-to-Forward Curriculum with Advantage Decomposition for LLM Agent",
            "The method changes curriculum learning and training order for reinforcement-learning agents.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Освіта")

    def test_does_not_classify_robot_skill_adaptation_as_education(self):
        result = self.check(
            "Reconfiguring Procedural Knowledge for Compositional Robot Skill Adaptation",
            "The method adapts robot skills through procedural knowledge and reinforcement learning.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Освіта")

    def test_does_not_classify_befit_sensing_as_education(self):
        result = self.check(
            "BeFit: Shifting Complexity from Weights to Bernstein Activations for Resource-Constrained Sensing",
            "The paper evaluates a machine learning model for efficient sensing on constrained devices.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Освіта")

    def test_does_not_classify_banking_environments_as_ecology(self):
        result = self.check(
            "ATLAS-Finance: Benchmarking AI Agents in Realistic Banking Environments",
            "The benchmark evaluates agents in realistic banking environments.",
        )
        self.assertNotEqual(result["category"], "Екологія")

    def test_does_not_classify_ai_ecosystem_as_natural_ecology(self):
        result = self.check(
            "Mapping the AI Supply Chain: Dependencies, Vulnerabilities, and Market Concentration in the AI Ecosystem",
            "The paper maps dependencies and market concentration in the artificial intelligence supply chain ecosystem.",
        )
        self.assertNotEqual(result["category"], "Екологія")

    def test_accepts_patient_oriented_medical_benchmark(self):
        result = self.check(
            "MedGuardBench: A Patient-Oriented Benchmark for Personalized Guardrail Development",
            "A benchmark evaluates patient-oriented safeguards for personalized clinical AI systems.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Медицина")

    def test_accepts_clinical_dataset_for_information_retrieval(self):
        result = self.check(
            "LusoClin: A Synthetic Clinical Note Dataset for Medical Information Retrieval",
            "The dataset supports evaluation of medical information retrieval from clinical notes.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Медицина")

    def test_accepts_climate_prediction_with_human_utility(self):
        result = self.check(
            "Trustworthy AI models improve climate prediction",
            "The method enables faster climate forecasting to support adaptation planning.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Екологія")

    def test_rejects_military_application(self):
        result = self.check(
            "AI-assisted military target recognition",
            "A machine learning method improves battlefield target recognition.",
        )
        self.assertFalse(result["accepted"])

    def test_rejects_sabotage_topic(self):
        result = self.check(
            "Methods to Execute Sabotage and Evade Detection in AI Safety Reviews",
            "The paper describes methods to execute sabotage and evade detection.",
        )
        self.assertFalse(result["accepted"])

    def test_accepts_auditing_research_that_helps_detect_sabotage(self):
        result = self.check(
            "Auditors Struggle to Catch Sabotage in End-to-End Transcripts of AI Safety Research",
            "The study evaluates auditors and methods to detect sabotage in AI safety research transcripts.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Надійність ШІ")

    def test_does_not_classify_generic_multimodal_alignment_as_ai_reliability(self):
        result = self.check(
            "From Points to Trajectories: Rethinking Multimodal Alignment for Physical Events",
            "The paper studies alignment between visual and motion representations.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Надійність ШІ")

    def test_accepts_ai_safety_alignment(self):
        result = self.check(
            "DACE: Diversity-Driven Adversarial Co-Evolution for Robust LLM Safety Alignment",
            "The method evaluates safety alignment and robustness of large language models.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Надійність ШІ")

    def test_accepts_bias_audit_as_reliability_topic(self):
        result = self.check(
            "Once Upon a Bias: Gender Stereotyping in LLM-Generated Children's Stories",
            "The study audits gender stereotyping and harmful bias in outputs from language models.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Надійність ШІ")

    def test_accepts_clinical_ner_comparison_as_research_potential(self):
        result = self.check(
            "Fine-Grained Japanese Clinical Named Entity Recognition: A Controlled Comparison of BERT and Open-Weight Large Language Models",
            "A controlled comparison evaluates named entity recognition methods for clinical text processing.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Медицина")

    def test_classifies_sleep_apnea_research_as_medicine(self):
        result = self.check(
            "From Real to Synthetic: PSG-GAN Learns Sleep Apnea Signal Dynamics for AI Training",
            "The synthetic dataset models sleep apnea signals to support medical research and evaluation.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Медицина")

    def test_accepts_public_regulatory_oversight(self):
        result = self.check(
            "Honest Brokers in AI Regulation: How Public Comments Introduce Evidence to Regulators",
            "Public comments introduce evidence to regulators and strengthen public oversight and accountability in AI regulation.",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Державне управління")

    def test_does_not_treat_technical_agent_governance_as_public_administration(self):
        result = self.check(
            "RegimeCouncil: Paired-Evidence Routing for Memory Conflict Governance in LLM Agents",
            "This method studies governance of memory conflicts in language-model agents.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Державне управління")

    def test_domain_feed_requires_ai_mention(self):
        result = self.check(
            "A new approach improves cancer screening",
            "The clinical method improves early detection of cancer.",
            DOMAIN_FEED,
        )
        self.assertFalse(result["accepted"])

    def test_domain_feed_accepts_ai_health_application(self):
        result = self.check(
            "Machine learning improves cancer screening",
            "The AI-supported clinical method improves early detection for patients.",
            DOMAIN_FEED,
        )
        self.assertTrue(result["accepted"])

    def test_institutional_health_feed_does_not_require_ai(self):
        feed = {"kind": "institutional", "requires_ai": False}
        result = self.check(
            "Public health programme expands cancer screening",
            "The programme supports early detection and improves access to screening for patients.",
            feed,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Медицина")

    def test_nasa_space_technology_without_ai_is_accepted(self):
        feed = {"kind": "institutional", "requires_ai": False}
        result = self.check(
            "Space technology demonstration improves spacecraft navigation",
            "A technology demonstration tests a navigation system and measures accuracy for future space missions.",
            feed,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Наука і технології")

    def test_noaa_climate_monitoring_without_ai_is_accepted(self):
        feed = {"kind": "institutional", "requires_ai": False}
        result = self.check(
            "Climate change monitoring supports coastal adaptation",
            "Environmental monitoring and forecasting measure long-term climate conditions and support adaptation planning for coastal communities.",
            feed,
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["category"], "Екологія")

    def test_nasa_lifelong_machine_learning_not_misclassified_as_education(self):
        feed = {"kind": "institutional", "requires_ai": False}
        result = self.check(
            "Spacecraft navigation system improves orbital observation",
            "The system measures spacecraft position and supports navigation during a technology demonstration.",
            feed,
        )
        self.assertNotEqual(result.get("category"), "Освіта")

    def test_expected_root_host_allows_official_subdomains(self):
        self.assertEqual(
            normalized_url("https://news.mit.edu/2026/ai-study", "mit.edu"),
            "https://news.mit.edu/2026/ai-study",
        )
        self.assertEqual(
            normalized_url("https://oceanservice.noaa.gov/rss/nosnews.xml", "noaa.gov"),
            "https://oceanservice.noaa.gov/rss/nosnews.xml",
        )
        self.assertEqual(normalized_url("https://example.org/article", "noaa.gov"), "")

    def test_normalizes_tracking_parameters_and_fragment(self):
        self.assertEqual(
            normalized_url("https://arxiv.org/abs/1234.5678?utm_source=rss#abstract"),
            "https://arxiv.org/abs/1234.5678",
        )

    def test_extracts_doi_from_source_url(self):
        article = {"title": "A study", "sources": [{"url": "https://doi.org/10.1234/AbC-567"}]}
        self.assertEqual(doi_key(article), "10.1234/abc-567")

    def test_restores_legacy_description_and_marks_approved(self):
        legacy = {
            "id": "legacy-1", "autoPublished": True, "sourceType": "rss",
            "title": "AI tool helps doctors detect cancer earlier",
            "summary": "Short summary only.", "category": "Медицина",
            "sources": [{"publisher": "arXiv", "url": "https://arxiv.org/abs/1234.5678"}],
        }
        feed = {"kind": "ai_topic", "name": "arXiv — Штучний інтелект", "publisher": "arXiv", "host": "arxiv.org"}
        row = {
            "title": legacy["title"], "link": "https://arxiv.org/abs/1234.5678",
            "description": "A clinical tool supports early cancer detection and may improve patient care through evaluation of diagnostic assistance.",
        }
        kept, removed, restored, updated, review = prune_existing([legacy], {normalized_url(row["link"]): (feed, row)})
        self.assertEqual(removed, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("sourceDescription", kept[0])
        self.assertEqual(kept[0]["filterVersion"], FILTER_VERSION)
        self.assertEqual(kept[0]["editorialStatus"], "approved")
        self.assertEqual(review, 0)
        self.assertGreaterEqual(updated, 1)

    def test_rejected_existing_article_is_retained_for_review_not_deleted(self):
        legacy = {
            "id": "legacy-bad", "autoPublished": True, "sourceType": "rss",
            "title": "Open-world model learning method",
            "sourceDescription": "This paper studies lifelong learning in autonomous machine-learning agents.",
            "sources": [{"url": "https://arxiv.org/abs/1234.9999"}],
        }
        kept, removed, restored, updated, review = prune_existing([legacy], {})
        self.assertEqual(len(kept), 1)
        self.assertEqual(removed, 0)
        self.assertEqual(kept[0]["editorialStatus"], "needs_review")
        self.assertTrue(kept[0].get("editorialReviewReason"))
        self.assertEqual(review, 1)

    def test_keeps_legacy_card_when_description_cannot_be_recovered(self):
        legacy = {
            "id": "legacy-2", "autoPublished": True, "sourceType": "rss",
            "title": "Older card", "summary": "Short excerpt.",
            "sources": [{"url": "https://arxiv.org/abs/missing"}],
        }
        kept, removed, restored, updated, review = prune_existing([legacy], {})
        self.assertEqual(len(kept), 1)
        self.assertEqual((removed, restored, updated), (0, 0, 1))
        self.assertEqual(kept[0]["editorialStatus"], "needs_review")
        self.assertEqual(review, 1)

    def test_duplicate_rss_records_are_flagged_not_deleted(self):
        a = {"id": "a", "autoPublished": True, "sourceType": "rss", "title": "Paper A", "editorialStatus": "approved", "sources": [{"url": "https://example.org/a?utm_source=rss"}]}
        b = {"id": "b", "autoPublished": True, "sourceType": "rss", "title": "Paper B", "editorialStatus": "approved", "sources": [{"url": "https://example.org/a"}]}
        kept, duplicate_count, seen_urls, seen_titles, seen_dois = dedupe_existing([a, b])
        self.assertEqual(len(kept), 2)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(kept[1]["editorialStatus"], "duplicate")

    def test_dedupe_never_hides_or_deletes_manual_content(self):
        manual = {"id": "manual", "title": "Same title", "body": "Human-written article."}
        rss = {"id": "rss", "autoPublished": True, "sourceType": "rss", "title": "Same title", "sources": [{"url": "https://example.org/a"}]}
        kept, duplicate_count, *_ = dedupe_existing([rss, manual])
        self.assertEqual(len(kept), 2)
        manual_kept = next(a for a in kept if a["id"] == "manual")
        rss_kept = next(a for a in kept if a["id"] == "rss")
        self.assertNotIn("editorialStatus", manual_kept)
        self.assertEqual(rss_kept["editorialStatus"], "duplicate")

    def test_manual_records_are_not_modified_by_prune(self):
        manual = {"id": "manual-1", "title": "Manual article", "body": "Written by editor."}
        kept, removed, restored, updated, review = prune_existing([manual], {})
        self.assertEqual(kept, [manual])
        self.assertEqual((removed, restored, updated, review), (0, 0, 0, 0))

    def test_duplicate_doi_is_flagged_without_deleting_record(self):
        a = {"id": "doi-a", "autoPublished": True, "sourceType": "rss", "title": "Paper A", "editorialStatus": "approved", "sources": [{"url": "https://doi.org/10.5555/abc.2026"}]}
        b = {"id": "doi-b", "autoPublished": True, "sourceType": "rss", "title": "Paper B", "editorialStatus": "approved", "sources": [{"url": "https://publisher.example/article/2", "title": "DOI 10.5555/abc.2026"}]}
        kept, duplicate_count, *_ = dedupe_existing([a, b])
        self.assertEqual(len(kept), 2)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(kept[1]["editorialStatus"], "duplicate")

    def test_education_requires_human_audience_not_only_curriculum_word(self):
        result = self.check(
            "Curriculum Optimization for Language Model Agents",
            "The paper optimizes curriculum learning schedules for machine-learning agents.",
        )
        self.assertFalse(result["accepted"])
        self.assertNotEqual(result["category"], "Освіта")

    def test_existing_record_and_new_candidate_use_same_decision(self):
        title = "AI tool helps doctors detect cancer earlier"
        description = "A clinical tool supports early cancer detection and may improve patient care through evaluation of diagnostic assistance."
        link = "https://arxiv.org/abs/1234.5678"
        feed = {"kind": "ai_topic", "name": "arXiv AI", "publisher": "arXiv", "host": "arxiv.org"}
        legacy = {
            "id": "legacy-same", "autoPublished": True, "sourceType": "rss", "title": title,
            "sourceDescription": description, "sources": [{"publisher": "arXiv", "url": link}],
        }
        expected = assess_relevance({"title": title, "description": description}, feed)
        kept, _, _, _, _ = prune_existing([legacy], {normalized_url(link): (feed, {"title": title, "link": link, "description": description})})
        self.assertEqual(kept[0]["editorialStatus"], "approved" if expected["accepted"] else "needs_review")


    def test_human_approved_decision_is_not_overwritten_by_automatic_recheck(self):
        article = {
            "id": "human-approved", "autoPublished": True, "sourceType": "rss",
            "title": "A title with limited category cues", "sourceDescription": "A full source description with enough content to review manually.",
            "editorialStatus": "approved", "editorialDecisionSource": "human",
            "editorialReviewedAt": "2026-11-20T08:00:00+00:00", "editorialReviewedBy": "Editor",
            "editorialNote": "Checked original source and context.", "category": "Права людини",
            "sources": [{"url": "https://arxiv.org/abs/9999.0001"}],
        }
        kept, *_ = prune_existing([article], {})
        self.assertEqual(kept[0]["editorialStatus"], "approved")
        self.assertEqual(kept[0]["category"], "Права людини")
        self.assertEqual(kept[0]["editorialDecisionSource"], "human")
        self.assertEqual(kept[0]["editorialNote"], "Checked original source and context.")

    def test_human_rejected_decision_is_not_overwritten_by_automatic_recheck(self):
        article = {
            "id": "human-rejected", "autoPublished": True, "sourceType": "rss",
            "title": "AI tool helps doctors detect cancer earlier",
            "sourceDescription": "A clinical tool supports early cancer detection and may improve patient care through evaluation of diagnostic assistance.",
            "editorialStatus": "rejected", "editorialDecisionSource": "human",
            "editorialReviewedAt": "2026-11-20T08:00:00+00:00", "editorialReviewedBy": "Editor",
            "editorialNote": "The source does not support the headline claim.",
            "sources": [{"url": "https://arxiv.org/abs/9999.0002"}],
        }
        kept, *_ = prune_existing([article], {})
        self.assertEqual(kept[0]["editorialStatus"], "rejected")
        self.assertEqual(kept[0]["editorialNote"], "The source does not support the headline claim.")

    def test_human_needs_review_decision_remains_pending(self):
        article = {
            "id": "human-pending", "autoPublished": True, "sourceType": "rss",
            "title": "AI tool helps doctors detect cancer earlier",
            "sourceDescription": "A clinical tool supports early cancer detection and may improve patient care through evaluation of diagnostic assistance.",
            "editorialStatus": "needs_review", "editorialDecisionSource": "human",
            "editorialReviewedAt": "2026-11-20T08:00:00+00:00", "editorialReviewedBy": "Editor",
            "editorialNote": "Waiting for full paper.",
            "sources": [{"url": "https://arxiv.org/abs/9999.0003"}],
        }
        kept, *_ = prune_existing([article], {})
        self.assertEqual(kept[0]["editorialStatus"], "needs_review")
        self.assertEqual(kept[0]["editorialNote"], "Waiting for full paper.")

    def test_automatic_record_is_published_without_human_review(self):
        feed = {"name": "arXiv AI", "publisher": "arXiv", "kind": "ai_topic", "preprint": True}
        row = {
            "title": "AI tool helps doctors detect cancer earlier",
            "description": "A clinical tool supports early cancer detection and may improve patient care through evaluation of diagnostic assistance.",
            "link": "https://arxiv.org/abs/9999.0004",
        }
        assessment = self.check(row["title"], row["description"])
        self.assertTrue(assessment["accepted"])
        from update_feed import article_from
        article = article_from(row, feed, __import__("datetime").datetime(2026, 11, 20, tzinfo=__import__("datetime").timezone.utc), assessment)
        self.assertTrue(article["autoPublished"])
        self.assertEqual(article["editorialStatus"], "approved")
        self.assertEqual(article["editorialDecisionSource"], "automatic")
        self.assertIn(article["editorialLabel"], {"Позитивний вплив", "Перспективний розвиток", "Безпека та виклики"})


    def test_manually_approved_duplicate_override_survives_dedupe(self):
        a = {
            "id": "editorial-choice", "autoPublished": True, "sourceType": "rss",
            "title": "Same Paper", "sources": [{"url": "https://example.org/paper"}],
            "editorialStatus": "approved", "editorialDecisionSource": "human",
            "editorialReviewedAt": "2026-11-20T08:00:00+00:00", "editorialDuplicateOverride": True,
        }
        b = {
            "id": "duplicate-copy", "autoPublished": True, "sourceType": "rss",
            "title": "Same Paper", "sources": [{"url": "https://example.org/paper?utm_source=rss"}],
            "editorialStatus": "approved", "editorialDecisionSource": "automatic",
        }
        kept, duplicate_count, *_ = dedupe_existing([a, b])
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0]["editorialStatus"], "approved")
        self.assertEqual(kept[1]["editorialStatus"], "duplicate")
        self.assertEqual(duplicate_count, 1)

    def test_feed_payload_rejects_html_challenge_page(self):
        with self.assertRaisesRegex(ValueError, "HTML замість RSS/Atom XML"):
            validate_feed_payload(b"<!doctype html><html><body>Blocked</body></html>", "text/html")

    def test_feed_payload_rejects_oversized_response(self):
        from update_feed import MAX_FEED_BYTES
        with self.assertRaisesRegex(ValueError, "перевищує ліміт"):
            validate_feed_payload(b"x" * (MAX_FEED_BYTES + 1), "application/xml")

    def test_feed_payload_accepts_xml_with_utf8_bom(self):
        validate_feed_payload(b"\xef\xbb\xbf<?xml version='1.0'?><rss/>", "application/rss+xml")

    def test_title_key_ignores_punctuation_case(self):
        self.assertEqual(title_key("AI: A Better Future!"), title_key("ai a better future"))


    def test_feed_registry_covers_multiple_independent_publishers(self):
        domains = {str(feed.get("domain")) for feed in FEEDS}
        self.assertEqual(len(FEEDS), 27)
        self.assertTrue({
            "mit.edu", "arxiv.org", "unesco.org", "who.int", "nasa.gov", "noaa.gov",
            "un.org", "ecdc.europa.eu", "cdc.gov", "nih.gov", "copernicus.eu", "europa.eu",
        }.issubset(domains))

    def test_canonical_domains_group_subdomains(self):
        self.assertEqual(canonical_domain("https://export.arxiv.org/abs/1234.5678"), "arxiv.org")
        self.assertEqual(canonical_domain("https://science.nasa.gov/earth/"), "nasa.gov")
        self.assertEqual(canonical_domain("https://oceanservice.noaa.gov/rss/nosnews.xml"), "noaa.gov")
        self.assertEqual(canonical_domain("https://connect.unevoc.unesco.org/unevoc_news.xml"), "unesco.org")
        self.assertEqual(canonical_domain("https://news.un.org/en/story"), "un.org")
        self.assertEqual(canonical_domain("https://www.ecdc.europa.eu/en/news"), "ecdc.europa.eu")
        self.assertEqual(canonical_domain("https://wwwnc.cdc.gov/eid/article"), "cdc.gov")
        self.assertEqual(canonical_domain("https://www.niehs.nih.gov/news"), "nih.gov")
        self.assertEqual(canonical_domain("https://dataspace.copernicus.eu/news"), "copernicus.eu")
        self.assertEqual(canonical_domain("https://ec.europa.eu/eurostat"), "europa.eu")

    def test_diverse_selector_limits_each_publisher_domain(self):
        candidates = []
        for domain in ("arxiv.org", "mit.edu", "nasa.gov", "noaa.gov"):
            for i in range(5):
                candidates.append({"id": f"{domain}-{i}", "sourceDomain": domain, "date": f"2026-11-{20-i:02d}"})
        selected, deferred = select_diverse_candidates(candidates, max_total=10, max_per_domain=3)
        self.assertEqual(len(selected), 10)
        counts = {}
        for article in selected:
            domain = article["sourceDomain"]
            counts[domain] = counts.get(domain, 0) + 1
        self.assertTrue(all(value <= 3 for value in counts.values()))
        self.assertEqual(deferred, 10)

    def test_new_feed_registry_has_unique_ids_and_https_urls(self):
        ids = [str(feed["id"]) for feed in FEEDS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(str(feed["url"]).startswith("https://") for feed in FEEDS))
        for feed in FEEDS:
            parsed_host = (urlparse(str(feed["url"])).hostname or "").lower()
            expected_host = str(feed["host"]).lower()
            self.assertTrue(
                parsed_host == expected_host or parsed_host.endswith("." + expected_host),
                msg=f"Feed host mismatch for {feed['id']}: {parsed_host} vs {expected_host}",
            )

    def test_filter_version_is_27(self):
        self.assertEqual(FILTER_VERSION, "2.7")

    def test_university_and_institutional_feeds_do_not_require_ai_keyword(self):
        new_ids = {
            "un-health", "un-climate", "un-human-rights", "un-education", "un-humanitarian",
            "un-peace-security", "ecdc-news", "ecdc-publications", "cdc-eid-ahead",
            "niehs-news", "copernicus-general", "eurostat-environment-energy",
            "eurostat-science-tech", "eu-clima-news", "eu-env-news",
        }
        by_id = {str(feed["id"]): feed for feed in FEEDS}
        self.assertTrue(new_ids.issubset(by_id))
        self.assertTrue(all(by_id[feed_id]["requires_ai"] is False for feed_id in new_ids))

    def test_broken_sources_are_replaced(self):
        by_id = {str(feed["id"]): feed for feed in FEEDS}
        self.assertNotIn("nasa-jpl", by_id)
        self.assertIn("oceanfacts.xml", str(by_id["noaa-ocean"]["url"]))
        self.assertNotIn("nosnews.xml", str(by_id["noaa-ocean"]["url"]))

    def test_eurostat_atom_feed_entries_are_parsed(self):
        atom = b'''<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Energy and environment indicators</title>
            <link href="https://ec.europa.eu/eurostat/news/example" rel="alternate" />
            <updated>2026-11-24T08:00:00Z</updated>
            <summary>Official statistical update about renewable energy and environmental indicators.</summary>
          </entry>
        </feed>'''
        rows = get_entries(atom)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Energy and environment indicators")
        self.assertEqual(rows[0]["link"], "https://ec.europa.eu/eurostat/news/example")
        self.assertIn("renewable energy", rows[0]["description"])

    def test_source_stats_count_approved_library_by_canonical_domain(self):
        library = [
            {"title": "A", "body": "text", "autoPublished": True, "editorialStatus": "approved", "sourceDomain": "arxiv.org", "sources": [{"publisher": "arXiv", "url": "https://arxiv.org/abs/1"}]},
            {"title": "B", "body": "text", "autoPublished": True, "editorialStatus": "approved", "sourceDomain": "nasa.gov", "sources": [{"publisher": "NASA", "url": "https://www.nasa.gov/a"}]},
            {"title": "C", "body": "text", "autoPublished": True, "editorialStatus": "needs_review", "sourceDomain": "who.int", "sources": [{"publisher": "WHO", "url": "https://www.who.int/a"}]},
        ]
        stats = build_source_stats(library, [], {"added": 0})
        self.assertEqual(stats["libraryDomainCount"], 2)
        self.assertEqual(stats["library"]["publicRecords"], 2)
        self.assertEqual({row["domain"] for row in stats["libraryByDomain"]}, {"arxiv.org", "nasa.gov"})

if __name__ == "__main__":
    unittest.main(verbosity=2)
