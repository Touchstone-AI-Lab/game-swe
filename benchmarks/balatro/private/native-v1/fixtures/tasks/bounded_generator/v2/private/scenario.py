"""Five independent native scenes; no business repair or callback invocation."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.bounded_generator.observe_v1 import settled, index_of
from tasks.bounded_generator.protocol_v1 import use_once
from tasks.bounded_generator.v1.private.scenario import mapping, removed, usage, PRODUCT

GEN = 'c_bg2_generator'
SCENES = {'room': (5, [2, 2]), 'one': (2, [1]), 'three': (4, [3]),
          'recover': (3, [3]), 'mixed': (5, [1, 3])}
STEPS = {'room': ('generate0', 'generate1', 'mercury0', 'mercury1', 'hermit'),
         'one': ('generate0', 'hermit'), 'three': ('generate0', 'mercury0', 'hermit'),
         'recover': ('refusal', 'hermit', 'generate0', 'mercury0'),
         'mixed': ('generate0', 'generate1', 'mercury0', 'hermit')}
REQUIRED = tuple(scene + '.' + case for scene in SCENES for case in
    ('initial', 'queries') + tuple(step + '.' + kind for step in STEPS[scene]
        for kind in (('response', 'inventory', 'lifecycle', 'usage', 'invariants')
                     if step.startswith('generate') or step == 'refusal' else ('inventory', 'effect'))) + ('sealed',))


def evaluate(session, checks):
    for number, (scene, (capacity, counts)) in enumerate(SCENES.items()):
        if number:
            session.restart()
        client = session.client
        root = session.runtime.directory
        trace = []

        def record(name, actual, expected):
            check(checks, scene + '.' + name, actual, expected)

        def retain(name, before, reply, after):
            trace.append(dict(name=name, before=before, reply=reply, after=after))
            write(root / 'configured-generator-evidence-v2.json', trace)

        client.wait(lambda s: s['state'] == 'MENU')
        client.action('start', {'deck': 'RED', 'stake': 'WHITE', 'seed': 'BG2TASK'})
        client.wait(lambda s: s['state'] == 'BLIND_SELECT')
        prepared = client.action('poc.bg2.prepare', {'mode': scene})
        client.action('select')
        initial = settled(client)
        sources = initial['inventory'][:-1]
        hermit = initial['inventory'][-1]['id']
        expected_config = dict(sources=[dict(sort_id=c['sort_id'], products=n) for c, n in zip(sources, counts)],
                               default=2, fixture_calls=1)
        record('initial', dict(keys=[c['key'] for c in initial['inventory']], capacity=initial['capacity'],
               buffer=initial['buffer'], config=prepared, dollars=initial['dollars'], usage=usage(initial),
               ordinary=all(not c['edition'] and not c['debuff'] for c in initial['inventory'])),
               dict(keys=[GEN]*len(counts)+['c_hermit'], capacity=capacity, buffer=0, config=expected_config,
                    dollars=10, usage={}, ordinary=True))
        for _ in range(4):
            client.call('gamestate')
        queried = settled(client)
        keys = ('inventory', 'capacity', 'buffer', 'dollars', 'hand_levels', 'usage')
        record('queries', {k: queried[k] for k in keys}, {k: initial[k] for k in keys})

        def generate(label, source, quantity, accept=True):
            before = settled(client)
            identity = source['id']
            bm = mapping(before['inventory'])
            reply = use_once(client, index_of(before, identity))
            after = settled(client)
            am = mapping(after['inventory'])
            new = [c for c in after['inventory'] if c['id'] not in bm]
            action = after['actions'][-1]
            record(label+'.response', dict(kind=reply['kind'], responses=len(after['actions'])-len(before['actions']),
                target=action['target']), dict(kind='success' if accept else 'not_allowed', responses=1, target=identity))
            others = {k: v for k, v in bm.items() if k != identity}
            record(label+'.inventory', dict(others={k: v for k, v in am.items() if k in others},
                source_present=identity in am, source_removed=removed(after, identity),
                products=[{k: c[k] for k in PRODUCT} for c in new], distinct=len({c['id'] for c in new})==len(new),
                delta=after['count']-before['count']),
                dict(others=others, source_present=not accept, source_removed=accept,
                     products=[PRODUCT]*quantity if accept else [], distinct=True, delta=quantity-1 if accept else 0))
            rows = [r for r in after['rows'] if r['action'] == action['id']]
            effect = [i for i, r in enumerate(rows) if r['kind']=='effect_enter' and r['id']==identity]
            leave = [i for i, r in enumerate(rows) if r['kind']=='leave' and r['id']==identity]
            returned = [r for r in rows if r['kind']=='use_consumeable' and r['id']==identity]
            admission = [r for i, r in enumerate(rows) if r['kind']=='can_use_consumeable' and r['id']==identity
                         and (not effect or i < effect[0])]
            events = [e for e in after['events'] if e['action'] == action['id']]
            record(label+'.lifecycle', dict(effects=len(effect), leaves_first=bool(effect and leave and min(leave)<effect[0]),
                pure_admission=bool(admission) and all(r['buffer']==before['buffer'] and r['count']==before['count'] for r in admission),
                reserved=returned[0]['buffer'] if returned else None, buffer=after['buffer'], pending=after['pending_events'],
                deferred=any(e['delay']>0 and e['finished'] for e in events)),
                dict(effects=1 if accept else 0, leaves_first=accept, pure_admission=True,
                     reserved=quantity if accept else None, buffer=0, pending=0, deferred=accept))
            ledger = usage(before).copy()
            if accept:
                ledger[GEN] = ledger.get(GEN, 0)+1
            record(label+'.usage', usage(after), ledger)
            record(label+'.invariants', dict(capacity=after['capacity'], within=after['count']<=capacity,
                dollars=after['dollars'], levels=after['hand_levels']),
                dict(capacity=capacity, within=True, dollars=before['dollars'], levels=before['hand_levels']))
            retain(label, before, reply, after)
            return new

        def ordinary(label, identity, key):
            before = settled(client)
            reply = use_once(client, index_of(before, identity))
            after = settled(client)
            record(label+'.inventory', dict(kind=reply['kind'], inventory=mapping(after['inventory']),
                removed=removed(after, identity), capacity=after['capacity'], pending=after['pending_events']),
                dict(kind='success', inventory={k: v for k, v in mapping(before['inventory']).items() if k!=identity},
                     removed=True, capacity=capacity, pending=0))
            levels = before['hand_levels'].copy()
            money = before['dollars']
            if key=='c_mercury':
                levels['Pair'] += 1
            else:
                money += min(money, 20)
            ledger = usage(before).copy()
            ledger[key] = ledger.get(key, 0)+1
            record(label+'.effect', dict(levels=after['hand_levels'], money=after['dollars'], usage=usage(after),
                buffer_unchanged=after['buffer']==before['buffer']),
                dict(levels=levels, money=money, usage=ledger, buffer_unchanged=True))
            retain(label, before, reply, after)

        if scene=='recover':
            generate('refusal', sources[0], counts[0], False)
            ordinary('hermit', hermit, 'c_hermit')
        products = []
        for i, (source, quantity) in enumerate(zip(sources, counts)):
            created = generate('generate'+str(i), source, quantity)
            if i==0:
                products = created
        if scene!='one':
            needed = 2 if scene=='room' else 1
            if len(products)<needed or any(c['key']!='c_mercury' for c in products[:needed]):
                raise ProtocolError('Required real product-use prerequisite missing; no complete suite claim')
            for i in range(needed):
                ordinary('mercury'+str(i), products[i]['id'], 'c_mercury')
        if scene!='recover':
            ordinary('hermit', hermit, 'c_hermit')
        final = settled(client)
        record('sealed', dict(config=client.call('poc.bg2.config'), capacity=final['capacity'], pending=final['pending_events'],
            ordinary=all(not c['edition'] and not c['debuff'] for c in final['inventory'])),
            dict(config=expected_config, capacity=capacity, pending=0, ordinary=True))
