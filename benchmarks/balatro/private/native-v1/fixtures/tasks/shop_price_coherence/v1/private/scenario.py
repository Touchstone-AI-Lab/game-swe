"""Sealed inventory -> real ownership/rerolls/purchases -> later actual play."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write

CATALOG = {'j_spc_clerk':6,'j_joker':2,'j_greedy_joker':5,'j_banner':5,
           'j_half':5,'j_loyalty_card':5,'j_zany':4,'c_pluto':3,'c_mercury':3}
REQUIRED = ('prepared','clerk.buy','initial.prices','initial.buy',
            'reroll1','new1.prices','new1.buy','reroll2','new2.prices','new2.buy',
            'stable','clerk.sell','restored.prices','restored.buy',
            'reroll3','future.prices','future.buy','followup','sealed','configuration','identities')


def price(key, active):
    normal = CATALOG[key]
    return max(1, normal // 2) if active and key.startswith('j_') else normal


def ready(s, state='SHOP'):
    for key in ('frame','quiet_frames','observer_errors','dropped','dollars','discount',
                'reroll_cost','stage','stop_use','play_count','hands_played'):
        if type(s.get(key)) not in (int,float): raise ProtocolError('Missing numeric observation '+key)
    for key in ('state_complete','locked','paused','sealed'):
        if type(s.get(key)) is not bool: raise ProtocolError('Missing boolean '+key)
    for key in ('locks','shop','vouchers','owned','objects','rows'):
        if not isinstance(s.get(key),list): raise ProtocolError('Missing collection '+key)
    if s['observer_errors'] or s['dropped']: raise ProtocolError('Observer error/overflow')
    return (s['state']==state and s['state_complete'] and not s['locked'] and not s['locks']
            and not s['paused'] and s['stop_use']==0 and s['play_count']==0 and s['quiet_frames']>=8
            and (state!='SHOP' or all(c['buy_ready'] and c['quote'] for c in s['shop'])))


def locate(cards, identity):
    found = [i for i,c in enumerate(cards) if c['id']==identity]
    if len(found)!=1: raise ProtocolError('Expected unique identity unavailable')
    return found[0]


def evaluate(session, checks):
    client=session.client; root=session.runtime.directory; trace=[]; snapshots=[]
    owned=[]; seen={}; removed=[]; active=False
    def snap(label,state='SHOP'):
        s=client.wait(lambda v:ready(v,state),method='poc.spc.observe',timeout=25)
        snapshots.append(s);trace.append({'label':label,'observation':s});write(root/'price-scenario.json',trace)
        return s
    def action(method,params=None):
        response=client.action(method,params)
        trace.append({'action':method,'params':params,'response':response});write(root/'price-scenario.json',trace)
        return response
    def expected_prices(stock):
        return [{'id':c['id'],'key':c['key'],'cost':price(c['key'],active),
                 'quote':{'value':price(c['key'],active),'same_card':True,'field':'cost'}} for c in stock]
    def actual_prices(stock):
        return [{k:c[k] for k in ('id','key','cost','quote')} for c in stock]
    def prices(label): check(checks,label,actual_prices(s['shop']),expected_prices(s['shop']))
    def buy(label,position=0):
        nonlocal s
        target=s['shop'][position]; before=s; wanted=price(target['key'],active)
        remaining=[c['id'] for c in s['shop'] if c['id']!=target['id']]
        response=action('buy',{'card':position});s=snap(label);owned.append(target['id'])
        check(checks,label,{'state':response.get('state'),'debit':before['dollars']-s['dollars'],
              'quote':target['quote'],'stock':[c['id'] for c in s['shop']],
              'owned':[c['id'] for c in s['owned']],
              'owned_keys':[c['key'] for c in s['owned']]},
              {'state':'SHOP','debit':wanted,'quote':{'value':wanted,'same_card':True,'field':'cost'},
               'stock':remaining,'owned':owned.copy(),'owned_keys':[seen[i] for i in owned]})
        return target
    def reroll(number,keys):
        nonlocal s
        before=s; old=[c['id'] for c in before['shop']];removed.extend(old)
        response=action('reroll');s=snap('reroll'+str(number));now=[c['id'] for c in s['shop']]
        objects={c['id']:c for c in s['objects']}
        check(checks,'reroll'+str(number),{'state':response.get('state'),'debit':before['dollars']-s['dollars'],
              'fee_before':before['reroll_cost'],'new':len(now)==len(set(now)) and not set(seen)&set(now),
              'old_removed':all(objects[i]['removed'] for i in old),'keys':[c['key'] for c in s['shop']],
              'owned':[c['id'] for c in s['owned']],'queue':s['forced_remaining']},
              {'state':'SHOP','debit':4+number,'fee_before':4+number,'new':True,'old_removed':True,
               'keys':keys,'owned':owned.copy(),'queue':12-4*number})
        seen.update({c['id']:c['key'] for c in s['shop']})
    client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'SPCV1'})
    client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.spc.prepare',{'stage':'deck'})
    action('select');client.wait(lambda v:v['state']=='SELECTING_HAND');action('play',{'cards':[0,1,2,3,4]})
    client.wait(lambda v:v['state']=='ROUND_EVAL');action('cash_out');client.wait(lambda v:v['state']=='SHOP')
    action('poc.spc.prepare',{'stage':'shop'});s=snap('prepared')
    check(checks,'prepared',{'keys':[c['key'] for c in s['shop']],'owned':len(s['owned']),
          'discount':s['discount'],'queue':s['forced_remaining'],'vouchers':len(s['vouchers'])},
          {'keys':['j_spc_clerk','j_greedy_joker','c_pluto','j_joker'],'owned':0,'discount':0,'queue':12,'vouchers':0})
    seen.update({c['id']:c['key'] for c in s['shop']})
    clerk=buy('clerk.buy');active=True;prices('initial.prices');buy('initial.buy')
    reroll(1,['j_joker','j_half','c_mercury','j_banner']);prices('new1.prices');buy('new1.buy')
    reroll(2,['j_greedy_joker','c_pluto','j_loyalty_card','j_zany']);prices('new2.prices');buy('new2.buy')
    before=s;s=client.wait(lambda v:ready(v) and v['frame']>=before['frame']+12,method='poc.spc.observe',timeout=5)
    trace.append({'label':'stable','observation':s});write(root/'price-scenario.json',trace)
    check(checks,'stable',{'prices':actual_prices(s['shop']),'money':s['dollars'],'ids':[c['id'] for c in s['shop']]},
          {'prices':expected_prices(before['shop']),'money':before['dollars'],'ids':[c['id'] for c in before['shop']]})
    before=s;position=locate(s['owned'],clerk['id']);response=action('sell',{'joker':position});s=snap('clerk.sell')
    active=False;owned.remove(clerk['id']);removed.append(clerk['id'])
    objects={c['id']:c for c in s['objects']}
    check(checks,'clerk.sell',{'state':response.get('state'),'credit':s['dollars']-before['dollars'],
          'removed':objects[clerk['id']]['removed'],'owned':[c['id'] for c in s['owned']],
          'stock':[c['id'] for c in s['shop']]},
          {'state':'SHOP','credit':3,'removed':True,'owned':owned.copy(),'stock':[c['id'] for c in before['shop']]})
    prices('restored.prices');buy('restored.buy',1)
    reroll(3,['j_joker','c_mercury','j_half','j_banner']);prices('future.prices');buy('future.buy')
    final={c['id']:c for c in s['objects']}
    check(checks,'identities',{'removed':sorted(i for i in seen if final[i]['removed']),
          'keys':{i:final[i]['key'] for i in seen},'owned':[c['id'] for c in s['owned']]},
          {'removed':sorted(removed),'keys':seen.copy(),'owned':owned.copy()})
    action('next_round');client.wait(lambda v:v['state']=='BLIND_SELECT');action('select');before=snap('draw','SELECTING_HAND')
    action('play',{'cards':[0]});s=snap('followup','SELECTING_HAND')
    check(checks,'followup',{'hands':s['hands_played']-before['hands_played'],'owned':[c['id'] for c in s['owned']]},
          {'hands':1,'owned':owned.copy()})
    check(checks,'sealed',all(v['sealed'] and v['stage']==2 for v in snapshots),True)
    check(checks,'configuration',all(v['discount']==0 and all(not c['edition'] and not c['debuff']
          for c in v['shop']+v['owned']) for v in snapshots),True)
