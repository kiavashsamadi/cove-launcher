"""Fault-inject draft transactions on disposable copies of a verified snapshot.

No TV access or live executor. Private evidence stays below .local. A passing
audit qualifies only SQL isolation/inverses, never service behavior or deployment.
"""
from contextlib import closing
from pathlib import Path
import argparse
import hashlib
import json
import sqlite3
import prepare_privacy as prep

def dump(db):return '\n'.join(db.iterdump())

def copy_database(source):
 clone=sqlite3.connect(':memory:');source.backup(clone);return clone

def require_refusal(db,sql):
 before=dump(db)
 try:db.executescript(sql)
 except sqlite3.IntegrityError:
  if db.in_transaction or dump(db)!=before:raise ValueError('Conflict did not leave the database unchanged')
 else:raise ValueError('Conflict was accepted')

def expected_rows(db,patches):
 db.row_factory=sqlite3.Row
 before={r['app_id']:dict(r) for r in db.execute('SELECT * FROM package_app_info')}
 for patch in patches:
  for field,pair in patch['fields'].items():before[patch['app_id']][field]=pair['after']
 return before

def audit_group(source,patches):
 result={}
 with closing(copy_database(source)) as db:
  expected=expected_rows(db,patches)
  # Authorizer rejects writes outside the intended columns/table, even if a
  # future edit to the generator adds a broader assignment accidentally.
  allowed={field for patch in patches for field in patch['fields']}
  def authorize(action,arg1,arg2,database,origin):
   if action==sqlite3.SQLITE_UPDATE and database=='main':
    if arg1!='package_app_info' or arg2 not in allowed:return sqlite3.SQLITE_DENY
   if action in (sqlite3.SQLITE_INSERT,sqlite3.SQLITE_DELETE) and database=='main':
    return sqlite3.SQLITE_DENY
   return sqlite3.SQLITE_OK
  db.set_authorizer(authorize)
  db.executescript(prep.transaction(patches))
  actual={r['app_id']:dict(r) for r in db.execute('SELECT * FROM package_app_info')}
  if actual!=expected:raise ValueError('Apply changed a field or app outside the proposal')
  db.set_authorizer(None);result['exact_all_app_rows_after_apply']=True
 with closing(copy_database(source)) as db:
  # A failed last target must prevent every earlier intended change.
  patch=patches[-1];field=next(iter(patch['fields']))
  db.execute('UPDATE package_app_info SET '+field+'=? WHERE app_id=?',
   (patch['fields'][field]['after'],patch['app_id']));db.commit()
  require_refusal(db,prep.transaction(patches));result['forward_selected_field_drift_refused_atomically']=True
 with closing(copy_database(source)) as db:
  db.executescript(prep.transaction(patches));patch=patches[-1];field=next(iter(patch['fields']))
  db.execute('UPDATE package_app_info SET '+field+'=? WHERE app_id=?',
   (patch['fields'][field]['before'],patch['app_id']));db.commit()
  require_refusal(db,prep.transaction(patches,True));result['inverse_selected_field_drift_refused_atomically']=True
 with closing(copy_database(source)) as db:
  patch=patches[0]
  db.execute('UPDATE package_app_info SET package=? WHERE app_id=?',('changed.package',patch['app_id']));db.commit()
  require_refusal(db,prep.transaction(patches));result['replaced_package_refused']=True
 with closing(copy_database(source)) as db:
  # A realistic unrelated concurrent catalog edit must survive reversal. The
  # chosen field is never part of a draft and the protected Settings row is
  # never a target. Original snapshot bytes are never modified.
  baseline=db.execute("SELECT app_nodisplay FROM package_app_info WHERE app_id='org.tizen.menu'").fetchone()
  if baseline is None or baseline[0] not in ('true','false'):raise ValueError('Settings fixture differs')
  changed='false' if baseline[0]=='true' else 'true'
  db.execute("UPDATE package_app_info SET app_nodisplay=? WHERE app_id='org.tizen.menu'",(changed,));db.commit()
  expected=dump(db)
  db.executescript(prep.transaction(patches));db.executescript(prep.transaction(patches,True))
  if dump(db)!=expected:raise ValueError('Inverse erased an unrelated catalog update')
  result['unrelated_protected_app_edit_preserved']=True
 with closing(copy_database(source)) as db:
  # Canonical text booleans only, even on schema columns without a type CHECK.
  patch=patches[0];field=next(iter(patch['fields']))
  db.execute('UPDATE package_app_info SET '+field+'=? WHERE app_id=?',('TRUE',patch['app_id']));db.commit()
  require_refusal(db,prep.transaction(patches));result['noncanonical_encoding_refused']=True
 return result

def audit(snapshot,receipt,output):
 root=(prep.ROOT/'.local').resolve();output=output.resolve()
 if output==root or not output.is_relative_to(root) or output.exists():raise ValueError('Use new private .local output')
 before=prep.verified_snapshot(snapshot,receipt)
 results=[]
 with closing(prep.open_snapshot(snapshot)) as db:
  items=prep.inventory(db)
  for group in prep.GROUPS:
   if group in prep.HELD_GROUPS:continue
   for kind in ('disable',):
    patches=prep.proposed_patches(items,group,kind)
    if patches:results.append({'group':group,'kind':kind,'checks':audit_group(db,patches)})
 if prep.digest(snapshot)!=before:raise ValueError('Original snapshot changed')
 report={'scope':'PC_ONLY_FAILURE_INJECTION','snapshot_sha256':before,'snapshot_unchanged':True,
  'tv_contacted':False,'native_behavior_qualified':False,'ready_for_tv_apply':False,
  'drafts':results,'scenarios_passed':sum(len(r['checks']) for r in results),'passed':True}
 output.mkdir(parents=True,exist_ok=False)
 (output/'audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 return {'passed':True,'drafts':len(results),'scenarios':report['scenarios_passed'],'report':str(output/'audit.json'),'tv_contacted':False}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('snapshot','receipt','output'):parser.add_argument('--'+name,required=True,type=Path)
 args=parser.parse_args();print(json.dumps(audit(args.snapshot,args.receipt,args.output),indent=2))
