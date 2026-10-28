import copy
import unittest

from backend.map_predict import create_app
from tools.configure_cloudflare import with_hostname


class AdminDomainTests(unittest.TestCase):
    def test_admin_hostname_opens_admin_and_other_hosts_keep_their_portal(self):
        client = create_app({'TESTING': True}).test_client()
        for path in ('/', '/portal', '/portal/'):
            response = client.get(path, base_url='https://admin.danhgiaquyhoach.top')
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/portal/admin/ai')
        self.assertEqual(client.get('/', base_url='https://danhgiaquyhoach.top').location, '/portal/')
        self.assertEqual(client.get('/', base_url='http://localhost:8765').location, '/portal/')

    def test_adding_hostname_preserves_main_route_catch_all_and_tunnel_options(self):
        original = {'ingress': [{'hostname': 'danhgiaquyhoach.top', 'service': 'http://app:8000'},
                               {'service': 'http_status:404'}], 'warp-routing': {'enabled': True}}
        untouched = copy.deepcopy(original)
        updated = with_hostname(original, 'admin.danhgiaquyhoach.top', 'http://app:8000')
        self.assertEqual(original, untouched)
        self.assertEqual(updated['ingress'][0], original['ingress'][0])
        self.assertEqual(updated['ingress'][-1], original['ingress'][-1])
        self.assertEqual(updated['warp-routing'], original['warp-routing'])
        self.assertEqual(with_hostname(updated, 'admin.danhgiaquyhoach.top', 'http://app:8000'), updated)

    def test_conflicting_hostname_route_is_never_overwritten(self):
        original = {'ingress': [{'hostname': 'admin.danhgiaquyhoach.top', 'service': 'http://other:9000'}, {'service': 'http_status:404'}]}
        with self.assertRaises(RuntimeError):
            with_hostname(original, 'admin.danhgiaquyhoach.top', 'http://app:8000')

    def test_public_domain_never_serves_admin_page_or_admin_api(self):
        client = create_app({'TESTING': True}).test_client()
        for host in ('danhgiaquyhoach.top', 'www.danhgiaquyhoach.top', 'other.example'):
            for path in ('/portal/admin/ai', '/portal/admin/ai/', '/api/v1/ai-admin/state'):
                self.assertEqual(client.get(path, base_url='https://' + host).status_code, 404)
            self.assertEqual(client.post('/api/v1/ai-admin/login', base_url='https://' + host, json={'password': 'test'}).status_code, 404)
