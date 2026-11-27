"""Three independent native pack flows, plus isolated core protocol checks."""
from poc.checks import check
from poc.rpc import ProtocolError
from scripts.audit import write
from tasks.pack_choice_commit.probe_v1.probe import ready
from tasks.pack_choice_commit.v1.private.scenario import unique_position
from .oracle import Ledger,REWARDS,expected

MODES={'full_full':((0,2),(1,0)),'partial_full':((1,),(0,2)),'skip_full':((),(2,1))}
NATIVE=('initial',)+tuple('p'+str(i)+'.'+name for i in (1,2) for name in ('open','first','close','identities','stable','ledger'))+('sell','followup','play','final','sealed')
REQUIRED=tuple('core.'+k for k in expected())+tuple(mode+'.'+key for mode in MODES for key in NATIVE)


def evaluate(session,checks):
    session.client.wait(lambda v:v['state']=='MENU')
    core=session.client.call('poc.pc2.core')
    for key,value in expected().items():check(checks,'core.'+key,core.get(key),value)
    for number,(mode,operations) in enumerate(MODES.items()):
        if number:session.restart()
        client=session.client;root=session.runtime.directory;trace=[];snapshots=[];owned=[];old_previews=set();oracle=Ledger()
        def retain(row):trace.append(row);write(root/'two-choice-task-v2.json',trace)
        def action(method,args=None):
            value=client.action(method,args);retain(dict(action=method,params=args,response=value));return value
        def snap(label,state='SHOP',frame=None):
            value=client.wait(lambda v:ready(v,state) and (frame is None or v['frame']>=frame),method='poc.pc2.observe',timeout=25)
            if not isinstance(value.get('ledger'),dict):raise ProtocolError('Missing public ledger observation')
            snapshots.append(value);retain(dict(label=label,observation=value));return value
        def record(label,value,wanted):check(checks,mode+'.'+label,value,wanted)
        client.wait(lambda v:v['state']=='MENU');action('start',{'deck':'RED','stake':'WHITE','seed':'PACK2TSK'})
        client.wait(lambda v:v['state']=='BLIND_SELECT');action('poc.pc2.prepare',{'stage':'deck'})
        action('select');client.wait(lambda v:v['state']=='SELECTING_HAND');action('play',{'cards':[0,1,2,3,4]})
        client.wait(lambda v:v['state']=='ROUND_EVAL');action('cash_out');client.wait(lambda v:v['state']=='SHOP')
        action('poc.pc2.prepare',{'stage':'shop'});s=snap('initial');packs=[c['id'] for c in s['packs']]
        record('initial',dict(packs=[(c['key'],c['cost']) for c in s['packs']],unique=len(set(packs)),owned=s['owned'],ledger=s['ledger']),
            dict(packs=[('p_pc2_choices',4)]*2,unique=2,owned=[],ledger=oracle.view()))
        for index,choices in enumerate(operations,1):
            prefix='p'+str(index);before=s;response=action('buy',{'pack':0});opened=snap(prefix+'.open','SMODS_BOOSTER_OPENED')
            previews=opened['preview'];ids=[c['id'] for c in previews];selected=[];steps=[];wanted_steps=[]
            sid=str(packs[index-1]);oracle.begin(sid)
            for c in previews:
                if c['key'] not in REWARDS:raise ProtocolError('Required signing preview unavailable')
                oracle.register(sid,str(c['id']),REWARDS[c['key']])
            record(prefix+'.open',dict(state=response['state'],debit=before['dollars']-opened['dollars'],choices=opened['choices'],
                keys=[c['key'] for c in previews],unique=len(set(ids)),fresh=not old_previews&set(ids),owned=[c['id'] for c in opened['owned']],ledger=opened['ledger']),
                dict(state='SMODS_BOOSTER_OPENED',debit=4,choices=2,keys=list(REWARDS),unique=3,fresh=True,owned=owned.copy(),ledger=oracle.view()))
            old_previews.update(ids);s=opened;reward=0
            if choices:
                c=previews[choices[0]];selected.append(c['id']);owned.append(c['id']);reward+=REWARDS[c['key']]
                response=action('pack',{'card':unique_position(s['preview'],identity=c['id'])})
                s=snap(prefix+'.first','SMODS_BOOSTER_OPENED');ticket='acquire:'+str(c['id'])
                oracle.commit(sid,str(c['id']),ticket);oracle.settle(ticket)
                steps.append(dict(state=response['state'],choices=s['choices'],preview=[c['id'] for c in s['preview']],owned=[c['id'] for c in s['owned']],money=s['dollars'],ledger=s['ledger']))
                wanted_steps.append(dict(state='SMODS_BOOSTER_OPENED',choices=1,preview=[x for x in ids if x not in selected],owned=owned.copy(),money=opened['dollars']+reward,ledger=oracle.view()))
            record(prefix+'.first',steps,wanted_steps)
            if len(choices)==2:
                c=previews[choices[1]];selected.append(c['id']);owned.append(c['id']);reward+=REWARDS[c['key']]
                response=action('pack',{'card':unique_position(s['preview'],identity=c['id'])})
                ticket='acquire:'+str(c['id']);oracle.commit(sid,str(c['id']),ticket);oracle.settle(ticket)
            else:response=action('pack',{'skip':True})
            oracle.close(sid);s=snap(prefix+'.closed');objects={c['id']:c for c in s['objects']}
            record(prefix+'.close',dict(state=response['state'],pack_open=s['pack_open'],owned=[c['id'] for c in s['owned']],money=s['dollars'],pending=s['pending_events']),
                dict(state='SHOP',pack_open=False,owned=owned.copy(),money=opened['dollars']+reward,pending=0))
            record(prefix+'.identities',dict(removed=sorted(i for i in ids if objects[i]['removed']),
                acquired=[r['id'] for r in s['rows'] if r['kind']=='add_to_deck' and r['id'] in ids],
                owned_keys=[c['key'] for c in s['owned'] if c['id'] in selected]),
                dict(removed=sorted(set(ids)-set(selected)),acquired=selected,owned_keys=[previews[i]['key'] for i in choices]))
            stable=snap(prefix+'.stable',frame=s['frame']+12)
            record(prefix+'.stable',dict(money=stable['dollars'],owned=stable['owned'],preview=stable['preview'],pending=stable['pending_events'],ledger=stable['ledger']),
                dict(money=s['dollars'],owned=s['owned'],preview=[],pending=0,ledger=s['ledger']))
            record(prefix+'.ledger',stable['ledger'],oracle.view());s=stable
        victim=s['owned'][0];before=s;response=action('sell',{'joker':0});owned=owned[1:];s=snap('sold')
        record('sell',dict(state=response['state'],money=s['dollars']-before['dollars'],owned=[c['id'] for c in s['owned']],
            removed=[c['removed'] for c in s['objects'] if c['id']==victim['id']],ledger=s['ledger']),
            dict(state='SHOP',money=victim['sell_cost'],owned=owned.copy(),removed=[True],ledger=oracle.view()))
        offer=s['offers'][0];before=s;action('buy',{'card':0});s=snap('followup');owned.append(offer['id'])
        record('followup',dict(debit=before['dollars']-s['dollars'],owned=[c['id'] for c in s['owned']],stock=s['offers'],ledger=s['ledger']),
            dict(debit=2,owned=owned.copy(),stock=[],ledger=oracle.view()))
        action('next_round');client.wait(lambda v:v['state']=='BLIND_SELECT');action('select');before=snap('deal','SELECTING_HAND')
        action('play',{'cards':[0]});s=snap('play','SELECTING_HAND')
        record('play',dict(chips=s['chips']-before['chips'],hands=s['hands']-before['hands'],money=s['dollars']-before['dollars'],owned=[c['id'] for c in s['owned']],ledger=s['ledger']),
            dict(chips=35,hands=1,money=0,owned=owned.copy(),ledger=oracle.view()))
        final=snap('final','SELECTING_HAND',frame=s['frame']+12)
        record('final',dict(money=final['dollars'],ledger=final['ledger'],owned=final['owned'],pending=final['pending_events']),
            dict(money=s['dollars'],ledger=oracle.view(),owned=s['owned'],pending=0))
        record('sealed',all(v['stage']==2 and all(a['response_calls']==1 for a in v['actions']) for v in snapshots),True)
