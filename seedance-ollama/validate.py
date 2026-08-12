"""Non-LLM structural checks for a generated Seedance prompt, catches the
mechanical rule violations the guide calls out (formatting, timestamps,
shot-duration math) without needing another model call.
"""

import argparse
import re
import sys

REQUIRED_SECTIONS = [
    "FORMAT:",
    "SUBJECT:",
    "WARDROBE",
    "HERO PROPS:",
    "ENVIRONMENT:",
    "MOOD:",
    "MUSIC:",
    "COLOR LOGIC:",
    "STYLE:",
    "LOGIC RULE:",
]

FORMAT_RE = re.compile(r"^FORMAT:\s*(\d+)s\s*/\s*(\d+)\s*SHOTS", re.MULTILINE)
SHOT_HEADER_RE = re.compile(
    r"^SHOT\s+(\d+)\s*[—-]\s*(\d+):(\d+)\s+to\s+(\d+):(\d+)\s*,\s*"
    r"([A-Z/]+)\s*,\s*(\d+)\s*mm\s*,\s*([^.]+)\.\s*$",
    re.MULTILINE,
)
TIMESTAMP_DECIMAL_RE = re.compile(r"\d+:\d+\.\d")
BOLD_RE = re.compile(r"\*\*[^*]+\*\*")
SLASH_IN_SHOT_LINE_RE = re.compile(r"^SHOT\s+\d+.*/.*mm.*/", re.MULTILINE)
PITCH_BLACK_RE = re.compile(r"\bpitch black\b|\bblack void\b", re.IGNORECASE)


def _to_seconds(mm, ss):
    return int(mm) * 60 + int(ss)


def validate(prompt_text, expected_duration=None):
    """Run structural checks against a generated prompt. Returns a list of
    human-readable issue strings; empty list means it passed."""
    issues = []

    for section in REQUIRED_SECTIONS:
        if section not in prompt_text:
            issues.append(f"Missing required section: {section}")

    if "---" not in prompt_text:
        issues.append("Missing '---' divider between metadata and shots.")

    format_match = FORMAT_RE.search(prompt_text)
    stated_duration = None
    stated_shot_count = None
    if not format_match:
        issues.append("FORMAT line missing or malformed (expected '[N]s / [N] SHOTS').")
    else:
        stated_duration = int(format_match.group(1))
        stated_shot_count = int(format_match.group(2))
        if expected_duration is not None and stated_duration != expected_duration:
            issues.append(
                f"FORMAT duration ({stated_duration}s) does not match requested "
                f"duration ({expected_duration}s)."
            )

    if BOLD_RE.search(prompt_text):
        issues.append("Found markdown bold (**text**) in output; must be plain text.")

    if TIMESTAMP_DECIMAL_RE.search(prompt_text):
        issues.append("Found decimal timestamp; timestamps must be whole seconds.")

    if SLASH_IN_SHOT_LINE_RE.search(prompt_text):
        issues.append("Found '/' separator in a shot metadata line; use commas instead.")

    if PITCH_BLACK_RE.search(prompt_text):
        issues.append(
            "Found 'pitch black' / 'black void' language; use 'dim but visible' "
            "unless nothing should be visible."
        )

    shots = SHOT_HEADER_RE.findall(prompt_text)
    if not shots:
        issues.append("No valid SHOT lines found (expected 'SHOT N — 0:00 to 0:0X, "
                       "FRAMING, LENSmm, MOVEMENT.').")
    else:
        if stated_shot_count is not None and len(shots) != stated_shot_count:
            issues.append(
                f"FORMAT says {stated_shot_count} shots but found {len(shots)} SHOT lines."
            )

        prev_end = 0
        for (num, sm, ss, em, es, framing, lens, movement) in shots:
            start = _to_seconds(sm, ss)
            end = _to_seconds(em, es)
            if start != prev_end:
                issues.append(
                    f"SHOT {num} starts at {sm}:{ss} but previous shot ended at "
                    f"{prev_end // 60}:{prev_end % 60:02d}; shots must be contiguous."
                )
            if end <= start:
                issues.append(f"SHOT {num} end time is not after its start time.")
            prev_end = end

        if stated_duration is not None and prev_end != stated_duration:
            issues.append(
                f"Shot durations add up to {prev_end}s but FORMAT states {stated_duration}s."
            )
        elif expected_duration is not None and stated_duration is None and prev_end != expected_duration:
            issues.append(
                f"Shot durations add up to {prev_end}s but requested duration was "
                f"{expected_duration}s."
            )

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate a generated Seedance prompt.")
    parser.add_argument("prompt_file", help="Path to the prompt text file to validate.")
    parser.add_argument("--duration", type=int, default=None,
                         help="Expected total duration in seconds.")
    args = parser.parse_args()

    with open(args.prompt_file, "r", encoding="utf-8") as f:
        prompt_text = f.read()

    issues = validate(prompt_text, args.duration)
    if issues:
        print(f"FAILED ({len(issues)} issue(s)):")
        for issue in issues:
            print(f"- {issue}")
        sys.exit(1)
    else:
        print("OK: prompt passed all structural checks.")


if __name__ == "__main__":
    main()
