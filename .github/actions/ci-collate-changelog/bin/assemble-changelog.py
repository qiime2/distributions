#!/usr/bin/env python

"""Assemble the full release changelog from the per-plugin fragments.

Run by the ``collate`` job of ``ci-collate-changelog`` from the root of a
distributions checkout, after the per-plugin fragments (written by
``collate-changelog.py``) have been downloaded into ``--fragments``::

    fragments/plugins/<name>.md    -> "Plugin Updates"
    fragments/breaking/<name>.md   -> "Breaking Changes"

The release range is <released_epoch>.0 -> <active_epoch>.0 from data.yaml.

"Distribution Updates" is computed per distro by diffing the packages in the
env files of ``<active_epoch>/<distro>/passed/`` (the new release) against
``<released_epoch>/<distro>/released/`` (the previous release):

- added: present in the new release only, and a package in data.yaml
- removed: present in the previous release only, and either a package in
  data.yaml or pinned to the previous release's version (e.g. ``=2026.7.0``),
  which catches packages already dropped from data.yaml (e.g. q2cli)

Dependencies present on both sides are never reported, whatever their versions
(date-versioned ones like ca-certificates can look like ours). A distro folder
that only exists in the new release is reported as a new distribution (without
listing its packages), and one that only exists in the previous release as a
removed distribution.

Sections with nothing generated for them get a ``<!-- TODO -->`` placeholder
for the hand-written parts of the announcement.

With ``--mode patch`` it instead assembles a patch release announcement for
``--release-tag`` (the original <epoch>.0 release): the fixed intro and
closing text around the plugin fragments.
"""
import argparse
import os
import re

import yaml

TODO = "<!-- TODO -->"

PATCH_INTRO = """\
Hello QIIME 2 community! 👋🏼
We have just released a patch for the {epoch} release to address a few \
bugs/last minute improvements. If you've already installed any distribution \
for {epoch} prior to this patch, please re-install 🙏🏻

All of the changes included in this patch are listed below."""

PATCH_OUTRO = (
    "Thanks to everyone for getting these fixes out so quickly; please don't "
    "hesitate to reach out with any questions!"
)
SEPARATOR = "---"

# "  - q2-types=2026.10.0.dev0+4.g0ebb43c" -> ("q2-types", "2026.10.0.dev0+...")
PINNED_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_.\-]+)=(\S+)")


def read_fragments(directory):
    """Non-empty fragments in ``directory``, sorted by file (package) name."""
    if not os.path.isdir(directory):
        return []
    fragments = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(directory, fname)) as fh:
            text = fh.read().strip()
        if text:
            fragments.append(text)
    return fragments


def env_packages(env_dir):
    """{name: {versions}} for every package pinned in any env file."""
    packages = {}
    for fname in sorted(os.listdir(env_dir)):
        if not fname.endswith((".yml", ".yaml")):
            continue
        with open(os.path.join(env_dir, fname)) as fh:
            for line in fh:
                m = PINNED_RE.match(line)
                if m:
                    packages.setdefault(m.group(1), set()).add(m.group(2))
    return packages


def is_release_version(versions, epoch):
    """True if any version is a release of ``epoch``, e.g. 2026.7.0."""
    pattern = re.compile(rf"^{re.escape(epoch)}\.\d+$")
    return any(pattern.match(v) for v in versions)


def distros_in(root, epoch, stage):
    """Distro names that have a ``<epoch>/<distro>/<stage>/`` folder."""
    epoch_dir = os.path.join(root, epoch)
    if not os.path.isdir(epoch_dir):
        return set()
    return {d for d in os.listdir(epoch_dir)
            if os.path.isdir(os.path.join(epoch_dir, d, stage))}


