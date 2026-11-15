"""Offline S90C inventory and transaction rehearsal. No TV connection or executor.

Reads a receipt-verified local SQLite snapshot; writes private drafts below
.local only. Drafts do not establish firmware semantics or authorize deployment.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('app_disable', 'app_onboot', 'app_autorestart', 'app_preload')
GROUPS = {
 'analytics': ['com.samsung.tizen.samsung-analytics', 'com.samsung.tv.targeted-ad-service'],
 'acr-review': ['com.samsung.tv.acr', 'com.samsung.tv.contents-recognition-dbmgr'],
 'pisa-held': ['com.samsung.tv.adagent-service', 'com.samsung.tv.pisa-service', 'org.tizen.pisa-control-service'],
 'recognition-preserve': ['com.samsung.tv.canalysis-service'],
 'voice': ['com.samsung.tv.alexa-client', 'com.samsung.tv.alexa-fullscreen-app',
  'com.samsung.tv.bixby-context-client', 'com.samsung.tv.bixby-prov',
  'com.samsung.tv.bixbycapsuleviewer', 'com.samsung.tv.mybixby',
  'com.samsung.tv.ondevice-voice', 'com.samsung.tv.utterance-recommender-app',
  'com.samsung.tv.utterance-recommender-core', 'com.samsung.tv.voice-instant-app',
  'com.samsung.tv.voiceassistant-music', 'com.samsung.tv.wakeup-engine-alexa',
  'com.samsung.tv.wakeup-engine-bixby', 'org.tizen.voice-app',
  'org.tizen.voice-app-service', 'org.tizen.voice-client', 'org.tizen.voice-onboarding'],
 'context': ['com.samsung.tv.AICompanionAgent', 'com.samsung.tv.AICompanionUI',
  'com.samsung.tv.AICompanionUILauncher', 'com.samsung.tv.AICompanionUINotice',
  'com.samsung.tv.ai-discovery-service', 'com.samsung.tv.ai-discovery-ui',
  'com.samsung.tv.context-aware-agent', 'com.samsung.tv.context-aware-agent-toast-view',
  'com.samsung.tv.context-aware-grab-control', 'com.samsung.tv.context-aware-server-requester',
  'com.samsung.tv.context-aware-service', 'com.samsung.tv.vif', 'content-grab-service'],
 'smart-extras': ['com.samsung.tizen.smartthings-client', 'com.samsung.tv.adplayer',
  'com.samsung.tv.ambient-sound', 'com.samsung.tv.aov-dashboard',
  'com.samsung.tv.ghdaemon', 'com.samsung.tv.ghservice',
  'com.samsung.tv.health-mde-service', 'com.samsung.tv.health-mde-service-view',
  'com.samsung.tv.smartthingsfind-daemon', 'com.samsung.tv.smartthingsfind-ondemand',
  'samsunghealth-service-tv'],
 'shell-last': ['com.samsung.tv.home.sidebar', 'org.tizen.browser'],
 'tv-plus': ['HEPsqFNie0.tvplusstandalone'],
}
# These exclusions are independent of selection and prevent broad group recipes
# from reaching the carrier or HDMI/picture/audio/Settings/security stack.
PROTECTED = frozenset({
 'com.samsung.tv.bixby-promotion', 'org.tizen.menu', 'org.tizen.tv-viewer',
 'com.samsung.tv.canalysis-service', 'com.samsung.tv.csfs', 'com.samsung.tv.quicklaunch',
})
HELD_GROUPS = frozenset({'pisa-held', 'recognition-preserve'})

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def identifier(value):
 if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', value):
  raise ValueError('Invalid application/package ID')
 return "'" + value + "'"

def boolean(value):
 if type(value) is not str or value not in ('true', 'false'):
  raise ValueError('Only observed canonical TEXT booleans are supported')
 return "'" + value + "'"

def verified_snapshot(snapshot, receipt):
 for path in (snapshot, receipt):
  if not path.is_absolute() or str(path).startswith(('\\\\', '//')) or path.is_symlink():
   raise ValueError('Explicit local regular files required')
  if not path.is_file():raise ValueError('Input file missing')
 if snapshot.stat().st_size > 16 * 1024 * 1024 or receipt.stat().st_size > 1024 * 1024:
  raise ValueError('Input exceeds bound')
 matches = [r for r in json.loads(receipt.read_text(encoding='utf-8'))['databases']
  if r.get('file') == snapshot.name and r.get('source') == '/opt/dbspace/.pkgmgr_parser.db']
 if len(matches) != 1:raise ValueError('Expected one registry receipt')
 record = matches[0]
 if record.get('integrity') != ['ok'] or record.get('bytes') != snapshot.stat().st_size or record.get('sha256') != digest(snapshot):
  raise ValueError('Snapshot receipt/hash/size mismatch')
 # Reject a sidecar: immutable=1 would otherwise hide an uncheckpointed WAL.
 if any(Path(str(snapshot)+suffix).exists() for suffix in ('-wal', '-journal')):
  raise ValueError('A standalone consistent snapshot is required')
 return record['sha256']

def open_snapshot(snapshot):
 db = sqlite3.connect(snapshot.resolve().as_uri()+'?mode=ro&immutable=1', uri=True)
 try:
  if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:raise ValueError('Snapshot integrity failure')
  for table, fields in {
   'package_app_info': {'app_id', 'package', 'app_component', 'app_support_disable', *FIELDS},
   'package_info': {'package', 'package_support_disable', 'package_disable'},
   'package_dependency_info': {'package', 'depends_on', 'type', 'required_version'},
  }.items():
   if not fields.issubset({r[1] for r in db.execute('PRAGMA table_info('+table+')')}):
    raise ValueError('Snapshot schema mismatch: '+table)
  return db
 except BaseException:db.close();raise

def inventory(db):
 db.row_factory = sqlite3.Row
 all_apps = [dict(r) for r in db.execute('SELECT app_id,package,app_component,app_support_disable,'+','.join(FIELDS)+' FROM package_app_info ORDER BY app_id')]
 if len(all_apps)>4096:raise ValueError('App inventory exceeds bound')
 result=[]
 for group, ids in GROUPS.items():
  for app in ids:
   found=[r for r in all_apps if r['app_id']==app]
   item={'group':group,'app_id':app,'present':bool(found),'ready_for_tv_apply':False}
   if len(found)>1:raise ValueError('Duplicate app record')
   if found:
    row=found[0];package=row['package'];identifier(package)
    parents=db.execute('SELECT package,package_support_disable,package_disable FROM package_info WHERE package=?',(package,)).fetchall()
    if len(parents)!=1:raise ValueError('Package record missing/ambiguous')
    item.update(row=row,package_info=dict(parents[0]),
     siblings=[r for r in all_apps if r['package']==package],
     dependencies=[dict(r) for r in db.execute('SELECT package,depends_on,type,required_version FROM package_dependency_info WHERE package=? OR depends_on=?',(package,package))])
   item['blockers']=['fresh awake-TV snapshot and exact firmware recheck','native consumer/dependency review','temporary supervised trial and inverse validation','new explicit approval']
   if group in HELD_GROUPS:item['blockers'].insert(0,'hard hold: shutdown failures or required HDMI recognition')
   if found and found[0]['app_support_disable']!='true':item['blockers'].append('app does not advertise supported disable')
   if group=='shell-last':item['blockers'].append('new renderer Settings/recovery handoff not owner-verified')
   result.append(item)
 return result

def proposed_patches(items, group, kind):
 if group in HELD_GROUPS:raise ValueError('Group is held; no rehearsal mutation generated')
 if group not in GROUPS or kind!='disable':raise ValueError('Preload metadata is not a qualified background-launch control; only disable review drafts are supported')
 patches=[]
 for item in items:
  if item['group']!=group or not item['present']:continue
  row=item['row'];app=row['app_id'];package=row['package']
  if app in PROTECTED or any(s['app_id'] in PROTECTED for s in item['siblings']):
   raise ValueError('Protected app or shared package')
  targets={'app_disable':'true','app_onboot':'false','app_autorestart':'false'}
  changes={}
  for field, after in targets.items():
   before=row[field];boolean(before)
   if before!=after:changes[field]={'before':before,'after':after}
  if changes:patches.append({'app_id':app,'package':package,'fields':changes})
 return patches

def transaction(patches, restore=False):
 if not patches:raise ValueError('Empty transaction')
 if len({p['app_id'] for p in patches})!=len(patches):raise ValueError('Duplicate target')
 # RAISE(ROLLBACK) ends the entire transaction on drift, including earlier
 # changes. A CHECK constraint alone would only abort one statement.
 lines=['BEGIN IMMEDIATE;', 'CREATE TEMP TABLE still_draft_guard(ok INTEGER);',
  "CREATE TEMP TRIGGER still_draft_reject BEFORE INSERT ON still_draft_guard WHEN NEW.ok IS NOT 1 BEGIN SELECT RAISE(ROLLBACK,'draft_state_drift'); END;"]
 for patch in patches:
  if patch['app_id'] in PROTECTED:raise ValueError('Protected target')
  app=identifier(patch['app_id']);package=identifier(patch['package'])
  if not patch['fields'] or not set(patch['fields']).issubset(FIELDS):raise ValueError('Unapproved field')
  conditions=[f'app_id={app}',f'package={package}']
  for field, pair in patch['fields'].items():
   expected=boolean(pair['after' if restore else 'before']);boolean(pair['before']);boolean(pair['after'])
   conditions += [f'typeof({field})=\'text\'',f'{field} IS {expected}']
  lines.append('INSERT INTO still_draft_guard SELECT count(*)=1 FROM package_app_info WHERE app_id='+app+';')
  lines.append('INSERT INTO still_draft_guard SELECT count(*)=1 FROM package_app_info WHERE '+' AND '.join(conditions)+';')
 for patch in patches:
  assignments=','.join(field+'='+boolean(pair['before' if restore else 'after']) for field,pair in patch['fields'].items())
  lines.append('UPDATE package_app_info SET '+assignments+' WHERE app_id='+identifier(patch['app_id'])+';')
 lines+=['DROP TRIGGER still_draft_reject;','DROP TABLE still_draft_guard;','COMMIT;']
 return '\n'.join(lines)+'\n'

def rehearse(source, patches):
 with closing(sqlite3.connect(':memory:')) as clone:
  source.backup(clone)
  # Unexpected vendor triggers can modify unrelated records; do not rehearse
  # those as if this were an isolated flag update.
  if clone.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='package_app_info'").fetchone()[0]:
   raise ValueError('Registry triggers require separate review')
  before='\n'.join(clone.iterdump())
  clone.executescript(transaction(patches))
  for patch in patches:
   fields=list(patch['fields']);row=clone.execute('SELECT '+','.join(fields)+' FROM package_app_info WHERE app_id=?',(patch['app_id'],)).fetchone()
   if tuple(row)!=tuple(patch['fields'][field]['after'] for field in fields):raise ValueError('Draft readback failed')
  clone.executescript(transaction(patches,True))
  if '\n'.join(clone.iterdump())!=before:raise ValueError('Draft inverse changed snapshot contents')
 return {'in_memory_only':True,'apply_readback':True,'inverse_full_logical_dump_equal':True}

def prepare(snapshot, receipt, output):
 root=(ROOT/'.local').resolve();output=output.resolve()
 if not output.is_relative_to(root) or output==root or output.exists():raise ValueError('Use a new output directory below .local')
 sha=verified_snapshot(snapshot,receipt)
 with closing(open_snapshot(snapshot)) as db:
  items=inventory(db);drafts=[]
  # These are alternative review drafts, not a sequential or approved batch.
  for group in GROUPS:
   if group in HELD_GROUPS:continue
   for kind in ('disable',):
    patches=proposed_patches(items,group,kind)
    if patches:drafts.append({'group':group,'kind':kind,'patches':patches,'rehearsal':rehearse(db,patches)})
  report={'schema':1,'scope':'OFFLINE_REVIEW_ONLY','tv_contacted':False,'permanent_changes_approved':False,
   'ready_for_tv_apply':False,'snapshot_sha256':sha,'snapshot_is_historical':True,
   'inventory':items,'drafts':drafts,'missing_ids':[i['app_id'] for i in items if not i['present']],
   'limits':['Registry declarations are not a runtime dependency map or tracking audit.',
    'app_preload remains observational metadata; no preload-flag mutations are generated.',
    'In-memory inverse equality is not a successful TV service shutdown or recovery test.',
    'No sockets, transport, shell wrapper, app killer, boot hook or live executor is provided.']}
 output.mkdir(parents=True,exist_ok=False)
 (output/'review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 for draft in drafts:
  prefix=draft['group']+'-'+draft['kind']
  for action in ('apply','restore'):
   (output/(prefix+'-'+action+'.sql.txt')).write_text('-- OFFLINE REHEARSAL DRAFT. NOT QUALIFIED FOR TV EXECUTION.\n'+transaction(draft['patches'],action=='restore'),encoding='utf-8')
 return {'review':str(output/'review.json'),'present':sum(i['present'] for i in items),'missing':len(report['missing_ids']),
  'drafts_rehearsed':len(drafts),'ready_for_tv_apply':False,'tv_contacted':False}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--snapshot',required=True,type=Path);parser.add_argument('--receipt',required=True,type=Path)
 parser.add_argument('--output',required=True,type=Path)
 args=parser.parse_args()
 print(json.dumps(prepare(args.snapshot,args.receipt,args.output),indent=2))
