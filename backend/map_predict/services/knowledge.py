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


VERSION = re.compile(r'sửa ngày\s+1509|nckh_sua_ngay_1509|sửa ngày 15/9', re.I)
CRITERION = re.compile(r'^\s*(?:#{1,4}\s*)?sửa ngày\s+1509\s*\|\s*([1-9])(?:[.\s]|$)', re.I)
MAJOR = re.compile(r'^\s*(?:#{1,3}\s+)?sửa ngày\s+1509\s*\|\s*([1-9])(?:[.\s]|$)', re.I)


def requested_criteria(query):
    """Resolve column names and Vietnamese ordinals, not arbitrary score numbers."""
    text = ' '.join(tokens(query))
    result = {int(value) for value in re.findall(r'\bx\s*([1-9])\b', text)}
    ordinals = {'mot': 1, 'nhat': 1, 'dau tien': 1, 'hai': 2, 'ba': 3, 'tu': 4,
                'bon': 4, 'nam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9}
    number = r'(?:dau tien|nhat|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin|[1-9])'
    for match in re.finditer(r'\btieu chi\s+(?:thu\s+)?(' + number + r')\b', text):
        value = match[1]
        result.add(int(value) if value.isdecimal() else ordinals[value])
        tail = text[match.end():]
        while following := re.match(r'^\s+(?:va|voi|so voi)\s+(?:tieu chi\s+)?(?:thu\s+)?(' + number + r')\b', tail):
            value = following[1]
            result.add(int(value) if value.isdecimal() else ordinals[value])
            tail = tail[following.end():]
    return result


def source_sections(point):
    """A chunk may contain many criteria despite its single metadata label."""
    payload = point.get('payload') or {}
    content = payload.get('page_content')
    if not isinstance(content, str) or not VERSION.search(content):
        return []
    lines = content.splitlines(keepends=True)
    starts, offset = [], 0
    for line in lines:
        match = MAJOR.match(line)
        if match:
            starts.append((offset, int(match[1])))
        offset += len(line)
    if not starts:
        # Overlap chunks may begin at a subsection; still derive identity from text.
        match = next((CRITERION.match(line) for line in lines if CRITERION.match(line)), None)
        if not match:
            match = re.search(r'\*\*Tiêu chí:\*\*\s*([1-9])(?:[.\s]|$)', content, re.I)
        return [(int(match[1]) if match else None, point)]
    output = []
    prefix = content[:starts[0][0]].strip()
    if 'S3-HEADERS' in prefix:
        output.append((0, {**point, 'payload': {**payload, 'page_content': prefix}}))
    for index, (start, criterion) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(content)
        section = {**point, 'payload': {**payload, 'page_content': content[start:end].strip()}}
        output.append((criterion, section))
    return output


def select_sources(points, query):
    sections = [section for point in points for section in source_sections(point)]
    wanted = requested_criteria(query)
    if not wanted:
        normalized_query = ' ' + ' '.join(tokens(query)) + ' '
        matches = []
        for criterion, point in sections:
            if not criterion:
                continue
            first = point['payload']['page_content'].splitlines()[0]
            title = re.sub(r'^\s*[1-9][.\s]*', '', first.split('|')[1]).strip() if '|' in first else ''
            words = tokens(title)
            phrases = [' '.join(words[start:end]) for start in range(len(words))
                       for end in range(start + 2, len(words) + 1)]
            found = [phrase for phrase in phrases if ' ' + phrase + ' ' in normalized_query]
            if found:
                matches.append((criterion, max(found, key=len)))
        wanted = {criterion for criterion, phrase in matches if not any(
            criterion != other and phrase != longer and phrase in longer for other, longer in matches)}
    # Criterion aliases are resolved against content, never a chunk's coarse metadata.
    if wanted:
        selected = [point for criterion, point in sections if criterion in wanted]
    else:
        exact_ids = set(re.findall(r'\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b', query, re.I))
        if exact_ids:
            selected = [point for _, point in sections if str(point['id']).casefold() in {value.casefold() for value in exact_ids}]
        elif re.search(r'\b(?:9 tieu chi|cac tieu chi|toan bo tieu chi)\b', ' '.join(tokens(query))):
            selected = [point for criterion, point in sections if criterion is not None]
        else:
            selected = rank([point for _, point in sections], query, 5)
    if wanted and selected:
        selected = [point for criterion, point in sections if criterion == 0] + selected
    # Keep original Qdrant IDs while combining relevant subgroups from the same point.
    grouped = {}
    for point in selected:
        identity = str(point['id'])
        content = point['payload']['page_content']
        if identity not in grouped:
            grouped[identity] = {**point, 'payload': {**point['payload'], 'page_content': content}}
        elif content not in grouped[identity]['payload']['page_content']:
            grouped[identity]['payload']['page_content'] += '\n\n' + content
    return list(grouped.values())


def keyword_pool(url, kwargs):
    """Read payloads only, across pages, without truncating the criteria at 200."""
    pool, offset, seen, characters = [], None, set(), 0
    for _ in range(200):
        body = {'limit': 50, 'with_payload': True, 'with_vector': False}
        if offset is not None:
            body['offset'] = offset
        result = json_request(url + '/points/scroll', body, **kwargs)['result']
        page = result['points']
        characters += sum(len(str((point.get('payload') or {}).get('page_content', ''))) for point in page)
        pool.extend(page)
        if len(pool) > 10000 or characters > 20000000:
            raise ValueError('Collection exceeds direct retrieval capacity')
        offset = result.get('next_page_offset')
        if offset is None:
            return pool
        marker = json.dumps(offset, sort_keys=True)
        if marker in seen:
            raise ValueError('Qdrant scroll repeated an offset')
        seen.add(marker)
    raise ValueError('Collection exceeds direct retrieval capacity')


def retrieve(query, config):
    base = config.get('ASSISTANT_QDRANT_URL', '').rstrip('/')
    if not base:
        return {'mode': 'local_document', 'records': [], 'message': 'Dùng tài liệu tiêu chí local'}
    if config.get('ASSISTANT_RETRIEVAL_MODE') == 'ragwire':
        try:
            from .ragwire_search import retrieve as ragwire_retrieve
            return ragwire_retrieve(query, config)
        except Exception:
            result = retrieve(query, {**config, 'ASSISTANT_RETRIEVAL_MODE': 'keyword'})
            return {**result, 'mode': 'keyword_fallback',
                    'message': 'Truy xuất ngữ nghĩa chưa sẵn sàng, đang dùng từ khóa trên cùng collection Qdrant'}
    collection = config['ASSISTANT_QDRANT_COLLECTION']
    url = base + '/collections/' + quote(collection, safe='')
    kwargs = {'key': config.get('ASSISTANT_QDRANT_KEY', '')}
    try:
        info = json_request(url, **kwargs)['result']
        vectors = info.get('config', {}).get('params', {}).get('vectors') or {}
        vector_name = config.get('ASSISTANT_VECTOR_NAME', '')
        dimensions = vectors.get('size') if not vector_name else vectors.get(vector_name, {}).get('size')
        mode, points, note, scanned = 'dense', [], '', None
        embedding_url = config.get('ASSISTANT_EMBEDDING_URL', '').rstrip('/')
        try:
            if config.get('ASSISTANT_RETRIEVAL_MODE') == 'keyword':
                raise ValueError('Direct Qdrant retrieval selected')
            if not embedding_url:
                raise ValueError('Embedding service is not configured')
            vector = json_request(embedding_url + '/api/embed', {
                'model': config['ASSISTANT_EMBEDDING_MODEL'], 'input': query,
                'keep_alive': config.get('ASSISTANT_EMBEDDING_KEEP_ALIVE', '0s')}, timeout=90)['embeddings'][0]
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
            if config.get('ASSISTANT_RETRIEVAL_MODE') == 'keyword':
                mode = 'keyword'
                note = 'Tìm tài liệu theo từ khóa, chatbot không sử dụng embedding'
            pool = keyword_pool(url, kwargs)
            points = select_sources(pool, query)
            scanned = len(pool)
        if mode == 'dense':
            points = select_sources(points, query)
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
