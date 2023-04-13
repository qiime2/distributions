import argparse
import json
import os


def main(changed_files, epoch, distro):
    if epoch == distro:
        raise Exception('Epoch and distro cannot be passed simultaneously,'
                        ' and one must be present.')
    if epoch:
        seen = identify_epoch(changed_files)
    if distro:
        seen = identify_distro(changed_files)

    seen = list(seen)[0]
    print(seen, end='')


def identify_epoch(changed_files):
    epochs = set()
    for rel_path in changed_files:
        base = rel_path.split(os.path.sep)[0]
        if base.startswith('2') and '.' in base:
            epochs.add(base)

    if len(epochs) > 1:
        raise Exception('Multiple epochs cannot be changed simultaneously.'
                        ' Epochs: %s' % epochs)

    if not epochs:
        raise Exception('No epochs modified')

    return epochs


def identify_distro(changed_files):
    distros = set()
    for rel_path in changed_files:
        segments = rel_path.split(os.path.sep)
        if len(segments) < 3:
            continue

        base = segments[0]
        if base.startswith('2') and '.' in base and segments[2] == 'passed':
            distros.add(segments[1])

    if len(distros) > 1:
        raise Exception('Multiple distros cannot be changed simultaneously.'
                        ' distros: %s' % distros)
    if not distros:
        raise Exception('No distros modified')

    return distros


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='determine what changed')
    parser.add_argument('changed_files', type=str,
                        help='space-separated list of changed files')
    parser.add_argument('--epoch', action='store_true')
    parser.add_argument('--distro', action='store_true')

    args = parser.parse_args()
    changed_files = args.changed_files.split(' ')

    main(changed_files, args.epoch, args.distro)
