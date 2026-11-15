"""Full logical comparison of local registry snapshots; never opens a live TV DB."""
from collections import Counter
import re

def compare(before, after, expected_flags):
 """Permit only explicit app_disable before/after pairs; reject all other drift."""
 schema="SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
 if before.execute(schema).fetchall()!=after.execute(schema).fetchall():
  return {'passed':False,'reason':'schema_changed','changes':[]}
 tables=[r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
 if len(tables)>128 or any(not re.fullmatch('[A-Za-z0-9_]+',t) for t in tables):
  raise ValueError('Unexpected snapshot schema')
 changes=[];seen=set();valid=True
 for table in tables:
  old=Counter(before.execute('SELECT * FROM "'+table+'"').fetchall())
  new=Counter(after.execute('SELECT * FROM "'+table+'"').fetchall())
  removed=list((old-new).elements());added=list((new-old).elements())
  if not removed and not added:continue
  columns=[r[1] for r in before.execute('PRAGMA table_info("'+table+'")')]
  permitted=table=='package_app_info' and len(removed)==len(added)
  if permitted:
   oi=columns.index('app_id');fi=columns.index('app_disable')
   removed_by_id={r[oi]:r for r in removed};added_by_id={r[oi]:r for r in added}
   permitted=len(removed_by_id)==len(removed) and removed_by_id.keys()==added_by_id.keys()
   for app,row in removed_by_id.items():
    pair=expected_flags.get(app)
    anticipated=list(row)
    if pair is None:permitted=False;continue
    anticipated[fi]=pair[1]
    if row[fi]!=pair[0] or tuple(anticipated)!=added_by_id.get(app):permitted=False
    seen.add(app)
  valid=valid and permitted
  changes.append({'table':table,'removed_count':len(removed),'added_count':len(added),'only_expected_app_flags':permitted})
 return {'passed':valid and seen==set(expected_flags),'reason':None if valid and seen==set(expected_flags) else 'unexpected_or_missing_change','changes':changes}
