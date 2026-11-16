import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from model_dns_boot_recovery import Store,prepare,flip,recover,Conflict,Interrupted

class BootModel(unittest.TestCase):
 def test_repeated_boots_have_distinct_fences(self):
  s=Store(); seen={s.boot}
  for _ in range(4):
   s.reboot();self.assertNotIn(s.boot,seen);seen.add(s.boot)
 def test_retired_token_cannot_be_reused(self):
  s=Store();prepare(s,'one');flip(s,'one');recover(s,'one')
  with self.assertRaises(Conflict):prepare(s,'one')
 def test_power_loss_at_every_operation(self):
  for cut in range(1,6):
   s=Store(crash_at=cut)
   try:prepare(s,'one');flip(s,'one');recover(s,'one')
   except Interrupted:pass
   s.reboot()
   if s.journal:recover(s,'one')
   self.assertEqual(s.peer,'original-peer');self.assertIsNone(s.journal)
 def test_loopback_does_not_prevent_recovery_on_next_boot(self):
  s=Store();prepare(s,'one');flip(s,'one');s.reboot();recover(s,'one');self.assertEqual(s.peer,'original-peer')
 def test_old_watchdog_cannot_overwrite_new_transaction(self):
  s=Store();prepare(s,'one');flip(s,'one');recover(s,'one');s.peer='new-original';prepare(s,'two');flip(s,'two')
  with self.assertRaises(Conflict):recover(s,'one')
  self.assertEqual(s.peer,'temporary-loopback');recover(s,'two');self.assertEqual(s.peer,'new-original')
 def test_owner_change_preserved_with_evidence(self):
  s=Store();prepare(s,'one');flip(s,'one');s.peer='owner-choice';s.reboot()
  with self.assertRaises(Conflict):recover(s,'one')
  self.assertEqual(s.peer,'owner-choice');self.assertIsNotNone(s.journal)
 def test_untrusted_missing_or_corrupt_journal_refused(self):
  for value in (None,{},dict(token='one',boot='boot-1',original='original-peer',candidate='temporary-loopback',authenticated=False)):
   s=Store(peer='temporary-loopback',journal=value)
   with self.assertRaises(Conflict):recover(s,'one')
   self.assertEqual(s.peer,'temporary-loopback')
 def test_no_flip_without_fresh_ack(self):
  s=Store();prepare(s,'one');s.acknowledged=None
  with self.assertRaises(Conflict):flip(s,'one')
  self.assertEqual(s.peer,'original-peer')
  s.acknowledged=('one','boot-1');s.reboot()
  with self.assertRaises(Conflict):flip(s,'one')
 def test_pending_journal_prevents_reentry(self):
  s=Store();prepare(s,'one')
  with self.assertRaises(Conflict):prepare(s,'two')
 def test_original_change_before_flip(self):
  s=Store();prepare(s,'one');s.peer='owner-choice'
  with self.assertRaises(Conflict):flip(s,'one')
  self.assertEqual(s.peer,'owner-choice')
 def test_already_loopback_without_trusted_preimage_is_not_guessed(self):
  s=Store(peer='temporary-loopback')
  with self.assertRaises(Conflict):prepare(s,'one')
 def test_interrupted_restore_can_be_completed(self):
  s=Store();prepare(s,'one');flip(s,'one');s.crash_at=4
  with self.assertRaises(Interrupted):recover(s,'one')
  s.reboot();recover(s,'one');self.assertIsNone(s.journal)

if __name__=='__main__':unittest.main()
