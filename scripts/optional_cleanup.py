"""Fixed optional-app batch policy. No network, shell, TV path or executor.

The private adapter must provide verified one-app native transactions and a
durable event sink. A transport exception is an UNKNOWN outcome and includes the
current app in recovery. Restore failure never authorizes a broader operation.
"""
from dataclasses import dataclass

APPS = (
 'com.samsung.tizen.samsung-analytics',
 'com.samsung.tv.adplayer',
 'com.samsung.tv.health-mde-service',
 'com.samsung.tv.health-mde-service-view',
 'samsunghealth-service-tv',
 'com.samsung.tv.smartthingsfind-daemon',
 'com.samsung.tv.smartthingsfind-ondemand',
 'com.samsung.tv.acr',
)

@dataclass(frozen=True)
class Stage:
 app_id: str
 plan_id: str
 manifest_sha256: str

def validate(stages, *, prefix=False):
 expected=APPS[:len(stages)] if prefix else APPS
 if len(stages)>len(APPS) or tuple(s.app_id for s in stages) != expected:
  raise ValueError('Exact reviewed app selection/order required')
 for stage in stages:
  for digest in (stage.plan_id, stage.manifest_sha256):
   if type(digest) is not str or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
    raise ValueError('Exact sealed stage hashes required')
 if len({s.plan_id for s in stages}) != len(stages):
  raise ValueError('Distinct app-bound transactions required')

def restore_prefix(stages, adapter, event):
 validate(stages,prefix=True)
 results=[]
 for stage in reversed(stages):
  # Journal outage must not suppress an already-authorized recovery request.
  try:event('before_restore', stage)
  except Exception:pass
  try:
   ok=adapter.restore(stage) is True
  except Exception:
   ok=False
  try:event('restored' if ok else 'restore_unverified', stage)
  except Exception:pass
  results.append((stage.app_id,ok))
 return results

def apply(stages, adapter, event):
 validate(stages)
 attempted=[]
 for stage in stages:
  try:
   # This durable event must finish BEFORE any request can reach the TV.
   event('before_apply',stage)
   attempted.append(stage)
   if adapter.apply(stage) is not True:
    raise RuntimeError('Native apply/readback unverified')
   event('applied',stage)
  except Exception:
   recovery=restore_prefix(attempted,adapter,event)
   return {'status':'failed_restored' if all(ok for _,ok in recovery) else 'recovery_required',
    'attempted':[s.app_id for s in attempted],'recovery':recovery}
 return {'status':'applied_owner_restart_validation_pending','attempted':[s.app_id for s in attempted],'recovery':[]}
