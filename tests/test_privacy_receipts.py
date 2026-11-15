import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_privacy_receipts import APPS,assess,verify_apps,verify_pisa

def fixtures():
 common=dict(root_launched=False,settings_changed=False,errors=[],cleanup={'sdk_helpers_and_gates_absent':True})
 apps=dict(common,status='exact_final_batch_flags_verified',process_inventory_truncated=False,apps={})
 for app in APPS:
  apps['apps'][app]=dict(expected_complete_records_match=True,app_disable='true',global_uid=[],owner={'apps':0,'packages':0,'rows':[]},actual={'app':[{'app_id':app,'app_disable':'true'}]},process_name_match_observed=False,matching_process_name_rows=[])
 pisa=dict(common,status='startup_condition_block_verified',marker_matches_applied_inode_and_metadata=True,home_and_startup_preserved=True,matching_process_rows=[],units={})
 for name in ('pisa-service.service','adagent-service.service','pisa-service.socket','pisa-service.path'):
  state=dict(Id=name,LoadState='loaded',Result='success',DropInPaths='',NeedDaemonReload='no',ActiveState='inactive',SubState='dead',ConditionResult='yes')
  if name.endswith('.service'):state.update(MainPID='0',ConditionResult='no')
  if name.endswith('.path'):state.update(ActiveState='active',SubState='waiting')
  pisa['units'][name]=state
 return apps,pisa

class PrivacyReceipts(unittest.TestCase):
 def test_narrow_success_never_claims_all_telemetry(self):
  result=assess(*fixtures());self.assertEqual(result['disabled_global_flags'],9);self.assertFalse(result['all_telemetry_off']);self.assertFalse(result['new_restart_claimed'])
 def test_status_alone_cannot_hide_wrong_actual_flag(self):
  apps,_=fixtures();next(iter(apps['apps'].values()))['actual']['app'][0]['app_disable']='false'
  with self.assertRaises(ValueError):verify_apps(apps)
 def test_missing_extra_or_running_app_refuses(self):
  for defect in ('missing','extra','running'):
   apps,_=fixtures();key=next(iter(apps['apps']))
   if defect=='missing':del apps['apps'][key]
   elif defect=='extra':apps['apps']['foreign.app']=copy.deepcopy(apps['apps'][key])
   else:apps['apps'][key]['matching_process_name_rows']=['123 process']
   with self.subTest(defect=defect),self.assertRaises(ValueError):verify_apps(apps)
 def test_truncated_or_unclean_sample_refuses(self):
  for key,value in [('process_inventory_truncated',True),('errors',['read failed']),('cleanup',{}),('settings_changed',True)]:
   apps,_=fixtures();apps[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):verify_apps(apps)
 def test_marker_and_unit_activation_cannot_be_summarized_away(self):
  for key,value in [('MainPID','7'),('ConditionResult','yes'),('ActiveState','active'),('DropInPaths','override.conf')]:
   _,pisa=fixtures();pisa['units']['pisa-service.service'][key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):verify_pisa(pisa)
  _,pisa=fixtures();pisa['marker_matches_applied_inode_and_metadata']=False
  with self.assertRaises(ValueError):verify_pisa(pisa)
 def test_path_and_socket_are_part_of_evidence(self):
  _,pisa=fixtures();del pisa['units']['pisa-service.socket']
  with self.assertRaises(ValueError):verify_pisa(pisa)
if __name__=='__main__':unittest.main()
