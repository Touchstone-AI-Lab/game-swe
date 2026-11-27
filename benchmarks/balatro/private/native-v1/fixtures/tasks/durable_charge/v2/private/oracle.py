"""Independent Python event ledger used only to derive public protocol expectations."""
from copy import deepcopy


def event(id,kind,owner='a'):return dict(id=id,kind=kind,owner=owner)
def error(code):return dict(ok=False,code=code)


class Ledger:
    def __init__(self):self.events=[];self.owners={};self.retired=set();self.receipts={}
    def apply(self,id,kind,owner='a'):
        e=event(id,kind,owner)
        if kind not in ('add','remove','discard','consume'):return error('INVALID')
        if id in self.receipts:
            old,result=self.receipts[id]
            return deepcopy(result) if old==e else error('EVENT_CONFLICT')
        if kind=='add':
            if owner in self.owners:return error('OWNER_EXISTS')
            if owner in self.retired:return error('OWNER_RETIRED')
        elif owner not in self.owners:return error('OWNER_MISSING')
        if len(self.events)>=4096:return error('LIMIT')
        charge=min(6,self.owners[owner]+2) if kind=='discard' else 0
        if kind=='remove':del self.owners[owner];self.retired.add(owner)
        else:self.owners[owner]=charge
        self.events.append(e)
        result=dict(ok=True,seq=len(self.events),charge=charge,active=kind!='remove')
        self.receipts[id]=(e,deepcopy(result));return result
    def view(self):return dict(seq=len(self.events),owners=[dict(id=k,charge=v) for k,v in sorted(self.owners.items())])
    def snapshot(self):return dict(version=1,events=deepcopy(self.events))


def initial():
    s=Ledger();s.apply('a','add');s.apply('d','discard');return s


def expected():
    out={};s=initial();s.apply('b','add','b');out['ownership']=dict(view=s.view(),other=Ledger().view())
    s=initial();first=s.apply('d','discard');s.apply('c','consume')
    out['duplicate']=dict(first=first,again=s.apply('d','discard'),consumed=s.apply('c','consume'),view=s.view())
    s=initial();out['conflict']=dict(result=error('EVENT_CONFLICT'),before=s.view(),after=s.view())
    results=[error(c) for c in ('INVALID','INVALID','OWNER_MISSING','OWNER_EXISTS')];results.append(s.apply('x','discard'))
    out['invalid_atomic']=dict(results=results,view=s.view())
    s=initial();removed=s.apply('r','remove');out['retired']=dict(removed=removed,replay=s.apply('a','add'),again=s.apply('new','add'),missing=s.apply('no','discard'),view=s.view())
    s=Ledger();s.apply('a','add');s.apply('b','add','b')
    for i in range(1,5):s.apply('a'+str(i),'discard');s.apply('b'+str(i),'discard','b')
    s.apply('consume','consume');out['cap_interleave']=[s.view(),s.view()]
    s=initial();out['snapshot_alias']=dict(snapshot=s.snapshot(),view=s.view());out['view_alias']=s.view()
    out['receipt_alias']=dict(receipt=s.apply('d','discard'),view=s.view())
    one=Ledger();one.apply('a','add');out['input_alias']=dict(snapshot=one.snapshot(),replay=one.apply('a','add'),view=one.view())
    out['restore_input']=dict(result=dict(ok=True),view=s.view(),snapshot=s.snapshot())
    s.apply('c','consume');s.apply('b','add','b');out['zero_restore']=dict(view=s.view(),replay=s.apply('c','consume'),snapshot=s.snapshot())
    s=initial();s.apply('c','consume');s.apply('r','remove');out['restored_history']=dict(old=s.apply('d','discard'),conflict=s.apply('d','consume'),retired=s.apply('new','add'),view=s.view())
    s=initial();out['restore_atomic']=dict(result=error('SNAPSHOT_INVALID'),before=s.snapshot(),after=s.snapshot(),view=s.view(),receipt=s.apply('d','discard'))
    out['snapshot_validation']=dict(results=[error(c) for c in ('UNSUPPORTED_VERSION',)+('SNAPSHOT_INVALID',)*4],view=s.view())
    out['empty_restore']=dict(result=dict(ok=True),view=Ledger().view())
    s=Ledger();s.apply('a','add')
    for i in range(2,4097):s.apply('d'+str(i),'discard')
    out['limit']=dict(replay=s.apply('d2','discard'),limit=s.apply('overflow','consume'),view=s.view())
    return out
