"""Import an explicit point export into empty collections, then verify every vector.

The input is a private, temporary migration file, never committed to Git.
Existing nonempty collections are accepted only when their contents already match.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def digest(points):
    return hashlib.sha256(json.dumps(sorted(points, key=lambda p: str(p['id'])),
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def migrate(rows, api, verify_only=False):
    existing = {row['name'] for row in api('GET', '/collections')['collections']}
    total = 0
    for row in rows:
        name, source = row['name'], row['points']
        if digest(source) != row['sha256']:
            raise ValueError('Migration file checksum does not match')
        path = '/collections/' + quote(name, safe='')

        def read():
            points, offset = [], None
            while True:
                body = {'limit': 100, 'with_payload': True, 'with_vector': True}
                if offset is not None:
                    body['offset'] = offset
                page = api('POST', path + '/points/scroll', body)
                points.extend({key: point.get(key) for key in ('id', 'payload', 'vector')}
                              for point in page['points'])
                offset = page.get('next_page_offset')
                if offset is None:
                    return points

        current = read() if name in existing else []
        if current and digest(current) != row['sha256']:
            raise ValueError('Target collection already has different data, import stopped')
        if verify_only:
            if name not in existing or digest(current) != row['sha256']:
                raise ValueError('Target collection does not match the migration source')
        elif not current:
            if name not in existing:
                params = row['config']['params']
                config = {key: params[key] for key in ('vectors', 'sparse_vectors',
                    'on_disk_payload', 'shard_number', 'replication_factor',
                    'write_consistency_factor') if params.get(key) is not None}
                api('PUT', path, config)
            for start in range(0, len(source), 50):
                api('PUT', path + '/points?wait=true', {'points': source[start:start + 50]})
            for field, schema in row.get('payload_schema', {}).items():
                api('PUT', path + '/index?wait=true', {'field_name': field,
                    'field_schema': schema.get('params') or schema['data_type']})
            if digest(read()) != row['sha256']:
                raise ValueError('Imported payload or vector checksum does not match')
        total += len(source)
    return {'collections': len(rows), 'points': total, 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:6333')
    parser.add_argument('--key-file', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    options = parser.parse_args()
    headers = {'Content-Type': 'application/json'}
    if options.key_file:
        headers['api-key'] = options.key_file.read_text().strip()

    def api(method, path, body=None):
        request = Request(options.url.rstrip('/') + path, method=method, headers=headers,
                          data=json.dumps(body).encode() if body is not None else None)
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
        if payload.get('status') != 'ok':
            raise RuntimeError('Qdrant rejected the migration request')
        return payload['result']

    print(json.dumps(migrate(json.loads(options.input.read_text(encoding='utf-8')),
                             api, options.verify_only)))


if __name__ == '__main__':
    main()
