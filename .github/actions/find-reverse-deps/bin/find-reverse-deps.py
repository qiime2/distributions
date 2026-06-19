#!/usr/bin/env python
"""Find packages that depend on the paired plugins, for PR comment generation.

Reads inputs from stdin as JSON (via ActionAdapter). Fetches repodata.json
from the staged conda channel for the effective distribution and checks each
package's run-dependencies against the set of paired plugin names. Writes a
formatted markdown comment body to /tmp/reverse-deps-comment.md; the action's
capture step then reads the file into GITHUB_OUTPUT.
"""
import json
import urllib.error
import urllib.request

from alp.common import ActionAdapter

COMMENT_OUTPUT_PATH = '/tmp/reverse-deps-comment.md'
PACKAGES_BASE = 'https://packages.qiime2.org/qiime2'


def fetch_repodata(url):
    """Fetch and parse repodata.json from a channel subdir URL.

    Returns the parsed dict on success, None if the URL is unreachable or
    returns a non-200 status (e.g. the subdir does not exist for this distro).
    """
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError):
        return None


def build_pkg_deps(channel_base):
    """Return a mapping of package_name -> set of dep names from the channel.

    Checks both linux-64 and noarch subdirs, merging deps across all versions
    of the same package (latest version's deps dominate in practice, but
    merging is harmless and avoids having to sort by build number).
    """
    pkg_deps = {}
    for subdir in ('linux-64', 'noarch'):
        url = f'{channel_base}/{subdir}/repodata.json'
        data = fetch_repodata(url)
        if data is None:
            continue
        for section in ('packages', 'packages.conda'):
            for pkg_info in data.get(section, {}).values():
                name = pkg_info['name']
                if name not in pkg_deps:
                    pkg_deps[name] = set()
                for dep_str in pkg_info.get('depends', []):
                    # strip version constraint (e.g. "q2-types >=2026.7")
                    dep_name = dep_str.split()[0]
                    pkg_deps[name].add(dep_name)
    return pkg_deps


def build_comment(self_name, paired_repos, effective_distro, reverse_deps):
    """Return the formatted markdown comment body string."""
    sibling_names = [p['name'] for p in paired_repos]
    paired_display = ', '.join(f'`{n}`' for n in [self_name] + sibling_names)

    lines = [
        '<!-- paired-ci-dev-reverse-deps -->',
        '## Paired CI-Dev: Reverse Dependency Check',
        '',
        f'**Packages in this Paired PR:** {paired_display}  ',
        f'**Effective distribution:** `{effective_distro}`',
        '',
        f'The following plugins in the `{effective_distro}` distribution '
        f'list `{self_name}` as a conda run-dependency. '
        f'Please review them to confirm no additional plugins will have test '
        f'failures due to an API change.',
        '',
    ]

    dependents = reverse_deps.get(self_name, [])
    if dependents:
        for dep in sorted(dependents, key=lambda d: d['name']):
            name = dep['name']
            repo = dep.get('repo', '')
            if repo:
                lines.append(
                    f'- `{name}` — [{repo}](https://github.com/{repo})'
                )
            else:
                lines.append(f'- `{name}`')
    else:
        lines.append(
            f'_No reverse dependencies found for `{self_name}` in the '
            f'`{effective_distro}` distribution._'
        )
    lines.append('')

    lines += [
        '---',
        '_This comment is automatically generated once after tests pass._',
    ]

    return '\n'.join(lines) + '\n'


def main(packages, self_name, paired_repos, effective_distro, active_epoch):
    if isinstance(packages, str):
        packages = json.loads(packages)
    if isinstance(paired_repos, str):
        paired_repos = json.loads(paired_repos) if paired_repos else []

    paired_names = set([self_name] + [p['name'] for p in paired_repos])

    # Candidates: packages whose primary_distro matches the effective distro,
    # excluding the paired plugins themselves.
    candidates = [
        p for p in packages
        if p.get('primary_distro') == effective_distro
        and p['name'] not in paired_names
    ]

    print(
        f'Checking {len(candidates)} candidate package(s) in '
        f"'{effective_distro}' for reverse deps on: {self_name}"
    )

    channel_base = f'{PACKAGES_BASE}/{active_epoch}/{effective_distro}/staged'
    pkg_deps = build_pkg_deps(channel_base)

    if not pkg_deps:
        print(
            f'::warning::Could not fetch repodata from {channel_base}. '
            'Reverse dependency check skipped.'
        )

    # Only search reverse deps for self; the sibling's PR will carry its own.
    reverse_deps = {self_name: []}
    for candidate in candidates:
        name = candidate['name']
        deps = pkg_deps.get(name, set())
        if self_name in deps:
            reverse_deps[self_name].append(candidate)
            print(f'  {name} depends on {self_name}')

    comment_body = build_comment(
        self_name=self_name,
        paired_repos=paired_repos,
        effective_distro=effective_distro,
        reverse_deps=reverse_deps,
    )

    with open(COMMENT_OUTPUT_PATH, 'w') as fh:
        fh.write(comment_body)

    print(f'Comment body written to {COMMENT_OUTPUT_PATH}')


if __name__ == '__main__':
    ActionAdapter(main)
