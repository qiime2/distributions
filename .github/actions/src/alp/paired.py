class PairedDistroError(Exception):
    """
    Raised when an effective distro cannot be resolved for a paired ci-dev run
    """


def resolve_effective_distro(self_repo, self_distro, self_distros,
                              sibling_repo, sibling_distros,
                              sibling_primary_distro):
    """Resolve the effective distro for a single self/sibling pairing.

    Rules:
      - if sibling_primary_distro is in self_distros, use it
      - elif self_distro is in sibling_distros, use self_distro
      - if both of the above hold and disagree, that's ambiguous - raise
      - if neither holds, raise

    `sibling_primary_distro` may be `None` for repos that don't have a
    `primary_distro` in data.yaml (e.g. repos that don't use lib-ci-dev at
    all). In that case only the second rule can apply.
    """
    candidate_from_sibling = None
    if sibling_primary_distro is not None \
            and sibling_primary_distro in self_distros:
        candidate_from_sibling = sibling_primary_distro

    candidate_from_self = None
    if self_distro in sibling_distros:
        candidate_from_self = self_distro

    if candidate_from_sibling is not None \
            and candidate_from_self is not None \
            and candidate_from_sibling != candidate_from_self:
        raise PairedDistroError(
            f"Ambiguous effective distro between '{self_repo}' "
            f"(primary_distro={self_distro!r}) and '{sibling_repo}' "
            f"(primary_distro={sibling_primary_distro!r}): "
            f"'{candidate_from_sibling}' (from {sibling_repo}'s "
            f"primary_distro, which is in {self_repo}'s distros) and "
            f"'{candidate_from_self}' (from {self_repo}'s primary_distro, "
            f"which is in {sibling_repo}'s distros) are both valid "
            "candidates. Refusing to guess - this case is not currently "
            "supported."
        )

    if candidate_from_sibling is not None:
        return candidate_from_sibling

    if candidate_from_self is not None:
        return candidate_from_self

    raise PairedDistroError(
        f"Could not resolve an effective distro for the paired run between "
        f"'{self_repo}' (primary_distro={self_distro!r}, "
        f"distros={self_distros!r}) and '{sibling_repo}' "
        f"(primary_distro={sibling_primary_distro!r}, "
        f"distros={sibling_distros!r}). Neither repo's primary_distro is "
        "compatible with the other's distro list."
    )


def resolve_effective_distro_for_matches(self_repo, self_distro,
                                          self_distros, matches):
    """Resolve a single effective distro across one or more matched sibling
    repos.

    `matches` is an iterable of dicts with keys: `repo`, `distros`, and
    optionally `primary_distro` (treated as `None` if absent).

    Raises `PairedDistroError` if any individual match cannot be resolved,
    or if matches resolve to different effective distros (the multi-sibling
    case is supported mechanically, but punts on disagreement rather than
    picking a winner).
    """
    resolved = {}
    for match in matches:
        resolved[match['repo']] = resolve_effective_distro(
            self_repo=self_repo,
            self_distro=self_distro,
            self_distros=self_distros,
            sibling_repo=match['repo'],
            sibling_distros=match['distros'],
            sibling_primary_distro=match.get('primary_distro'),
        )

    distinct = set(resolved.values())
    if len(distinct) > 1:
        details = ', '.join(
            f"{repo}={dist!r}" for repo, dist in resolved.items())
        raise PairedDistroError(
            "Matched sibling repos resolved to different effective "
            f"distros, which is not currently supported: {details}"
        )

    return next(iter(distinct))
