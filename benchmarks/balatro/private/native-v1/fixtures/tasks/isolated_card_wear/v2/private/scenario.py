"""Four real rounds and three applications; independent per-object expected state."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.bounded_generator.observe_v1 import settled, ready
from tasks.bounded_generator.v1.private.scenario import usage
from tasks.isolated_card_wear.v1.private.scenario import position,semantic

REQUIRED=('initial','pair.first','r2','discard.held','refresh.worn','a.refreshed','b.last','r3',
          'refresh.depleted','a.last','b.refreshed','apply.new','c.first','r4','a.ordinary','pair.last','applications.lifecycle','stable','sealed')


def evaluate(session,checks):
    client=session.client;root=session.runtime.directory;trace=[];snapshots=[];applications=[]
    def retain(row):trace.append(row);write(root/'wear-reapplication-task-v2.json',trace)
    def action(method,args=None):
        r=client.action(method,args);retain(dict(action=method,params=args,response=r));return r
    def snap(label):
        settled(client);s=client.call('poc.wear2.observe');snapshots.append(s)
        retain(dict(label=label,observation=s));return s
    client.wait(lambda s:s['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'WEAR2TSK'})
    client.wait(lambda s:s['state']=='BLIND_SELECT');action('poc.wear2.prepare',{'stage':'deck'})
    action('select');settled(client);action('poc.wear2.prepare',{'stage':'polish'});s=snap('initial')
    a,b,c,d=s['hand'][:4];all_ids=s['hand'].copy();uses={i:(2 if i in (a,b,d) else None) for i in all_ids}
    ordinary=set(all_ids)-{a,b,d}
    def expected():
        return {i:dict(id=i,center='m_icw2_polish' if n is not None else 'c_base',uses=n,
            rank=2,suit='Hearts',edition=False,debuff=False) for i,n in uses.items()}
    check(checks,'initial',dict(cards=semantic(s['cards']),count=len(all_ids),stage=s['stage']),
        dict(cards=expected(),count=8,stage=2))
    def play(label,identities,chips):
        nonlocal s
        before=s;action('play',{'cards':[position(s['hand'],i) for i in identities]});s=snap(label)
        for i in identities:
            if uses[i] is not None:uses[i]=uses[i]-1 or None
        check(checks,label,dict(cards=semantic(s['cards']),chips=s['chips']-before['chips'],hands=s['hands']-before['hands']),
            dict(cards=expected(),chips=chips,hands=1))
    def advance(label,round_number,include_d=False):
        nonlocal s
        eligible=(ordinary-{c})|{d} if include_d else ordinary
        winners=[i for i,x in enumerate(s['hand']) if x in eligible][:5]
        if len(winners)!=5:raise ProtocolError('Initial native winning-card pool unavailable')
        action('play',{'cards':winners});client.wait(lambda v:v['state']=='ROUND_EVAL')
        if include_d:uses[d]-=1
        action('cash_out');client.wait(lambda v:v['state']=='SHOP');action('next_round')
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('select');s=snap(label)
        check(checks,label,dict(hand=sorted(s['hand']),cards=semantic(s['cards']),round=s['round']),
            dict(hand=sorted(all_ids),cards=expected(),round=round_number))
    def apply(label,identity):
        nonlocal s
        before=settled(client);source=before['inventory'][0]
        response=action('use',{'consumable':0,'cards':[position(s['hand'],identity)]})
        s=snap(label);after=settled(client);uses[identity]=2
        ledger=usage(before).copy();ledger['c_icw2_applicator']=ledger.get('c_icw2_applicator',0)+1
        calls=after['actions'][len(before['actions']):]
        applications.append(dict(usage=usage(after)==ledger,capacity=after['capacity']==before['capacity'],
            buffer=after['buffer']==before['buffer']==0,levels=after['hand_levels']==before['hand_levels'],
            action=len(calls)==1 and calls[0]['target']==source['id'],events=bool(after['events']),
            pending=after['pending_events']==0,errors=after['observer_errors']==after['dropped']==0))
        check(checks,label,dict(state=response['state'],cards=semantic(s['cards']),
            inventory=after['inventory'],removed=[v['removed'] for v in after['objects'] if v['id']==source['id']],
            money=after['dollars'],pending=after['pending_events']),
            dict(state='SELECTING_HAND',cards=expected(),inventory=before['inventory'][1:],removed=[True],money=before['dollars'],pending=0))
    play('pair.first',[a,b],108);advance('r2',2)
    action('discard',{'cards':[position(s['hand'],d)]});s=snap('discard.held')
    check(checks,'discard.held',dict(cards=semantic(s['cards']),absent=d not in s['hand']),dict(cards=expected(),absent=True))
    apply('refresh.worn',a);play('a.refreshed',[a],27);play('b.last',[b],27);advance('r3',3)
    apply('refresh.depleted',b);play('a.last',[a],27);play('b.refreshed',[b],27)
    apply('apply.new',c);play('c.first',[c],27);advance('r4',4,True)
    play('a.ordinary',[a],7);play('pair.last',[b,c],108)
    check(checks,'applications.lifecycle',applications,[{k:True for k in ('usage','capacity','buffer','levels','action','events','pending','errors')} for _ in range(3)])
    end=settled(client)
    client.wait(lambda v:ready(v) and v['frame']>=end['frame']+12,method='poc.bg.observe',timeout=5)
    again=snap('stable')
    check(checks,'stable',dict(cards=semantic(again['cards']),chips=again['chips'],hands=again['hands']),dict(cards=semantic(s['cards']),chips=s['chips'],hands=s['hands']))
    check(checks,'sealed',all(v['stage']==2 and len(v['cards'])==8 for v in snapshots),True)
