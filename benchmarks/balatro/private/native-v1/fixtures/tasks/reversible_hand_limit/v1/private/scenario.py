"""One clean process, sealed initial shop, real transactions and later actual draw/refill."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write

REQUIRED=('prepared','solo.buy','solo.sell','before.buy','background.buy','before.sell',
          'after.buy','second.buy','after.sell','second.sell','observation_stable','real_draw',
          'background.sell','real_play','identities','no_fixture_after_seal','configuration')


def ready(s, state):
    for k in ('frame','hand_limit','hand_count','quiet_frames','dropped','observer_errors','stop_use','play_count','preparations','dollars'):
        if type(s.get(k)) not in (int,float): raise ProtocolError('Missing numeric observation '+k)
    for k in ('state_complete','locked','paused','prepared','sealed'):
        if type(s.get(k)) is not bool: raise ProtocolError('Missing boolean '+k)
    for k in ('jokers','shop','hand_ids','rows','locks','objects'):
        if not isinstance(s.get(k),list): raise ProtocolError('Missing collection '+k)
    if s['dropped'] or s['observer_errors']: raise ProtocolError('Observer error/overflow')
    return (s['state']==state and s['state_complete'] and not s['locked'] and not s['locks']
            and not s['paused'] and s['stop_use']==0 and s['quiet_frames']>=8 and s['play_count']==0
            and all(c['buy_ready'] for c in s['shop']))


def index(s, area, identity):
    found=[i for i,c in enumerate(s[area]) if c['id']==identity]
    if len(found)!=1: raise ProtocolError('Required identity unavailable for actual action')
    return found[0]


def evaluate(session,checks):
    client=session.client; root=session.runtime.directory; trace=[]; snapshots=[]
    def snap(label,state):
        s=client.wait(lambda s:ready(s,state),method='poc.hl.observe',timeout=25)
        trace.append({'label':label,'observation':s});snapshots.append(s)
        write(root/'handlimit-scenario.json',trace)
        return s
    def action(method,params=None):
        response=client.action(method,params)
        trace.append({'action':method,'params':params,'response':response})
        write(root/'handlimit-scenario.json',trace)
        return response
    client.wait(lambda s:s['state']=='MENU')
    action('start',{'deck':'RED','stake':'WHITE','seed':'RHLV1'})
    client.wait(lambda s:s['state']=='BLIND_SELECT');action('poc.hl.prepare',{'stage':'deck'})
    action('select');client.wait(lambda s:s['state']=='SELECTING_HAND')
    action('play',{'cards':[0,1,2,3,4]});client.wait(lambda s:s['state']=='ROUND_EVAL')
    action('cash_out');client.wait(lambda s:s['state']=='SHOP')
    action('poc.hl.prepare',{'stage':'shop'});s=snap('prepared','SHOP')
    if len(s['shop'])!=5: raise ProtocolError('Fixture did not create declared stock')
    t1,t2,background,t3,t4=s['shop']
    ids=[c['id'] for c in s['shop']]
    check(checks,'prepared',{'limit':s['hand_limit'],'owned':len(s['jokers']),
          'keys':[c['key'] for c in s['shop']],'fresh':all(not c['added'] for c in s['shop'])},
          {'limit':8,'owned':0,'keys':['j_rhl_spacer','j_rhl_spacer','j_juggler','j_rhl_spacer','j_rhl_spacer'],'fresh':True})
    owned=[]; stock=ids.copy(); removed=[]
    def transaction(case,method,target,limit,state='SHOP'):
        nonlocal s
        area='shop' if method=='buy' else 'jokers'
        position=index(s,area,target['id']); actual=s[area][position]
        money=s['dollars']-actual['cost'] if method=='buy' else s['dollars']+actual['sell_cost']
        response=action(method,{'card' if method=='buy' else 'joker':position})
        if response.get('state')!=state: raise ProtocolError('Missing full transaction response')
        s=snap(case,state)
        if method=='buy':
            owned.append(target['id']);stock.remove(target['id'])
        else:
            owned.remove(target['id']);removed.append(target['id'])
        check(checks,case,{'limit':s['hand_limit'],'owned':[c['id'] for c in s['jokers']],
              'stock':[c['id'] for c in s['shop']] if state=='SHOP' else [],
              'dollars':s['dollars'],'removed':[c['id'] for c in s['objects'] if c['id'] in removed and c['removed']]},
              {'limit':limit,'owned':owned.copy(),'stock':stock.copy() if state=='SHOP' else [],
               'dollars':money,'removed':sorted(removed)})
    transaction('solo.buy','buy',t1,10)
    transaction('solo.sell','sell',t1,8)
    transaction('before.buy','buy',t2,10)
    transaction('background.buy','buy',background,11)
    transaction('before.sell','sell',t2,9)
    transaction('after.buy','buy',t3,11)
    transaction('second.buy','buy',t4,13)
    transaction('after.sell','sell',t3,11)
    transaction('second.sell','sell',t4,9)
    first=s; s=client.wait(lambda value:ready(value,'SHOP') and value['frame']>=first['frame']+12,
                         method='poc.hl.observe',timeout=5)
    check(checks,'observation_stable',{'limit':s['hand_limit'],'owned':[c['id'] for c in s['jokers']],
          'money':s['dollars']},{'limit':9,'owned':[background['id']],'money':first['dollars']})
    action('next_round');client.wait(lambda s:s['state']=='BLIND_SELECT')
    action('select');s=snap('real_draw','SELECTING_HAND')
    check(checks,'real_draw',{'limit':s['hand_limit'],'count':s['hand_count'],'unique':len(set(s['hand_ids']))},
          {'limit':9,'count':9,'unique':9})
    transaction('background.sell','sell',background,8,'SELECTING_HAND')
    before=s
    action('play',{'cards':[0]});s=snap('real_play','SELECTING_HAND')
    check(checks,'real_play',{'limit':s['hand_limit'],'count':s['hand_count'],
          'hand_delta':s['hands_played']-before['hands_played']},{'limit':8,'count':8,'hand_delta':1})
    final={c['id']:c for c in s['objects']}
    check(checks,'identities',{'unique_initial':len(set(ids)),'destroyed':[i for i in ids if final[i]['removed']],
          'owned':[c['id'] for c in s['jokers']]},{'unique_initial':5,'destroyed':ids,'owned':[]})
    check(checks,'no_fixture_after_seal',all(v['sealed'] and v['preparations']==2 for v in snapshots),True)
    check(checks,'configuration',all(not c['edition'] and not c['debuff'] for v in snapshots for c in v['jokers']),True)
