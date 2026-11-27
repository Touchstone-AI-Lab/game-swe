local R={}
function R.copy(v)if type(v)~='table'then return v end;local t={};for k,x in pairs(v)do t[k]=R.copy(x)end;return t end
function R.id(v)return type(v)=='string' and #v>0 and #v<=96 and v:match('^[%w_.:-]+$')~=nil end
function R.empty()return {sessions={},previews={},tickets={},paid=0}end
local function error(code)return {ok=false,code=code},false end
function R.step(d,kind,a)
    local session,preview,commit=a[1],a[2],a[3]
    if not R.id(session)then return error('INVALID')end
    if kind=='register' and (not R.id(preview) or (commit~=3 and commit~=5 and commit~=7))then return error('INVALID')end
    if kind=='commit' and (not R.id(preview) or not R.id(commit))then return error('INVALID')end
    if kind=='settle'then
        local ticket=d.tickets[session];if not ticket then return error('TICKET_MISSING')end
        if ticket.settled then return {ok=true,amount=0,already=true},false end
        ticket.settled=true;d.paid=d.paid+ticket.reward
        return {ok=true,amount=ticket.reward,already=false},true
    end
    local s=d.sessions[session]
    if kind=='begin'then
        if s then return {ok=true,created=false},false end
        d.sessions[session]={id=session,closed=false,remaining=2,previews={}}
        return {ok=true,created=true},true
    end
    if kind=='commit' and d.tickets[commit]then
        local t=d.tickets[commit]
        if t.session~=session or t.preview~=preview then return error('COMMIT_CONFLICT')end
        t.settled=false;return {ok=true,new=true,ticket=commit,amount=t.reward},true
    end
    if not s then return error('SESSION_MISSING')end
    if kind=='close'then
        local changed=not s.closed;s.closed=true;return {ok=true},changed
    end
    if kind=='register'then
        local p=d.previews[preview]
        if p then
            if p.session~=session or p.reward~=commit then return error('PREVIEW_CONFLICT')end
            return {ok=true,created=false},false
        end
        if s.closed or s.remaining<2 then return error('REGISTRATION_CLOSED')end
        if #s.previews>=3 then return error('PREVIEW_LIMIT')end
        p={id=preview,session=session,reward=commit,selected=false};d.previews[preview]=p;s.previews[#s.previews+1]=p
        return {ok=true,created=true},true
    end
    if s.closed then return error('SESSION_CLOSED')end
    if #s.previews~=3 then return error('PREVIEWS_INCOMPLETE')end
    local p=d.previews[preview]
    if not p or p.session~=session then return error('PREVIEW_MISSING')end
    if p.selected then return error('PREVIEW_COMMITTED')end
    if s.remaining==0 then return error('CHOICES_EXHAUSTED')end
    p.selected=true;s.remaining=s.remaining-1
    d.tickets[commit]={id=commit,session=session,preview=preview,reward=p.reward,settled=false}
    return {ok=true,new=true,ticket=commit,amount=p.reward},true
end
function R.view(d)
    local sessions,tickets={},{}
    for _,s in pairs(d.sessions)do
        local previews={};for _,p in ipairs(s.previews)do previews[#previews+1]={id=p.id,reward=p.reward,selected=p.selected}end
        table.sort(previews,function(a,b)return a.id<b.id end)
        sessions[#sessions+1]={id=s.id,closed=s.closed,remaining=s.remaining,previews=previews}
    end
    for _,t in pairs(d.tickets)do tickets[#tickets+1]=R.copy(t)end
    table.sort(sessions,function(a,b)return a.id<b.id end);table.sort(tickets,function(a,b)return a.id<b.id end)
    return {sessions=sessions,tickets=tickets,paid=d.paid}
end
return R
