import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from codex_rpc import CodexRPC, RPCError


class RPCTests(unittest.TestCase):
    def client(self, body, timeout=2):
        return CodexRPC(command=[sys.executable, '-u', '-c', body], timeout=timeout)

    def test_matches_response_id_despite_notifications(self):
        body = '''import sys,json
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 print(json.dumps({'method':'notification','params':{}}),flush=True)
 print(json.dumps({'id':r['id'],'result':{'method':r['method']}}),flush=True)
'''
        with self.client(body) as client:
            self.assertEqual(client.request('thread/read', {})['method'], 'thread/read')
            self.assertEqual(client.next_event(timeout=1)['method'], 'notification')

    def test_server_error_is_not_reported_as_success(self):
        body = '''import sys,json
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 answer={'result':{}} if r['method']=='initialize' else {'error':{'code':-1}}
 print(json.dumps({'id':r['id'],**answer}),flush=True)
'''
        with self.client(body) as client, self.assertRaises(RPCError):
            client.request('thread/name/set', {})

    def test_dead_server_fails_without_hanging(self):
        with self.assertRaises(RPCError):
            with self.client('pass'):
                pass

    def test_timeout_is_bounded(self):
        with self.assertRaises(RPCError):
            with self.client('import time; time.sleep(30)', timeout=0.05):
                pass


if __name__ == '__main__':
    unittest.main()
