#!/usr/bin/env python

import re
import subprocess
import sys
import textwrap

from alp.common import ActionAdapter


def get_section(markdown, header):
    lines = markdown.splitlines()
    start = None
    level = None

    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)", line.strip())
        if m and m.group(2).strip().upper() == header.upper():
            level = len(m.group(1))
            start = i + 1
            break

    if start is None:
        return None

    end = len(lines)
    for i in range(start, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[i].strip())
        if m and len(m.group(1)) <= level:
            end = i
            break

    return "\n".join(lines[start:end])

def clean(section):
    if section is None:
        return ""

    section = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    return section.strip()

def main(gh_token, gh_repo, pr_number):
    body = subprocess.check_output(
        [
        "gh", "api",
        f"repos/{gh_repo}/pulls/{pr_number}",
        "--jq", ".body // \"\"",
        ],
        text=True,
    ).strip()

    if not body:
        print('PR template validation failed:')
        print(textwrap.dedent(
        """
        PR template has been removed.
        Please copy/paste the template below back into the PR body and fill it out prior to requesting a review:

        <!-- PR guidance and examples: https://github.com/rachis-org/governance/blob/main/pr_template_guidelines.md -->
        <!-- rachis Generative AI Policy: https://github.com/rachis-org/governance/blob/main/ai_policy.md -->

        # Description
        <!-- REQUIRED: Briefly describe this PR, or link the issue it closes. -->


        # AI Disclosure
        <!-- REQUIRED: Check exactly one option. -->

        - [ ] NO AI USED.
        - [ ] AI USED.


        # AI Usage Details
        <!-- REQUIRED if 'AI USED' is checked. This section can be deleted if 'NO AI USED' is checked. -->
        """
        ))

        sys.exit(1)

    errors = []

    if body:
        description = clean(get_section(body, "Description"))
        if not description:
            errors.append(
                "Description must include a brief summary or an issue link."
            )

        ai_disclosure = clean(get_section(body, "AI Disclosure"))
        no_ai = bool(re.search(
        r"(?im)^\s*-\s*\[[xX]\]\s*NO AI USED\.?\s*$",
        ai_disclosure,
        ))
        ai_used = bool(re.search(
        r"(?im)^\s*-\s*\[[xX]\]\s*AI USED\.?\s*$",
        ai_disclosure,
        ))

        if no_ai == ai_used:
            errors.append(
                "AI Disclosure must have exactly one checked option: "
                "NO AI USED or AI USED."
            )

        ai_details_section = get_section(body, "AI Usage Details")
        if ai_used and not clean(ai_details_section):
            errors.append(
                "AI Usage Details must describe how AI was used when "
                "AI USED is checked."
            )

        if errors:
            print("PR template validation failed:")
            for error in errors:
                print(f"- {error}")
            sys.exit(1)

    print("PR template validation passed!")


if __name__ == '__main__':
    ActionAdapter(main)
