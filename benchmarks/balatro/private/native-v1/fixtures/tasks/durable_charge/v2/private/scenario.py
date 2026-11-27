"""Candidate-owned native trajectories and separate isolated public-core tests."""
from pathlib import Path
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import sha,write
from tasks.bounded_generator.observe_v1 import settled
from tasks.durable_charge.v1.private.scenario import ready,stable,score_delta
from .oracle import expected

CP=('save','new_process','prep','load','native','identity','charge','hash')
NATIVE=('initial','discard.a','recruit.b','reorder','discard.both','pair.consume','postload.discard',
        'sell.restored','recruit.c','postload.score','cap.1','cap.2','cap.3','cap.4','cap.score','cap.next','configuration')
REQUIRED=tuple('core.'+k for k in expected())+tuple('restored.'+k for k in NATIVE)+tuple(
    'restored.'+name+'.'+k for name in ('unequal1','unequal2','zero') for k in CP)+tuple(
    'local.'+k for k in NATIVE)+('trajectory.equivalent',)


def evaluate(session,checks):
    session.client.wait(lambda s:s['state']=='MENU')
    results=session.client.call('poc.dc2.core')
    for name,value in expected().items():check(checks,'core.'+name,results.get(name),value)
    trajectories={}
    for mode in ('restored','local'):
        if mode=='local':session.restart()
        client=session.client;root=session.runtime.directory;trace=[];snapshots=[];checkpoints=[];roles={};trajectory=[]
        def retain(row):trace.append(row);write(root/'multi-charge-task-v2.json',trace)
        def record(name,actual,wanted):check(checks,mode+'.'+name,actual,wanted)
        def observe(live=True):
            value=client.call('poc.dc2.observe')
            if not isinstance(value.get('targets'),list) or value.get('dropped')!=0:raise ProtocolError('Incomplete charge observation')
            if live:snapshots.append(value)
            retain(dict(observation=value));return value
        def balances(value):return {str(c['id']):c['charge'] for c in value['targets']}
        def note(label,s,score=None):
            trajectory.append(dict(label=label,balances={roles[c['id']]:c['charge'] for c in s['targets']},
                order=[roles[c['id']] for c in s['targets']],score=score))
        def discard(label,n,wanted):
            before=client.call('gamestate');client.action('discard',{'cards':list(range(n))});settled(client)
            after=client.call('gamestate');s=observe()
            record(label,dict(charge=balances(s),discards=after['round']['discards_used']-before['round']['discards_used']),
                dict(charge=wanted,discards=1));note(label,s);return s
        def recruit(label,wanted,role):
            before=observe();life=settled(client);source=life['inventory'][0];old_ids={c['id'] for c in before['targets']}
            reply=client.action('use',{'consumable':0});after_life=settled(client);after=observe()
            fresh=[c['id'] for c in after['targets'] if c['id'] not in old_ids]
            if len(fresh)!=1:raise ProtocolError('Fresh target identity unavailable for membership actions')
            new=fresh[0];roles[new]=role;wanted=dict(wanted,**{str(new):0})
            record(label,dict(state=reply['state'],charge=balances(after),new_loaded=next(c['loaded'] for c in after['targets'] if c['id']==new),
                inventory=after_life['inventory'],source_removed=[c['removed'] for c in after_life['objects'] if c['id']==source['id']],pending=after_life['pending_events']),
                dict(state='SELECTING_HAND',charge=wanted,new_loaded=False,inventory=life['inventory'][1:],source_removed=[True],pending=0))
            note(label,after);return new,after
        def play(label,n,bonus,wanted):
            before=client.call('gamestate');s=observe();client.action('play',{'cards':list(range(n))});settled(client)
            after=client.call('gamestate');t=observe();delta=t['chips']-s['chips']
            record(label,dict(chips=delta,hands=after['round']['hands_played']-before['round']['hands_played'],charge=balances(t)),
                dict(chips=score_delta(n,bonus),hands=1,charge=wanted));note(label,t,delta)
        def checkpoint(name,wanted):
            nonlocal client
            if mode=='local':return
            settled(client);saved=client.call('gamestate');saved_obs=observe();source=session.runtime
            path=source.directory/(name+'.jkr');response=client.action('save',{'path':str(path)})
            if response.get('success') is not True or response.get('path')!=str(path):raise ProtocolError('Mismatched save completion')
            digest=sha(path);record(name+'.save',dict(nonempty=path.stat().st_size>0,success=response['success']),dict(nonempty=True,success=True))
            evidence=dict(name=name,path=str(path),source_run=source.run_id,before_sha256=digest,bytes=path.stat().st_size,
                save_response=response,saved_native=stable(saved),saved_semantics=saved_obs,candidate=source.metadata['fingerprints']['candidate'])
            checkpoints.append(evidence);write(root/'multi-charge-checkpoints-v2.json',checkpoints)
            client=session.restart();destination=session.runtime
            record(name+'.new_process',dict(pid=source.process.pid!=destination.process.pid,nonce=source.nonce!=destination.nonce,
                save_dir=source.metadata['save_dir']!=destination.metadata['save_dir'],normal=source.process.returncode==0,
                fingerprints=source.metadata['fingerprints']==destination.metadata['fingerprints']),
                dict(pid=True,nonce=True,save_dir=True,normal=True,fingerprints=True))
            client.wait(lambda s:s['state']=='MENU');menu=observe(False)
            client.action('start',{'deck':'BLUE','stake':'WHITE','seed':'LOADPREP'});primed=client.wait(lambda s:s['state']=='BLIND_SELECT')
            readiness=client.wait(ready,method='poc.load_diagnostic',timeout=30);prep=observe(False)
            record(name+'.prep',dict(menu=menu['targets'],targets=prep['targets'],fixture=prep['fixture_calls'],add=prep['add_count'],load=prep['load_count'],seed=primed['seed']),
                dict(menu=[],targets=[],fixture=0,add=0,load=0,seed='LOADPREP'))
            response=client.action('load',{'path':str(path)})
            if response.get('success') is not True or response.get('path')!=str(path):raise ProtocolError('Mismatched load completion')
            record(name+'.load',dict(success=True,path_matches=True),dict(success=True,path_matches=True))
            settled(client);restored=client.call('gamestate');after=observe();record(name+'.native',stable(restored),stable(saved))
            record(name+'.identity',dict(ids=[c['id'] for c in after['targets']],loaded=[c['loaded'] for c in after['targets']],
                inventory=after['inventory'],fixture=after['fixture_calls'],adds=after['add_count'],loads=after['load_count']),
                dict(ids=[c['id'] for c in saved_obs['targets']],loaded=[True]*len(saved_obs['targets']),
                inventory=saved_obs['inventory'],fixture=0,adds=0,loads=len(saved_obs['targets'])))
            record(name+'.charge',balances(after),wanted)
            evidence.update(destination_run=destination.run_id,readiness=readiness,load_response=response,restored_native=stable(restored),restored_semantics=after)
            write(root/'multi-charge-checkpoints-v2.json',checkpoints)
        client.wait(lambda s:s['state']=='MENU');client.action('start',{'deck':'RED','stake':'WHITE','seed':'DURABLE2'})
        client.wait(lambda s:s['state']=='BLIND_SELECT');client.action('poc.dc2.prepare');s=observe()
        if len(s['targets'])!=1:raise ProtocolError('Initial target missing')
        a=s['targets'][0]['id'];roles[a]='a'
        record('initial',dict(charge=balances(s),inventory=[c['key'] for c in s['inventory']],fixture=s['fixture_calls']),
            dict(charge={str(a):0},inventory=['c_dc2_recruit']*2,fixture=1));note('initial',s)
        client.action('select');settled(client);discard('discard.a',3,{str(a):2});b,s=recruit('recruit.b',{str(a):2},'b')
        checkpoint('unequal1',{str(a):2,str(b):0})
        client.action('rearrange',{'jokers':[1,0]});s=observe()
        record('reorder',dict(order=[c['id'] for c in s['targets']],charge=balances(s)),dict(order=[b,a],charge={str(a):2,str(b):0}));note('reorder',s)
        discard('discard.both',1,{str(a):4,str(b):2});checkpoint('unequal2',{str(a):4,str(b):2})
        play('pair.consume',2,6,{str(a):0,str(b):0});checkpoint('zero',{str(a):0,str(b):0})
        s=discard('postload.discard',1,{str(a):2,str(b):2});index=[c['id'] for c in s['targets']].index(a)
        client.action('sell',{'joker':index});settled(client);s=observe()
        record('sell.restored',dict(charge=balances(s),removed=[c['removed'] for c in s['objects'] if c['id']==a]),dict(charge={str(b):2},removed=[True]));note('sell.restored',s)
        c,s=recruit('recruit.c',{str(b):2},'c');play('postload.score',1,2,{str(b):0,str(c):0})
        for i in range(1,5):discard('cap.'+str(i),1,{str(b):min(6,2*i),str(c):min(6,2*i)})
        play('cap.score',3,12,{str(b):0,str(c):0});play('cap.next',1,0,{str(b):0,str(c):0})
        for evidence in checkpoints:
            digest=sha(Path(evidence['path']));record(evidence['name']+'.hash',digest,evidence['before_sha256']);evidence['after_sha256']=digest
        write(root/'multi-charge-checkpoints-v2.json',checkpoints)
        record('configuration',all(v['capacity']==5 and v['joker_count']==len(v['targets']) and not v['dropped']
            and all(t['key']=='j_dc2_charge' and not t['edition'] and not t['debuff'] for t in v['targets']) for v in snapshots),True)
        trajectories[mode]=trajectory;write(root/'normalized-trajectory-v2.json',trajectory)
    check(checks,'trajectory.equivalent',trajectories['restored'],trajectories['local'])
