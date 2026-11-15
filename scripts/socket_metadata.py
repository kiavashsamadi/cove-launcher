"""Decode bounded Linux little-endian proc socket metadata. Offline; never connects."""
from __future__ import annotations
import ipaddress
import re

SCOPE = 'fixed-read-only-selected-sockets-v3'
NAMES = ('data-service', 'pushd', 'sso-service', 'connmand', 'canalysis-daemo',
         'canalysis-daemon', 'pisa-service', 'adagent-service')
TABLES = ('tcp', 'tcp6', 'udp', 'udp6')

def endpoint(value, ipv6):
    width = 32 if ipv6 else 8
    if not isinstance(value, str) or not re.fullmatch(r'[0-9A-Fa-f]{'+str(width)+r'}:[0-9A-Fa-f]{4}', value):
        raise ValueError('Malformed full proc endpoint')
    raw, port = value.split(':')
    # Kernel prints native u32 values, including each IPv6 word; this profile
    # is explicitly little endian. The port is printed in host numeric order.
    decoded = b''.join(bytes.fromhex(raw[i:i+8])[::-1] for i in range(0, width, 8))
    return {'address': str(ipaddress.ip_address(decoded)), 'port': int(port, 16)}

def positive(value):
    return type(value) is int and value > 0

def validate(report):
    if report.get('scope') != SCOPE or report.get('schema_version') != 3 or report.get('completed') is not True:
        raise ValueError('Incomplete or wrong metadata scope')
    if report.get('uid') != 0 or report.get('euid') != 0 or report.get('little_endian') is not True:
        raise ValueError('Wrong identity or byte order')
    if any(report.get(k) is not False for k in ('payload_capture', 'service_control', 'settings_or_registry_write')):
        raise ValueError('Unexpected diagnostic capabilities')
    if report.get('known_children_ended') is not True or report.get('started_children') != []:
        raise ValueError('This diagnostic has no child processes')
    if report.get('selected_names') != list(NAMES):
        raise ValueError('Process allowlist differs')
    samples = report.get('snapshots', [])
    if len(samples) != 2: raise ValueError('Two complete snapshots required')
    result = []
    for sample in samples:
        if sample.get('tables') != list(TABLES) or sample.get('complete') is not True:
            raise ValueError('Incomplete protocol coverage')
        skipped = sample.get('transient_processes_skipped')
        if type(skipped) is not int or not 0 <= skipped <= 640 or sample.get('process_inventory_complete') is not (skipped == 0):
            raise ValueError('Process churn must be explicit')
        processes = sample.get('processes', [])
        if not isinstance(processes, list) or len(processes) > 16:
            raise ValueError('Process bound exceeded')
        owners = {}
        for p in processes:
            pid = p.get('pid')
            if (not positive(pid) or pid in owners or p.get('name') not in NAMES or
                not positive(p.get('start_ticks')) or p.get('identity_stable') is not True or
                type(p.get('uid')) is not int or p['uid'] < 0 or p.get('same_network_namespace') is not True):
                raise ValueError('Unstable/ambiguous process identity')
            owners[pid] = p
        sockets = sample.get('sockets', [])
        if not isinstance(sockets, list) or len(sockets) > 128:
            raise ValueError('Socket bound exceeded')
        rows = []; seen = set()
        for s in sockets:
            p = owners.get(s.get('pid')); protocol = s.get('protocol')
            if p is None or protocol not in TABLES or not positive(s.get('inode')):
                raise ValueError('Unknown socket owner/protocol')
            identity = (s['pid'], protocol, s['inode'])
            if identity in seen: raise ValueError('Duplicate socket mapping')
            seen.add(identity)
            if not isinstance(s.get('state'), str) or not re.fullmatch(r'[0-9A-Fa-f]{2}', s['state']):
                raise ValueError('Malformed socket state')
            if type(s.get('uid')) is not int or s['uid'] < 0: raise ValueError('Malformed socket UID')
            rows.append({**s, 'process_name': p['name'],
                         'local': endpoint(s['local_hex'], protocol.endswith('6')),
                         'remote': endpoint(s['remote_hex'], protocol.endswith('6'))})
        result.append({'processes': processes, 'sockets': rows, 'transient_processes_skipped': skipped, 'process_inventory_complete': skipped == 0})
    return {'metadata_read_verified': True, 'snapshots': result, 'all_telemetry_off': False,
            'process_absence_proven': False, 'byte_rates_measured': False, 'payload_contents_known': False,
            'limitation': 'Two non-atomic samples of selected processes only. Short-lived sockets, later sends, shared hosts and other network namespaces are not excluded.'}
