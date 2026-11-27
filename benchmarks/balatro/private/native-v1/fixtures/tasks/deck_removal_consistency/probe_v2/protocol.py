"""Fixed use endpoint's pre-selection BAD_REQUEST, with exact request binding."""
from poc.rpc import RemoteError


def empty_selection_rejection(error, request_id, params):
    if not isinstance(error, RemoteError):return False
    response=error.response
    if error.request!={'jsonrpc':'2.0','id':request_id,'method':'use','params':params}:return False
    if not isinstance(response,dict) or set(response)!={'jsonrpc','id','error'}:return False
    if response['jsonrpc']!='2.0' or type(response['id']) is not int or response['id']!=request_id:return False
    value=response['error']
    return (isinstance(value,dict) and type(value.get('code')) is int and value['code']==-32001
            and isinstance(value.get('message'),str) and value.get('data')=={'name':'BAD_REQUEST'})
