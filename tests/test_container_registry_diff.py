import unittest,tempfile,sqlite3
from contextlib import closing
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from container_registry_diff import compare,APP
class GuardTests(unittest.TestCase):
 def test_only_carrier_rows_allowed(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=[Path(d)/n for n in ('a.db','b.db')]
   for p in (a,b):
    with closing(sqlite3.connect(p)) as db,db:db.execute('CREATE TABLE apps(app_id TEXT,package TEXT,disabled TEXT)');db.execute("INSERT INTO apps VALUES('other','other','true')")
   with closing(sqlite3.connect(b)) as db,db:db.execute('INSERT INTO apps VALUES(?,?,?)',(APP,APP,'false'))
   self.assertEqual(len(compare(a,b,True)),1)
   with self.assertRaises(ValueError):compare(a,b)
   with closing(sqlite3.connect(b)) as db,db:db.execute("UPDATE apps SET disabled='false' WHERE app_id='other'")
   with self.assertRaises(ValueError):compare(a,b,True)
 def test_foreign_app_and_schema_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   a,b=[Path(d)/n for n in ('a.db','b.db')]
   for p in (a,b):
    with closing(sqlite3.connect(p)) as db,db:db.execute('CREATE TABLE apps(app_id TEXT,package TEXT)')
   with closing(sqlite3.connect(b)) as db,db:db.execute('INSERT INTO apps VALUES(?,?)',('foreign',APP))
   with self.assertRaises(ValueError):compare(a,b,True)
   with closing(sqlite3.connect(b)) as db,db:db.execute('ALTER TABLE apps ADD COLUMN x TEXT')
   with self.assertRaises(ValueError):compare(a,b,True)
if __name__=='__main__':unittest.main()
