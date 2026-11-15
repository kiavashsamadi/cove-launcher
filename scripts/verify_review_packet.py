"""Validate a private evidence ZIP without extracting files or executing code."""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import re
import stat
import zipfile

MAX_ENTRIES=512
MAX_FILE=32*1024*1024
MAX_TOTAL=256*1024*1024

def unique_object(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('Duplicate manifest key')
  result[key]=value
 return result

def safe_name(name):
 path=PurePosixPath(name)
 if not name or path.is_absolute() or '\\' in name or ':' in name or any(part in ('','..','.') for part in name.split('/')):
  raise ValueError('Invalid archive path')
 return name

def verify(path):
 with zipfile.ZipFile(path) as packet:
  entries=packet.infolist()
  if len(entries)>MAX_ENTRIES:raise ValueError('Too many entries')
  names=[safe_name(item.filename) for item in entries]
  if len(names)!=len(set(names)):raise ValueError('Duplicate archive name')
  if sum(item.file_size for item in entries)>MAX_TOTAL:raise ValueError('Packet exceeds total bound')
  for item in entries:
   mode=item.external_attr>>16
   if item.is_dir() or stat.S_IFMT(mode) not in (0,stat.S_IFREG) or item.file_size>MAX_FILE or item.flag_bits&1:
    raise ValueError('Unsupported entry type, size or encryption')
  if 'manifest.json' not in names or packet.getinfo('manifest.json').file_size>1024*1024:
   raise ValueError('Manifest missing or oversized')
  manifest=json.loads(packet.read('manifest.json'),object_pairs_hook=unique_object)
  if type(manifest.get('schema')) is not int or manifest['schema']!=1 or manifest.get('scope')!='PRIVATE_EVIDENCE_NOT_A_PORTABLE_INSTALLER' or not isinstance(manifest.get('files'),dict):
   raise ValueError('Unknown packet manifest')
  expected=manifest['files']
  if set(names)!=(set(expected)|{'manifest.json'}):raise ValueError('Unexpected or missing file')
  for name,record in expected.items():
   safe_name(name)
   if not isinstance(record,dict) or type(record.get('bytes')) is not int or not isinstance(record.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',record['sha256']):
    raise ValueError('Invalid file record')
   item=packet.getinfo(name)
   if item.file_size!=record['bytes']:raise ValueError('File size differs: '+name)
   digest=hashlib.sha256();count=0
   with packet.open(item) as stream:
    while True:
     chunk=stream.read(1024*1024)
     if not chunk:break
     count+=len(chunk)
     if count>MAX_FILE:raise ValueError('Uncompressed read bound')
     digest.update(chunk)
   if count!=record['bytes'] or digest.hexdigest()!=record['sha256']:raise ValueError('File hash differs: '+name)
 return {'verified':True,'files':len(expected),'uncompressed_bytes':sum(i.file_size for i in entries),
  'extracted':False,'executed':False,'tv_contacted':False,
  'limit':'Integrity against this manifest; no cryptographic authenticity or native recovery proof'}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('packet');args=parser.parse_args()
 print(json.dumps(verify(args.packet),indent=2))
