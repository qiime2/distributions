#!/usr/bin/env python

"""Generate per-repo changelog fragments for the collated release changelog.

For a single repo, this pulls the commits between the previous and current
release tags, keeps only one entry per squash-merged or merged PR),
categorizes them by commit-message prefix, and writes two Markdown fragments:

- ``output``: the plugin's section for "Plugin Updates"
- ``breaking-output``: the plugin's API:/DEPR: entries for the top-level
  "Breaking Changes" section (breaking entries are listed only there)

With ``mode: patch``, ``release-tag`` is the original release (<epoch>.0) and
the range is <epoch>.0 -> the plugin's latest <epoch>.N tag (cumulative
across patches). The fragment is a flat list of entries, written to
``output`` only; plugins without a patch tag yield an empty fragment.

The ``ci-collate-changelog`` workflow runs this action once per plugin
(matrix) and then assembles the fragments into the full changelog (see
``assemble-changelog.py``), skipping empty fragments.

Breaking Changes -> prefix mapping (see BREAKING_STRUCTURE below):

    API Changes             : API
    Deprecations            : DEPR

Plugin Updates category / subsection -> prefix mapping (see
CATEGORY_STRUCTURE below):

    New and Improved! 🚀
        New Features            : NEW
        Improvements            : IMP
    Bug Fixes 🪲                : BUG   (no subsection)
    Maintenance ⚙️
        Testing                 : TEST
        Documentation           : DOC
        Dependency Pins         : PIN
        Code Refactorization    : REF
        Continuous Integration  : CI
        Miscellaneous           : MAINT

A subsection heading is only rendered when more than one subsection of its
category has entries. Recognized prefixes are stripped from the rendered line
item (only the commit message, sha link, and author remain); the message's
first letter is capitalized and trailing periods are dropped. Any commit whose
subject does not start with a recognized prefix (matched as ``PREFIX:``
exactly, including the colon) lands in an "Uncategorized" section for manual
review, with its subject otherwise intact. Release-machinery commits
(REL:/DEV:) created by the join-release action, internal commits
(LANG:/PREP:), and commits explicitly marked SKIP: are skipped entirely. A
repository with no remaining changes yields empty fragments.

A GitHub token is read from the GH_TOKEN (or GITHUB_TOKEN) environment variable;
it is intentionally NOT an action input, since inputs are echoed to the log.
"""
import json
import os
import re
import urllib.parse
import urllib.request

from alp.common import ActionAdapter

API = "https://api.github.com"

# Breaking entries go to the top-level "Breaking Changes" section only, as an
# ordered list of (subsection_name, prefix) pairs.
BREAKING_STRUCTURE = [
    ("API Changes", "API"),
    ("Deprecations", "DEPR"),
]

# Ordered category structure for "Plugin Updates". Each category has a display
# name, an emoji, and an ordered list of (subsection_name, prefix) pairs. A
# subsection_name of None means the commits are listed directly under the
# category with no subheader. Categories, subsections, and the Uncategorized
# bucket are only rendered when they contain matching commits, and subsection
# headers only when more than one subsection of the category has commits.
CATEGORY_STRUCTURE = [
    ("New and Improved!", "🚀", [
        ("New Features", "NEW"),
        ("Improvements", "IMP"),
    ]),
    ("Bug Fixes", "🪲", [
        (None, "BUG"),
    ]),
    ("Maintenance", "⚙️", [
        ("Testing", "TEST"),
        ("Documentation", "DOC"),
        ("Dependency Pins", "PIN"),
        ("Code Refactorization", "REF"),
        ("Continuous Integration", "CI"),
        ("Miscellaneous", "MAINT"),
    ]),
]

# all prefixes that map to a category/subsection above
KNOWN_PREFIXES = {
    prefix for _, _, subs in CATEGORY_STRUCTURE for _, prefix in subs
} | {prefix for _, prefix in BREAKING_STRUCTURE}

