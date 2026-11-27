"""Actual cash, operation cardinality and native RNG isolation; no candidate introspection."""
import json
from pathlib import Path
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.seeded_effect_stream.probe_v1.probe import ready

SCENES=(('clean1','STREAM01',False),('clean2','STREAM01',False),
        ('noise','STREAM01',True),('other','STREAM02',False))
CARDINALITIES=(1,2,3,1)
REQUIRED=tuple(n+'.'+c for n,_,_ in SCENES for c in ('initial','actions','payouts','native_noise','stable','sealed'))+(
    'reproduce','isolated','different_seed')
ORACLE=json.loads((Path(__file__).parent/'native-oracle.json').read_text(encoding='utf-8'))


def ordinary_positions(state,count):
    choices=[i for i,c in enumerate(state['hand']) if c['id']!=state['lucky_id']]
    if len(choices)<count:raise ProtocolError('Insufficient ordinary discard targets')
    return choices[:count]


def native_money(draws):
    values=[d['value'] for d in draws if d['key']=='lucky_money']
    # This diagnostic interpretation never samples the RNG or changes money.
    # The sole ordinary native Lucky Card has the fixed 1/15, $20 effect.
    return sum(20 if value<1/15 else 0 for value in values)


def evaluate(session,checks):
    root=session.runtime.directory;trace=[];previous=None;rewards={}
    for name,seed,noise in SCENES:
        client=session.client if previous is None else session.restart()
        fresh=previous is None or (previous.process.returncode==0 and previous.process.pid!=session.runtime.process.pid
            and previous.nonce!=session.runtime.nonce and previous.metadata['save_dir']!=session.runtime.metadata['save_dir'])
        states=[]
        def retain(row):trace.append(dict(scene=name,run_id=session.runtime.run_id,**row));write(root/'stream-scenario.json',trace)
        def action(method,args=None):
            response=client.action(method,args);retain({'action':method,'params':args,'response':response});return response
        def snap(label):
            state=client.wait(ready,method='poc.stream.observe',timeout=25);states.append(state)
            retain({'label':label,'observation':state});return state
        client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':seed})
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.stream.prepare',{'stage':'deck'})
        action('select');snap('dealt');action('poc.stream.prepare',{'stage':'lucky'});s=snap('initial');states=[]
        initial_jokers=s['jokers']
        check(checks,name+'.initial',{'fresh':fresh,'money':s['dollars'],'hands':s['hands'],'discards':s['discards'],
            'lucky':sum(c['key']=='m_lucky' for c in s['hand']),
            'jokers':[{k:c[k] for k in ('key','edition','added')} for c in initial_jokers]},
            {'fresh':True,'money':4,'hands':0,'discards':0,'lucky':1,
             'jokers':[{'key':'j_ses_private_stream','edition':False,'added':True}]})
        operations=[];payouts=[];stable=[];noise_draws=[];noise_income=0
        for index,count in enumerate(CARDINALITIES):
            before=s
            observed=client.wait(lambda v:ready(v) and v['frame']>=before['frame']+8,method='poc.stream.observe',timeout=10)
            states.append(observed);retain({'label':'stable'+str(index),'observation':observed})
            stable.append(observed['dollars']-before['dollars']);s=observed
            if noise and index==1:
                positions=[i for i,c in enumerate(s['hand']) if c['id']==s['lucky_id']]
                if len(positions)!=1:raise ProtocolError('Initial Lucky target unavailable')
                before=s;action('play',{'cards':positions});s=snap('native_noise')
                noise_draws=s['draws'][len(before['draws']):];noise_income=s['dollars']-before['dollars']
            positions=ordinary_positions(s,count);selected=[s['hand'][i]['id'] for i in positions]
            before=s;response=action('discard',{'cards':positions});s=snap('discard'+str(index+1))
            discard_ids={c['id'] for c in s['discard']}
            operations.append({'state':response.get('state'),'delta':s['discards']-before['discards'],
                               'targets_discarded':all(i in discard_ids for i in selected),'selected':len(selected)})
            payouts.append(s['dollars']-before['dollars'])
        check(checks,name+'.actions',operations,[{'state':'SELECTING_HAND','delta':1,'targets_discarded':True,'selected':n} for n in CARDINALITIES])
        check(checks,name+'.payouts',payouts,ORACLE['rewards'][seed])
        native=[d for d in noise_draws if d['key'] in ('lucky_mult','lucky_money')]
        check(checks,name+'.native_noise',{'hands':s['hands'],'chips':s['chips'],
              'keys':sorted(d['key'] for d in native),'income':noise_income},
              {'hands':1 if noise else 0,'chips':ORACLE['native_noise_chips'] if noise else 0,
               'keys':['lucky_money','lucky_mult'] if noise else [],'income':native_money(native)})
        before=s;s=client.wait(lambda v:ready(v) and v['frame']>=before['frame']+8,method='poc.stream.observe',timeout=10)
        states.append(s);retain({'label':'final_stable','observation':s});stable.append(s['dollars']-before['dollars'])
        check(checks,name+'.stable',stable,[0]*5)
        check(checks,name+'.sealed',all(v['stage']==2 and not v['dropped'] and v['playing_count']==52
              and v['jokers']==initial_jokers for v in states),True)
        rewards[name]=payouts;previous=session.runtime
    check(checks,'reproduce',rewards['clean2'],rewards['clean1'])
    check(checks,'isolated',rewards['noise'],rewards['clean1'])
    check(checks,'different_seed',rewards['other']!=rewards['clean1'],True)
