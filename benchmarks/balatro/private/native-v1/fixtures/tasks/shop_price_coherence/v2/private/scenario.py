"""Public-core protocol plus independently modeled native transactions."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.shop_price_coherence.v1.private.scenario import ready,locate
from tasks.shop_price_coherence.probe_v2.protocol import buy_once
from .oracle import price,protocol_expected

RULES={'j_sp2_flat':'flat','j_sp2_ratio':'ratio','j_sp2_coupon':'coupon'}
COSTS={'j_sp2_flat':4,'j_sp2_ratio':6,'j_sp2_coupon':4,'j_fibonacci':8,
       'j_joker':2,'j_greedy_joker':5,'j_banner':5,'c_pluto':3,'c_mercury':3}
NORMAL_OPERATIONS=('flat.buy','ratio1.buy','ratio2.buy','coupon.buy','reroll1','planet.buy',
                   'first.buy','second.buy','ratio.sell','post_remove.buy','reroll2','flat2.buy',
                   'coupon2.buy','planet2.buy','third.buy','shop2','new_ratio.buy','new_fib.buy')
REJECT_OPERATIONS=('coupon.buy','recover.sell','recover.buy')
REQUIRED=tuple('core.'+key for key in protocol_expected())+tuple(
    scene+'.'+name for scene in ('normal','funds','capacity')
    for name in (('prepared',)+tuple(x for op in (NORMAL_OPERATIONS if scene=='normal' else REJECT_OPERATIONS)
                                for x in (op,op+'.quotes'))+
                 (('followup',) if scene=='normal' else ('reject','unchanged','followup'))+
                 ('stable','sealed','identities')))


def evaluate(session,checks):
    client=session.client
    client.wait(lambda s:s['state']=='MENU')
    protocol=client.call('poc.spc2.protocol')
    if protocol.get('scope')!='isolated-core-protocol' or set(protocol.get('cases',{}))!=set(protocol_expected()):
        raise ProtocolError('Incomplete private protocol response')
    for key,expected in protocol_expected().items():check(checks,'core.'+key,protocol['cases'][key],expected)
    for turn,scene in enumerate(('normal','funds','capacity')):
        if turn:session.restart()
        client=session.client;root=session.runtime.directory;trace=[];snapshots=[]
        owners={};expected_jokers=[];expected_consumables=[];seen={};removed=[]
        def persist():write(root/'checkout-v2-trace.json',trace)
        def action(method,params=None):
            response=client.action(method,params);trace.append(dict(action=method,params=params,response=response));persist();return response
        def snap(label,state='SHOP'):
            value=client.wait(lambda v:ready(v,state),method='poc.spc2.observe',timeout=25)
            trace.append(dict(label=label,observation=value));snapshots.append(value);persist();return value
        def record(label,observed,expected):check(checks,scene+'.'+label,observed,expected)
        def expected_price(key):
            f=sum(v['kind']=='flat' for v in owners.values())
            r=sum(v['kind']=='ratio' for v in owners.values())
            c=sum(v['kind']=='coupon' and v['available'] for v in owners.values())
            return price(COSTS[key],f,r,c,key.startswith('j_') and key not in RULES)
        def quotes(label,s):
            record(label+'.quotes',[{k:c[k] for k in ('id','key','cost','quote')} for c in s['shop']],
                   [dict(id=c['id'],key=c['key'],cost=expected_price(c['key']),quote={
                    'value':expected_price(c['key']),'same_card':True,'field':'cost'}) for c in s['shop']])
        def key_id(s,key):
            ids=[c['id'] for c in s['shop'] if c['key']==key]
            if not ids:raise ProtocolError('Required offer unavailable: '+key)
            return ids[0]
        def buy(label,s,key):
            ident=key_id(s,key);index=locate(s['shop'],ident);target=s['shop'][index]
            wanted=expected_price(key);reply=buy_once(client,index)
            trace.append(dict(action='buy',params={'card':index},response=reply));persist();after=snap(label)
            destination=expected_jokers if key.startswith('j_') else expected_consumables
            destination.append(ident)
            record(label,dict(kind=reply['kind'],debit=s['dollars']-after['dollars'],quote=target['quote'],
                   stock=[c['id'] for c in after['shop']],owned=[c['id'] for c in after['owned']],
                   consumables=[c['id'] for c in after['consumables']]),
                   dict(kind='success',debit=wanted,quote={'value':wanted,'same_card':True,'field':'cost'},
                   stock=[c['id'] for c in s['shop'] if c['id']!=ident],owned=expected_jokers.copy(),consumables=expected_consumables.copy()))
            if key in RULES:owners[ident]=dict(kind=RULES[key],available=True)
            elif key.startswith('j_'):
                for source in owners.values():
                    if source['kind']=='coupon':source['available']=False
            quotes(label,after);return after,ident
        def sell(label,s,ident):
            index=locate(s['owned'],ident);target=s['owned'][index]
            response=action('sell',{'joker':index});after=snap(label)
            expected_jokers.remove(ident);owners.pop(ident,None);removed.append(ident)
            record(label,dict(state=response['state'],credit=after['dollars']-s['dollars'],
                   owned=[c['id'] for c in after['owned']],stock=[c['id'] for c in after['shop']]),
                   dict(state='SHOP',credit=target['sell_cost'],owned=expected_jokers.copy(),stock=[c['id'] for c in s['shop']]))
            quotes(label,after);return after
        def reroll(label,s,keys):
            response=action('reroll');after=snap(label);old=[c['id'] for c in s['shop']];removed.extend(old)
            record(label,dict(state=response['state'],debit=s['dollars']-after['dollars'],keys=[c['key'] for c in after['shop']],
                   new=not set(seen)&set(c['id'] for c in after['shop']),owned=[c['id'] for c in after['owned']]),
                   dict(state='SHOP',debit=s['reroll_cost'],keys=keys,new=True,owned=expected_jokers.copy()))
            seen.update({c['id']:c['key'] for c in after['shop']});quotes(label,after);return after
        def followup(s):
            removed.extend(c['id'] for c in s['shop'])
            action('next_round');client.wait(lambda s:s['state']=='BLIND_SELECT');action('select');before=snap('draw','SELECTING_HAND')
            action('play',{'cards':[0]});after=snap('followup','SELECTING_HAND')
            # Heart 2: Greedy is Diamonds-only. Three Fibonacci give 7*(1+3*8)=175.
            expected_score={'normal':175,'funds':35,'capacity':63}[scene]
            record('followup',dict(hands=after['hands_played']-before['hands_played'],chips=after['chips']-before['chips'],
                   money=after['dollars']-before['dollars'],owned=[c['id'] for c in after['owned']]),
                   dict(hands=1,chips=expected_score,money=0,owned=expected_jokers.copy()))
            return after
        client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'SPC2V1'})
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.spc2.prepare',{'stage':'deck','scene':scene})
        action('select');client.wait(lambda v:v['state']=='SELECTING_HAND');action('play',{'cards':[0,1,2,3,4]})
        client.wait(lambda v:v['state']=='ROUND_EVAL');action('cash_out');client.wait(lambda v:v['state']=='SHOP')
        action('poc.spc2.prepare',{'stage':'shop'});s=snap('prepared')
        expected_jokers.extend(c['id'] for c in s['owned']);seen.update({c['id']:c['key'] for c in s['shop']+s['owned']})
        keys=['j_sp2_flat','j_sp2_ratio','j_sp2_ratio','j_sp2_coupon'] if scene=='normal' else ['j_sp2_coupon','j_fibonacci','j_joker','c_pluto']
        record('prepared',dict(keys=[c['key'] for c in s['shop']],prices=[c['cost'] for c in s['shop']],
               owned=[c['key'] for c in s['owned']],consumables=len(s['consumables']),limit=s['joker_limit'],discount=s['discount']),
               dict(keys=keys,prices=[COSTS[k] for k in keys],owned=[] if scene=='normal' else ['j_banner'],
                    consumables=0,limit=2 if scene=='capacity' else 12,discount=0))
        if scene=='normal':
            s,_=buy('flat.buy',s,'j_sp2_flat');s,ratio=buy('ratio1.buy',s,'j_sp2_ratio')
            s,_=buy('ratio2.buy',s,'j_sp2_ratio');s,_=buy('coupon.buy',s,'j_sp2_coupon')
            s=reroll('reroll1',s,['c_pluto','j_fibonacci','j_fibonacci','j_greedy_joker'])
            s,_=buy('planet.buy',s,'c_pluto');s,_=buy('first.buy',s,'j_fibonacci');s,_=buy('second.buy',s,'j_fibonacci')
            s=sell('ratio.sell',s,ratio);s,_=buy('post_remove.buy',s,'j_greedy_joker')
            s=reroll('reroll2',s,['j_sp2_flat','j_fibonacci','c_mercury','j_sp2_coupon'])
            s,_=buy('flat2.buy',s,'j_sp2_flat');s,_=buy('coupon2.buy',s,'j_sp2_coupon')
            s,_=buy('planet2.buy',s,'c_mercury');s,_=buy('third.buy',s,'j_fibonacci')
            s=followup(s);old_shop=[c['id'] for c in s['shop']];removed.extend(old_shop)
            action('play',{'cards':[0,1,2,3,4]});client.wait(lambda v:v['state']=='ROUND_EVAL');action('cash_out');s=snap('shop2')
            record('shop2',dict(round=s['round'],keys=[c['key'] for c in s['shop']],
                   new=not set(seen)&set(c['id'] for c in s['shop']),owned=[c['id'] for c in s['owned']]),
                   dict(round=2,keys=['j_fibonacci','j_sp2_ratio','j_joker','c_pluto'],new=True,owned=expected_jokers.copy()))
            seen.update({c['id']:c['key'] for c in s['shop']});quotes('shop2',s)
            s,_=buy('new_ratio.buy',s,'j_sp2_ratio');s,_=buy('new_fib.buy',s,'j_fibonacci')
        else:
            bridge=expected_jokers[0];s,_=buy('coupon.buy',s,'j_sp2_coupon')
            before=s;index=locate(s['shop'],key_id(s,'j_fibonacci'));reply=buy_once(client,index)
            trace.append(dict(action='buy',params={'card':index},response=reply));persist();s=snap('reject')
            record('reject',reply['kind'],'bad_request')
            def invariant(v):return {'money':v['dollars'],'shop':[{k:c[k] for k in ('id','key','cost','quote')} for c in v['shop']],
                                      'owned':[c['id'] for c in v['owned']],'consumables':[c['id'] for c in v['consumables']]}
            record('unchanged',invariant(s),invariant(before))
            s=sell('recover.sell',s,bridge)
            s,_=buy('recover.buy',s,'j_joker' if scene=='funds' else 'j_fibonacci')
            s=followup(s)
        before=s
        s=client.wait(lambda v:ready(v,before['state']) and v['frame']>=before['frame']+12,method='poc.spc2.observe',timeout=5)
        trace.append(dict(label='stable',observation=s));persist()
        def stable(v):return {'money':v['dollars'],'shop':[{k:c[k] for k in ('id','key','cost','quote')} for c in v['shop']],
                             'owned':[c['id'] for c in v['owned']],'consumables':[c['id'] for c in v['consumables']]}
        record('stable',stable(s),stable(before))
        record('sealed',all(v['sealed'] and v['stage']==2 for v in snapshots),True)
        objects={c['id']:c for c in s['objects']}
        record('identities',dict(keys={i:objects[i]['key'] for i in seen},removed=sorted(i for i in seen if objects[i]['removed']),
               owned=[c['id'] for c in s['owned']],consumables=[c['id'] for c in s['consumables']]),
               dict(keys=seen.copy(),removed=sorted(removed),owned=expected_jokers.copy(),consumables=expected_consumables.copy()))
