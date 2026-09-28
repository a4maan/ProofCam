"""Command-line development client and issuer. Run `python -m provenance --help`."""
import argparse
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .http_server import make_server
from .protocol import MAX_MESSAGE, Rejected, decode, encode, hexstr, key_id, message, public_bytes, sign
from .service import Service
from .storage import create_key, load_key, private_write, regular_reader
from .verifier import development_trust, file_hash, verify_file


def request(base, route, body=None):
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise Rejected('local_development_endpoint_required')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise Rejected('redirect_rejected')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(base.rstrip('/')+route, data=body, headers={'Content-Type':'application/cbor'})
    try:
        with opener.open(req, timeout=10) as response:
            result = response.read(MAX_MESSAGE+1)
    except urllib.error.HTTPError as exc:
        error = decode(exc.read(MAX_MESSAGE+1))
        reason = error.get('error') if type(error) is dict else None
        raise Rejected(reason if type(reason) is str and len(reason) < 80 and reason.replace('_','').isalnum() else 'request_rejected') from exc
    decode(result)  # Strict bounds before saving anything.
    return result


def read(path):
    with regular_reader(path) as stream:
        result = stream.read(MAX_MESSAGE+1)
    decode(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['init-server','invite','serve','export-trust','revoke']:
        p = sub.add_parser(name); p.add_argument('--state', default='provenance/local/server')
        if name in ('init-server','export-trust'): p.add_argument('--out', required=True, help='Local development trust file')
        if name=='invite': p.add_argument('--out',required=True,help='Private invitation file')
        if name=='serve': p.add_argument('--port',type=int,default=8765)
        if name=='revoke': p.add_argument('--installation',required=True)
    p=sub.add_parser('keygen');p.add_argument('--key',required=True)
    for name in ['enroll','challenge','prepare','submit','lookup','remove']:
        p=sub.add_parser(name)
        p.add_argument('--url',default='http://127.0.0.1:8765')
        if name in ('enroll','challenge','prepare','remove'):p.add_argument('--key',required=True)
        if name=='enroll':p.add_argument('--invitation',required=True)
        if name=='challenge':p.add_argument('--purpose',choices=['register','remove'],default='register')
        if name in ('challenge','prepare','submit','lookup'):p.add_argument('--out',required=True)
        if name in ('prepare','remove'):p.add_argument('--challenge')
        if name=='prepare':p.add_argument('--file',required=True);p.add_argument('--id',required=True)
        if name=='submit':
            p.add_argument('--request',required=True)
            p.add_argument('--kind',choices=['register','enroll'],default='register')
        if name in ('lookup','remove'):p.add_argument('--id',required=True)
    p=sub.add_parser('verify');p.add_argument('--file',required=True);p.add_argument('--certificate',required=True)
    p.add_argument('--trust',required=True);p.add_argument('--allow-development',action='store_true');p.add_argument('--id')
    args=parser.parse_args()
    if args.command in ('init-server','invite','serve','export-trust','revoke'):
        state=Path(args.state);keypath=state/'issuer.pem'
        key=create_key(keypath) if args.command=='init-server' else load_key(keypath)
        service=Service(state/'registry.sqlite3',key)
        if args.command in ('init-server','export-trust'):
            private_write(args.out,encode(development_trust(key)));print('Development trust exported; expires in 24 hours. Distribute only through a trusted local channel.')
        elif args.command=='invite':
            private_write(args.out,encode({'invitation':service.invitation()}));print('Private, single-use invitation saved.')
        elif args.command=='revoke':service.revoke(args.installation);print('Installation disabled for future requests.')
        else:
            server=make_server(service,args.port)
            print(f'Development only: http://127.0.0.1:{server.server_port}',flush=True)
            try:server.serve_forever()
            finally:server.server_close()
        return
    if args.command=='keygen':
        print('Development installation:',key_id(create_key(args.key)));return
    if args.command=='verify':
        result=verify_file(read(args.certificate),args.file,decode(read(args.trust)),allow_development=args.allow_development,expected_id=args.id)
        print(json.dumps(result,indent=2));return 0 if result['content']=='exact_match' else 2
    key=load_key(args.key) if hasattr(args,'key') else None
    if args.command=='enroll':
        p=message('enroll',public_key=public_bytes(key),invitation=decode(read(args.invitation))['invitation'])
        print(json.dumps(decode(request(args.url,'/v1/enroll',sign(p,key,'enroll')))));return
    if args.command=='challenge':
        p=message('challenge',session=secrets.token_hex(16),purpose=args.purpose)
        private_write(args.out,request(args.url,'/v1/challenges',sign(p,key,'challenge')));return
    if args.command=='prepare':
        challenge=decode(read(args.challenge)) if args.challenge else None
        if challenge and challenge['purpose']!='register':raise Rejected('wrong_challenge_purpose')
        p=message('register',id=hexstr(args.id,32),file_sha256=file_hash(args.file),
                  session=challenge['session'] if challenge else secrets.token_hex(16),
                  mode='online' if challenge else 'offline',challenge=challenge['nonce'] if challenge else None,source='import')
        private_write(args.out,sign(p,key,'register'))
        print('Signed request saved for submission/retry. Source is an import; camera origin is unverified.');return
    if args.command=='submit':
        private_write(args.out,request(args.url,'/v1/'+args.kind,read(args.request)));return
    if args.command=='lookup':
        private_write(args.out,request(args.url,'/v1/records/'+hexstr(args.id,32)));return
    if args.command=='remove':
        if not args.challenge:raise Rejected('removal_challenge_required')
        challenge=decode(read(args.challenge))
        if challenge['purpose']!='remove':raise Rejected('wrong_challenge_purpose')
        p=message('remove',id=hexstr(args.id,32),session=challenge['session'],challenge=challenge['nonce'])
        print(json.dumps(decode(request(args.url,'/v1/remove',sign(p,key,'remove')))))


if __name__=='__main__':
    try:
        sys.exit(main() or 0)
    except (Rejected, OSError, KeyError, ValueError) as exc:
        # Do not dump private paths, request bodies or server traceback to the terminal.
        print(str(exc) if isinstance(exc,Rejected) else 'local_operation_failed',file=sys.stderr)
        sys.exit(1)
