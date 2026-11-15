"""Offline transaction integrity checks; never import a TV transport."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('preparation',Path(__file__).resolve().parents[1]/'scripts/prepare_privacy.py')
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)

class Transactions(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:')
  self.db.executescript('CREATE TABLE package_app_info(app_id TEXT,package TEXT,app_disable TEXT,app_onboot TEXT,app_autorestart TEXT,app_preload TEXT,note TEXT);')
  self.db.executemany('INSERT INTO package_app_info VALUES(?,?,?,?,?,?,?)',[
   ('optional.one','optional.pkg','false','false','true','true','keep'),
   ('optional.two','optional.pkg','false','true','false','true','keep'),
   ('org.tizen.menu','settings','false','false','true','true','protected')])
  self.db.commit()
  self.patches=[{'app_id':'optional.one','package':'optional.pkg','fields':{'app_preload':{'before':'true','after':'false'}}}]
 def tearDown(self):self.db.close()
 def rows(self):return self.db.execute('SELECT * FROM package_app_info ORDER BY app_id').fetchall()
 def test_roundtrip_and_readback(self):
  original=self.rows();self.db.executescript(prep.transaction(self.patches))
  self.assertEqual(self.db.execute("SELECT app_preload FROM package_app_info WHERE app_id='optional.one'").fetchone(),('false',))
  self.db.executescript(prep.transaction(self.patches,True));self.assertEqual(self.rows(),original)
 def test_inverse_preserves_unrelated_changes(self):
  self.db.executescript(prep.transaction(self.patches));self.db.execute("UPDATE package_app_info SET note='new',app_onboot='true' WHERE app_id='optional.one'");self.db.commit()
  self.db.executescript(prep.transaction(self.patches,True))
  self.assertEqual(self.db.execute("SELECT app_preload,note,app_onboot FROM package_app_info WHERE app_id='optional.one'").fetchone(),('true','new','true'))
 def test_drift_aborts_entire_transaction(self):
  self.db.execute("UPDATE package_app_info SET app_preload='false' WHERE app_id='optional.one'");self.db.commit();before=self.rows()
  with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(prep.transaction(self.patches))
  self.assertFalse(self.db.in_transaction);self.assertEqual(self.rows(),before)
 def test_inverse_refuses_selected_field_drift(self):
  before=self.rows()
  with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(prep.transaction(self.patches,True))
  self.assertFalse(self.db.in_transaction);self.assertEqual(self.rows(),before)
 def test_second_target_drift_keeps_first_untouched(self):
  second={'app_id':'optional.two','package':'optional.pkg','fields':{'app_preload':{'before':'false','after':'true'}}}
  before=self.rows()
  with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(prep.transaction(self.patches+[second]))
  self.assertEqual(self.rows(),before)
 def test_duplicate_record_refused(self):
  self.db.execute("INSERT INTO package_app_info SELECT * FROM package_app_info WHERE app_id='optional.one'");self.db.commit();before=self.rows()
  with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(prep.transaction(self.patches))
  self.assertEqual(self.rows(),before)
 def test_package_replacement_refused(self):
  self.db.execute("UPDATE package_app_info SET package='replacement' WHERE app_id='optional.one'");self.db.commit()
  with self.assertRaises(sqlite3.IntegrityError):self.db.executescript(prep.transaction(self.patches))
  self.assertFalse(self.db.in_transaction)
 def test_unknown_boolean_encoding_refused(self):
  for value in (True,False,1,0,None,'TRUE','0','true;DROP TABLE x'):
   with self.subTest(value=value),self.assertRaises(ValueError):prep.boolean(value)
 def test_protected_and_arbitrary_fields_refused(self):
  for app,fields in [('org.tizen.menu',self.patches[0]['fields']),('optional.one',{'app_exec':{'before':'true','after':'false'}})]:
   with self.assertRaises(ValueError):prep.transaction([{'app_id':app,'package':'settings','fields':fields}])
 def test_id_injection_and_duplicate_targets_refused(self):
  with self.assertRaises(ValueError):prep.identifier("x';DROP TABLE x;--")
  with self.assertRaises(ValueError):prep.transaction(self.patches*2)
 def test_held_groups_have_no_draft(self):
  for group in prep.HELD_GROUPS:
   with self.assertRaises(ValueError):prep.proposed_patches([],group,'disable')
 def test_shared_protected_package_refused(self):
  row={'app_id':'optional.one','package':'settings','app_preload':'true'}
  item={'group':'voice','present':True,'row':row,'siblings':[row,{'app_id':'org.tizen.menu'}]}
  with self.assertRaises(ValueError):prep.proposed_patches([item],'voice','disable')
 def test_preload_metadata_not_a_qualified_launch_control(self):
  with self.assertRaises(ValueError):prep.proposed_patches([],'voice','preload')
 def test_memory_rehearsal_restores_full_dump(self):
  self.assertTrue(prep.rehearse(self.db,self.patches)['inverse_full_logical_dump_equal'])
 def test_vendor_trigger_requires_review(self):
  self.db.executescript("CREATE TRIGGER vendor AFTER UPDATE ON package_app_info BEGIN UPDATE package_app_info SET note='side effect';END;")
  with self.assertRaises(ValueError):prep.rehearse(self.db,self.patches)

class Receipts(unittest.TestCase):
 def test_hash_sidecar_and_input_refusals(self):
  with tempfile.TemporaryDirectory() as folder:
   snapshot=Path(folder)/'.pkgmgr_parser.db';snapshot.write_bytes(b'fixture');receipt=Path(folder)/'receipt.json'
   data={'databases':[{'file':snapshot.name,'source':'/opt/dbspace/.pkgmgr_parser.db','integrity':['ok'],'bytes':7,'sha256':prep.digest(snapshot)}]}
   receipt.write_text(json.dumps(data));self.assertEqual(prep.verified_snapshot(snapshot,receipt),prep.digest(snapshot))
   sidecar=Path(str(snapshot)+'-wal');sidecar.touch()
   with self.assertRaises(ValueError):prep.verified_snapshot(snapshot,receipt)
   sidecar.unlink();snapshot.write_bytes(b'changed')
   with self.assertRaises(ValueError):prep.verified_snapshot(snapshot,receipt)
   with self.assertRaises(ValueError):prep.verified_snapshot(Path('relative.db'),receipt)
 def test_no_output_outside_private_directory(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(ValueError):prep.prepare(Path('absent'),Path('absent'),Path(folder)/'outside')

if __name__=='__main__':unittest.main()
