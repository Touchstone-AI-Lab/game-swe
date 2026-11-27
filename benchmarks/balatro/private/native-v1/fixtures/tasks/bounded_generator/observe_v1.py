"""Readiness is independent of the business buffer value being graded."""
from poc.rpc import ProtocolError


def validate(s):
    for key in ('frame','count','capacity','buffer','stop_use','pending_events','observer_errors','dropped','quiet_frames','play_count','dollars'):
        if type(s.get(key)) not in (int,float):raise ProtocolError('Missing numeric lifecycle observation: '+key)
    for key in ('use_lock','locked','state_complete','paused'):
        if type(s.get(key)) is not bool:raise ProtocolError('Missing boolean lifecycle observation: '+key)
    for key in ('inventory','objects','actions','rows','events'):
        if not isinstance(s.get(key),list):raise ProtocolError('Missing lifecycle collection: '+key)
    if s['observer_errors'] or s['dropped']:raise ProtocolError('Observer error or telemetry overflow')
    return s


def ready(value):
    s=validate(value)
    return (s['state']=='SELECTING_HAND' and s['state_complete'] and not s['locked'] and not s['use_lock']
        and not s['paused'] and s['stop_use']==0 and s['play_count']==0 and s['pending_events']==0 and s['quiet_frames']>=8)


def settled(client):return validate(client.wait(ready,method='poc.bg.observe',timeout=20))


def index_of(snapshot,identity):
    found=[i for i,c in enumerate(snapshot['inventory']) if c['id']==identity]
    if len(found)!=1:raise ProtocolError('Required object identity unavailable for a real action')
    return found[0]
