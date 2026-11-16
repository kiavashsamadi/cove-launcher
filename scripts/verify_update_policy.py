"""Offline verification of a private, read-only automatic-update policy receipt.

Does not contact a TV, change policy, or prove that all update paths are blocked.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from verify_privacy_receipts import _clean, load

POLICIES = {
    'db/menu/support/softwareupdate/autoupdate': 'Int32',
    'db/SyncML/ivi-oma-dm-service/software-update/autoupdate/setting': 'Int32',
    'db/apps/auto_update': 'Boolean',
    'db/built-in-app-upgrader/server_upgrade': 'Boolean',
}
PENDING = {
    'db/menu/support/softwareupdate/reboot': 'Int32',
    'db/menu/support/softwareupdate/upgrade_verified_successfully': 'Int32',
    'db/menu/support/softwareupdate/upgrade_finalization_schedule': 'Int32',
}

def output(receipt, name):
    row = receipt.get('reads', {}).get(name, {})
    text = row.get('output')
    if type(row.get('exit_code')) is not int or row['exit_code'] != 0 or not isinstance(text, str):
        raise ValueError('Successful typed read required: ' + name)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or lines[-1] != '[cove_read_status:0]' or lines.count('[cove_read_status:0]') != 1:
        raise ValueError('Unambiguous read completion required')
    return lines[:-1]

def assess(receipt):
    _clean(receipt)
    if receipt.get('status') != 'read_completed':
        raise ValueError('Completed read-only receipt required')
    expected = {**POLICIES, **PENDING}
    values = {}
    for line in output(receipt, 'update_keys'):
        match = re.fullmatch(r'([^,]+), value = (0|1|True|False) \((Int32|Boolean)\)', line)
        if not match or match[1] not in expected or match[1] in values or match[3] != expected[match[1]]:
            raise ValueError('Unknown, duplicate or incorrectly typed policy key')
        off = 'False' if match[3] == 'Boolean' else '0'
        if match[2] != off:
            raise ValueError('Policy is enabled, pending state is nonzero, or value has the wrong type')
        values[match[1]] = match[2]
    if set(values) != set(expected):
        raise ValueError('All four policies and three pending-update keys required')
    if output(receipt, 'pending_markers') != ['markers_absent']:
        raise ValueError('Known pending-update markers not established absent')
    return {
        'automatic_update_policies_off': 4,
        'inspected_pending_flags_zero': 3,
        'known_pending_markers_absent_at_read': True,
        'new_restart_verified': False,
        'all_update_paths_blocked': False,
        'all_telemetry_off': False,
        'tv_contacted': False,
        'limitations': [
            'Receipt checks do not establish freshness or independently attest its origin.',
            'A new cold boot and fresh device-bound readback are separate persistence checks.',
            'Manual updates, store/server restoration and network traffic remain separate paths.',
        ],
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(assess(load(args.receipt)), indent=2))
