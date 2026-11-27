"""No candidate: real same-center duplicates, reorder/sale/acquisition, then score."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write

REQUIRED=('initial','reorder','first_score','sale','after_sale_score','shop','purchase','next_blind','final_score','sealed')


def ready(s,state):
    for key in ('frame','joker_limit','chips','dollars','hands','round','stop_use','play_count'):
        if type(s.get(key)) not in (int,float):raise ProtocolError('Missing native identity observation '+key)
    return s['state']==state and s['state_complete'] and not s['locked'] and not s['locks'] and not s['paused'] and s['stop_use']==0 and s['play_count']==0


def evaluate(session,checks):
    client=session.client;root=session.runtime.directory;trace=[];snapshots=[]
    def retain(row):trace.append(row);write(root/'multi-joker-probe-v2.json',trace)
    def action(method,args=None):
        r=client.action(method,args);retain(dict(action=method,params=args,response=r));return r
    def snap(label,state='SELECTING_HAND'):
        s=client.wait(lambda v:ready(v,state),method='poc.lja2p.observe',timeout=25)
        snapshots.append(s);retain(dict(label=label,observation=s));return s
    def ids(s):return [c['id'] for c in s['owned']]
    def play(label,s):
        action('play',{'cards':[0]});after=snap(label)
        check(checks,label,dict(chips=after['chips']-s['chips'],hands=after['hands']-s['hands'],owned=ids(after)),
              dict(chips=7,hands=1,owned=ids(s)))
        return after
    client.wait(lambda s:s['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'ADJ2PROBE'})
    client.wait(lambda s:s['state']=='BLIND_SELECT');action('poc.lja2p.prepare');action('select');s=snap('initial')
    initial=ids(s);credit=s['owned'][0]
    check(checks,'initial',dict(keys=[c['key'] for c in s['owned']],unique=len(set(initial)),capacity=s['joker_limit']),
        dict(keys=['j_credit_card','j_splash','j_splash','j_four_fingers','j_shortcut'],unique=5,capacity=5))
    order=[2,0,1,3,4];response=action('rearrange',{'jokers':order});s=snap('reordered')
    expected=[initial[i] for i in order]
    check(checks,'reorder',dict(state=response['state'],owned=ids(s)),dict(state='SELECTING_HAND',owned=expected))
    s=play('first_score',s);before=s;action('sell',{'joker':ids(s).index(credit['id'])});s=snap('sold')
    expected=[identity for identity in expected if identity != credit['id']];objects={c['id']:c for c in s['objects']}
    check(checks,'sale',dict(income=s['dollars']-before['dollars'],owned=ids(s),removed=objects[credit['id']]['removed']),
        dict(income=credit['sell_cost'],owned=expected,removed=True))
    s=play('after_sale_score',s)
    action('play',{'cards':[0,1,2,3,4]});client.wait(lambda v:v['state']=='ROUND_EVAL')
    action('cash_out');s=snap('shop','SHOP')
    check(checks,'shop',dict(keys=[c['key'] for c in s['shop']],owned=ids(s)),dict(keys=['j_splash','c_pluto'],owned=expected))
    offered=s['shop'][0];before=s;action('buy',{'card':0});s=snap('purchase','SHOP');expected=expected+[offered['id']]
    check(checks,'purchase',dict(debit=before['dollars']-s['dollars'],owned=ids(s),fresh=offered['id'] not in initial,
        stock=[c['key'] for c in s['shop']]),dict(debit=offered['cost'],owned=expected,fresh=True,stock=['c_pluto']))
    action('next_round');client.wait(lambda v:v['state']=='BLIND_SELECT');action('select');s=snap('next_blind')
    check(checks,'next_blind',dict(round=s['round'],owned=ids(s)),dict(round=2,owned=expected))
    play('final_score',s)
    check(checks,'sealed',all(v['prepared'] and v['joker_limit']==5 and all(not c['edition'] and not c['debuff'] for c in v['owned']) for v in snapshots),True)
