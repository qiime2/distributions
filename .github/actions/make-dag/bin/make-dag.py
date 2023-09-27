#!/usr/bin/env python
import os
import json
import urllib.request

import networkx as nx
import jinja2

from alp.common import ActionAdapter


# Convert DAG subplot to mermaid diagram for use in job summary
def to_mermaid(G, highlight_from=None):
    lookup = {n: f'{i:x}' for i, n in enumerate(sorted(G.nodes, reverse=True))}

    if highlight_from is None:
        highlight_from = set()
    else:
        highlight_from = set(highlight_from)

    build = set()
    for parent in highlight_from:
        build.update([x[1] for x in G.out_edges(parent)])
        build.add(parent)

    build = [lookup[x] for x in build]

    G = nx.transitive_reduction(G)

    lines = ['flowchart LR']
    for key, value in lookup.items():
        lines.append(f'{value}["{key}"]')

    test = set()
    for parent in highlight_from:
        test.update(nx.descendants(G, parent))
        test.add(parent)

    test = [lookup[x] for x in test]

    edges = []
    for idx, (a, b) in enumerate(sorted(G.edges)):
        lines.append(f'{lookup[a]} --> {lookup[b]}')
        if lookup[a] in test:
            edges.append(str(idx))

    lines.append('linkStyle default opacity:0.25')
    if edges:
        lines.append(f'linkStyle {",".join(edges)} opacity:1')
    lines.append('classDef default fill:#e0f2fe,stroke:#7dd3fc')
    if test:
        lines.append('classDef test fill:#38bdf8,stroke:#0284c7')
        lines.append(f'class {",".join(test)} test')
    if build:
        lines.append('classDef build fill:#818cf8,stroke:#4f46e5')
        lines.append(f'class {",".join(build)} build')
    if highlight_from:
        lines.append('classDef origin fill:#f472b6,stroke:#ec4899')
        lines.append(
            f'class {",".join([lookup[parent] for parent in highlight_from])} '
            'origin')
    return '\n'.join(lines)


def get_source_revdeps(dag, all_changes):
    src_revdeps = {}
    for pkg in all_changes:
        revdeps = [edge[1] for edge in dag.out_edges(pkg)]
        src_revdeps[pkg] = revdeps

    return src_revdeps


# Create new DiGraph object & add list of pkgs from a given pkg dict as nodes
def make_dag(pkg_dict, env_versions):
    dag = nx.DiGraph()
    # Add edges connecting each pkg to their list of deps
    for pkg, deps in pkg_dict.items():
        for dep in deps:
            dag.add_edge(dep, pkg)

    for pkg, _ in env_versions.items():
        dag.add_node(pkg)

    return dag


def _fetch_url(url):
    http_response = urllib.request.urlopen(url)
    obj = http_response.read().decode('utf-8')
    return obj


def get_distro_deps(channel, relevant_pkgs):

    missing_pkgs = relevant_pkgs.copy()
    q2_pkg_channel_url = channel + '/linux-64/repodata.json'

    response = _fetch_url(q2_pkg_channel_url)
    repodata = json.loads(response)

    # this is what's pulled from our tested channel on packages.qiime2.org
    q2_dep_dict = {}

    for info in repodata['packages'].values():
        name = info['name']
        if (name not in missing_pkgs
                or missing_pkgs[name] != info['version']):
            continue
        del missing_pkgs[name]
        q2_dep_dict[name] = [dep.split(' ')[0] for dep in info['depends']]

    print('Q2 DEP DICT')
    print(q2_dep_dict)

    if missing_pkgs:
        print('MISSING PKGS')
        print(missing_pkgs)
        missing = {}
        for name in missing_pkgs:
            del q2_dep_dict[name]
            missing[name] = []
    else:
        missing = None

    return q2_dep_dict, missing


def main(epoch, distro, changed, rebuild, env_versions, distro_versions,
         matrix_path, rev_deps_path, search_channels):
    """
    changed: list of package names
    rebuild: dict of package name -> repository/package
    *_versions: dict of package name -> version
    """
    gh_summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary_path is None:
        raise Exception()

    GITHUB_ACTION_PATH = os.environ.get('GITHUB_ACTION_PATH')
    if GITHUB_ACTION_PATH is None:
        raise Exception('Expected $GITHUB_ACTION_PATH, not in a github runner')

    TEMPLATE_DIR = os.path.join(GITHUB_ACTION_PATH, 'templates')
    J_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))

    distro_deps, missing = get_distro_deps(search_channels[0], distro_versions)

    core_dag = make_dag(pkg_dict=distro_deps, env_versions=env_versions)
    core_sub = nx.subgraph(core_dag, env_versions)

    rebuild_generations = list(nx.topological_generations(
        nx.induced_subgraph(core_sub, rebuild)
    ))

    src_revdeps = get_source_revdeps(core_dag, [*changed, *rebuild])

    pkgs_to_test = sorted(set.union(set(src_revdeps),
                                    *(nx.descendants(core_dag, pkg)
                                      for pkg in src_revdeps)))
    # Filter to only packages that we manage
    pkgs_to_test = [pkg for pkg in pkgs_to_test if pkg in distro_versions]
    if missing is not None:
        pkgs_to_test.extend(list(missing))

    core_mermaid = to_mermaid(core_sub, highlight_from=src_revdeps)
    template = J_ENV.get_template("job-summary-template.j2")

    with open(gh_summary_path, 'w') as fh:
        fh.write(template.render(epoch=epoch,
                                 distro=distro,
                                 core_mermaid=core_mermaid,
                                 source_dep_dict=src_revdeps,
                                 pkgs_to_test=pkgs_to_test))

    with open(os.path.join(matrix_path, 'rebuild_matrix.json'), 'w') as fh:
        rebuild_repos = [
            [rebuild[key] for key in generation]
            for generation in rebuild_generations
        ]
        if missing is not None:
            rebuild_repos.append(list(missing))
        json.dump(rebuild_repos, fh)

    with open(os.path.join(matrix_path, 'retest_matrix.json'), 'w') as fh:
        json.dump(pkgs_to_test, fh)

    with open(os.path.join(rev_deps_path, 'rev_deps.json'), 'w') as fh:
        json.dump(src_revdeps, fh)


if __name__ == '__main__':
    ActionAdapter(main)
