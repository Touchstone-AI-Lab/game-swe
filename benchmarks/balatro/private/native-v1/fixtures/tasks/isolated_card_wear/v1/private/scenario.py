"""Actual scoring, depletion, redealing and a later real enhancement application."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.bounded_generator.observe_v1 import settled

REQUIRED=('initial','a.first','r2.redeal','a.second','b.first','r3.redeal','new.instance',
          'applicator.lifecycle','a.depleted','b.second','c.first','sealed')


def position(hand,identity):
    if hand.count(identity)!=1:raise ProtocolError('Required physical object unavailable for the real action')
    return hand.index(identity)


def semantic(cards):
    out={}
    for c in cards:
        if c['id'] in out:raise ProtocolError('Duplicate physical identity')
        uses=c['uses']
        if uses is not False and type(uses) not in (int,float):raise ProtocolError('Malformed remaining-use semantic value')
        out[c['id']]=dict(c,uses=None if uses is False else uses)
    return out


def evaluate(session,checks):
    client=session.client;root=session.runtime.directory;trace=[];snapshots=[]
    def retain(row):trace.append(row);write(root/'wear-scenario.json',trace)
    def action(method,args=None):
        r=client.action(method,args);retain({'action':method,'params':args,'response':r});return r
    def snap(label):
        settled(client);s=client.call('poc.wear.observe');snapshots.append(s)
        retain({'label':label,'observation':s});return s
    client.wait(lambda s:s['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'POLISH01'})
    client.wait(lambda s:s['state']=='BLIND_SELECT');action('poc.wear.prepare',{'stage':'deck'})
    action('select');settled(client);action('poc.wear.prepare',{'stage':'polish'});s=snap('initial')
    a,b=s['hand'][:2];all_ids=s['hand'].copy();ordinary=set(all_ids)-{a,b};c=s['hand'][2]
    uses={identity:(2 if identity in (a,b) else None) for identity in all_ids}
    def expected():
        return {identity:dict(id=identity,center='m_icw_polish' if count is not None else 'c_base',
            uses=count,rank=2,suit='Hearts',edition=False,debuff=False) for identity,count in uses.items()}
    check(checks,'initial',{'cards':semantic(s['cards']),'count':len(all_ids),'stage':s['stage']},
          {'cards':expected(),'count':8,'stage':2})
    def play(label,identity,remaining,chips):
        nonlocal s
        before=s;action('play',{'cards':[position(s['hand'],identity)]});s=snap(label);uses[identity]=remaining
        check(checks,label,{'cards':semantic(s['cards']),'chips':s['chips']-before['chips'],'hands':s['hands']-before['hands']},
              {'cards':expected(),'chips':chips,'hands':1})
    def advance(label,round_number):
        nonlocal s
        winners=[i for i,identity in enumerate(s['hand']) if identity in ordinary][:5]
        if len(winners)!=5:raise ProtocolError('Original ordinary winner pool no longer available')
        action('play',{'cards':winners});client.wait(lambda v:v['state']=='ROUND_EVAL')
        action('cash_out');client.wait(lambda v:v['state']=='SHOP');action('next_round')
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('select');s=snap(label)
        check(checks,label,{'hand':sorted(s['hand']),'cards':semantic(s['cards']),'round':s['round']},
              {'hand':sorted(all_ids),'cards':expected(),'round':round_number})
    play('a.first',a,1,27);advance('r2.redeal',2)
    play('a.second',a,None,27);play('b.first',b,1,27);advance('r3.redeal',3)
    before_life=settled(client);source=before_life['inventory'][0]
    response=action('use',{'consumable':0,'cards':[position(s['hand'],c)]});s=snap('new.instance');after_life=settled(client)
    uses[c]=2
    check(checks,'new.instance',{'state':response.get('state'),'cards':semantic(s['cards'])},
          {'state':'SELECTING_HAND','cards':expected()})
    removed=[v['removed'] for v in after_life['objects'] if v['id']==source['id']]
    check(checks,'applicator.lifecycle',{'source':source['key'],'inventory':after_life['inventory'],
        'removed':removed,'pending':after_life['pending_events'],'errors':after_life['observer_errors'],'dropped':after_life['dropped']},
        {'source':'c_icw_applicator','inventory':[],'removed':[True],'pending':0,'errors':0,'dropped':0})
    retain({'label':'applicator_lifecycle','observation':after_life})
    play('a.depleted',a,None,7);play('b.second',b,None,27);play('c.first',c,1,27)
    check(checks,'sealed',all(v['stage']==2 and len(v['cards'])==8 for v in snapshots),True)
