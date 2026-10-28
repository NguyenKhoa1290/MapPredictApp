"""Read-only retrieval from the user's existing Qdrant collection."""
from collections import Counter
import json
import math
import re
import unicodedata
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler

from .prediction import PredictionError


def json_request(url, body=None, *, key='', timeout=10):
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['api-key'] = key
    payload = json.dumps(body).encode() if body is not None else None
    with build_opener(ProxyHandler({})).open(Request(url, data=payload, headers=headers), timeout=timeout) as response:
        content = response.read(3_000_001)
    if len(content) > 3_000_000:
        raise ValueError('Qdrant response exceeded retrieval limit')
    return json.loads(content)


def tokens(text):
    normalized = unicodedata.normalize('NFKD', text.casefold()).replace('đ', 'd')
    return re.findall(r'[a-z0-9]+', ''.join(c for c in normalized if not unicodedata.combining(c)))


def rank(points, query, limit):
    terms = Counter(tokens(query))
    documents = [Counter(tokens(p.get('payload', {}).get('page_content', ''))) for p in points]
    frequencies = Counter(term for document in documents for term in document)
    average = sum(sum(doc.values()) for doc in documents) / max(1, len(documents)) or 1
    scores = []
    for index, document in enumerate(documents):
        length = sum(document.values())
        score = sum(math.log(1 + (len(documents) - frequencies[term] + .5) / (frequencies[term] + .5))
                    * document[term] * 2.2 / (document[term] + 1.2 * (.25 + .75 * length / average))
                    for term in terms if document[term])
        scores.append((score, index))
    return [points[index] for score, index in sorted(scores, key=lambda row: (-row[0], row[1]))[:limit] if score > 0]


def retrieve(query, config):
    base = config.get('ASSISTANT_QDRANT_URL', '').rstrip('/')
    if not base:
        return {'mode': 'local_document', 'records': [], 'message': 'Dùng tài liệu tiêu chí local'}
    collection = config['ASSISTANT_QDRANT_COLLECTION']
    url = base + '/collections/' + quote(collection, safe='')
    kwargs = {'key': config.get('ASSISTANT_QDRANT_KEY', '')}
    try:
        info = json_request(url, **kwargs)['result']
        vectors = info['config']['params']['vectors']
        vector_name = config.get('ASSISTANT_VECTOR_NAME', '')
        dimensions = vectors.get('size') if not vector_name else vectors[vector_name]['size']
        mode, points, note, scanned = 'dense', [], '', None
        embedding_url = config.get('ASSISTANT_EMBEDDING_URL', '').rstrip('/')
        try:
            if not embedding_url:
                raise ValueError('Embedding service is not configured')
            vector = json_request(embedding_url + '/api/embed', {
                'model': config['ASSISTANT_EMBEDDING_MODEL'], 'input': query,
                'keep_alive': '5m'}, timeout=45)['embeddings'][0]
            if len(vector) != dimensions or any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector):
                raise ValueError('Embedding dimensions do not match the collection')
            body = {'query': vector, 'limit': 5, 'with_payload': True, 'with_vector': False}
            if vector_name:
                body['using'] = vector_name
            points = json_request(url + '/points/query', body, **kwargs)['result']['points']
        except Exception:
            # Explicit fallback, never replace the user's embedding model or reindex.
            mode = 'keyword_fallback'
            note = 'Embedding chưa sẵn sàng, đang xếp hạng từ khóa trên nội dung Qdrant'
            pool, offset = [], None
            for _ in range(4):
                body = {'limit': 50, 'with_payload': True, 'with_vector': False}
                if offset is not None:
                    body['offset'] = offset
                result = json_request(url + '/points/scroll', body, **kwargs)['result']
                pool.extend(result['points'])
                offset = result.get('next_page_offset')
                if offset is None:
                    break
            points = rank(pool, query, 5)
            scanned = len(pool)
            if offset is not None:
                note += ', chỉ xét 200 đoạn đầu do giới hạn dự phòng'
        records, used = [], 0
        for point in points:
            payload = point.get('payload') or {}
            content = payload.get('page_content')
            if not isinstance(content, str) or not content.strip():
                continue
            # Only the requested source version may drive scoring.
            if not re.search(r'sửa ngày\s+1509|nckh_sua_ngay_1509|sửa ngày 15/9', content, re.I):
                continue
            if used + len(content) > 60000:
                continue
            metadata = payload.get('metadata') or {}
            refs = list(dict.fromkeys(re.findall(r'sửa ngày 1509![A-Z]+\d+(?::[A-Z]+\d+)?', content, re.I)))
            records.append({'id': str(point['id']), 'content': content,
                            'file': str(metadata.get('file_name', ''))[:150],
                            'source_refs': refs[:40],
                            'record_ids': list(dict.fromkeys(re.findall(r'S3-[A-Z]+\d+(?:-[A-Z]+)?', content)))[:40]})
            used += len(content)
        return {'mode': mode, 'collection': collection, 'records': records, 'message': note,
                'vector_dimensions': dimensions, 'total_points': info.get('points_count'),
                'scanned_points': scanned}
    except Exception as error:
        raise PredictionError('KNOWLEDGE_UNAVAILABLE',
                              'Chưa đọc được collection Qdrant đã cấu hình, dữ liệu chưa thay đổi', 503) from error
