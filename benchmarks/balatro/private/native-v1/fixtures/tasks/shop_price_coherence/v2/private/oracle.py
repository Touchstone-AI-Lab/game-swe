"""Independent integer arithmetic and public-protocol expectations, no candidate fields."""


def price(base, flat=0, ratio=0, coupon=0, eligible=True):
    return max(1, ((base-flat-2*coupon)*2**ratio)//3**ratio) if eligible else base


def view(version, *sources):
    return {'version':version,'sources':[dict(id=i,kind=k,available=a) for i,k,a in sorted(sources)]}


def receipt(debit, version):return dict(ok=True,debit=debit,version=version)
def error(code):return dict(ok=False,code=code)


def protocol_expected():
    initial=view(1,('owner','coupon',True));spent=view(2,('owner','coupon',False))
    flat=view(1,('owner','flat',True));ok=receipt(8,2)
    values=[]
    for f in range(3):
        for r in range(3):
            for c in range(3):
                for b in range(1,26):values.extend((price(b,f,r,c),b))
    return {
        'formula':values,
        'ownership':view(4,('a','flat',True),('c','coupon',True)),
        'pure_query':dict(before=initial,after=initial,prices=[8]*4),
        'view_alias':dict(view=initial,price=8),
        'versions':dict(receipt=receipt(6,3),view=view(3,('owner','coupon',False),('other','coupon',False)),next_price=10),
        'noneligible':dict(receipt=receipt(3,2),view=view(2,('owner','coupon',True),('flat','flat',True)),next_price=5),
        'stale':dict(result=error('STALE_QUOTE'),before=flat,after=flat),
        'funds_atomic':dict(refused=error('INSUFFICIENT_FUNDS'),before=initial,after=initial,retry=ok),
        'quote_atomic':dict(refused=error('QUOTE_MISMATCH'),before=initial,after=initial,retry=ok),
        'dedup':dict(first=ok,repeated=ok,conflict=error('TRANSACTION_CONFLICT'),other=error('OFFER_COMMITTED'),
                     view=view(3,('owner','coupon',False),('flat','flat',True))),
        'receipt_alias':dict(repeated=ok,view=spent),
        'invalid_atomic':dict(results=[error(c) for c in ('INVALID','INVALID','OWNER_MISSING','INVALID','INVALID','INVALID','INVALID','OWNER_EXISTS')],view=flat),
        'order':[3]*4,
    }
