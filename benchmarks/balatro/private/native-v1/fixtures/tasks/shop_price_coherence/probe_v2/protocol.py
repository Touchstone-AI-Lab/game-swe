"""Only fixed buy endpoint BAD_REQUEST is classified; no global RPC swallowing."""
from poc.rpc import RemoteError


def rejected_buy(error, request_id, params):
    if not isinstance(error, RemoteError): return False
    response, request = error.response, error.request
    if not isinstance(response, dict) or set(response) != {'jsonrpc', 'id', 'error'}: return False
    if response['jsonrpc'] != '2.0' or type(response['id']) is not int or response['id'] != request_id: return False
    if request != dict(jsonrpc='2.0', id=request_id, method='buy', params=params): return False
    value = response['error']
    return (isinstance(value, dict) and type(value.get('code')) is int and value['code'] == -32001
            and isinstance(value.get('message'), str) and value.get('data') == {'name': 'BAD_REQUEST'})


def buy_once(client, index):
    params = {'card': index}
    try:
        return {'kind': 'success', 'response': client.action('buy', params)}
    except RemoteError as error:
        if not rejected_buy(error, client.request_id, params): raise
        return {'kind': 'bad_request', 'response': error.response}
