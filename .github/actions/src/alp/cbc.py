def split_spec(install_spec):
    # incomplete and lazy, but matches what we assume for now
    return install_spec.split('=')


def process_seed_env_deps(env):
    cbc = {}
    mapping = {}
    for install_spec in env['dependencies']:
        package, version = split_spec(install_spec)

        cbc_package = package.replace('-', '_')
        cbc_version = [version]

        mapping[package] = cbc_package
        cbc[cbc_package] = cbc_version

    if 'extras' in env and 'variant_override' in env['extras']:
        cbc.update(env['extras']['variant_override'])

    return mapping, cbc
