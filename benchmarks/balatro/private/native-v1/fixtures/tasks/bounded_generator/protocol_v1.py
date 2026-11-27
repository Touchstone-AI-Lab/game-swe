"""Narrow, endpoint-specific recognition; all other RPC failures propagate."""
from poc.rpc import RemoteError


def not_allowed(error, request_id, params):
    if not isinstance(error, RemoteError): return False
    response=error.response
    request=error.request
    if not isinstance(response,dict) or set(response)!={'jsonrpc','id','error'}: return False
    if response['jsonrpc']!='2.0' or type(response['id']) is not int or response['id']!=request_id: return False
    if request!={'jsonrpc':'2.0','id':request_id,'method':'use','params':params}: return False
    value=response['error']
    return (isinstance(value,dict) and type(value.get('code')) is int and value['code']==-32003
            and isinstance(value.get('message'),str) and value.get('data')=={'name':'NOT_ALLOWED'})


def use_once(client, index):
    params={'consumable':index}
    try:
        result=client.action('use',params)
        return {'kind':'success','response':result}
    except RemoteError as error:
        if not not_allowed(error,client.request_id,params): raise
        return {'kind':'not_allowed','response':error.response}
