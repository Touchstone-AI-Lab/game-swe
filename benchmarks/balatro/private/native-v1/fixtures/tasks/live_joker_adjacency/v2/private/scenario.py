"""Independent physical instances, native row edits and actual summed score."""
from poc.checks import check
from scripts.audit import write
from tasks.live_joker_adjacency.probe_v2.probe import ready

TARGET = 'j_lja2_neighbors'
REQUIRED = tuple('single.'+k for k in ('initial','first_score','repeat_score','stable','sealed')) + tuple(
    'multi.'+k for k in ('initial','first_score','reorder','reordered_score','neighbor_sale','after_sale_score',
                        'shop','purchase','next_blind','three_order','three_score','target_sale',
                        'last_score','stable','sealed'))


def evaluate(session, checks):
    for number, mode in enumerate(('single','multi')):
        if number:
            session.restart()
        client = session.client
        root = session.runtime.directory
        trace, snapshots, stability = [], [], []

        def retain(row):
            trace.append(row)
            write(root/'multi-instance-adjacency-v2.json', trace)

        def record(name, actual, expected):
            check(checks, mode+'.'+name, actual, expected)

        def action(method, params=None):
            value = client.action(method, params)
            retain(dict(action=method, params=params, response=value))
            return value

        def snap(label, state='SELECTING_HAND'):
            value = client.wait(lambda s: ready(s,state),method='poc.lja2.observe',timeout=25)
            snapshots.append(value)
            retain(dict(label=label,observation=value))
            return value

        def ids(s):
            return [c['id'] for c in s['owned']]

        def semantic(s):
            return {k:s[k] for k in ('owned','shop','dollars','hands','chips','round','joker_limit')}

        def play(label, before, expected_chips):
            response = action('play',{'cards':[0]})
            after = snap(label)
            record(label,dict(state=response['state'],chips=after['chips']-before['chips'],
                             hands=after['hands']-before['hands'],owned=ids(after)),
                         dict(state='SELECTING_HAND',chips=expected_chips,hands=1,owned=ids(before)))
            stable = client.wait(lambda s:ready(s,'SELECTING_HAND') and s['frame']>=after['frame']+12,
                                 method='poc.lja2.observe',timeout=5)
            snapshots.append(stable)
            retain(dict(label=label+'_stable',observation=stable))
            stability.append(semantic(stable)==semantic(after))
            return after

        def sell(label, before, identity):
            sold = next(c for c in before['owned'] if c['id']==identity)
            response = action('sell',{'joker':ids(before).index(identity)})
            after = snap(label)
            objects = {c['id']:c for c in after['objects']}
            record(label,dict(state=response['state'],income=after['dollars']-before['dollars'],
                   owned=ids(after),removed=objects[identity]['removed']),
                   dict(state='SELECTING_HAND',income=sold['sell_cost'],
                   owned=[i for i in ids(before) if i!=identity],removed=True))
            return after

        client.wait(lambda s:s['state']=='MENU')
        action('start',{'deck':'RED','stake':'WHITE','seed':'MULTINEIGHBOR2'})
        client.wait(lambda s:s['state']=='BLIND_SELECT')
        action('poc.lja2.prepare',{'mode':mode})
        action('select')
        s = snap('initial')
        keys = ['j_credit_card',TARGET,'j_four_fingers'] if mode=='single' else [
            'j_credit_card',TARGET,TARGET,'j_four_fingers','j_splash']
        record('initial',dict(keys=[c['key'] for c in s['owned']],unique=len(set(ids(s))),
                             capacity=s['joker_limit'],round=s['round']),
                         dict(keys=keys,unique=len(keys),capacity=5,round=1))
        initial = ids(s)
        if mode=='single':
            s = play('first_score',s,28)
            play('repeat_score',s,28)
        else:
            credit,t1,t2,uncommon,splash = initial
            s = play('first_score',s,70)
            order = [1,3,0,2,4]
            response = action('rearrange',{'jokers':order})
            s = snap('reorder')
            record('reorder',dict(state=response['state'],owned=ids(s)),
                            dict(state='SELECTING_HAND',owned=[t1,uncommon,credit,t2,splash]))
            s = play('reordered_score',s,49)
            s = sell('neighbor_sale',s,credit)
            s = play('after_sale_score',s,28)
            action('play',{'cards':[0,1,2,3,4]})
            client.wait(lambda v:v['state']=='ROUND_EVAL')
            action('cash_out')
            s = snap('shop','SHOP')
            record('shop',dict(keys=[c['key'] for c in s['shop']],owned=ids(s)),
                          dict(keys=[TARGET,'c_pluto'],owned=[t1,uncommon,t2,splash]))
            offered = s['shop'][0]
            t3 = offered['id']
            before = s
            response = action('buy',{'card':0})
            s = snap('purchase','SHOP')
            record('purchase',dict(state=response['state'],debit=before['dollars']-s['dollars'],
                owned=ids(s),fresh=t3 not in initial,stock=[c['key'] for c in s['shop']]),
                dict(state='SHOP',debit=offered['cost'],owned=[t1,uncommon,t2,splash,t3],
                     fresh=True,stock=['c_pluto']))
            action('next_round')
            client.wait(lambda v:v['state']=='BLIND_SELECT')
            action('select')
            s = snap('next_blind')
            record('next_blind',dict(round=s['round'],owned=ids(s)),
                               dict(round=2,owned=[t1,uncommon,t2,splash,t3]))
            action('rearrange',{'jokers':[0,2,4,1,3]})
            s = snap('three_order')
            record('three_order',ids(s),[t1,t2,t3,uncommon,splash])
            s = play('three_score',s,91)
            s = sell('target_sale',s,t2)
            play('last_score',s,49)
        record('stable',all(stability),True)
        record('sealed',all(s['prepared'] and s['joker_limit']==5 and all(
            not c['edition'] and not c['debuff'] for c in s['owned']) for s in snapshots),True)
