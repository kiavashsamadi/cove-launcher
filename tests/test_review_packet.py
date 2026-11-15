import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('packet_verify',Path(__file__).resolve().parents[1]/'scripts/verify_review_packet.py')
verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)

class Packets(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'review.zip'
 def tearDown(self):self.folder.cleanup()
 def packet(self,extra=None,wrong_hash=False):
  content=b'private fixture'
  manifest={'schema':1,'scope':'PRIVATE_EVIDENCE_NOT_A_PORTABLE_INSTALLER','files':{
   'review.txt':{'bytes':len(content),'sha256':'0'*64 if wrong_hash else hashlib.sha256(content).hexdigest()}}}
  with zipfile.ZipFile(self.path,'w') as out:
   out.writestr('manifest.json',json.dumps(manifest));out.writestr('review.txt',content)
   if extra is not None:out.writestr(extra,b'extra')
 def test_valid_without_extraction(self):
  self.packet();result=verify.verify(self.path)
  self.assertTrue(result['verified']);self.assertFalse(result['extracted']);self.assertEqual(list(Path(self.folder.name).iterdir()),[self.path])
 def test_corruption_refused(self):
  self.packet(wrong_hash=True)
  with self.assertRaises(ValueError):verify.verify(self.path)
 def test_extra_and_duplicate_files_refused(self):
  for name in ('unexpected.txt','review.txt'):
   with self.subTest(name=name):
    if name=='review.txt':
     with self.assertWarns(UserWarning):self.packet(extra=name)
    else:self.packet(extra=name)
    with self.assertRaises(ValueError):verify.verify(self.path)
 def test_path_traversal_and_platform_paths_refused(self):
  for name in ('../escape','/absolute','a/../escape','a\\escape','C:/escape','a//b','a/./b'):
   with self.subTest(name=name):
    self.packet(extra=name)
    with self.assertRaises(ValueError):verify.verify(self.path)
 def test_symlink_refused(self):
  self.packet()
  with zipfile.ZipFile(self.path,'a') as out:
   item=zipfile.ZipInfo('link');item.create_system=3;item.external_attr=0o120777<<16;out.writestr(item,b'review.txt')
  with self.assertRaises(ValueError):verify.verify(self.path)
 def test_manifest_duplicate_keys_refused(self):
  with zipfile.ZipFile(self.path,'w') as out:out.writestr('manifest.json','{"schema":1,"schema":1}')
  with self.assertRaises(ValueError):verify.verify(self.path)
 def test_limits_enforced(self):
  self.packet();old=verify.MAX_TOTAL
  try:
   verify.MAX_TOTAL=1
   with self.assertRaises(ValueError):verify.verify(self.path)
  finally:verify.MAX_TOTAL=old

if __name__=='__main__':unittest.main()
