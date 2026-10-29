import copy
import unittest
from tools.import_qdrant_migration import digest, migrate


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.points = [{'id': 1, 'payload': {'text': 'source'}, 'vector': [0.25, 0.5]}]
        self.row = {'name': 'knowledge', 'points': self.points, 'sha256': digest(self.points),
                    'config': {'params': {'vectors': {'size': 2, 'distance': 'Cosine'}}}}
        self.target = {}
        self.writes = []

    def api(self, method, path, body=None):
        if path == '/collections':
            return {'collections': [{'name': name} for name in self.target]}
        name = path.split('/')[2]
        if path.endswith('/scroll'):
            return {'points': copy.deepcopy(self.target[name]), 'next_page_offset': None}
        self.writes.append((method, path, body))
        if '/points?' in path:
            self.target[name].extend(copy.deepcopy(body['points']))
        else:
            self.target[name] = []
        return True

    def test_empty_target_is_imported_and_verified_idempotently(self):
        result = migrate([self.row], self.api)
        self.assertEqual(result, {'collections': 1, 'points': 1, 'verified': True})
        self.assertEqual(self.target['knowledge'], self.points)
        writes = len(self.writes)
        migrate([self.row], self.api)
        migrate([self.row], self.api, verify_only=True)
        self.assertEqual(len(self.writes), writes)

    def test_existing_different_data_is_never_overwritten(self):
        self.target['knowledge'] = [{'id': 2, 'payload': {}, 'vector': [1, 0]}]
        with self.assertRaisesRegex(ValueError, 'different data'):
            migrate([self.row], self.api)
        self.assertEqual(self.writes, [])

    def test_corrupted_source_is_rejected_before_writing(self):
        self.row['points'][0]['payload']['text'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            migrate([self.row], self.api)
        self.assertEqual(self.writes, [])

    def test_verification_does_not_create_missing_collections(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            migrate([self.row], self.api, verify_only=True)
        self.assertEqual(self.writes, [])


if __name__ == '__main__':
    unittest.main()
