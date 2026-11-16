"""Compare an explicit package catalog with global registry rows, offline.

Package IDs and application IDs are different namespaces. A disabled native
application does not establish that a similarly named web package is disabled.
This reports recorded global flags only: it does not inspect per-user overrides,
prove effective launch prevention, qualify removal, or contact a TV.
"""
import argparse
import json
import re
from pathlib import Path


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value):
        raise ValueError('Invalid registry identifier')
    return value


def compare(catalog, packages, apps):
    if type(catalog) is not list or not 1 <= len(catalog) <= 128:
        raise ValueError('An explicit bounded package catalog is required')
    wanted = {_identifier(value) for value in catalog}
    if len(wanted) != len(catalog):
        raise ValueError('Duplicate catalog package')
    if type(packages) is not list or len(packages) > 128 or type(apps) is not list or len(apps) > 256:
        raise ValueError('Bounded package/application rows required')
    present = set()
    for row in packages:
        if type(row) is not dict:
            raise ValueError('Invalid package row')
        package = _identifier(row.get('package'))
        if package not in wanted or package in present:
            raise ValueError('Unexpected or duplicate package')
        present.add(package)
    grouped = {package: [] for package in present}
    seen = set()
    for row in apps:
        if type(row) is not dict:
            raise ValueError('Invalid application row')
        app_id = _identifier(row.get('app_id'))
        package = _identifier(row.get('package'))
        if app_id in seen or package not in present:
            raise ValueError('Duplicate application or missing parent package')
        if type(row.get('disable')) is not str or row['disable'] not in ('true', 'false'):
            raise ValueError('Exact native text flag required')
        seen.add(app_id)
        grouped[package].append((app_id, row['disable'] == 'true'))
    rows = []
    for package in catalog:
        entries = sorted(grouped.get(package, []))
        disabled = [app for app, flag in entries if flag]
        enabled = [app for app, flag in entries if not flag]
        if package not in present:
            state = 'absent'
        elif not entries:
            state = 'no_registered_apps'
        elif not enabled:
            state = 'all_global_app_flags_disabled'
        elif disabled:
            state = 'mixed_global_app_flags'
        else:
            state = 'no_global_app_flags_disabled'
        rows.append(dict(package=package, registration_state=state,
                         disabled_app_ids=disabled, enabled_app_ids=enabled))
    return dict(scope='Recorded global application flags only', rows=rows,
                effective_launch_prevention_established=False, removal_qualified=False,
                runtime_or_per_user_state_checked=False, tv_contacted=False)


def load(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 262144:
        raise ValueError('Bounded regular JSON input required')
    return json.loads(path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path, help='Private JSON with catalog, packages and apps arrays')
    args = parser.parse_args()
    data = load(args.inventory)
    print(json.dumps(compare(data['catalog'], data['packages'], data['apps']), indent=2))
