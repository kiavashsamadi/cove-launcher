"""Host-only checks, source-export privacy scan and optional native compilation. No TV access."""
from pathlib import Path
import argparse,json,os,re,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--dotnet',default='dotnet')
parser.add_argument('--framework-dir',type=Path)
parser.add_argument('--browser',action='store_true',help='Also run the offline Playwright interaction regressions')
parser.add_argument('--node',default='node')
args=parser.parse_args()
env=os.environ.copy();env.update(DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',DOTNET_EnableDiagnostics='0')
runs=[]
def run(command):
 p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
 runs.append(dict(command=command,exit_code=p.returncode,output=p.stdout+p.stderr))
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return p.stdout

def audit_export():
 entries=run(['git','ls-files','-z','--cached','--others','--exclude-standard']).split('\0')
 deleted=set(run(['git','ls-files','-z','--deleted']).split('\0'))
 paths=sorted(set(p for p in entries if p and p not in deleted))
 rules={
  'GitHub credential':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})',
  'private key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
  'private network address':rb'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b',
  'personal Windows path':rb'[A-Za-z]:\\Users\\[^\\\s]+\\',
  'hardware network identity':rb'\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b',
 }
 for name in paths:
  path=ROOT/name
  if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise RuntimeError('Export path escapes repository: '+name)
  if path.suffix.lower() in ('.dll','.db','.sqlite3','.zip','.pdb','.key','.pem'):raise RuntimeError('Private/binary export: '+name)
  if path.suffix.lower() in ('.png','.jpg'):continue
  data=path.read_bytes()
  if path.suffix.lower() in ('.cs','.csproj','.py','.js','.cjs','.css','.html','.md','.json','.yml','.yaml','.svg'):
   decoded=data.decode('utf-8')
   if '\ufffd' in decoded:raise RuntimeError('Replacement character in public text: '+name)
  for label,pattern in rules.items():
   if re.search(pattern,data):raise RuntimeError(label+' found in '+name+'; no contents printed')
 return dict(files=len(paths),checked=True,scope='Publishable Git paths only; pattern scan plus explicit source-only export review')

try:
 export=audit_export()
 run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
 # The baseline control policy and native interop are shared; these checks do not call it.
 for project in ['Cove.Controls','Cove.Bootstrap','Cove.Presentation','Cove.Lifecycle']:
  run([args.dotnet,'run','--project',f'tests/{project}/{project}.csproj','-c','Release','-p:UseSharedCompilation=false'])
 if args.browser:run([args.node,'scripts/check-preview.cjs'])
 native=None
 if args.framework_dir:
  run([args.dotnet,'build','src/Cove.Native/Cove.Native.csproj','-c','Release','--nologo','-v','quiet','-p:UseSharedCompilation=false','-p:TV_FRAMEWORK_DIR='+str(args.framework_dir.resolve())])
  native=ROOT/'src/Cove.Native/bin/Release/net6.0/BixbyPromotion.dll'
  if native.stat().st_size>1048576:raise RuntimeError('Existing transport 1MiB artifact bound exceeded')
 report=dict(passed=True,source_export=export,runs=runs,native_bytes=native.stat().st_size if native else None,tv_contacted=False,github_published=False)
except Exception as error:
 report=dict(passed=False,error=str(error),runs=runs,tv_contacted=False,github_published=False)
(ROOT/'artifacts').mkdir(exist_ok=True)
(ROOT/'artifacts/checks.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='runs'},indent=2))
for item in runs:
 if item['command'][0]!='git':print(item['output'].strip())
raise SystemExit(0 if report['passed'] else 1)
