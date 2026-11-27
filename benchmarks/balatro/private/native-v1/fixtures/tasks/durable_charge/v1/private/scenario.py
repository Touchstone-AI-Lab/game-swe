"""One candidate owns all four processes and all three native checkpoints."""
from __future__ import annotations
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import sha, write


def checkpoint_cases(name):
    return tuple(name+'.'+suffix for suffix in ('save','new_process','prep','load','native','identity','charge','hash'))


REQUIRED = ('initial','local.discard3','local.pair','local.high','cp2.discard1') + checkpoint_cases('cp2') + (
    'cp2.pair','cp2.next','cp4.discard1','cp4.discard2') + checkpoint_cases('cp4') + (
    'cp4.high',) + checkpoint_cases('cp0') + (
    'cp0.pair','cap.discard1','cap.discard2','cap.discard3','cap.discard4','cap.three','cap.next','configuration')


def stable(state):
    return {key: state[key] for key in ('state','seed','round','hand')}


def ready(snapshot):
    s=snapshot['state']
    return (s['state_name']=='BLIND_SELECT'
        and s['state_complete']=={'type':'boolean','value':True}
        and s['locked']=={'type':'boolean','value':False}
        and s['paused']=={'type':'boolean','value':False}
        and s['overlay']['type']=='nil' and s['screenwipe']['type']=='nil'
        and s['locks'].get('load',{}).get('value') is not True)


def score_delta(cards, bonus):
    # Independent ordinary poker arithmetic, never reads candidate code or label.
    chips, mult={1:(13,1),2:(26,2),3:(54,3)}[cards]
    return chips*(mult+bonus)


def validate_observation(value):
    for key in ('target_count','joker_count','load_count','add_count','fixture_calls','frame','chips',
                'dropped','suit_count','hand_limit','high_level','pair_level','three_level','blind_target'):
        if type(value.get(key)) not in (int,float): raise ProtocolError('Missing numeric observation: '+key)
    if value['target_count'] and type(value.get('charge')) not in (int,float):
        raise ProtocolError('Missing semantic charge')
    if not isinstance(value.get('events'),list): raise ProtocolError('Missing callback observations')
    return value


