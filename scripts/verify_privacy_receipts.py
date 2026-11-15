"""Offline checks for the narrow, already-applied privacy measures.

Does not contact a TV, change settings, or establish that all telemetry is off.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path

APPS=frozenset({
 'com.samsung.tv.targeted-ad-service','com.samsung.tizen.samsung-analytics',
 'com.samsung.tv.adplayer','com.samsung.tv.acr','com.samsung.tv.health-mde-service',
 'com.samsung.tv.health-mde-service-view','samsunghealth-service-tv',
 'com.samsung.tv.smartthingsfind-daemon','com.samsung.tv.smartthingsfind-ondemand',
})

def _clean(receipt):
 if receipt.get('root_launched') is not False or receipt.get('settings_changed') is not False:
  raise ValueError('Read-only SDK receipt required')
 if receipt.get('errors')!=[] or receipt.get('cleanup')!={'sdk_helpers_and_gates_absent':True}:
  raise ValueError('Complete read and SDK cleanup required')

def verify_apps(receipt):
 _clean(receipt)
 if receipt.get('status')!='exact_final_batch_flags_verified' or receipt.get('process_inventory_truncated') is not False:
  raise ValueError('Complete flag/process observation required')
 apps=receipt.get('apps',{})
 if set(apps)!=APPS:raise ValueError('Exactly the nine reviewed applications are required')
 for app,entry in apps.items():
  if entry.get('expected_complete_records_match') is not True or entry.get('app_disable')!='true':
   raise ValueError('Reviewed flag or surrounding records differ: '+app)
  if entry.get('global_uid')!=[] or entry.get('owner')!={'apps':0,'packages':0,'rows':[]}:
   raise ValueError('Unexpected per-user registration: '+app)
  rows=entry.get('actual',{}).get('app',[])
  if len(rows)!=1 or rows[0].get('app_id')!=app or rows[0].get('app_disable')!='true':
   raise ValueError('Actual global record does not establish the disable: '+app)
  if entry.get('process_name_match_observed') is not False or entry.get('matching_process_name_rows')!=[]:
   raise ValueError('A selected process was observed; investigate without auto-killing: '+app)
 return {'disabled_global_flags':len(apps),'selected_process_aliases_absent_in_sample':True}

def verify_pisa(receipt):
 _clean(receipt)
 if receipt.get('status')!='startup_condition_block_verified' or receipt.get('marker_matches_applied_inode_and_metadata') is not True:
  raise ValueError('Bound startup marker must match the applied identity')
 if receipt.get('home_and_startup_preserved') is not True or receipt.get('matching_process_rows')!=[]:
  raise ValueError('Routing or runtime evidence differs')
 units=receipt.get('units',{})
 expected={'pisa-service.service','adagent-service.service','pisa-service.socket','pisa-service.path'}
 if set(units)!=expected:raise ValueError('All four relevant activation units are required')
 for name,u in units.items():
  if any(u.get(k)!=v for k,v in {'Id':name,'LoadState':'loaded','Result':'success','DropInPaths':'','NeedDaemonReload':'no'}.items()):
   raise ValueError('Unit definition/status differs: '+name)
  state={'ActiveState':'inactive','SubState':'dead','ConditionResult':'yes'}
  if name.endswith('.service'):state.update(MainPID='0',ConditionResult='no')
  elif name.endswith('.path'):state.update(ActiveState='active',SubState='waiting')
  if any(u.get(k)!=v for k,v in state.items()):raise ValueError('Unexpected activation state: '+name)
 return {'pisa_adagent_startup_condition_block_verified':True,'new_restart_claimed':False}

def assess(apps,pisa):
 return {**verify_apps(apps),**verify_pisa(pisa),'all_telemetry_off':False,
  'limitations':['Process samples do not exclude renamed, shared-host or later activation.',
                 'Startup conditions do not prove every direct entry point is blocked.',
                 'No packet-content or traffic-rate audit; Internet access is retained.'],
  'tv_contacted':False}

def load(path):
 if not path.is_file() or path.is_symlink() or path.stat().st_size>1024*1024:raise ValueError('Bounded regular receipt required')
 return json.loads(path.read_text(encoding='utf-8'))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apps',type=Path,required=True);p.add_argument('--pisa',type=Path,required=True);args=p.parse_args()
 print(json.dumps(assess(load(args.apps),load(args.pisa)),indent=2))
