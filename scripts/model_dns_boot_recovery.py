"""Offline boot-peer recovery model. No TV/file/network execution.

Atomic durable authenticated journaling and compare-and-set are MODEL assumptions.
Neither is established for Samsung's native peer setter. This is not deployable.
"""
from dataclasses import dataclass,field

class Conflict(RuntimeError):pass
class Interrupted(RuntimeError):pass

@dataclass
class Store:
    peer:str='original-peer'
    boot:str='boot-1'
    journal:dict|None=None
    acknowledged:tuple|None=None
    events:list=field(default_factory=list)
    tokens:set=field(default_factory=set)
    crash_at:int|None=None
    boot_count:int=1
    def event(self,name):
        self.events.append(name)
        if self.crash_at==len(self.events):raise Interrupted(name)
    def reboot(self):
        self.boot_count+=1
        self.boot='boot-'+str(self.boot_count);self.acknowledged=None;self.crash_at=None
    def compare_peer(self,expected,replacement):
        if self.peer!=expected:raise Conflict('Concurrent peer change')
        self.peer=replacement

def validate(s,token):
    j=s.journal
    if not isinstance(j,dict) or set(j)!={'token','boot','original','candidate','authenticated'} or j['token']!=token or j['authenticated']is not True or j['candidate']!='temporary-loopback' or not j['original'] or j['original']==j['candidate']:
        raise Conflict('Missing/foreign/untrusted preimage')
    return j

def prepare(s,token):
    if s.journal is not None or not token or token in s.tokens or s.peer=='temporary-loopback':raise Conflict('Recover before preparing; fresh token required')
    # One atomic operation represents a fully durable, authenticated preimage.
    s.tokens.add(token)
    s.journal=dict(token=token,boot=s.boot,original=s.peer,candidate='temporary-loopback',authenticated=True)
    s.event('durable-preimage')
    s.acknowledged=(token,s.boot);s.event('watchdog-acknowledged')

def flip(s,token):
    j=validate(s,token)
    if s.acknowledged!=(token,s.boot) or j['boot']!=s.boot:raise Conflict('Fresh watchdog required')
    s.compare_peer(j['original'],j['candidate']);s.event('peer-flipped')

def recover(s,token):
    j=validate(s,token)
    if s.peer==j['candidate']:
        s.compare_peer(j['candidate'],j['original']);s.event('peer-restored')
    elif s.peer!=j['original']:
        raise Conflict('Independent choice preserved; preimage retained')
    # Must be atomic with checking the exact active token, like the peer CAS.
    if s.journal is not j:raise Conflict('Journal replaced')
    s.journal=None;s.acknowledged=None;s.event('journal-retired')
