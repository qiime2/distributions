#!/usr/bin/env python
import yaml
import urllib
import json
import re
import networkx as nx
from yaml import SafeLoader


# Helper methods ##

# Helper for parsing CBC and tested channel URLs
def _parse_url(url):
    http_response = urllib.request.urlopen(url)
    obj = http_response.read().decode('utf-8')

    return obj


# Helper method to deal with pkg version formats
def _pkg_ver_helper(pkg, ver):
    ver_str = ""
    pkg_ver = pkg.replace('_', '-') + '-' + ver_str.join(ver)

    return pkg_ver


# Helper method to simplify DAG to only first order deps
def _get_subgraph(cbc_yaml, dag):
    pkg_list = list(cbc_yaml.keys())
    pkgs = [x.replace('_', '-') for x in pkg_list]
    sub = nx.subgraph(dag, pkgs)

    return sub


# DAG generation methods ##

# Parses the cmd line diff into a dict with pkgs added, changed, and removed
def find_diff(diff):
    dependency = r"\n?.*:\n"
    # `\n?.*\n` -> matches any line that ends with colon,
    #              will match dependency name line
    added_dependency = r"\n?\+.*:\n"
    # same as above but match when line begins with '+'
    removed_dependency = r"\n?-.*:\n"
    # same as above but match when line begins with '-'

    removed_version = r"\n?-\t? *- '?[(<=)(>=)]?[0-9]+\..*'?"
    # `\n?` -> optional newline
    # `- ` -> diff syntax for line in old file
    # `\t *` -> optional tab and any number of spaces (identation in yaml)
    # `'?` -> optional quote in version line
    # `[(<=)(>=)]?` -> optional '>=' or '<=' in version
    # `[0-9]+\.` -> a version number followed by a dot followed by anything
    #               else
    # `'?` -> optional close quote
    added_version = r"\n?\+\t? *- '?[(<=)(>=)]?[0-9]+\..*'?\n"
    # same as above but line begins with '+'

    version_change_pattern = rf"{dependency}{removed_version}{added_version}"
    added_dependency_pattern = rf"{added_dependency}{added_version}"
    removed_dependency_pattern = rf"{removed_dependency}{removed_version}"

    with open(diff, 'r') as file:
        contents = file.read()
        version_change_matches = re.findall(version_change_pattern, contents)
        added_dependency_matches = re.findall(added_dependency_pattern,
                                              contents)
        removed_dependency_matches = re.findall(removed_dependency_pattern,
                                                contents)

    changed_pkgs = [match.split(':')[0].strip()
                    for match in version_change_matches]
    added_pkgs = [match.split(':')[0].strip().strip('+')
                  for match in added_dependency_matches]
    removed_pkgs = [match.split(':')[0].strip().strip('-')
                    for match in removed_dependency_matches]

    pkgs = {
        'changed_pkgs': changed_pkgs,
        'added_pkgs': added_pkgs,
        'removed_pkgs': removed_pkgs,
    }

    return pkgs


# Pull CBC structure and pkg list from our tested CBC.yml for a given epoch
def get_cbc_info(epoch):
    cbc_url = ('https://raw.githubusercontent.com/qiime2/package-integration'
               f'/main/{epoch}/tested/conda_build_config.yaml')

    # Convert HTTP response to a YAML-friendly format
    cbc_obj = _parse_url(cbc_url)

    # Convert to YAML object
    cbc_yaml = yaml.load(cbc_obj, Loader=SafeLoader)

    # Create pkg list that includes pkg versions from CBC dict
    pkg_ver_list = []
    for pkg, ver in cbc_yaml.items():
        pkg_ver = _pkg_ver_helper(pkg, ver)
        pkg_ver_list.append(pkg_ver)

    return cbc_yaml, pkg_ver_list


# Filter down CBC list of pkgs based on diff results with only changed pkgs
def filter_cbc_from_diff(changed_pkgs, epoch):
    cbc_yaml, _ = get_cbc_info(epoch)

    changed_pkg_list = []
    for changed_pkg in changed_pkgs:
        changed_pkg_list.append(changed_pkg.replace('-', '_'))

    filtered_cbc_list = []
    filtered_cbc_yaml = {}
    for cbc_pkg, cbc_ver in cbc_yaml.items():
        for changed_pkg in changed_pkg_list:
            if changed_pkg == cbc_pkg:
                filtered_cbc_yaml[cbc_pkg.replace('_', '-')] = cbc_ver
                pkg_ver = _pkg_ver_helper(cbc_pkg, cbc_ver)
                filtered_cbc_list.append(pkg_ver)

    return filtered_cbc_yaml, filtered_cbc_list


