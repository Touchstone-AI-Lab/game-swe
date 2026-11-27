"""Mixed physical batches and a later independent cut, driven only by public actions."""
from poc.checks import check
from poc.rpc import ProtocolError, RemoteError
from scripts.audit import write
from tasks.bounded_generator.observe_v1 import settled
from tasks.bounded_generator.protocol_v1 import not_allowed
from tasks.bounded_generator.v1.private.scenario import usage
from tasks.deck_removal_consistency.v1.private.scenario import ready, ids, mapping, semantic
from tasks.deck_removal_consistency.probe_v2.protocol import empty_selection_rejection

GEN = 'c_dr2_clean_cut'
SCENES = {'single': [0], 'four': [0, 2, 5, 7], 'repeat': [1, 4, 7]}
CUT_CASES = ('response','consumption','targets','registered','areas','unchanged','lifecycle','stable')
REQUIRED = tuple(scene+'.'+key for scene in SCENES for key in
    ('initial','refusal.empty','refusal.five') + tuple('first.'+k for k in CUT_CASES) +
    ('refill','next_blind') + (tuple('second.'+k for k in CUT_CASES) if scene=='repeat' else ()) +
    ('full_pool','followup','sealed'))


def evaluate(session, checks):
    for number, (scene, positions) in enumerate(SCENES.items()):
        if number:
            session.restart()
        client = session.client
        root = session.runtime.directory
        trace, snapshots = [], []
        all_targets, used_sources = set(), []

        def record(name, actual, expected):
            check(checks, scene+'.'+name, actual, expected)

        def retain(row):
            trace.append(row)
            write(root/'physical-batch-evidence-v2.json', trace)

        def action(method, params=None):
            response = client.action(method, params)
            retain(dict(action=method, params=params, response=response))
            return response

        def snap(label):
            state = client.wait(ready, method='poc.dr2.observe', timeout=10)
            snapshots.append(state)
            retain(dict(label=label, observation=state))
            return state

        client.wait(lambda s: s['state']=='MENU')
        action('start', {'deck':'RED','stake':'WHITE','seed':'BATCHTASK2'})
        client.wait(lambda s: s['state']=='BLIND_SELECT')
        action('poc.dr2.prepare', {'stage':'deck','mode':scene})
        action('select')
        settled(client)
        action('poc.dr2.prepare', {'stage':'hand','mode':scene})
        before = snap('initial')
        life = settled(client)
        original = mapping(before['registered'])
        quantity = 2 if scene=='repeat' else 1
        record('initial', dict(count=len(original), hand=len(before['hand']), limit=before['deck_limit'],
            faces=[(c['rank'],c['suit']) for c in before['hand']],
            ordinary=all(c['center']=='c_base' and not c['removed'] for c in original.values()),
            inventory=[c['key'] for c in life['inventory']], capacity=life['capacity'], prepared=before['prepared']),
            dict(count=16, hand=8, limit=16, faces=[(2,'Hearts'),(3,'Diamonds'),(4,'Spades'),(2,'Hearts'),
                 (2,'Hearts'),(5,'Clubs'),(2,'Hearts'),(3,'Diamonds')], ordinary=True,
                 inventory=[GEN]*quantity+['c_pluto'], capacity=quantity+1, prepared=True))

        for label, invalid in (('empty', []), ('five', [0,1,2,3,4])):
            previous = snap('before_refusal_'+label)
            old_life = settled(client)
            params = {'consumable':0,'cards':invalid}
            kind = 'unexpected_success'
            try:
                response = client.action('use', params)
            except RemoteError as error:
                if not empty_selection_rejection(error, client.request_id, params):
                    raise
                kind, response = 'bad_request', error.response
            after = snap('refusal_'+label)
            current = settled(client)
            retain(dict(action='use',params=params,response=response))
            resource_keys = ('inventory','capacity','buffer','dollars','hand_levels','usage')
            record('refusal.'+label, dict(kind=kind, state=semantic(after),
                   resources={k:current[k] for k in resource_keys}),
                   dict(kind='bad_request', state=semantic(previous), resources={k:old_life[k] for k in resource_keys}))

        def cut(label, selected):
            previous = snap('before_'+label)
            old_life = settled(client)
            targets = [previous['hand'][i]['id'] for i in selected]
            fresh_targets = not all_targets.intersection(targets)
            all_targets.update(targets)
            survivors = sorted(set(original)-all_targets)
            source = old_life['inventory'][0]
            fresh_source = source['id'] not in used_sources
            used_sources.append(source['id'])
            params = {'consumable':0,'cards':selected}
            kind = 'success'
            try:
                response = client.action('use', params)
            except RemoteError as error:
                if not not_allowed(error, client.request_id, params):
                    raise
                kind, response = 'not_allowed', error.response
            retain(dict(action='use',params=params,response=response))
            current = settled(client)
            after = snap(label)
            record(label+'.response', dict(kind=kind, state=response.get('state') if kind=='success' else None,
                   fresh_source=fresh_source), dict(kind='success',state='SELECTING_HAND',fresh_source=True))
            source_rows = [c for c in current['objects'] if c['id']==source['id']]
            if len(source_rows)!=1:
                raise ProtocolError('Consumed source identity missing from passive observation')
            ledger = usage(old_life).copy()
            ledger[GEN] = ledger.get(GEN,0)+1
            record(label+'.consumption', dict(inventory=current['inventory'],source_removed=source_rows[0]['removed'],
                money=current['dollars'],levels=current['hand_levels'],usage=usage(current),capacity=current['capacity']),
                dict(inventory=old_life['inventory'][1:],source_removed=True,money=old_life['dollars'],
                     levels=old_life['hand_levels'],usage=ledger,capacity=old_life['capacity']))
            objects = mapping(after['objects'])
            actual = mapping(after['registered'])
            record(label+'.targets', dict(removed={i:objects[i]['removed'] for i in all_targets},fresh=fresh_targets),
                   dict(removed={i:True for i in all_targets},fresh=True))
            record(label+'.registered', dict(ids=ids(after['registered']),limit=after['deck_limit']),
                   dict(ids=survivors,limit=len(survivors)))
            record(label+'.areas', ids(sum((after[k] for k in ('hand','deck','discard','play')),[])), survivors)
            record(label+'.unchanged', {i:actual.get(i) for i in survivors}, {i:original[i] for i in survivors})
            calls = current['actions'][len(old_life['actions']):]
            record(label+'.lifecycle', dict(actions=len(calls),target=[a['target'] for a in calls],
                events=bool(current['events']),pending=current['pending_events'],buffer=current['buffer'],
                errors=current['observer_errors'],dropped=current['dropped']),
                dict(actions=1,target=[source['id']],events=True,pending=0,buffer=0,errors=0,dropped=0))
            stable = client.wait(lambda s: ready(s) and s['frame']>=after['frame']+12,
                                 method='poc.dr2.observe',timeout=5)
            snapshots.append(stable)
            retain(dict(label=label+'_stable',observation=stable))
            record(label+'.stable', semantic(stable), semantic(after))
            return after, survivors

        after, survivors = cut('first', positions)
        game = client.call('gamestate')
        rank = after['hand'][0]['rank']
        action('play', {'cards':[0]})
        settled(client)
        refill = snap('refill')
        next_game = client.call('gamestate')
        record('refill', dict(hand=len(refill['hand']),ids=ids(refill['registered']),
            hands=next_game['round']['hands_played']-game['round']['hands_played'],
            chips=next_game['round']['chips']-game['round']['chips']),
            dict(hand=8,ids=survivors,hands=1,chips=5+rank))
        winning = [i for i,c in enumerate(refill['hand']) if c['rank']==2 and c['suit']=='Hearts'][:5]
        if len(winning)!=5:
            raise ProtocolError('Required real winning hand unavailable; no complete claim')
        action('play', {'cards':winning})
        client.wait(lambda s: s['state']=='ROUND_EVAL')
        action('cash_out')
        client.wait(lambda s: s['state']=='SHOP')
        action('next_round')
        client.wait(lambda s: s['state']=='BLIND_SELECT')
        action('select')
        settled(client)
        deal = snap('next_blind')
        record('next_blind', dict(hand=len(deal['hand']),ids=ids(deal['registered']),limit=deal['deck_limit'],
               absent=not all_targets.intersection(ids(deal['hand']))),
               dict(hand=8,ids=survivors,limit=len(survivors),absent=True))
        if scene=='repeat':
            deal, survivors = cut('second', [3])
        reachable = set(ids(deal['hand']))
        discards = (4,3) if scene=='single' else (5,) if scene=='repeat' else (4,)
        for count in discards:
            action('discard', {'cards':list(range(count))})
            settled(client)
            pool = snap('draw_pool')
            reachable.update(ids(pool['hand']))
        record('full_pool', dict(reachable=sorted(reachable),deck=len(pool['deck']),ids=ids(pool['registered']),
               absent=not all_targets.intersection(reachable),properties=mapping(pool['registered'])),
               dict(reachable=survivors,deck=0,ids=survivors,absent=True,properties={i:original[i] for i in survivors}))
        matching = [i for i,c in enumerate(pool['hand']) if c['rank']==2 and c['suit']=='Hearts']
        if not matching:
            raise ProtocolError('Required native H2 follow-up object missing')
        game = client.call('gamestate')
        action('play', {'cards':[matching[0]]})
        settled(client)
        next_game = client.call('gamestate')
        record('followup', dict(hands=next_game['round']['hands_played']-game['round']['hands_played'],
               chips=next_game['round']['chips']-game['round']['chips']),dict(hands=1,chips=7))
        record('sealed', all(s['prepared'] is True for s in snapshots), True)
