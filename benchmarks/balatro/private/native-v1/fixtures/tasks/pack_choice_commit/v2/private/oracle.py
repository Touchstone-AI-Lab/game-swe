"""Independent scalar protocol model and native reward expectations."""
from copy import deepcopy
import re

REWARDS={'j_pc2_copper':3,'j_pc2_silver':5,'j_pc2_gold':7}
def error(code):return dict(ok=False,code=code)
def valid(value):return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}',value) is not None


class Ledger:
    def __init__(self):self.sessions={};self.previews={};self.tickets={};self.paid=0
    def begin(self,sid):
        if not valid(sid):return error('INVALID')
        if sid in self.sessions:return dict(ok=True,created=False)
        self.sessions[sid]=dict(id=sid,closed=False,remaining=2,previews=[]);return dict(ok=True,created=True)
    def register(self,sid,pid,reward):
        if not valid(sid) or not valid(pid) or type(reward) is not int or reward not in (3,5,7):return error('INVALID')
        if sid not in self.sessions:return error('SESSION_MISSING')
        if pid in self.previews:
            p=self.previews[pid]
            return dict(ok=True,created=False) if p['session']==sid and p['reward']==reward else error('PREVIEW_CONFLICT')
        s=self.sessions[sid]
        if s['closed'] or s['remaining']<2:return error('REGISTRATION_CLOSED')
        if len(s['previews'])==3:return error('PREVIEW_LIMIT')
        self.previews[pid]=dict(id=pid,session=sid,reward=reward,selected=False);s['previews'].append(pid)
        return dict(ok=True,created=True)
    def commit(self,sid,pid,cid):
        if not all(valid(x) for x in (sid,pid,cid)):return error('INVALID')
        if cid in self.tickets:
            t=self.tickets[cid]
            return dict(ok=True,new=False,ticket=cid,amount=t['reward']) if (t['session'],t['preview'])==(sid,pid) else error('COMMIT_CONFLICT')
        if sid not in self.sessions:return error('SESSION_MISSING')
        s=self.sessions[sid]
        if s['closed']:return error('SESSION_CLOSED')
        if len(s['previews'])!=3:return error('PREVIEWS_INCOMPLETE')
        if pid not in s['previews']:return error('PREVIEW_MISSING')
        p=self.previews[pid]
        if p['selected']:return error('PREVIEW_COMMITTED')
        if not s['remaining']:return error('CHOICES_EXHAUSTED')
        p['selected']=True;s['remaining']-=1
        self.tickets[cid]=dict(id=cid,session=sid,preview=pid,reward=p['reward'],settled=False)
        return dict(ok=True,new=True,ticket=cid,amount=p['reward'])
    def close(self,sid):
        if not valid(sid):return error('INVALID')
        if sid not in self.sessions:return error('SESSION_MISSING')
        self.sessions[sid]['closed']=True;return dict(ok=True)
    def settle(self,cid):
        if not valid(cid):return error('INVALID')
        if cid not in self.tickets:return error('TICKET_MISSING')
        t=self.tickets[cid]
        if t['settled']:return dict(ok=True,amount=0,already=True)
        t['settled']=True;self.paid+=t['reward'];return dict(ok=True,amount=t['reward'],already=False)
    def view(self):
        sessions=[]
        for sid,s in sorted(self.sessions.items()):
            previews=[{k:self.previews[pid][k] for k in ('id','reward','selected')} for pid in sorted(s['previews'])]
            sessions.append(dict(id=sid,closed=s['closed'],remaining=s['remaining'],previews=previews))
        return dict(sessions=sessions,tickets=[deepcopy(t) for _,t in sorted(self.tickets.items())],paid=self.paid)


def full(s,sid='s'):
    s.begin(sid)
    for name,reward in [('a',3),('b',5),('c',7)]:s.register(sid,sid+name,reward)
    return s


def expected():
    out={};s=full(Ledger());before=s.view()
    out['pure']=dict(before=before,again=s.begin('s'),duplicate=s.register('s','sa',3),after=s.view(),other=Ledger().view())
    first=s.commit('s','sb','t1');second=s.commit('s','sc','t2');s.close('s')
    out['two_choices']=dict(first=first,second=second,pending=s.view(),payments=[s.settle('t2'),s.settle('t1')],view=s.view())
    s=full(Ledger());s.commit('s','sb','t');s.close('s');out['close_pending']=dict(before=s.view(),close=s.close('s'),payment=s.settle('t'),repeated=s.settle('t'),view=s.view())
    s=full(Ledger());s.close('s');out['skip']=s.view()
    full(s,'u');s.commit('u','ua','t');s.settle('t');out['next_session']=s.view()
    s=full(Ledger());first=s.commit('s','sa','t');s.settle('t');s.close('s')
    out['commit_replay']=dict(first=first,again=s.commit('s','sa','t'),conflict=s.commit('s','sb','t'),view=s.view())
    s=full(Ledger());s.commit('s','sa','t');before=s.view()
    out['selected_atomic']=dict(result=s.commit('s','sa','new'),before=before,after=s.view(),reuse=s.commit('s','sb','new'),view=s.view())
    s=full(Ledger());results=[s.register('s','extra',3),s.register('s','sa',5),s.commit('s','absent','x')]
    s.commit('s','sa','a');s.commit('s','sb','b');results+=[s.commit('s','sc','x'),s.register('s','extra',3)]
    out['limits']=dict(results=results,view=s.view())
    s=Ledger();s.begin('s');s.register('s','sa',3);before=s.view();bad=s.commit('s','sa','t');s.register('s','sb',5);s.register('s','sc',7)
    out['incomplete']=dict(before=before,result=bad,reuse=s.commit('s','sa','t'),view=s.view())
    s=full(Ledger());out['invalid']=dict(results=[error('INVALID')]*4+[error('SESSION_MISSING'),error('TICKET_MISSING')],view=s.view())
    s.commit('s','sa','t');out['view_alias']=s.view();out['receipt_alias']=dict(replay=s.commit('s','sa','t'),view=s.view())
    s=full(Ledger());s.close('s');out['closed']=dict(commit=s.commit('s','sa','t'),register=s.register('s','extra',3),begin=s.begin('s'),view=s.view())
    s=full(Ledger());full(s,'u');s.commit('s','sa','a');s.commit('u','uc','c');s.close('u');s.settle('a');s.settle('c')
    out['interleave']=dict(conflict=s.register('u','sa',3),view=s.view())
    return out
