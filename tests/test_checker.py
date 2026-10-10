"""Tests for the rule-based ATS checker."""

import pytest

from ats_checker.checker import (
    _check_action_verbs,
    _check_contact_info,
    _check_formatting_hints,
    _check_length,
    _check_quantifiable_results,
    _check_sections,
    _check_skills_keywords,
    analyse_resume,
)


class TestContactInfo:
    def test_all_present(self):
        text = "me@mail.com (555) 123-4567 linkedin.com/in/johndoe"
        r = _check_contact_info(text)
        assert r.score == 15
        assert len(r.warnings) == 0

    def test_missing_all(self):
        r = _check_contact_info("nothing useful here")
        assert r.score == 0
        assert len(r.warnings) == 3

    def test_partial(self):
        r = _check_contact_info("me@mail.com and nothing else")
        assert r.score == 5
        assert len(r.passed) == 1


class TestSections:
    def test_all_sections(self, good_resume_text: str):
        r = _check_sections(good_resume_text)
        assert r.score == r.max_score

    def test_no_sections(self, bare_resume_text: str):
        r = _check_sections(bare_resume_text)
        assert r.score == 0
        assert len(r.warnings) == 3  # only required sections warn

    def test_optional_sections_no_warning(self):
        text = "Experience\nEducation\nSkills"
        r = _check_sections(text)
        assert len(r.warnings) == 0
        assert r.score == r.max_score


class TestActionVerbs:
    def test_many_verbs(self, good_resume_text: str):
        r = _check_action_verbs(good_resume_text)
        assert r.score >= 10

    def test_no_verbs(self):
        r = _check_action_verbs("I did things at my job for a while.")
        assert r.score == 0
        assert len(r.warnings) == 1


class TestQuantifiableResults:
    def test_strong_metrics(self, good_resume_text: str):
        r = _check_quantifiable_results(good_resume_text)
        assert r.score == 15

    def test_no_metrics(self):
        r = _check_quantifiable_results("I worked on projects and helped the team.")
        assert r.score == 0


class TestLength:
    def test_good_length(self):
        text = "word " * 500
        r = _check_length(text)
        assert r.score == 10

    def test_too_short(self):
        r = _check_length("short")
        assert r.score == 3

    def test_too_long(self):
        text = "word " * 1500
        r = _check_length(text)
        assert r.score == 4


class TestFormattingHints:
    def test_bullet_points_add_formatting_credit(self):
        lines = ["Delivered a project"] * 6
        plain = _check_formatting_hints("\n".join(lines))
        bulleted = _check_formatting_hints("\n".join(f"- {line}" for line in lines))
        assert bulleted.score == plain.score + 5


class TestSkillsKeywords:
    def test_skills_present(self):
        text = "Skills\nPython, Java, SQL, AWS, Docker, Kubernetes"
        r = _check_skills_keywords(text)
        assert r.score == 10

    def test_skills_absent(self):
        r = _check_skills_keywords("No relevant section here.")
        assert r.score == 0


class TestAnalyseResume:
    def test_returns_all_checks(self, good_resume_text: str):
        report = analyse_resume(good_resume_text)
        assert len(report.checks) == 7
        assert 0 <= report.overall_score <= 100

    def test_score_is_sum_of_checks(self, good_resume_text: str):
        report = analyse_resume(good_resume_text)
        assert report.overall_score == sum(c.score for c in report.checks)

    def test_max_scores_sum_to_100(self, good_resume_text: str):
        report = analyse_resume(good_resume_text)
        assert sum(c.max_score for c in report.checks) == 100


def test_section_keywords_in_prose_are_not_headings():
    prose = "I have experience, a degree, and communication skills, writing, music, travel."
    assert _check_sections(prose).score == 0
    assert _check_skills_keywords(prose).score == 0


def test_section_heading_aliases_use_parser_normalization():
    assert _check_sections("WORK HISTORY:\nAcademic\nSkills & Tools").score == 20


def test_action_verbs_require_whole_words_and_do_not_inflate_on_repetition():
    assert _check_action_verbs("Knowledge of SQL and skilled troubleshooting.").score == 0
    assert _check_action_verbs("Led led LED " * 10).score == 5


def test_contact_details_and_dates_are_not_achievement_metrics():
    metadata = (
        "jane@example.com | (555) 123-4567\nExperience\nCompany 2019-2021\n"
        "Education\nBS 2015-2019\nhttps://example.com/30%25\n"
    )
    assert _check_quantifiable_results(metadata).score == 0
    assert _check_quantifiable_results(metadata + "Managed a team of 8").score == 5


@pytest.mark.parametrize("achievement", [
    "Managed a team of 8", "Reduced latency by 30%", "Saved $50K annually",
    "Served 2000 clients during 2020-2022", "Reduced latency to 800ms",
    "Designed APIs serving 10M+ requests/day",
])
def test_contextual_achievement_quantities_receive_credit(achievement):
    assert _check_quantifiable_results(achievement).score == 5