def evaluate(session, checks):
    client=session.client
    first_directory=session.runtime.directory
    checkpoints=[]
    observations=[]
    def state(name): return client.wait(lambda s:s['state']==name,timeout=35)
    def observe(live=True):
        value=validate_observation(client.call('poc.dc.observe'))
        if live: observations.append(value)
        return value
    def count(value,kind): return sum(e[kind] for e in value['events'])
    def discard(case,n,expected):
        before=client.call('gamestate'); b=observe()
        client.action('discard',{'cards':list(range(n))}); after=state('SELECTING_HAND'); a=observe()
        check(checks,case,{'charge':a['charge'], 'discard_delta':after['round']['discards_used']-before['round']['discards_used'],
                          'operation_callbacks':count(a,'pre_discard')-count(b,'pre_discard'),
                          'card_callbacks':count(a,'discard')-count(b,'discard')},
                         {'charge':expected,'discard_delta':1,'operation_callbacks':1,'card_callbacks':n})
    def play(case,n,bonus):
        before=client.call('gamestate'); b=observe()
        client.action('play',{'cards':list(range(n))}); after=state('SELECTING_HAND'); a=observe()
        check(checks,case,{'score_delta':a['chips']-b['chips'],'charge':a['charge'],
                          'hand_delta':after['round']['hands_played']-before['round']['hands_played'],
                          'main_callbacks':count(a,'joker_main')-count(b,'joker_main'),
                          'after_callbacks':count(a,'after')-count(b,'after')},
                         {'score_delta':score_delta(n,bonus),'charge':0,'hand_delta':1,'main_callbacks':1,'after_callbacks':1})
    def checkpoint(name,expected):
        nonlocal client
        saved=state('SELECTING_HAND'); saved_obs=observe()
        source=session.runtime; file=source.directory/(name+'.jkr')
        response=client.action('save',{'path':str(file)})
        if response.get('success') is not True or response.get('path')!=str(file):
            raise ProtocolError('Save response does not match checkpoint')
        digest=sha(file)
        check(checks,name+'.save',{'success':True,'nonempty':file.stat().st_size>0},{'success':True,'nonempty':True})
        evidence={'name':name,'path':str(file),'source_run':source.run_id,'sha256_before':digest,
                  'bytes':file.stat().st_size,'save_response':response,'saved_native':stable(saved),
                  'saved_semantics':saved_obs,'candidate':source.metadata['fingerprints']['candidate']}
        checkpoints.append(evidence)
        write(first_directory/'durable-checkpoints.json',checkpoints)
        client=session.restart()
        destination=session.runtime
        check(checks,name+'.new_process',{
            'different_pid':source.process.pid!=destination.process.pid,
            'different_nonce':source.nonce!=destination.nonce,'first_exited':source.process.returncode==0,
            'different_save_dir':source.metadata['observed_runtime']['save_dir']!=destination.metadata['observed_runtime']['save_dir'],
            'candidate_same':source.metadata['fingerprints']['candidate']==destination.metadata['fingerprints']['candidate']},
            {'different_pid':True,'different_nonce':True,'first_exited':True,'different_save_dir':True,'candidate_same':True})
        state('MENU'); initial=observe(False)
        client.action('start',{'deck':'BLUE','stake':'WHITE','seed':'LOADPREP'})
        primed=state('BLIND_SELECT')
        readiness=client.wait(ready,method='poc.load_diagnostic',timeout=30)
        pre=observe(False)
        prep_keys=('target_count','joker_count','fixture_calls','add_count','load_count')
        check(checks,name+'.prep',{'menu_target_count':initial['target_count'],'seed':primed['seed'],
                                  **{k:pre[k] for k in prep_keys}},
                                 {'menu_target_count':0,'seed':'LOADPREP',**{k:0 for k in prep_keys}})
        response=client.action('load',{'path':str(file)})
        if response.get('success') is not True or response.get('path')!=str(file):
            raise ProtocolError('Load response does not match checkpoint')
        check(checks,name+'.load',{'success':True,'path_matches':True},{'success':True,'path_matches':True})
        restored=state('SELECTING_HAND'); after=observe()
        check(checks,name+'.native',stable(restored),stable(saved))
        check(checks,name+'.identity',{
            'sort_id':after['sort_id'],'target_key':after['target_key'],'target_count':after['target_count'],
            'joker_count':after['joker_count'],'target_loaded':after['target_loaded'],'load_count':after['load_count'],
            'fixture_calls':after['fixture_calls'],'add_count':after['add_count']},
            {'sort_id':saved_obs['sort_id'],'target_key':'j_dur_charge','target_count':1,'joker_count':1,
             'target_loaded':True,'load_count':1,'fixture_calls':0,'add_count':0})
        check(checks,name+'.charge',after['charge'],expected)
        evidence.update(destination_run=destination.run_id,load_response=response,readiness=readiness,
                        loadprep_observation=pre,restored_native=stable(restored),restored_semantics=after,
                        load_diagnostic=client.call('poc.load_diagnostic'))
        write(first_directory/'durable-checkpoints.json',checkpoints)

    state('MENU')
    client.action('start',{'deck':'RED','stake':'WHITE','seed':'DURABLE1'})
    state('BLIND_SELECT'); client.action('poc.dc.prepare')
    a=observe()
    check(checks,'initial',{'charge':a['charge'],'target_count':a['target_count'],'fixture_calls':a['fixture_calls']},
                           {'charge':0,'target_count':1,'fixture_calls':1})
    client.action('select');state('SELECTING_HAND')
    discard('local.discard3',3,2)
    play('local.pair',2,2);play('local.high',1,0)
    discard('cp2.discard1',1,2);checkpoint('cp2',2)
    play('cp2.pair',2,2);play('cp2.next',1,0)
    discard('cp4.discard1',1,2);discard('cp4.discard2',2,4);checkpoint('cp4',4)
    play('cp4.high',1,4);checkpoint('cp0',0)
    play('cp0.pair',2,0)
    for i,n in enumerate((1,2,3,1),1): discard('cap.discard'+str(i),n,min(6,2*i))
    play('cap.three',3,6);play('cap.next',2,0)
    for evidence in checkpoints:
        from pathlib import Path
        actual=sha(Path(evidence['path']))
        check(checks,evidence['name']+'.hash',actual,evidence['sha256_before'])
        evidence['sha256_after']=actual
    write(first_directory/'durable-checkpoints.json',checkpoints)
    expected={'target_count':1,'joker_count':1,'target_key':'j_dur_charge','target_debuff':False,
              'target_edition':False,'plain':True,'suit_count':4,'hand_limit':8,
              'high_level':1,'pair_level':1,'three_level':1,'dropped':0}
    invalid=[{k:s.get(k) for k in expected} for s in observations if any(s.get(k)!=v for k,v in expected.items())]
    check(checks,'configuration',invalid,[])
