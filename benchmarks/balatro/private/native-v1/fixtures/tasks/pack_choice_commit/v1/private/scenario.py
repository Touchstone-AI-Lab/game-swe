"""Same real pack/score/sale behavior across independently submitted candidates."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.pack_choice_commit.probe_v1.probe import ready

SCENES=(('three','j_pcc_sign_three',3),('five','j_pcc_sign_five',5),('skip',None,0))
REQUIRED=tuple(mode+'.'+case for mode,_,_ in SCENES for case in
    ('initial','open','preview','commit','cleanup','stable','followup','play','sale','sealed'))

def unique_position(cards,key=None,identity=None):
    matches=[i for i,c in enumerate(cards) if (key is not None and c['key']==key) or
             (identity is not None and c['id']==identity)]
    if len(matches)!=1:raise ProtocolError('Required real action object missing or ambiguous')
    return matches[0]

def evaluate(session,checks):
    root=session.runtime.directory;records=[];previous=None
    for mode,target_key,bonus in SCENES:
        client=session.client if previous is None else session.restart()
        fresh=previous is None or (previous.process.returncode==0 and previous.process.pid!=session.runtime.process.pid
            and previous.nonce!=session.runtime.nonce and previous.metadata['save_dir']!=session.runtime.metadata['save_dir'])
        snapshots=[]
        def retain(item):
            records.append(dict(mode=mode,run_id=session.runtime.run_id,**item));write(root/'pack-scenario.json',records)
        def action(method,args=None):
            response=client.action(method,args);retain({'action':method,'params':args,'response':response});return response
        def snap(label,state='SHOP',after_frame=None):
            s=client.wait(lambda v:ready(v,state) and (after_frame is None or v['frame']>=after_frame),
                method='poc.pack.observe',timeout=25)
            for key in ('chips','hands','round'):
                if type(s.get(key)) not in (int,float):raise ProtocolError('Missing native play observation '+key)
            snapshots.append(s);retain({'label':label,'observation':s});return s
        client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'SIGNPACK'})
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.pack.prepare',{'stage':'deck'})
        action('select');client.wait(lambda v:v['state']=='SELECTING_HAND');action('play',{'cards':[0,1,2,3,4]})
        client.wait(lambda v:v['state']=='ROUND_EVAL');action('cash_out');client.wait(lambda v:v['state']=='SHOP')
        action('poc.pack.prepare',{'stage':'shop'});before=snap('initial')
        check(checks,mode+'.initial',{'fresh':fresh,'owned':before['owned'],
            'packs':[(c['key'],c['cost']) for c in before['packs']],
            'offers':[(c['key'],c['cost'],c['edition']) for c in before['offers']]},
            {'fresh':True,'owned':[],'packs':[('p_pcc_signing',4)],'offers':[('j_joker',2,False)]})
        response=action('buy',{'pack':0});opened=snap('open','SMODS_BOOSTER_OPENED')
        check(checks,mode+'.open',{'state':response.get('state'),'debit':before['dollars']-opened['dollars'],
            'pack_open':opened['pack_open'],'choices':opened['choices'],'owned':opened['owned']},
            {'state':'SMODS_BOOSTER_OPENED','debit':4,'pack_open':True,'choices':1,'owned':[]})
        previews=opened['preview'];ids=[c['id'] for c in previews]
        check(checks,mode+'.preview',{'unique':len(set(ids)),'options':sorted((c['key'],c['set'],c['cost'],
            c['sell_cost'],c['edition'],c['added']) for c in previews)},
            {'unique':2,'options':[('j_pcc_sign_five','Joker',4,2,False,False),('j_pcc_sign_three','Joker',4,2,False,False)]})
        index=unique_position(previews,key=target_key) if target_key else None
        selected=[previews[index]['id']] if index is not None else []
        response=action('pack',{'card':index} if index is not None else {'skip':True});closed=snap('commit')
        objects={c['id']:c for c in closed['objects']}
        check(checks,mode+'.commit',{'state':response.get('state'),'pack_open':closed['pack_open'],
            'owned':[c['id'] for c in closed['owned']],'removed':sorted(i for i in ids if objects[i]['removed']),
            'grant':closed['dollars']-opened['dollars']},
            {'state':'SHOP','pack_open':False,'owned':selected,'removed':sorted(set(ids)-set(selected)),'grant':bonus})
        check(checks,mode+'.cleanup',{'pending':closed['pending_events'],
            'adds':[r['id'] for r in closed['rows'] if r['kind']=='add_to_deck' and r['id'] in ids],
            'pack_responses':[(a['method'],a['response_calls']) for a in closed['actions'] if a['method'] in ('buy','pack')],
            'events_observed':bool(closed['events'])},
            {'pending':0,'adds':selected,'pack_responses':[('buy',1),('pack',1)],'events_observed':True})
        stable=snap('stable',after_frame=closed['frame']+12)
        check(checks,mode+'.stable',{'money':stable['dollars'],'owned':stable['owned'],'preview':stable['preview'],
            'pending':stable['pending_events']},
            {'money':closed['dollars'],'owned':closed['owned'],'preview':[],'pending':0})
        offer=before['offers'][0];response=action('buy',{'card':0});bought=snap('followup')
        check(checks,mode+'.followup',{'state':response.get('state'),'debit':stable['dollars']-bought['dollars'],
            'owned':[c['id'] for c in bought['owned']],'offers':bought['offers']},
            {'state':'SHOP','debit':2,'owned':selected+[offer['id']],'offers':[]})
        action('next_round');client.wait(lambda v:v['state']=='BLIND_SELECT');action('select')
        dealt=snap('dealt','SELECTING_HAND');response=action('play',{'cards':[0]});played=snap('played','SELECTING_HAND')
        check(checks,mode+'.play',{'state':response.get('state'),'round':played['round'],'chips':played['chips']-dealt['chips'],
            'hands':played['hands']-dealt['hands'],'income':played['dollars']-dealt['dollars'],'owned':played['owned']},
            {'state':'SELECTING_HAND','round':2,'chips':35,'hands':1,'income':0,'owned':bought['owned']})
        sell_id=selected[0] if selected else offer['id'];quote=2 if selected else 1
        response=action('sell',{'joker':unique_position(played['owned'],identity=sell_id)});sold=snap('sold','SELECTING_HAND')
        obj={c['id']:c for c in sold['objects']}
        check(checks,mode+'.sale',{'state':response.get('state'),'income':sold['dollars']-played['dollars'],
            'owned':[c['id'] for c in sold['owned']],'removed':obj[sell_id]['removed'],'pending':sold['pending_events']},
            {'state':'SELECTING_HAND','income':quote,'owned':[offer['id']] if selected else [],'removed':True,'pending':0})
        check(checks,mode+'.sealed',all(s['stage']==2 and not s['observer_errors'] and not s['dropped']
            and all(a['response_calls']==1 for a in s['actions']) for s in snapshots),True)
        previous=session.runtime
