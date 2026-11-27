"""Two fresh scenes; complete observations are required even for a behavior rejection."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.bounded_generator.observe_v1 import settled,index_of
from tasks.bounded_generator.protocol_v1 import use_once

GEN='c_bgen_generator'
PRODUCT={'key':'c_mercury','set':'Planet','hand_type':'Pair','removed':False,
         'in_inventory':True,'edition':False,'debuff':False}


def gen_cases(prefix):return tuple(prefix+'.'+s for s in ('response','inventory','lifecycle','usage','invariants'))
def native_cases(prefix):return (prefix+'.inventory',prefix+'.effect')
REQUIRED=(('room.initial',)+gen_cases('room.first')+gen_cases('room.second')+
          native_cases('room.mercury1')+native_cases('room.mercury2')+native_cases('room.hermit')+('room.final',)+
          ('edge.initial',)+gen_cases('edge.refusal')+native_cases('edge.hermit')+gen_cases('edge.retry_after_space')+('edge.final',))


def usage(s):
    value=s['usage']
    if value==[]:return {}
    if not isinstance(value,dict) or any(type(n) is not int for n in value.values()):
        raise ProtocolError('Malformed native usage ledger')
    return value


def mapping(cards):
    result={c['id']:c for c in cards}
    if len(result)!=len(cards):raise ProtocolError('Duplicate object identity in observation')
    return result


def removed(s,identity):
    values=[c['removed'] for c in s['objects'] if c['id']==identity]
    if len(values)!=1 or type(values[0]) is not bool:raise ProtocolError('Missing object destruction observation')
    return values[0]


def evaluate(session,checks):
    root=session.runtime.directory;records=[];all_seen=[]
    previous=None
    for scene in ('room','edge'):
        if previous is not None:session.restart()
        client=session.client
        fresh=(previous is None or (
            previous.process.returncode==0 and previous.process.pid!=session.runtime.process.pid
            and previous.nonce!=session.runtime.nonce
            and previous.metadata['observed_runtime']['save_dir']!=session.runtime.metadata['observed_runtime']['save_dir']))
        client.wait(lambda s:s['state']=='MENU')
        client.action('start',{'deck':'RED','stake':'WHITE','seed':'BGROOM1' if scene=='room' else 'BGEDGE1'})
        client.wait(lambda s:s['state']=='BLIND_SELECT')
        prep=client.action('poc.bg.prepare',{'mode':scene})
        client.action('select');initial=settled(client)
        seen=[initial];record={'scene':scene,'run_id':session.runtime.run_id,'initial':initial,'operations':[]}
        records.append(record)
        def retain(step):
            record['operations'].append(step);seen.append(step['after'])
            write(root/'bounded-evidence.json',records)
        capacity=5 if scene=='room' else 2
        expected_keys=[GEN,GEN,'c_hermit'] if scene=='room' else [GEN,'c_hermit']
        check(checks,scene+'.initial',{'keys':[c['key'] for c in initial['inventory']],
            'capacity':initial['capacity'],'buffer':initial['buffer'],'dollars':initial['dollars'],
            'all_levels_one':all(v==1 for v in initial['hand_levels'].values()),'usage':usage(initial),
            'fresh_process':fresh,'fixture_calls':prep.get('fixture_calls')},
            {'keys':expected_keys,'capacity':capacity,'buffer':0,'dollars':10,'all_levels_one':True,
             'usage':{},'fresh_process':True,'fixture_calls':1})
        first=initial['inventory'][0]['id'];hermit=initial['inventory'][-1]['id']

        def generator(case,identity,accept=True):
            before=settled(client);bm=mapping(before['inventory'])
            outcome=use_once(client,index_of(before,identity));after=settled(client)
            am=mapping(after['inventory']);new=[c for c in after['inventory'] if c['id'] not in bm]
            action=after['actions'][-1]
            response_count=len(after['actions'])-len(before['actions'])
            check(checks,case+'.response',{'kind':outcome['kind'],'response_count':response_count,'target':action['target']},
                  {'kind':'success' if accept else 'not_allowed','response_count':1,'target':identity})
            expected_others={i:c for i,c in bm.items() if i!=identity}
            check(checks,case+'.inventory',{
                'unchanged_others':{i:c for i,c in am.items() if i in expected_others},
                'source_present':identity in am,'source_destroyed':removed(after,identity),
                'products':[{k:c[k] for k in PRODUCT} for c in new],
                'new_ids_distinct':len({c['id'] for c in new})==len(new),
                'count_delta':after['count']-before['count']},
                {'unchanged_others':expected_others,'source_present':not accept,'source_destroyed':accept,
                 'products':[PRODUCT]*2 if accept else [],'new_ids_distinct':True,'count_delta':1 if accept else 0})
            rows=[r for r in after['rows'] if r['action']==action['id']]
            effect=[(i,r) for i,r in enumerate(rows) if r['kind']=='effect_enter' and r['id']==identity]
            leave=[i for i,r in enumerate(rows) if r['kind']=='leave' and r['id']==identity]
            returns=[r for r in rows if r['kind']=='use_consumeable' and r['id']==identity]
            events=[e for e in after['events'] if e['action']==action['id']]
            check(checks,case+'.lifecycle',{
                'effect_count':len(effect),'source_leaves_before_effect':bool(effect and leave and min(leave)<effect[0][0]),
                'buffer_when_effect_returns':returns[0]['buffer'] if returns else None,
                'buffer_after':after['buffer'],'pending_events':after['pending_events'],
                'has_deferred_events':any(e['delay']>0 and e['finished'] for e in events)},
                {'effect_count':1 if accept else 0,'source_leaves_before_effect':accept,
                 'buffer_when_effect_returns':before['buffer']+2 if accept else None,
                 'buffer_after':0,'pending_events':0,'has_deferred_events':accept})
            expected_usage=usage(before).copy()
            if accept:expected_usage[GEN]=expected_usage.get(GEN,0)+1
            check(checks,case+'.usage',usage(after),expected_usage)
            check(checks,case+'.invariants',{'capacity':after['capacity'],'within_capacity':after['count']<=capacity,
                  'dollars':after['dollars'],'levels':after['hand_levels']},
                  {'capacity':capacity,'within_capacity':True,'dollars':before['dollars'],'levels':before['hand_levels']})
            retain({'case':case,'before':before,'outcome':outcome,'after':after})
            return new

        def native_use(case,identity,key):
            before=settled(client);bm=mapping(before['inventory']);index=index_of(before,identity)
            outcome=use_once(client,index)
            if outcome['kind']!='success':raise ProtocolError('Required generated/unrelated object could not be used')
            after=settled(client)
            check(checks,case+'.inventory',{'inventory':mapping(after['inventory']),'destroyed':removed(after,identity),
                'capacity':after['capacity'],'pending_events':after['pending_events']},
                {'inventory':{i:c for i,c in bm.items() if i!=identity},'destroyed':True,'capacity':capacity,'pending_events':0})
            levels=before['hand_levels'].copy();money=before['dollars']
            if key=='c_mercury':levels['Pair']+=1
            else:money+=min(money,20)
            ledger=usage(before).copy();ledger[key]=ledger.get(key,0)+1
            check(checks,case+'.effect',{'levels':after['hand_levels'],'dollars':after['dollars'],
                'usage':usage(after),'buffer_unchanged':after['buffer']==before['buffer']},
                {'levels':levels,'dollars':money,'usage':ledger,'buffer_unchanged':True})
            retain({'case':case,'before':before,'outcome':outcome,'after':after})

        if scene=='room':
            second=initial['inventory'][1]['id']
            products=generator('room.first',first)
            if len(products)<2 or any(c['set']!='Planet' for c in products[:2]):
                raise ProtocolError('Cannot perform both required real product uses; no complete suite claim')
            generator('room.second',second)
            native_use('room.mercury1',products[0]['id'],'c_mercury')
            native_use('room.mercury2',products[1]['id'],'c_mercury')
            native_use('room.hermit',hermit,'c_hermit')
        else:
            generator('edge.refusal',first,False)
            native_use('edge.hermit',hermit,'c_hermit')
            generator('edge.retry_after_space',first)
        final=settled(client);seen.append(final);record['final']=final
        check(checks,scene+'.final',{'keys':sorted(c['key'] for c in final['inventory']),
            'buffer':final['buffer'],'count':final['count'],'capacity_constant':all(s['capacity']==capacity for s in seen),
            'all_ordinary':all(not c['edition'] and not c['debuff'] for s in seen for c in s['inventory']),
            'actions':len(final['actions']),'pending_events':final['pending_events']},
            {'keys':['c_mercury','c_mercury'],'buffer':0,'count':2,'capacity_constant':True,'all_ordinary':True,
             'actions':5 if scene=='room' else 3,'pending_events':0})
        write(root/'bounded-evidence.json',records)
        previous=session.runtime
