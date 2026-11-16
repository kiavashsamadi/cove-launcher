import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_update_policy import POLICIES, PENDING, assess

def fixture():
    lines = [key + ', value = ' + ('False' if kind == 'Boolean' else '0') + ' (' + kind + ')'
             for key, kind in {**POLICIES, **PENDING}.items()]
    return dict(root_launched=False, settings_changed=False, errors=[],
                cleanup={'sdk_helpers_and_gates_absent': True}, status='read_completed', reads={
                    'update_keys': dict(exit_code=0, output='\n'.join(lines) + '\n[cove_read_status:0]'),
                    'pending_markers': dict(exit_code=0, output='markers_absent\n[cove_read_status:0]'),
                })

class UpdatePolicy(unittest.TestCase):
    def test_verified_values_make_only_narrow_claims(self):
        result = assess(fixture())
        self.assertEqual(result['automatic_update_policies_off'], 4)
        for key in ('all_update_paths_blocked', 'all_telemetry_off', 'new_restart_verified', 'tv_contacted'):
            self.assertFalse(result[key])

    def test_each_enabled_or_pending_value_refuses(self):
        for key, kind in {**POLICIES, **PENDING}.items():
            r = fixture()
            r['reads']['update_keys']['output'] = r['reads']['update_keys']['output'].replace(
                key + ', value = ' + ('False' if kind == 'Boolean' else '0'),
                key + ', value = ' + ('True' if kind == 'Boolean' else '1'))
            with self.subTest(key=key), self.assertRaises(ValueError): assess(r)

    def test_missing_extra_duplicate_or_wrong_type_refuses(self):
        for defect in ('missing', 'extra', 'duplicate', 'type', 'bool-as-int', 'int-as-bool'):
            r = fixture(); lines = r['reads']['update_keys']['output'].splitlines()
            if defect == 'missing': lines.pop(0)
            elif defect == 'extra': lines.insert(0, 'unreviewed.key, value = 0 (Int32)')
            elif defect == 'duplicate': lines.insert(0, lines[0])
            elif defect == 'type': lines[0] = lines[0].replace('Int32', 'Boolean')
            elif defect == 'bool-as-int': lines[2] = lines[2].replace('False', '0')
            else: lines[0] = lines[0].replace('value = 0', 'value = False')
            r['reads']['update_keys']['output'] = '\n'.join(lines)
            with self.subTest(defect=defect), self.assertRaises(ValueError): assess(r)

    def test_incomplete_read_or_marker_guard_refuses(self):
        for name in ('update_keys', 'pending_markers'):
            for defect in ('exit', 'missing', 'duplicate', 'content'):
                r = fixture(); row = r['reads'][name]
                if defect == 'exit': row['exit_code'] = 1
                elif defect == 'missing': row['output'] = row['output'].replace('[cove_read_status:0]', '')
                elif defect == 'duplicate': row['output'] += '\n[cove_read_status:0]'
                else: row['output'] = 'unknown\n[cove_read_status:0]'
                with self.subTest(name=name, defect=defect), self.assertRaises(ValueError): assess(r)

    def test_unclean_or_mutating_receipt_refuses(self):
        for key, value in [('root_launched', True), ('settings_changed', True), ('errors', ['error']),
                           ('cleanup', {}), ('status', 'stopped')]:
            r = fixture(); r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): assess(r)

if __name__ == '__main__': unittest.main()