# Get current distro dep structure from repodata.json under tested channel
def get_distro_deps(epoch, os):
    q2_pkg_channel_url = (f'https://packages.qiime2.org/qiime2/{epoch}/'
                          f'tested/{os}/repodata.json')
    q2_obj = _parse_url(q2_pkg_channel_url)
    q2_json = json.loads(q2_obj)

    # this is what's pulled from our tested channel on packages.qiime2.org
    q2_dep_dict = {}

    for name, info in q2_json['packages'].items():
        # stripping this segment for exact matching with the pkg list from CBC
        name = name.replace('-py38_0.tar.bz2', '')
        q2_dep_dict[name] = info['depends']

    dep_list = []
    for pkg, deps in q2_dep_dict.items():
        for dep in deps:
            if dep not in dep_list:
                dep = dep.split(' ')[0]
                dep_list.append(dep)
        q2_dep_dict[pkg] = dep_list
        dep_list = []

    return q2_dep_dict


# Get pkg dict with deps for pkgs on our tested channel
# that match the exact version from CBC.yml
# When used with a filtered pkg version list
# this will be the output that's used to generate repodata.patch
def get_pkg_dict(q2_dep_dict, pkg_ver_list):

    q2_pkg_dict = {}

    for q2_pkg, q2_deps in q2_dep_dict.items():
        for pkg in pkg_ver_list:
            # only selecting pkgs that match the exact ver from CBC vers
            if pkg == q2_pkg and q2_pkg not in q2_pkg_dict:
                q2_pkg_dict[q2_pkg] = q2_deps

    q2_pkg_dict = \
        {pkg.split('-2')[0]: deps for pkg, deps in q2_pkg_dict.items()}

    return q2_pkg_dict


# Generates both required outputs for the DAG:
# versioned downstream dep dict for patching purposes
# and a non-versioned downstream dep dict for DAG visualization
def get_changed_pkgs_downstream_deps(changed_pkgs, epoch, q2_pkg_dict):
    filtered_cbc_yaml, filtered_cbc_list = filter_cbc_from_diff(
        changed_pkgs=changed_pkgs, epoch=epoch)
    filtered_downstream_dict = {}

    for pkg in filtered_cbc_yaml.keys():
        dep_list = []
        for q2_pkg, deps in q2_pkg_dict.items():
            if pkg in deps:
                dep_list.append(q2_pkg)

        filtered_downstream_dict[pkg] = dep_list

    versioned_downstream_dict = \
        {versioned_pkg: filtered_downstream_dict[pkg]
         for pkg, versioned_pkg in zip(filtered_downstream_dict.keys(),
                                       filtered_cbc_list)}

    return filtered_downstream_dict, versioned_downstream_dict


# Create new DiGraph object & add list of pkgs from a given pkg dict as nodes
def make_dag(pkg_dict):

    dag = nx.DiGraph()
    dag.add_nodes_from(list(pkg_dict.keys()))

    # Add edges connecting each pkg to their list of deps
    for pkg, deps in pkg_dict.items():
        for dep in deps:
            dag.add_edge(dep, pkg)

    return dag


def draw_dag(G, edge_alpha=0.3):
    import matplotlib.pyplot as plt
    for layer, nodes in enumerate(nx.topological_generations(G)):
        # `multipartite_layout` expects the layer as a node attribute, so add
        # the numeric layer value as a node attribute
        for node in nodes:
            G.nodes[node]["layer"] = layer

    # Compute the multipartite_layout using the "layer" node attribute
    pos = nx.multipartite_layout(G, subset_key="layer", scale=800)

    fig, ax = plt.subplots(figsize=(18, 10))
    nx.draw_networkx_labels(G, pos=pos, font_weight='bold', ax=ax)
    nx.draw_networkx_edges(G, pos=pos, alpha=edge_alpha, ax=ax)
    fig.tight_layout()


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
