"""Two native fresh pack scenes: commit versus skip, then another real purchase."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write

REQUIRED=tuple(mode+'.'+case for mode in ('select','skip') for case in
               ('initial','open','preview','close','lifecycle','followup','sealed'))


def ready(s,state):
    for k in ('frame','quiet_frames','observer_errors','dropped','pending_events','dollars','choices','stage','stop_use','play_count'):
        if type(s.get(k)) not in (int,float):raise ProtocolError('Missing pack observation '+k)
    for k in ('state_complete','locked','paused','pack_open'):
        if type(s.get(k)) is not bool:raise ProtocolError('Missing pack flag '+k)
    for k in ('locks','preview','owned','offers','packs','rows','events','objects','actions'):
        if not isinstance(s.get(k),list):raise ProtocolError('Missing pack collection '+k)
    if s['observer_errors'] or s['dropped']:raise ProtocolError('Pack observer error/overflow')
    return (s['state']==state and s['state_complete'] and not s['locked'] and not s['locks'] and not s['paused']
            and s['stop_use']==0 and s['play_count']==0 and s['pending_events']==0 and s['quiet_frames']>=8)


def evaluate(session,checks):
    root=session.runtime.directory;records=[];previous=None
    for mode in ('select','skip'):
        client=session.client if previous is None else session.restart()
        fresh=(previous is None or (previous.process.returncode==0 and previous.process.pid!=session.runtime.process.pid
               and previous.nonce!=session.runtime.nonce and previous.metadata['save_dir']!=session.runtime.metadata['save_dir']))
        states=[]
        def retain(item):records.append(dict(mode=mode,run_id=session.runtime.run_id,**item));write(root/'pack-probe.json',records)
        def action(method,args=None):
            response=client.action(method,args);retain({'action':method,'params':args,'response':response});return response
        def snap(label,state='SHOP'):
            s=client.wait(lambda v:ready(v,state),method='poc.pack.observe',timeout=25)
            states.append(s);retain({'label':label,'observation':s});return s
        client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'PACKPR1'})
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.pack.prepare',{'stage':'deck'})
        action('select');client.wait(lambda v:v['state']=='SELECTING_HAND');action('play',{'cards':[0,1,2,3,4]})
        client.wait(lambda v:v['state']=='ROUND_EVAL');action('cash_out');client.wait(lambda v:v['state']=='SHOP')
        action('poc.pack.prepare',{'stage':'shop'});before=snap('initial')
        check(checks,mode+'.initial',{'fresh':fresh,'owned':len(before['owned']),
              'packs':[(c['key'],c['cost']) for c in before['packs']],
              'offers':[(c['key'],c['cost']) for c in before['offers']]},
              {'fresh':True,'owned':0,'packs':[('p_buffoon_normal_1',4)],'offers':[('j_joker',2)]})
        response=action('buy',{'pack':0});opened=snap('open','SMODS_BOOSTER_OPENED')
        check(checks,mode+'.open',{'state':response.get('state'),'debit':before['dollars']-opened['dollars'],
              'pack_open':opened['pack_open'],'choices':opened['choices'],'owned':len(opened['owned'])},
              {'state':'SMODS_BOOSTER_OPENED','debit':4,'pack_open':True,'choices':1,'owned':0})
        preview=opened['preview'];ids=[c['id'] for c in preview]
        check(checks,mode+'.preview',{'count':len(ids),'unique':len(set(ids)),
              'types':[c['set'] for c in preview],'owned_flags':[c['added'] for c in preview],
              'early_adds':[r['id'] for r in opened['rows'] if r['kind']=='add_to_deck' and r['id'] in ids]},
              {'count':2,'unique':2,'types':['Joker','Joker'],'owned_flags':[False,False],'early_adds':[]})
        target=preview[1];selected=[target['id']] if mode=='select' else []
        response=action('pack',{'card':1} if mode=='select' else {'skip':True});closed=snap('close')
        objects={c['id']:c for c in closed['objects']}
        check(checks,mode+'.close',{'state':response.get('state'),'pack_open':closed['pack_open'],
              'owned':[c['id'] for c in closed['owned']],
              'removed':sorted(i for i in ids if objects[i]['removed']),
              'money':closed['dollars']},
              {'state':'SHOP','pack_open':False,'owned':selected,
               'removed':sorted(set(ids)-set(selected)),'money':opened['dollars']})
        check(checks,mode+'.lifecycle',{'pending':closed['pending_events'],
              'owned_adds':[r['id'] for r in closed['rows'] if r['kind']=='add_to_deck' and r['id'] in ids],
              'response_calls':[a['response_calls'] for a in closed['actions']],
              'events_observed':bool(closed['events'])},
              {'pending':0,'owned_adds':selected,'response_calls':[1,1],'events_observed':True})
        offer=before['offers'][0];response=action('buy',{'card':0});end=snap('followup')
        check(checks,mode+'.followup',{'state':response.get('state'),'debit':closed['dollars']-end['dollars'],
              'owned':[c['id'] for c in end['owned']],'offers':len(end['offers'])},
              {'state':'SHOP','debit':2,'owned':selected+[offer['id']],'offers':0})
        check(checks,mode+'.sealed',all(s['stage']==2 for s in states),True)
        previous=session.runtime
