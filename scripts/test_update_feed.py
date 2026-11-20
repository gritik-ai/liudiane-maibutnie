#!/usr/bin/env python3
"""Offline regression tests for the free RSS editorial filter v2.2."""
import unittest
from update_feed import (
    assess_relevance,
    dedupe_existing,
    normalized_url,
    prune_existing,
    title_key,
)

AI_FEED = {"kind": "ai_topic"}
DOMAIN_FEED = {"kind": "domain_topic"}


class EditorialFilterV22Tests(unittest.TestCase):
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
        self.assertFalse(result["accepted"])
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

    def test_normalizes_tracking_parameters_and_fragment(self):
        self.assertEqual(
            normalized_url("https://arxiv.org/abs/1234.5678?utm_source=rss#abstract"),
            "https://arxiv.org/abs/1234.5678",
        )

    def test_restores_legacy_description_from_matching_feed_entry(self):
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
        kept, removed, restored, updated = prune_existing([legacy], {normalized_url(row["link"]): (feed, row)})
        self.assertEqual(removed, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(len(kept), 1)
        self.assertIn("sourceDescription", kept[0])
        self.assertEqual(kept[0]["filterVersion"], "2.2")
        self.assertGreaterEqual(updated, 1)

    def test_keeps_legacy_card_when_description_cannot_be_recovered(self):
        legacy = {
            "id": "legacy-2", "autoPublished": True, "sourceType": "rss",
            "title": "Older card", "summary": "Short excerpt.",
            "sources": [{"url": "https://arxiv.org/abs/missing"}],
        }
        kept, removed, restored, updated = prune_existing([legacy], {})
        self.assertEqual(len(kept), 1)
        self.assertEqual((removed, restored, updated), (0, 0, 0))

    def test_dedupe_never_deletes_manual_content(self):
        manual = {"id": "manual", "title": "Same title", "body": "Human-written article."}
        rss = {"id": "rss", "autoPublished": True, "sourceType": "rss", "title": "Same title", "sources": [{"url": "https://example.org/a"}]}
        kept, removed, _, _ = dedupe_existing([rss, manual])
        self.assertEqual(removed, 1)
        self.assertEqual([item["id"] for item in kept], ["manual"])

    def test_dedupe_collapses_duplicate_rss_urls(self):
        a = {"id": "a", "autoPublished": True, "sourceType": "rss", "title": "Paper A", "sources": [{"url": "https://example.org/a?utm_source=rss"}]}
        b = {"id": "b", "autoPublished": True, "sourceType": "rss", "title": "Paper B", "sources": [{"url": "https://example.org/a"}]}
        kept, removed, _, _ = dedupe_existing([a, b])
        self.assertEqual(removed, 1)
        self.assertEqual([item["id"] for item in kept], ["a"])

    def test_title_key_ignores_punctuation_case(self):
        self.assertEqual(title_key("AI: A Better Future!"), title_key("ai a better future"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
