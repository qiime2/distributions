#!/usr/bin/env python
from ghapi.all import GhApi, paged

from alp.common import ActionAdapter
from alp.paired import resolve_effective_distro_for_matches, PairedDistroError


def is_branch_in_pager(pager, branch):
    for page in pager:
        for page_branch in page:
            if branch == page_branch['name']:
                return True
    return False


def main(packages, self_repo, self_distro, pair_ref):
    self_entry = next(
        (p for p in packages if p['repo'] == self_repo), None)
    if self_entry is None:
        print(f"::error::Could not find an entry for '{self_repo}' in "
              "data.yaml's package list.")
        raise SystemExit(1)

    self_distros = self_entry['distros']

    candidates = [p for p in packages if p['repo'] != self_repo]

    api = GhApi()
    matches = []
    for package in candidates:
        repo = package['repo']
        pager = paged(api.repos.list_branches, *repo.split('/'))
        if is_branch_in_pager(pager, pair_ref):
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
