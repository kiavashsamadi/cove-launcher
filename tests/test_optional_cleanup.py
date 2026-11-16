import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import optional_cleanup as p

def stages():return tuple(p.Stage(app,f'{n+1:064x}',f'{n+101:064x}') for n,app in enumerate(p.APPS))
class Adapter:
 def __init__(self,fail=None,unknown=None,restore_fail=None):
  self.fail=fail;self.unknown=unknown;self.restore_fail=restore_fail;self.calls=[];self.disabled=set()
 def apply(self,stage):
  app=stage.app_id;self.calls.append(('apply',app));self.disabled.add(app)
  if app==self.unknown:raise TimeoutError('Request outcome unknown')
  return app!=self.fail
 def apply_is_terminal(self,stage):
  # In this fixture the mutation commits before any simulated transport error.
  return True
 def restore(self,stage):
  app=stage.app_id;self.calls.append(('restore',app))
  if app==self.restore_fail:return False
  self.disabled.discard(app);return True
class BatchPolicy(unittest.TestCase):
 def test_only_explicit_optional_apps(self):
  for bad in ((),stages()[:-1],tuple(reversed(stages())),(p.Stage('org.tizen.menu','a'*64,'b'*64),)+stages()[1:]):
   with self.assertRaises(ValueError):p.validate(bad)
 def test_hashes_and_duplicate_contracts(self):
  for bad in (p.Stage(p.APPS[0],'short','b'*64),p.Stage(p.APPS[0],'g'*64,'b'*64)):
   with self.assertRaises(ValueError):p.validate((bad,)+stages()[1:])
  with self.assertRaises(ValueError):p.validate(tuple(p.Stage(s.app_id,'a'*64,s.manifest_sha256) for s in stages()))
 def test_success_is_complete_batch_no_undo(self):
  a=Adapter();r=p.apply(stages(),a,lambda *_:None)
  self.assertEqual(r['status'],'applied_owner_restart_validation_pending');self.assertEqual(len(a.calls),len(p.APPS))
 def test_every_failure_restores_only_attempted_prefix_reverse_order(self):
  for n,app in enumerate(p.APPS):
   with self.subTest(n=n):
    a=Adapter(fail=app);r=p.apply(stages(),a,lambda *_:None)
    self.assertEqual(r['status'],'failed_restored');self.assertFalse(a.disabled)
    self.assertEqual([app for role,app in a.calls if role=='restore'],list(reversed(p.APPS[:n+1])))
 def test_unknown_transport_outcome_includes_current_app_in_inverse(self):
  for app in p.APPS:
   a=Adapter(unknown=app);r=p.apply(stages(),a,lambda *_:None)
   self.assertEqual(r['status'],'failed_restored');self.assertFalse(a.disabled)
 def test_failed_inverse_does_not_skip_remaining_recovery(self):
  a=Adapter(fail=p.APPS[4],restore_fail=p.APPS[3]);r=p.apply(stages(),a,lambda *_:None)
  self.assertEqual(r['status'],'recovery_required')
  self.assertEqual([app for role,app in a.calls if role=='restore'],list(reversed(p.APPS[:5])))
 def test_durable_intent_failure_prevents_that_mutation(self):
  a=Adapter()
  def event(kind,stage):
   if kind=='before_apply' and stage.app_id==p.APPS[2]:raise OSError('Journal unavailable')
  r=p.apply(stages(),a,event)
  self.assertEqual(r['status'],'failed_restored');self.assertFalse(a.disabled)
  self.assertNotIn(('apply',p.APPS[2]),a.calls)
 def test_apply_acknowledgement_journal_failure_also_restores(self):
  a=Adapter()
  def event(kind,stage):
   if kind=='applied' and stage.app_id==p.APPS[1]:raise OSError('Journal unavailable')
  r=p.apply(stages(),a,event);self.assertEqual(r['status'],'failed_restored');self.assertFalse(a.disabled)
 def test_persistent_journal_outage_does_not_suppress_approved_inverse(self):
  a=Adapter();failed=False
  def event(kind,stage):
   nonlocal failed
   if kind=='applied':failed=True
   if failed:raise OSError('Journal unavailable')
  r=p.apply(stages(),a,event)
  self.assertEqual(r['status'],'failed_restored');self.assertFalse(a.disabled)
  self.assertIn(('restore',p.APPS[0]),a.calls)
 def test_recovery_rejects_foreign_or_reordered_selection(self):
  a=Adapter()
  for bad in (tuple(reversed(stages())),(p.Stage('org.tizen.menu','a'*64,'b'*64),)):
   with self.assertRaises(ValueError):p.restore_prefix(bad,a,lambda *_:None)
  self.assertFalse(a.calls)
 def test_late_apply_is_not_raced_by_an_early_inverse(self):
  class Delayed(Adapter):
   pending=None
   def apply(self,stage):
    if stage.app_id==p.APPS[2]:
     self.calls.append(('apply',stage.app_id));self.pending=stage
     raise TimeoutError('Server request remains live after the client timed out')
    return super().apply(stage)
   def apply_is_terminal(self,stage):return self.pending!=stage
   def complete_pending(self):
    self.disabled.add(self.pending.app_id);self.pending=None
  a=Delayed();r=p.apply(stages(),a,lambda *_:None)
  self.assertEqual(r['status'],'recovery_required')
  self.assertNotIn(('restore',p.APPS[2]),a.calls)
  self.assertEqual([app for role,app in a.calls if role=='restore'],[p.APPS[1],p.APPS[0]])
  self.assertFalse(a.disabled)
  a.complete_pending()
  self.assertEqual(a.disabled,{p.APPS[2]})
  recovered=p.restore_prefix(stages()[:3],a,lambda *_:None)
  self.assertTrue(all(ok for _,ok in recovered));self.assertFalse(a.disabled)
 def test_acknowledged_but_nonterminal_request_stops_next_stage(self):
  class Pending(Adapter):
   def apply_is_terminal(self,stage):return stage.app_id!=p.APPS[0]
  a=Pending();r=p.apply(stages(),a,lambda *_:None)
  self.assertEqual(r['status'],'recovery_required')
  self.assertEqual(a.calls,[('apply',p.APPS[0])])
 def test_unknown_terminal_evidence_never_authorizes_restore(self):
  for value in (False,None,0,1,'true'):
   a=Adapter(fail=p.APPS[0]);a.apply_is_terminal=lambda stage:value
   r=p.apply(stages(),a,lambda *_:None)
   self.assertEqual(r['status'],'recovery_required')
   self.assertNotIn(('restore',p.APPS[0]),a.calls)
 def test_terminal_evidence_exception_preserves_unknown_outcome(self):
  a=Adapter(fail=p.APPS[0])
  def unavailable(stage):raise OSError('Native completion evidence unavailable')
  a.apply_is_terminal=unavailable
  r=p.apply(stages(),a,lambda *_:None)
  self.assertEqual(r['status'],'recovery_required')
  self.assertEqual(a.calls,[('apply',p.APPS[0])])
 def test_old_adapter_is_rejected_before_any_apply(self):
  a=Adapter();a.apply_is_terminal=None
  with self.assertRaises(TypeError):p.apply(stages(),a,lambda *_:None)
  self.assertFalse(a.calls)
if __name__=='__main__':unittest.main()
