"""Tests for the rule-based ATS checker."""

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
        assert len(r.warnings) == 6


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
    def test_good_bullets(self):
        lines = ["- bullet point"] * 6 + ["Normal line"]
        r = _check_formatting_hints("\n".join(lines))
        assert r.score >= 5

    def test_no_bullets(self):
        r = _check_formatting_hints("No bullet points here at all.")
        assert any("bullet" in w.lower() for w in r.warnings)


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
