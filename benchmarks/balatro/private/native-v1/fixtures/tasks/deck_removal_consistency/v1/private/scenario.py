"""Complete identity-based removal suites, each in its own fresh native process."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.bounded_generator.observe_v1 import settled

SCENES=(('single',[4]),('double',[2,6]))
REQUIRED=tuple(scene+'.'+case for scene,_ in SCENES for case in (
    'initial','response','consumption','targets','registered','areas','unchanged','lifecycle',
    'stable','next_deal','full_pool','followup','sealed'))


def ids(cards):return sorted(c['id'] for c in cards)


def mapping(cards):
    value={c['id']:c for c in cards}
    if len(value)!=len(cards):raise ProtocolError('Duplicate physical identity in deck observation')
    return value


def ready(s):
    for key in ('frame','quiet_frames','observer_errors','dropped','deck_limit'):
        if type(s.get(key)) not in (int,float):raise ProtocolError('Missing deck observation '+key)
    for key in ('registered','hand','deck','discard','play','objects','rows'):
        if not isinstance(s.get(key),list):raise ProtocolError('Missing deck collection '+key)
    if s['observer_errors'] or s['dropped']:raise ProtocolError('Deck observation error/overflow')
    return s['quiet_frames']>=8


def semantic(s):
    return {k:s[k] for k in ('registered','hand','deck','discard','play','deck_limit','prepared')}


def evaluate(session,checks):
    root=session.runtime.directory;trace=[];previous=None
    for scene,positions in SCENES:
        client=session.client if previous is None else session.restart()
        fresh=previous is None or (previous.process.returncode==0 and previous.process.pid!=session.runtime.process.pid
            and previous.nonce!=session.runtime.nonce and previous.metadata['save_dir']!=session.runtime.metadata['save_dir'])
        snapshots=[]
        def retain(row):
            trace.append(dict(scene=scene,run_id=session.runtime.run_id,**row));write(root/'deck-removal-scenario.json',trace)
        def action(method,params=None):
            r=client.action(method,params);retain({'action':method,'params':params,'response':r});return r
        def snap(label):
            s=client.wait(ready,method='poc.decktask.observe',timeout=10);snapshots.append(s)
            retain({'label':label,'observation':s});return s
        client.wait(lambda s:s['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'CUTSNG1' if scene=='single' else 'CUTDBL1'})
        client.wait(lambda s:s['state']=='BLIND_SELECT');prep=action('poc.decktask.prepare')
        action('select');initial_life=settled(client);before=snap('initial');original=mapping(before['registered'])
        targets=[before['hand'][i]['id'] for i in positions];survivors=sorted(set(original)-set(targets))
        check(checks,scene+'.initial',{'fresh':fresh,'count':len(original),'limit':before['deck_limit'],'hand':len(before['hand']),
            'ordinary':all(c['rank']==2 and c['suit']=='Hearts' and c['center']=='c_base' for c in original.values()),
            'inventory':[c['key'] for c in initial_life['inventory']],'capacity':initial_life['capacity'],
            'prepared':prep.get('prepared')},
            {'fresh':True,'count':12,'limit':12,'hand':8,'ordinary':True,
             'inventory':['c_drc_clean_cut','c_pluto'],'capacity':2,'prepared':True})
        source,unrelated=initial_life['inventory']
        response=action('use',{'consumable':0,'cards':positions});life=settled(client);after=snap('removed')
        retain({'lifecycle':life})
        check(checks,scene+'.response',response.get('state'),'SELECTING_HAND')
        source_record=next((c for c in life['objects'] if c['id']==source['id']),None)
        if source_record is None:raise ProtocolError('Missing consumed object observation')
        check(checks,scene+'.consumption',{'inventory':life['inventory'],'source_removed':source_record['removed'],
            'money':life['dollars'],'levels':life['hand_levels']},
            {'inventory':[unrelated],'source_removed':True,'money':initial_life['dollars'],'levels':initial_life['hand_levels']})
        objects=mapping(after['objects']);actual=mapping(after['registered'])
        check(checks,scene+'.targets',{i:objects[i]['removed'] for i in targets},{i:True for i in targets})
        check(checks,scene+'.registered',{'ids':ids(after['registered']),'limit':after['deck_limit']},
              {'ids':survivors,'limit':len(survivors)})
        check(checks,scene+'.areas',ids(sum((after[k] for k in ('hand','deck','discard','play')),[])),survivors)
        check(checks,scene+'.unchanged',{i:actual.get(i) for i in survivors},{i:original[i] for i in survivors})
        calls=life['actions'][len(initial_life['actions']):]
        check(checks,scene+'.lifecycle',{'action_count':len(calls),'target_ids':[a['target'] for a in calls],
            'events_observed':bool(life['events']),'pending':life['pending_events'],
            'observer_errors':life['observer_errors'],'dropped':life['dropped'],'buffer':life['buffer']},
            {'action_count':1,'target_ids':[source['id']],'events_observed':True,'pending':0,'observer_errors':0,'dropped':0,'buffer':0})
        stable=client.wait(lambda s:ready(s) and s['frame']>=after['frame']+12,method='poc.decktask.observe',timeout=5)
        snapshots.append(stable);retain({'label':'stable','observation':stable})
        check(checks,scene+'.stable',semantic(stable),semantic(after))
        action('play',{'cards':[0,1,2,3,4]});client.wait(lambda s:s['state']=='ROUND_EVAL')
        action('cash_out');client.wait(lambda s:s['state']=='SHOP');action('next_round')
        client.wait(lambda s:s['state']=='BLIND_SELECT');action('select');settled(client);deal=snap('next_blind')
        check(checks,scene+'.next_deal',{'hand':len(deal['hand']),'no_targets':not set(targets)&set(ids(deal['hand'])),
            'registered':ids(deal['registered']),'limit':deal['deck_limit']},
            {'hand':8,'no_targets':True,'registered':survivors,'limit':len(survivors)})
        action('discard',{'cards':list(range(4-len(targets)))});settled(client);last=snap('pool_exhausted')
        check(checks,scene+'.full_pool',{'reachable':sorted(set(ids(deal['hand']))|set(ids(last['hand']))),
            'draw_pile':len(last['deck']),'registered':ids(last['registered'])},
            {'reachable':survivors,'draw_pile':0,'registered':survivors})
        before_game=client.call('gamestate');action('play',{'cards':[0]});settled(client);after_game=client.call('gamestate')
        # Native gamestate exposes round chips as numeric chip totals.
        check(checks,scene+'.followup',{'hands':after_game['round']['hands_played']-before_game['round']['hands_played'],
            'chips':after_game['round']['chips']-before_game['round']['chips']}, {'hands':1,'chips':7})
        check(checks,scene+'.sealed',all(s['prepared'] is True for s in snapshots),True)
        previous=session.runtime
