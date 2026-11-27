"""Named stream versus actual native Lucky interference in fresh seeded games."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write

SCENES=(('clean1','STREAM01',False),('clean2','STREAM01',False),
        ('noise','STREAM01',True),('other','STREAM02',False))
REQUIRED=tuple(name+'.'+case for name,_,_ in SCENES for case in ('initial','actions','samples','native_noise','sealed'))+(
    'reproduce','isolated','different_seed')


def ready(s):
    for key in ('frame','stop_use','play_count','stage','dropped','hands','discards','chips'):
        if type(s.get(key)) not in (int,float):raise ProtocolError('Missing stream observation '+key)
    if s['dropped']:raise ProtocolError('Stream observation overflow')
    return (s['state']=='SELECTING_HAND' and s['state_complete'] and not s['locked'] and not s['locks']
            and not s['paused'] and s['stop_use']==0 and s['play_count']==0)


def evaluate(session,checks):
    root=session.runtime.directory;trace=[];previous=None;ends={}
    for name,seed,noise in SCENES:
        client=session.client if previous is None else session.restart()
        fresh=previous is None or (previous.process.returncode==0 and previous.process.pid!=session.runtime.process.pid
            and previous.nonce!=session.runtime.nonce and previous.metadata['save_dir']!=session.runtime.metadata['save_dir'])
        states=[]
        def retain(row):trace.append(dict(scene=name,run_id=session.runtime.run_id,**row));write(root/'stream-probe.json',trace)
        def action(method,args=None):
            r=client.action(method,args);retain({'action':method,'params':args,'response':r});return r
        def snap(label):
            s=client.wait(ready,method='poc.stream.observe',timeout=25);states.append(s)
            retain({'label':label,'observation':s});return s
        client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':seed})
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.stream.prepare',{'stage':'deck'})
        action('select');snap('dealt');action('poc.stream.prepare',{'stage':'lucky'});s=snap('initial');states=[]
        check(checks,name+'.initial',{'fresh':fresh,'samples':s['samples'],'lucky':sum(c['key']=='m_lucky' for c in s['hand'])},
              {'fresh':True,'samples':[],'lucky':1})
        actions=[]
        for index in range(4):
            if noise and index==1:
                position=next(i for i,c in enumerate(s['hand']) if c['id']==s['lucky_id'])
                action('play',{'cards':[position]});s=snap('native_noise')
            position=next(i for i,c in enumerate(s['hand']) if c['id']!=s['lucky_id'])
            before=s;response=action('discard',{'cards':[position]});s=snap('discard'+str(index+1))
            actions.append({'state':response.get('state'),'delta':s['discards']-before['discards']})
        check(checks,name+'.actions',actions,[{'state':'SELECTING_HAND','delta':1}]*4)
        check(checks,name+'.samples',{'count':len(s['samples']),'range':all(type(v['named']) in (int,float) and 0<=v['named']<1 for v in s['samples']),
              'selected':[v['selected'] for v in s['samples']]}, {'count':4,'range':True,'selected':[1]*4})
        native=[v for v in s['draws'] if not v['diagnostic'] and v['key'] in ('lucky_mult','lucky_money')]
        check(checks,name+'.native_noise',{'hands':s['hands'],'noise_seen':bool(native),'positive_score':s['chips']>0},
              {'hands':1 if noise else 0,'noise_seen':noise,'positive_score':noise})
        check(checks,name+'.sealed',all(v['stage']==2 and not v['dropped'] for v in states),True)
        ends[name]=s;previous=session.runtime
    named=lambda name:[s['named'] for s in ends[name]['samples']]
    shared=lambda name:[s['shared'] for s in ends[name]['samples']]
    check(checks,'reproduce',{'named':named('clean2'),'shared':shared('clean2')},
          {'named':named('clean1'),'shared':shared('clean1')})
    check(checks,'isolated',{'named_equal':named('noise')==named('clean1'),
          'shared_changed':shared('noise')!=shared('clean1')},{'named_equal':True,'shared_changed':True})
    check(checks,'different_seed',named('other')!=named('clean1'),True)
