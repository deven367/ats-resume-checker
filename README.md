# ATS Resume Checker

A simple CLI tool that scores your resume for ATS (Applicant Tracking System) compatibility and suggests improvements.

## What it checks

| Check                | Weight | What it looks for                                   |
|----------------------|--------|-----------------------------------------------------|
| Contact Information  | 15     | Email, phone number, LinkedIn URL                   |
| Standard Sections    | 20     | Experience, Education, Skills, Summary, etc.        |
| Action Verbs         | 15     | Strong verbs at the start of bullet points          |
| Quantifiable Results | 15     | Numbers, percentages, dollar amounts                |
| Resume Length         | 10     | Word count (sweet spot: 300-800 words for 1 page)   |
| Formatting & ATS Tips| 15     | Bullet points, URLs, special characters             |
| Skills / Keywords    | 10     | Dedicated skills section with parseable keywords    |

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Using the installed command
ats-check path/to/resume.pdf
ats-check path/to/resume.docx

# Or run as a Python module
python -m ats_checker path/to/resume.pdf
```

## Example output

```
╭──── ATS Score — resume.pdf ────╮
│          72 / 100              │
╰────────────────────────────────╯

  Contact Information  [10/15]
    ✓ Email address found.
    ✓ Phone number found.
    ✗ No LinkedIn profile link detected.
    → Add your LinkedIn profile URL (linkedin.com/in/yourname).

  ...
```
