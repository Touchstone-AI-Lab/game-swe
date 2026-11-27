from __future__ import annotations
import time
from poc.rpc import ProtocolError

REQUIRED = ('initial','discard','r1.high','r1.pair','r1.end','r1.context','r1.shop',
            'r2.entry','r2.pair','r2.end','r2.context','r2.shop','r3.entry','r3.high',
            'r3.end','r3.context','r3.shop','configuration')


def evaluate(client, checks):
    observations=[]
    def check(case,actual,expected):
        checks.append({'id':case,'observed':actual,'expected':expected,'passed':actual==expected})
    def state(name):
        return client.wait(lambda s:s['state']==name,timeout=35)
    def observe():
        s=client.call('poc.observe')
        for key in ('growth','frame','round','chips','hand_count','hand_limit','suit_count','joker_count','high_level','pair_level','four_level'):
            if type(s.get(key)) not in (int,float):raise ProtocolError('Missing numeric observation '+key)
        for key in ('plain','joker_debuff','joker_edition'):
            if type(s.get(key)) is not bool:raise ProtocolError('Missing boolean '+key)
        if not isinstance(s.get('events'),list):raise ProtocolError('Missing events')
        observations.append(s);return s
    def play(case,cards,expected_chips,growth,end=False):
        before=client.call('gamestate')
        client.action('play',{'cards':list(range(cards))})
        after=state('ROUND_EVAL' if end else 'SELECTING_HAND')
        s=observe()
        check(case,{'chips':s['chips'],'growth':s['growth'],'hand_delta':after['round']['hands_played']-before['round']['hands_played']},
              {'chips':expected_chips,'growth':growth,'hand_delta':1})
        return s
    def end_context(s,round_number):
        main=[e for e in s['events'] if e.get('round')==round_number and e.get('end_of_round') and e.get('main_eval') and not e.get('individual') and not e.get('repetition')]
        check(f'r{round_number}.context',{'count':len(main),'held':[e['held'] for e in main]}, {'count':1,'held':[2]})
    def shop(round_number,growth):
        client.action('cash_out');state('SHOP')
        first=observe(); values=[first['growth']]; start=first['frame'];deadline=time.monotonic()+5
        while len(values)<3:
            if time.monotonic()>deadline:raise ProtocolError('No frame progress')
            s=observe()
            if s['frame']>=start+10:values.append(s['growth']);start=s['frame']
            time.sleep(.05)
        check(f'r{round_number}.shop',values,[growth]*3)
    state('MENU')
    client.action('start',{'deck':'RED','stake':'WHITE','seed':'POC2026A'})
    state('BLIND_SELECT'); client.action('poc.prepare')
    check('initial',observe()['growth'],0)
    client.action('select');before=state('SELECTING_HAND')
    client.action('discard',{'cards':[0]});after=state('SELECTING_HAND')
    check('discard',{'growth':observe()['growth'],'count':after['round']['discards_used']-before['round']['discards_used']},{'growth':0,'count':1})
    play('r1.high',1,13,0);play('r1.pair',2,65,0)
    end_context(play('r1.end',4,709,2,True),1);shop(1,2)
    client.action('next_round');state('BLIND_SELECT');client.action('select');state('SELECTING_HAND')
    check('r2.entry',observe()['growth'],2)
    play('r2.pair',2,104,2);end_context(play('r2.end',4,932,4,True),2);shop(2,4)
    client.action('next_round');state('BLIND_SELECT');client.action('select');state('SELECTING_HAND')
    s=observe();check('r3.entry',{'growth':s['growth'],'blind':s['blind_key']},{'growth':4,'blind':'bl_ox'})
    play('r3.high',1,65,4);end_context(play('r3.end',4,1077,6,True),3);shop(3,6)
    expected={'joker_key':'j_poc_growth','joker_count':1,'joker_debuff':False,'joker_edition':False,'plain':True,'suit_count':4,'hand_limit':6,'high_level':1,'pair_level':1,'four_level':1}
    invalid=[{k:s.get(k) for k in expected} for s in observations if any(s.get(k)!=v for k,v in expected.items())]
    check('configuration',invalid,[])