def join_names(names):
    names = list(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def distribution_updates(root, data):
    released, active = data["released_epoch"], data["active_epoch"]
    by_name = {p["name"]: p for p in data.get("packages") or []}
    distro_order = data.get("distros") or []

    def order(distros):
        return sorted(distros, key=lambda d: (
            distro_order.index(d) if d in distro_order else len(distro_order),
            d))

    def label(name):
        pkg = by_name.get(name)
        if pkg is None:
            return name
        display = pkg.get("display_name") or name
        return f"[{display}](https://github.com/{pkg['repo']})"

    def where(distros):
        noun = "distribution" if len(distros) == 1 else "distributions"
        return f"the {join_names(order(distros))} {noun}"

    before = distros_in(root, released, "released")
    after = distros_in(root, active, "passed")

    added, removed = {}, {}
    for distro in before & after:
        old = env_packages(os.path.join(root, released, distro, "released"))
        new = env_packages(os.path.join(root, active, distro, "passed"))
        for name in new.keys() - old.keys():
            if name in by_name:
                added.setdefault(name, set()).add(distro)
        for name in old.keys() - new.keys():
            if name in by_name or is_release_version(old[name], released):
                removed.setdefault(name, set()).add(distro)

    lines = []
    for distro in order(after - before):
        lines.append(f"- **New {distro} distribution has been added**")
    for distro in order(before - after):
        lines.append(f"- **The {distro} distribution has been removed**")
    for name in sorted(added):
        lines.append(f"- **{label(name)} has been added** to "
                     f"{where(added[name])}")
    for name in sorted(removed):
        lines.append(f"- **{label(name)} has been removed** from "
                     f"{where(removed[name])}")
    return lines


def section(title, body_lines):
    return "\n".join([title, ""] + (body_lines or [TODO]))


def assemble(root, data, fragments_dir):
    release_tag = f"{data['active_epoch']}.0"
    previous_tag = f"{data['released_epoch']}.0"
    breaking = read_fragments(os.path.join(fragments_dir, "breaking"))
    plugins = read_fragments(os.path.join(fragments_dir, "plugins"))

    sections = [
        "\n".join([
            "# 🚨 Important Announcements 🚨", "",
            f"### Changes coming in {data['next_epoch']} :boom:", "",
            TODO,
        ]),
        section("# :bangbang: Breaking Changes :bangbang:",
                ["\n\n".join(breaking)] if breaking else []),
        section("# Developer Announcements 🧱", []),
        "# ✨ Here are the Highlights of the Release! ✨",
        section("# [Q2View Updates](https://view.qiime2.org) :mag:", []),
        section("# [Distribution Updates](https://github.com/qiime2/"
                "distributions) :package:",
                distribution_updates(root, data)),
        section("# Docker Container Updates :jar:", []),
        section("# Documentation Updates :book:", []),
        section("# Interface Updates :tv:", []),
        section("# Plugin Updates :electric_plug:",
                [f"_Changes in {previous_tag} → {release_tag}_", "",
                 "\n\n".join(plugins)] if plugins else []),
    ]
    return f"\n\n{SEPARATOR}\n\n".join(sections) + "\n"


def assemble_patch(release_tag, fragments_dir):
    epoch = release_tag.rsplit(".", 1)[0]
    plugins = read_fragments(os.path.join(fragments_dir, "plugins"))
    return "\n\n".join([
        PATCH_INTRO.format(epoch=epoch),
        "\n\n".join(plugins) if plugins else TODO,
        PATCH_OUTRO,
    ]) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".",
                        help="root of the distributions checkout")
    parser.add_argument("--data", default="data.yaml")
    parser.add_argument("--fragments", default="fragments")
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="release",
                        choices=["release", "patch"])
    parser.add_argument("--release-tag",
                        help="the original <epoch>.0 release (patch mode)")
    args = parser.parse_args()

    if args.mode == "patch":
        if not args.release_tag:
            parser.error("--release-tag is required with --mode patch")
        changelog = assemble_patch(args.release_tag, args.fragments)
    else:
        with open(args.data) as fh:
            data = yaml.safe_load(fh)
        changelog = assemble(args.root, data, args.fragments)
    with open(args.output, "w") as fh:
        fh.write(changelog)
    print(changelog)


if __name__ == "__main__":
    main()