# commits excluded from the changelog entirely:
#   REL/DEV   - release-machinery commits created by the join-release action
#               (empty "[skip ci]" payload)
#   LANG/PREP - internal changes users don't need to be aware of
#   SKIP      - explicitly marked by the author as not changelog-worthy
SKIP_PREFIXES = {"REL", "DEV", "LANG", "PREP", "SKIP"}

# match "PREFIX:" exactly (uppercase letters followed by a colon)
PREFIX_RE = re.compile(r"^([A-Z]+):")
# a trailing PR reference, e.g. "Fix a thing (#123)"
PR_SUFFIX_RE = re.compile(r"^(.*?)(\s*\(#\d+\))?\s*$", re.DOTALL)
# stable release tag, e.g. 2026.7.0 (dev tags look like 2026.7.0.dev0)
VERSION_RE = re.compile(r"^(\d{4})\.(\d+)\.(\d+)$")


def gh_get(url, token, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def parse_version(tag):
    m = VERSION_RE.match(tag)
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def get_stable_tags(repo, token):
    """Return a list of (version_tuple, tag_name) for stable X.Y.Z tags."""
    tags = []
    page = 1
    while True:
        batch = gh_get(
            f"{API}/repos/{repo}/tags",
            token,
            params={"per_page": 100, "page": page},
        )
        if not batch:
            break
        for t in batch:
            name = t["name"]
            if "dev" in name:
                continue
            version = parse_version(name)
            if version is not None:
                tags.append((version, name))
        if len(batch) < 100:
            break
        page += 1
    return tags


def find_patch_tag(stable_tags, release_version):
    """Return the latest patch tag (X.Y.N, N > 0) of release X.Y.0, if any."""
    year, minor, _ = release_version
    patches = [t for t in stable_tags
               if t[0][:2] == (year, minor) and t[0][2] > 0]
    if not patches:
        return None
    return max(patches, key=lambda t: t[0])[1]


def find_previous_tag(stable_tags, head_version):
    """Return the greatest stable tag strictly less than head_version."""
    candidates = [t for t in stable_tags if t[0] < head_version]
    if not candidates:
        return None
    return max(candidates, key=lambda t: t[0])[1]


def first_parent_chain(raw):
    """Keep only the commits on the first-parent chain from the head commit.

    Each PR is expected to land on the release line as a single commit: a
    squash-merge (one parent) or a merge commit (two parents). Following only
    first parents walks that mainline and drops the individual commits of any
    PR branch that was merged with a merge commit instead of squashed (and any
    "Merge branch 'dev' into <feature>" commits on those branches).

    ``raw`` is a list of GitHub commit objects in any order. The head is the
    one commit that is not a parent of any other commit in the list; the walk
    stops at the first parent outside the list (the merge base, or the end of
    history). Returns the kept commits oldest-first.
    """
    by_sha = {c["sha"]: c for c in raw}
    parent_shas = {p["sha"] for c in raw for p in c.get("parents", [])}
    heads = [sha for sha in by_sha if sha not in parent_shas]
    if len(heads) != 1:
        print(
            f"::warning::expected one head commit, found {len(heads)}; "
            "listing all commits instead of the first-parent chain"
        )
        return raw

    chain = []
    sha = heads[0]
    while sha in by_sha:
        commit = by_sha[sha]
        chain.append(commit)
        parents = commit.get("parents", [])
        sha = parents[0]["sha"] if parents else None
    chain.reverse()
    return chain


def get_commits(repo, base, head, token):
    """Return a list of (short_sha, subject, html_url, login, author_url).

    Only the first-parent chain from ``head`` is returned (see
    ``first_parent_chain``), i.e. one entry per squash-merged or merged PR plus
    any commits pushed directly to the branch.

    If ``base`` is None (no prior release tag exists) the first-parent chain
    over all history reachable from ``head`` is returned instead.
    """
    raw = []
    page = 1
    if base:
        # the compare API caps an unpaginated response at 250 commits; paging
        # (per_page <= 100) returns the full comparison
        while True:
            response = gh_get(
                f"{API}/repos/{repo}/compare/{base}...{head}",
                token,
                params={"per_page": 100, "page": page},
            )
            batch = response.get("commits", [])
            raw.extend(batch)
            if not batch or len(raw) >= response.get("total_commits", 0):
                break
            page += 1
    else:
        while True:
            batch = gh_get(
                f"{API}/repos/{repo}/commits",
                token,
                params={"sha": head, "per_page": 100, "page": page},
            )
            if not batch:
                break
            raw.extend(batch)
            if len(batch) < 100:
                break
            page += 1

    commits = []
    for c in first_parent_chain(raw):
        subject = c["commit"]["message"].splitlines()[0].strip()
        # c["author"] is the linked GitHub account (may be null for commits not
        # associated with a GitHub user); fall back to no author link.
        author = c.get("author") or {}
        login = author.get("login")
        author_url = author.get("html_url")
        commits.append((c["sha"][:7], subject, c["html_url"], login, author_url))
    return commits


def strip_prefix(subject):
    """Remove a leading ``PREFIX:`` and any following whitespace."""
    return PREFIX_RE.sub("", subject, count=1).lstrip()


def categorize(commits):
    """Group commits by prefix.

    Returns (by_prefix, uncategorized): a dict of prefix -> [entries] for
    recognized prefixes, and a list of entries whose subject has no recognized
    prefix. Skip-listed commits (see SKIP_PREFIXES) are dropped.
    """
    by_prefix = {}
    uncategorized = []
    for entry in commits:
        subject = entry[1]
        m = PREFIX_RE.match(subject)
        prefix = m.group(1) if m else None
        if prefix in SKIP_PREFIXES:
            continue
        if prefix in KNOWN_PREFIXES:
            by_prefix.setdefault(prefix, []).append(entry)
        else:
            uncategorized.append(entry)
    return by_prefix, uncategorized


def capitalize_first(text):
    """Uppercase the first character if it is a lowercase letter.

    Unlike ``str.capitalize`` this leaves the rest of the string alone, and it
    leaves text that starts with anything else (e.g. a backtick-quoted
    identifier) untouched.
    """
    if text and text[0].islower():
        return text[0].upper() + text[1:]
    return text


def strip_trailing_periods(text):
    """Drop trailing periods, including ones before a trailing ``(#123)``."""
    body, pr_ref = PR_SUFFIX_RE.match(text).groups()
    return body.rstrip().rstrip(".").rstrip() + (pr_ref or "")


def format_item(entry, strip):
    sha, subject, url, login, author_url = entry
    message = strip_prefix(subject) if strip else subject
    message = capitalize_first(strip_trailing_periods(message))
    item = f"- {message} ([`{sha}`]({url})"
    if login and author_url:
        item += f" by [{login}]({author_url})"
    item += ")"
    return item


def render_subsections(subs, by_prefix, header):
    """Render (subsection_name, prefix) pairs that have entries.

    Subsection headers (``header`` + name) are only emitted when more than one
    subsection has entries; otherwise the entries are listed directly.
    """
    present = [(name, by_prefix[prefix]) for name, prefix in subs
               if by_prefix.get(prefix)]
    lines = []
    for name, entries in present:
        if name and len(present) > 1:
            lines += [f"{header} {name}", ""]
        lines.extend(format_item(e, strip=True) for e in entries)
        lines.append("")
    return lines


def heading(level, display_name, repo):
    return f"{'#' * level} [{display_name}](https://github.com/{repo})"


def range_note(base, head, expected_base):
    """The release range is printed once at the top of the changelog section,
    so a fragment only carries its own range when it differs from that shared
    one: e.g. a newly added plugin with no prior release (full history), or a
    plugin whose last release was older than ``expected_base``."""
    if base == expected_base:
        return []
    return [f"_Changes in {base or '<initial>'} → {head}_", ""]


def render(display_name, repo, base, head, expected_base, by_prefix,
           uncategorized):
    """Render the plugin's "Plugin Updates" section (non-breaking entries)."""
    body = []
    for category, emoji, subs in CATEGORY_STRUCTURE:
        block = render_subsections(subs, by_prefix, "#####")
        if block:
            body += [f"#### {category} {emoji}", ""] + block

    if uncategorized:
        body += ["#### Uncategorized", ""]
        body.extend(format_item(e, strip=False) for e in uncategorized)
        body.append("")

    if not body:
        # plugin had no (non-breaking) changes this cycle -> emit nothing so it
        # can be omitted from the collated changelog entirely
        return ""
    lines = [heading(2, display_name, repo), ""]
    lines += range_note(base, head, expected_base) + body
    return "\n".join(lines)


def render_breaking(display_name, repo, base, head, expected_base, by_prefix):
    """Render the plugin's entry for the top-level "Breaking Changes" section."""
    body = render_subsections(BREAKING_STRUCTURE, by_prefix, "####")
    if not body:
        return ""
    lines = [heading(3, display_name, repo), ""]
    lines += range_note(base, head, expected_base) + body
    return "\n".join(lines)


def render_patch(display_name, repo, commits):
    """Render the plugin's section of a patch changelog: a flat list."""
    entries = [e for e in commits
               if (m := PREFIX_RE.match(e[1])) is None
               or m.group(1) not in SKIP_PREFIXES]
    if not entries:
        return ""
    lines = [heading(2, display_name, repo), ""]
    lines.extend(format_item(e, strip=True) for e in entries)
    return "\n".join(lines)


def write_fragment(path, fragment):
    with open(path, "w") as fh:
        # an empty fragment leaves a 0-byte file, which assembly skips
        if fragment:
            fh.write(fragment)
            if not fragment.endswith("\n"):
                fh.write("\n")


def main_patch(repo, name, release_tag, output, display_name, token):
    release_version = parse_version(release_tag)
    if release_version is None:
        raise ValueError(f"release tag '{release_tag}' is not X.Y.Z")

    stable_tags = get_stable_tags(repo, token)
    head = find_patch_tag(stable_tags, release_version)
    if head is None or release_tag not in {t[1] for t in stable_tags}:
        print(f"{name}: no patch of {release_tag}")
        write_fragment(output, "")
        return dict(has_changes="false", has_breaking_changes="false")

    print(f"{name}: comparing {release_tag}...{head}")
    commits = get_commits(repo, release_tag, head, token)
    fragment = render_patch(display_name, repo, commits)
    write_fragment(output, fragment)
    print(fragment or f"{name}: no changes in {head}")
    return dict(has_changes="true" if fragment else "false",
                has_breaking_changes="false")


def main(repo, name, release_tag, output, breaking_output="",
         previous_tag="", display_name="", mode=""):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    display_name = display_name or name
    if mode == "patch":
        return main_patch(repo, name, release_tag, output, display_name, token)

    expected_base = previous_tag or None

    head_version = parse_version(release_tag)
    if head_version is None:
        print(
            f"::warning::release tag '{release_tag}' is not X.Y.Z; "
            f"cannot resolve a previous tag for {repo}, using full history"
        )

    stable_tags = get_stable_tags(repo, token)
    base = find_previous_tag(stable_tags, head_version) if head_version else None

    print(f"{name}: comparing {base or '<initial>'}...{release_tag}")

    commits = get_commits(repo, base, release_tag, token)
    by_prefix, uncategorized = categorize(commits)
    fragment = render(display_name, repo, base, release_tag, expected_base,
                      by_prefix, uncategorized)
    breaking = render_breaking(display_name, repo, base, release_tag,
                               expected_base, by_prefix)

    write_fragment(output, fragment)
    if breaking_output:
        write_fragment(breaking_output, breaking)

    print(breaking or f"{name}: no breaking changes this cycle")
    print(fragment or f"{name}: no other changes this cycle")

    return dict(
        has_changes="true" if fragment else "false",
        has_breaking_changes="true" if breaking else "false",
    )


if __name__ == "__main__":
    ActionAdapter(main)
