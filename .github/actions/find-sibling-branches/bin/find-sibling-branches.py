#!/usr/bin/env python
import os
import urllib.error
import urllib.parse
import urllib.request

import yaml

from alp.common import ActionAdapter


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


def find_packages_to_build(repos, branch):
    to_build = {}
    for name, repo in repos.items():
        if branch_exists(repo, branch):
            to_build[name] = repo
    return to_build


def main(repos, is_rebuild, sibling_ref):
    if is_rebuild != 'true':
        repos = find_packages_to_build(repos, sibling_ref)

    return dict(repos=repos)


if __name__ == '__main__':
    ActionAdapter(main)
