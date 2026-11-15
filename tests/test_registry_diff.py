import sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from registry_diff import compare
def db():
 c=sqlite3.connect(':memory:');c.executescript("CREATE TABLE package_app_info(app_id TEXT PRIMARY KEY,app_disable TEXT,app_onboot TEXT,package TEXT);CREATE TABLE package_info(package TEXT PRIMARY KEY,disabled TEXT);INSERT INTO package_app_info VALUES('leaf','false','true','shared'),('sibling','false','false','shared'),('protected','true','false','core');INSERT INTO package_info VALUES('shared','false'),('core','false');")
 return c
class RegistryDiff(unittest.TestCase):
 def test_one_native_flag_only(self):
  a,b=db(),db();b.execute("UPDATE package_app_info SET app_disable='true' WHERE app_id='leaf'")
  self.assertTrue(compare(a,b,{'leaf':('false','true')})['passed'])
 def test_missing_request_not_reported_as_applied(self):self.assertFalse(compare(db(),db(),{'leaf':('false','true')})['passed'])
 def test_unselected_sibling_cascade_rejected(self):
  a,b=db(),db();b.execute("UPDATE package_app_info SET app_disable='true' WHERE package='shared'")
  self.assertFalse(compare(a,b,{'leaf':('false','true')})['passed'])
 def test_other_field_or_package_mutation_rejected(self):
  for sql in ("UPDATE package_app_info SET app_onboot='false' WHERE app_id='leaf'","UPDATE package_info SET disabled='true' WHERE package='shared'","DELETE FROM package_app_info WHERE app_id='protected'"):
   a,b=db(),db();b.execute("UPDATE package_app_info SET app_disable='true' WHERE app_id='leaf'");b.execute(sql)
   self.assertFalse(compare(a,b,{'leaf':('false','true')})['passed'])
 def test_schema_change_rejected(self):
  a,b=db(),db();b.execute('CREATE TABLE foreign_table(id INTEGER)');self.assertFalse(compare(a,b,{})['passed'])
 def test_typed_flag_change_rejected(self):
  a,b=db(),db();b.execute("UPDATE package_app_info SET app_disable=1 WHERE app_id='leaf'");self.assertFalse(compare(a,b,{'leaf':('false','true')})['passed'])
 def test_no_change_inverse_comparison(self):self.assertTrue(compare(db(),db(),{})['passed'])
 def test_inverse_does_not_restore_unrelated_protected_flag(self):
  original=db();disabled=db();disabled.execute("UPDATE package_app_info SET app_disable='true' WHERE app_id='leaf'")
  self.assertTrue(compare(disabled,original,{'leaf':('true','false')})['passed'])
  original.execute("UPDATE package_app_info SET app_disable='false' WHERE app_id='protected'")
  self.assertFalse(compare(disabled,original,{'leaf':('true','false')})['passed'])
if __name__=='__main__':unittest.main()
