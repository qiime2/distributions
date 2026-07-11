#!/usr/bin/env python
import os
import urllib.error
import urllib.parse
import urllib.request

from alp.common import ActionAdapter
from alp.paired import resolve_effective_distro_for_matches, PairedDistroError


def branch_exists(repo, branch):
    owner, repo_name = repo.split('/')
    encoded = urllib.parse.quote(branch, safe='')
    url = (f'https://api.github.com/repos/{owner}/{repo_name}'
           f'/branches/{encoded}')
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def main(packages, self_repo, self_distro, pair_ref):
    self_entry = next(
        (p for p in packages if p['repo'] == self_repo), None)
    if self_entry is None:
        print(f"::error::Could not find an entry for '{self_repo}' in "
              "data.yaml's package list.")
        raise SystemExit(1)

    self_distros = self_entry['distros']

    candidates = [p for p in packages if p['repo'] != self_repo]

    matches = []
    for package in candidates:
        repo = package['repo']
        if branch_exists(repo, pair_ref):
            matches.append(package)

    if not matches:
        print(f"::error::No sibling repo with a '{pair_ref}' branch was "
              f"found for the paired ci-dev run of '{self_repo}'. Searched "
              f"{len(candidates)} other package(s) listed in data.yaml.")
        raise SystemExit(1)

    print(f"Found {len(matches)} sibling repo(s) with a '{pair_ref}' "
          f"branch: {', '.join(p['repo'] for p in matches)}")

    try:
        effective_distro = resolve_effective_distro_for_matches(
            self_repo=self_repo,
            self_distro=self_distro,
            self_distros=self_distros,
            matches=matches,
        )
    except PairedDistroError as e:
        print(f"::error::{e}")
        raise SystemExit(1)

    print(f"Resolved effective distro for this paired run: "
          f"{effective_distro}")

    paired_repos = [
        {'name': p['name'], 'repo': p['repo']} for p in matches
    ]

    return dict(
        paired_repos=paired_repos,
        effective_distro=effective_distro,
    )


if __name__ == '__main__':
    ActionAdapter(main)
