#!/usr/bin/env python

import json
import os
import sys
import time
import urllib.error
import urllib.request

from alp.common import ActionAdapter


API = 'https://readthedocs.org/api/v3'

# RTD syncs its version records off the tag push webhook; give it more time
# than we ever expect for any of our builds to complete
SYNC_TIMEOUT = 15 * 60
BUILD_TIMEOUT = 90 * 60
POLL_INTERVAL = 30


def call(path, method='GET'):
    request = urllib.request.Request(
        API + path,
        headers={'Authorization': 'Token ' + os.environ['RTD_API_TOKEN']},
        method=method)

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        print(f'{method} {path} -> HTTP {e.code}: {e.read()[:500]!r}')
        raise


def stable_ref(rtd_slug):
    """The branch or tag that RTD' `stable` version resolves to.

    Newer payloads carry this as `ref`; older ones only as `identifier`.
    """
    version = call(f'/projects/{rtd_slug}/versions/stable/')

    return version.get('ref') or version.get('identifier')


def await_stable_ref(rtd_slug, epoch, commit):
    """Block until `stable` tracks epoch.

    The tag is force-pushed rather than deleted and recreated, so `stable`
    won't resolve to the prior epoch.
    """
    print(f'Waiting for RTD `stable` on {rtd_slug} to track {epoch}')
    deadline = time.time() + SYNC_TIMEOUT

    while True:
        ref = stable_ref(rtd_slug)
        print(f'  stable -> {ref}')

        if ref in (epoch, commit):
            return

        if time.time() > deadline:
            sys.exit(
                f'::error::RTD `stable` for {rtd_slug} still points at'
                f' {ref!r} after {SYNC_TIMEOUT // 60}m; expected {epoch}.'
                f' The tag push may not have reached RTD.')

        time.sleep(POLL_INTERVAL)


def trigger_build(rtd_slug):
    """Build `stable` explicitly instead of relying on the push webhook.
    """
    triggered = call(f'/projects/{rtd_slug}/versions/stable/builds/', 'POST')
    build_id = triggered.get('build', triggered)['id']
    print(f'Triggered `stable` build {build_id} for {rtd_slug}')

    return build_id


def await_build(rtd_slug, build_id):
    deadline = time.time() + BUILD_TIMEOUT

    while True:
        build = call(f'/projects/{rtd_slug}/builds/{build_id}/')
        state = (build.get('state') or {}).get('code')
        print(f'  state: {state}')

        if state == 'finished':
            return build

        if time.time() > deadline:
            sys.exit(
                f'::error::RTD build {build_id} for {rtd_slug} did not'
                f' finish within {BUILD_TIMEOUT // 60}m (state: {state}).')

        time.sleep(POLL_INTERVAL)


def verify_build(rtd_slug, build_id, build, epoch, commit):
    """Verify this was the same build from what we just pushed.
    """
    if not build.get('success'):
        sys.exit(f'::error::RTD `stable` build {build_id} for'
                 f' {rtd_slug} failed.')

    built = str(build.get('commit') or '')

    if built and not built.startswith(commit[:12]):
        sys.exit(
            f'::error::RTD `stable` build {build_id} for {rtd_slug}'
            f' succeeded but built commit {built}, expected {commit}.'
            f' `stable` is serving the wrong epoch.')

    print(f'RTD `stable` for {rtd_slug} is built from'
          f' {commit} ({epoch}).')


def main(rtd_slug, epoch, commit):
    await_stable_ref(rtd_slug, epoch, commit)
    build_id = trigger_build(rtd_slug)
    build = await_build(rtd_slug, build_id)
    verify_build(rtd_slug, build_id, build, epoch, commit)

    return {'build_id': build_id}


if __name__ == '__main__':
    ActionAdapter(main)
