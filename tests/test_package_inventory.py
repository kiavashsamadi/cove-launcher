import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import compare_package_inventory as inventory


def fixture():
    return (['adplatform', 'com.samsung.tv.adplayer'],
            [{'package': 'adplatform'}, {'package': 'com.samsung.tv.adplayer'}],
            [{'app_id': 'adplatform.ADPlayer', 'package': 'adplatform', 'disable': 'false'},
             {'app_id': 'com.samsung.tv.adplayer', 'package': 'com.samsung.tv.adplayer', 'disable': 'true'}])


class PackageIdentity(unittest.TestCase):
    def test_distinct_web_and_native_players_are_not_conflated(self):
        result = inventory.compare(*fixture())
        self.assertEqual(result['rows'][0]['registration_state'], 'no_global_app_flags_disabled')
        self.assertEqual(result['rows'][1]['registration_state'], 'all_global_app_flags_disabled')
        self.assertEqual(result['rows'][0]['enabled_app_ids'], ['adplatform.ADPlayer'])
        for key in ('effective_launch_prevention_established', 'removal_qualified', 'runtime_or_per_user_state_checked', 'tv_contacted'):
            self.assertIs(result[key], False)

    def test_sibling_application_remains_enabled(self):
        catalog, packages, apps = fixture()
        apps.append(dict(app_id='extra.component', package=catalog[1], disable='false'))
        self.assertEqual(inventory.compare(catalog, packages, apps)['rows'][1]['registration_state'], 'mixed_global_app_flags')

    def test_package_flag_does_not_replace_app_evidence(self):
        catalog, packages, apps = fixture()
        packages[0]['disable'] = 'true'
        result = inventory.compare(catalog, packages, apps)
        self.assertEqual(result['rows'][0]['registration_state'], 'no_global_app_flags_disabled')

    def test_missing_package_and_empty_app_rows_are_distinct(self):
        result = inventory.compare(['missing', 'empty'], [{'package': 'empty'}], [])
        self.assertEqual([r['registration_state'] for r in result['rows']], ['absent', 'no_registered_apps'])

    def test_duplicate_or_out_of_scope_rows_are_rejected(self):
        baseline = fixture()
        for index, row in ((0, 'adplatform'), (1, {'package': 'adplatform'}), (2, baseline[2][0]),
                           (1, {'package': 'foreign'}), (2, {'app_id': 'orphan', 'package': 'foreign', 'disable': 'false'})):
            data = copy.deepcopy(baseline)
            data[index].append(row)
            with self.subTest(index=index, row=row), self.assertRaises(ValueError):
                inventory.compare(*data)

    def test_flag_coercion_and_missing_flag_are_rejected(self):
        for flag in (True, False, 0, 1, None, 'TRUE', 'False', '', 'true '):
            data = fixture()
            data[2][0]['disable'] = flag
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                inventory.compare(*data)
        data = fixture()
        del data[2][0]['disable']
        with self.assertRaises(ValueError): inventory.compare(*data)

    def test_identifiers_and_bounds_are_validated(self):
        for catalog in ([], ['x'] * 129, ['bad/id'], [None], 'not an array'):
            with self.subTest(catalog=catalog), self.assertRaises(ValueError):
                inventory.compare(catalog, [], [])
        with self.assertRaises(ValueError): inventory.compare(['x'], [], [{}] * 257)


if __name__ == '__main__': unittest.main()
