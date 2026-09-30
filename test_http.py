APP_NAME = 'PesoLens'
READ_PATH = '/api/peso/summary'
WRITE_PATH = '/api/peso/transactions'
WRITE_DATA = {'kind': 'expense', 'category': 'HTTP', 'amount': '0.29', 'date': '2020-01-01', 'note': 'Demo'}

"""Actual HTTP-boundary checks for this independent app."""
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from run import allowed_addresses, create_server

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch.dict('os.environ', {'CODESPACES':'true','CODESPACE_NAME':'demo-space-123','GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev'}):
            cls.server = create_server(0, cls.temp.name)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, method='GET', data=None, headers=None):
        raw = None if data is None else json.dumps(data).encode()
        req = Request(self.base+path, raw, {'Content-Type':'application/json',**(headers or {})}, method=method)
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            parsed = json.loads(body) if response.headers.get('Content-Type','').startswith('application/json') else body
            return response.status, parsed, response.headers

    def test_home_guide_and_assets(self):
        for path in ['/','/guide.html','/app.js','/style.css','/icon.svg']:
            status,_,headers = self.request(path)
            self.assertEqual(status,200)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])

    def test_health_identifies_app(self):
        status,data,_ = self.request('/api/health')
        self.assertEqual((status,data['status']),(200,'ok'))
        self.assertEqual(data['app'],APP_NAME)

    def test_own_api(self):
        status,data,_ = self.request(READ_PATH) if READ_PATH else self.request(WRITE_PATH,'POST',WRITE_DATA)
        self.assertEqual(status,200 if READ_PATH else 201)
        if not READ_PATH:
            self.assertEqual(data['output'],['7'])

    def test_json_input_boundary(self):
        self.assertEqual(self.request(WRITE_PATH,'POST',[])[0],400)
        self.assertEqual(self.request(WRITE_PATH,'POST',WRITE_DATA,{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request(WRITE_PATH,'POST')[0],413)

    def test_foreign_host_and_origin_rejected(self):
        self.assertEqual(self.request('/',headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request(WRITE_PATH,'POST',WRITE_DATA,{'Origin':'https://example.com'})[0],403)

    def test_exact_codespace_get_and_write(self):
        host = f'demo-space-123-{self.server.server_port}.app.github.dev'
        headers = {'Host':host,'Origin':'https://'+host}
        self.assertEqual(self.request('/',headers=headers)[0],200)
        self.assertEqual(self.request(WRITE_PATH,'POST',WRITE_DATA,headers)[0],201)
        other = f'other-space-{self.server.server_port}.app.github.dev'
        self.assertEqual(self.request('/',headers={'Host':other})[0],403)
        self.assertEqual(self.request(WRITE_PATH,'POST',WRITE_DATA,{'Host':host,'Origin':'https://'+other})[0],403)

    def test_codespace_requires_valid_environment(self):
        base = {'CODESPACES':'true','CODESPACE_NAME':'demo-space-123','GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev'}
        for changes in ({'CODESPACES':'false'},{'CODESPACE_NAME':'invalid/name'},{'GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN':'app.github.dev/evil'}):
            hosts,origins = allowed_addresses(8000,{**base,**changes})
            self.assertEqual(hosts,{'localhost:8000','127.0.0.1:8000'})
            self.assertEqual(origins,{'http://localhost:8000','http://127.0.0.1:8000'})

    def test_no_private_files_or_other_apps(self):
        for path in ['/run.py','/app.py','/core.py','/README.md','/test_business.py','/data/test.db','/../run.py','/api/unknown/x','/missing']:
            self.assertEqual(self.request(path)[0],404)

    def test_csv_export_content_type(self):
        status,body,headers = self.request('/api/peso/export?month=2020-01')
        self.assertEqual(status,200)
        self.assertTrue(headers['Content-Type'].startswith('text/csv'))
        self.assertIn(b',',body)
