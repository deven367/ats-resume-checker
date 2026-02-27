"""ATS resume checker — rule-based analysis and scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"
)
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s]+")

SECTION_KEYWORDS: dict[str, list[str]] = {
    "experience": ["experience", "work history", "employment", "professional experience"],
    "education": ["education", "academic", "qualifications", "degree"],
    "skills": ["skills", "technical skills", "core competencies", "proficiencies"],
    "summary": ["summary", "objective", "profile", "about me", "professional summary"],
    "projects": ["projects", "personal projects", "key projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}

ACTION_VERBS = [
    "achieved", "built", "created", "delivered", "designed", "developed",
    "drove", "enabled", "engineered", "established", "executed", "generated",
    "implemented", "improved", "increased", "initiated", "launched", "led",
    "managed", "mentored", "negotiated", "optimized", "orchestrated",
    "produced", "reduced", "resolved", "revamped", "scaled", "spearheaded",
    "streamlined", "supervised", "transformed",
]

QUANTIFIER_RE = re.compile(r"\d+[%$xX]|\$\d|#?\d{2,}")


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    score: int  # 0-100
    max_score: int  # weight (all weights sum to 100)
    passed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ATSReport:
    overall_score: int
    checks: list[CheckResult]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_contact_info(text: str) -> CheckResult:
    r = CheckResult(name="Contact Information", score=0, max_score=15)
    has_email = bool(EMAIL_RE.search(text))
    has_phone = bool(PHONE_RE.search(text))
    has_linkedin = bool(LINKEDIN_RE.search(text))

    points = 0
    if has_email:
        r.passed.append("Email address found.")
        points += 5
    else:
        r.warnings.append("No email address detected.")
        r.suggestions.append("Add a professional email address at the top of your resume.")

    if has_phone:
        r.passed.append("Phone number found.")
        points += 5
    else:
        r.warnings.append("No phone number detected.")
        r.suggestions.append("Include a phone number so recruiters can reach you.")

    if has_linkedin:
        r.passed.append("LinkedIn URL found.")
        points += 5
    else:
        r.warnings.append("No LinkedIn profile link detected.")
        r.suggestions.append("Add your LinkedIn profile URL (linkedin.com/in/yourname).")

    r.score = points
    return r


def _check_sections(text: str) -> CheckResult:
    r = CheckResult(name="Standard Sections", score=0, max_score=20)
    text_lower = text.lower()

    found = 0
    for section, keywords in SECTION_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            r.passed.append(f"'{section.title()}' section detected.")
            found += 1
        else:
            r.warnings.append(f"Missing '{section.title()}' section.")
            r.suggestions.append(
                f"Consider adding a clearly labelled '{section.title()}' section."
            )

    r.score = round((found / len(SECTION_KEYWORDS)) * r.max_score)
    return r


def _check_action_verbs(text: str) -> CheckResult:
    r = CheckResult(name="Action Verbs", score=0, max_score=15)
    text_lower = text.lower()
    used = [v for v in ACTION_VERBS if v in text_lower]

    if len(used) >= 8:
        r.score = 15
        r.passed.append(f"Great use of action verbs ({len(used)} found).")
    elif len(used) >= 4:
        r.score = 10
        r.passed.append(f"Decent action verb usage ({len(used)} found).")
        r.suggestions.append("Use more action verbs like: led, improved, built, scaled.")
    elif len(used) >= 1:
        r.score = 5
        r.warnings.append(f"Few action verbs found ({len(used)}).")
        r.suggestions.append(
            "Start bullet points with strong action verbs: achieved, delivered, optimized, etc."
        )
    else:
        r.warnings.append("No action verbs detected.")
        r.suggestions.append(
            "Rewrite bullet points to start with action verbs (e.g. 'Developed …', 'Led …')."
        )

    return r


def _check_quantifiable_results(text: str) -> CheckResult:
    r = CheckResult(name="Quantifiable Results", score=0, max_score=15)
    matches = QUANTIFIER_RE.findall(text)

    if len(matches) >= 5:
        r.score = 15
        r.passed.append(f"Strong use of numbers/metrics ({len(matches)} found).")
    elif len(matches) >= 2:
        r.score = 10
        r.passed.append(f"Some metrics found ({len(matches)}).")
        r.suggestions.append("Add more quantifiable results: percentages, dollar amounts, team sizes.")
    else:
        r.score = 0 if not matches else 5
        r.warnings.append("Very few or no quantifiable results.")
        r.suggestions.append(
            "Quantify your impact: 'Reduced load time by 40%', 'Managed a team of 8', etc."
        )

    return r


def _check_length(text: str) -> CheckResult:
    r = CheckResult(name="Resume Length", score=0, max_score=10)
    word_count = len(text.split())

    if 300 <= word_count <= 800:
        r.score = 10
        r.passed.append(f"Good length ({word_count} words) — fits a 1-page resume.")
    elif 200 <= word_count < 300:
        r.score = 6
        r.warnings.append(f"Resume seems short ({word_count} words).")
        r.suggestions.append("Expand your bullet points with more detail and accomplishments.")
    elif 800 < word_count <= 1200:
        r.score = 7
        r.passed.append(f"Resume is on the longer side ({word_count} words) — fine for 2 pages if senior.")
    elif word_count > 1200:
        r.score = 4
        r.warnings.append(f"Resume may be too long ({word_count} words).")
        r.suggestions.append("Trim to the most relevant experience — aim for 1-2 pages.")
    else:
        r.score = 3
        r.warnings.append(f"Very short resume ({word_count} words).")
        r.suggestions.append("Your resume appears very sparse. Add more content.")

    return r


def _check_formatting_hints(text: str) -> CheckResult:
    r = CheckResult(name="Formatting & ATS Tips", score=0, max_score=15)
    points = 0

    lines = text.strip().splitlines()
    bullet_lines = [l for l in lines if l.strip().startswith(("•", "-", "–", "▪", "●", "*"))]
    if len(bullet_lines) >= 5:
        points += 5
        r.passed.append("Good use of bullet points.")
    else:
        r.warnings.append("Few bullet points detected.")
        r.suggestions.append("Use bullet points to make content scannable for ATS and recruiters.")

    urls = URL_RE.findall(text)
    if len(urls) <= 5:
        points += 5
        r.passed.append("URL count looks reasonable.")
    else:
        r.warnings.append("Many URLs detected — some ATS systems struggle with excessive links.")
        r.suggestions.append("Keep URLs to essentials: LinkedIn, portfolio, GitHub.")

    if not re.search(r"[^\x00-\x7F]", text.replace("•", "").replace("–", "").replace("'", "")):
        points += 5
        r.passed.append("No unusual special characters found.")
    else:
        r.warnings.append("Non-ASCII characters detected — some ATS parsers may misread them.")
        r.suggestions.append("Replace fancy characters (curly quotes, em-dashes) with plain equivalents.")

    r.score = points
    return r


def _check_skills_keywords(text: str) -> CheckResult:
    r = CheckResult(name="Skills / Keywords", score=0, max_score=10)
    text_lower = text.lower()

    has_skills_section = any(
        kw in text_lower for kw in SECTION_KEYWORDS["skills"]
    )
    if has_skills_section:
        r.score += 5
        r.passed.append("Skills section found.")
    else:
        r.warnings.append("No dedicated skills section found.")
        r.suggestions.append(
            "Add a 'Skills' section listing your key technical and soft skills."
        )

    comma_or_pipe = len(re.findall(r"[,|]", text))
    if comma_or_pipe >= 5:
        r.score += 5
        r.passed.append("Looks like skills/keywords are listed clearly.")
    else:
        r.suggestions.append(
            "List skills as comma-separated keywords (e.g. Python, SQL, AWS) "
            "so ATS systems can parse them."
        )

    return r


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    _check_contact_info,
    _check_sections,
    _check_action_verbs,
    _check_quantifiable_results,
    _check_length,
    _check_formatting_hints,
    _check_skills_keywords,
]


def analyse_resume(text: str) -> ATSReport:
    checks = [fn(text) for fn in ALL_CHECKS]
    total = sum(c.score for c in checks)
    return ATSReport(overall_score=total, checks=checks)
