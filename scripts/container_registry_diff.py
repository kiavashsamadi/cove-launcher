"""Host-only package restoration diff. Reads local snapshots; no network, TV API or database writes."""
from collections import Counter
from contextlib import closing
import sqlite3
from pathlib import Path
APP='com.samsung.tv.bixby-promotion'
def owned(columns,row):
 ids=[row[i] for i,k in enumerate(columns) if k in ('app_id','package')]
 return bool(ids) and all(x==APP for x in ids)
def compare(before,after,allow_carrier=False):
 def open_db(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
 with closing(open_db(before)) as a,closing(open_db(after)) as b:
  schema=lambda db:sorted(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
  if schema(a)!=schema(b):raise ValueError('Registry schema changed')
  tables=[r[0] for r in a.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")];changes=[]
  for name in tables:
   ident='"'+name.replace('"','""')+'"';cols=[r[1] for r in a.execute('PRAGMA table_info('+ident+')')]
   av=Counter(a.execute('SELECT * FROM '+ident));bv=Counter(b.execute('SELECT * FROM '+ident));removed=list((av-bv).elements());added=list((bv-av).elements())
   if removed or added:
    if not allow_carrier or any(not owned(cols,row) for row in removed+added):raise ValueError('Unrelated registry changes: '+name)
    changes.append({'table':name,'removed':len(removed),'added':len(added)})
  return changes
