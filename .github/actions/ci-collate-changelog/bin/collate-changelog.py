#!/usr/bin/env python

"""Generate a per-repo changelog fragment for the collated release changelog.

For a single repository, this pulls the commits between the previous stable
release tag and the current release tag via the GitHub compare API, keeps only
the first-parent chain (one entry per squash-merged or merged PR, so a PR's
individual branch commits are never listed), categorizes them by
commit-message prefix, and writes a Markdown fragment to the ``output``
path. The ``ci-collate-changelog`` workflow runs this action once per plugin
(matrix) and then stitches the fragments into one alphabetically-sorted
changelog, skipping empty fragments (plugins with no changes this cycle).

Category / subsection -> prefix mapping (see CATEGORY_STRUCTURE below):

    Breaking Changes 💥
        API Changes             : API
        Deprecations            : DEPR
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

Recognized prefixes are stripped from the rendered line item (only the commit
message, sha link, and author remain). Any commit whose subject does not start
with a recognized prefix (matched as ``PREFIX:`` exactly, including the colon)
lands in an "Uncategorized" section for manual review, with its subject left
intact. Release-machinery commits (REL:/DEV:) created by the join-release
action, internal commits (LANG:/PREP:), and commits explicitly marked SKIP:
are skipped entirely. A repository with no remaining
changes yields an empty fragment.

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

# Ordered category structure. Each category has a display name, an emoji, and an
# ordered list of (subsection_name, prefix) pairs. A subsection_name of None
# means the commits are listed directly under the category with no subheader.
# Categories, subsections, and the Uncategorized bucket are only rendered when
# they contain matching commits.
CATEGORY_STRUCTURE = [
    ("Breaking Changes", "💥", [
        ("API Changes", "API"),
        ("Deprecations", "DEPR"),
    ]),
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
}

# commits excluded from the changelog entirely:
#   REL/DEV   - release-machinery commits created by the join-release action
#               (empty "[skip ci]" payload)
#   LANG/PREP - internal changes users don't need to be aware of
#   SKIP      - explicitly marked by the author as not changelog-worthy
SKIP_PREFIXES = {"REL", "DEV", "LANG", "PREP", "SKIP"}

# match "PREFIX:" exactly (uppercase letters followed by a colon)
PREFIX_RE = re.compile(r"^([A-Z]+):")
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


def format_item(entry, strip):
    sha, subject, url, login, author_url = entry
    message = capitalize_first(strip_prefix(subject) if strip else subject)
    item = f"- {message} ([`{sha}`]({url})"
    if login and author_url:
        item += f" by [{login}]({author_url})"
    item += ")"
    return item


def render(name, base, head, expected_base, by_prefix, uncategorized):
    """Render one plugin's fragment.

    The release range is printed once at the top of the collated changelog,
    so a fragment only carries its own range when it differs from that shared
    one: e.g. a newly added plugin with no prior release (full history), or a
    plugin whose last release was older than ``expected_base``.
    """
    lines = [f"## {name}", ""]
    if base != expected_base:
        lines += [f"_Changes in {base or '<initial>'} → {head}_", ""]
    any_content = False

    for category, emoji, subs in CATEGORY_STRUCTURE:
        # build subsection blocks that actually have commits
        sub_blocks = []
        for sub_name, prefix in subs:
            entries = by_prefix.get(prefix)
            if not entries:
                continue
            block = []
            if sub_name:
                block.append(f"##### {sub_name}")
                block.append("")
            block.extend(format_item(e, strip=True) for e in entries)
            block.append("")
            sub_blocks.append(block)
        if not sub_blocks:
            continue
        any_content = True
        lines.append(f"#### {category} {emoji}")
        lines.append("")
        for block in sub_blocks:
            lines.extend(block)

    if uncategorized:
        any_content = True
        lines.append("#### Uncategorized")
        lines.append("")
        lines.extend(format_item(e, strip=False) for e in uncategorized)
        lines.append("")

    if not any_content:
        # plugin had no changes this cycle -> emit nothing so it can be omitted
        # from the collated changelog entirely
        return ""
    return "\n".join(lines)


def main(repo, name, release_tag, output, previous_tag=""):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

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
    fragment = render(
        name, base, release_tag, previous_tag or None, by_prefix, uncategorized
    )

    with open(output, "w") as fh:
        # an empty fragment (no changes this cycle) leaves a 0-byte file, which
        # the collate step skips
        if fragment:
            fh.write(fragment)
            if not fragment.endswith("\n"):
                fh.write("\n")

    print(fragment or f"{name}: no changes this cycle")

    return dict(has_changes="true" if fragment else "false")


if __name__ == "__main__":
    ActionAdapter(main)
