"""Read-only RAGWire retrieval over the existing, already embedded collection.

The stock constructor initializes ingestion and creates payload indexes. This
retrieval-only subclass deliberately initializes only the components it uses.
"""
from functools import lru_cache
import json
import math
import re
import tempfile
from types import SimpleNamespace
from urllib.parse import quote

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from ragwire import RAGWire
from ragwire.retriever.hybrid import get_retriever

from .knowledge import json_request, requested_criteria, select_sources, source_sections, tokens, VERSION

FIELDS = ('so_tieu_chi', 'ten_tieu_chi', 'phan_nhom', 'loai_noi_dung', 'phuong_phap_gis',
          'diem', 'nhom_diem', 'muc_do_thuan_loi', 'source_ref', 'record_id',
          'nguong_dinh_luong', 'file_name', 'source_file', 'phien_ban', 'sheet_name')
TITLES = ('', 'Cao độ nền địa hình', 'Độ dốc', 'Khoảng cách tới mặt nước', 'Hiện trạng sử dụng đất',
          'Mật độ xây dựng hiện trạng', 'Sự phù hợp quy hoạch', 'Chi phí GPMB',
          'Tiếp cận giao thông', 'Mật độ mạng lưới đường')


class OllamaQueryEmbedding(Embeddings):
    def __init__(self, config, dimensions):
        self.config, self.dimensions = config, dimensions

    def embed_documents(self, texts):
        result = json_request(self.config['ASSISTANT_EMBEDDING_URL'].rstrip('/') + '/api/embed', {
            'model': self.config['ASSISTANT_EMBEDDING_MODEL'], 'input': texts,
            'keep_alive': '0s', 'options': {'num_ctx': 2048}}, timeout=90)
        vectors = result['embeddings']
        if len(vectors) != len(texts) or any(len(vector) != self.dimensions or any(
                type(value) not in (float, int) or not math.isfinite(value) for value in vector) for vector in vectors):
            raise ValueError('Embedding dimensions do not match the existing collection')
        return vectors

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class StoredCatalog:
    def __init__(self, points):
        self.values = {field: [] for field in FIELDS}
        for point in points:
            metadata = point.get('payload', {}).get('metadata') or {}
            for field in FIELDS:
                value = metadata.get(field)
                for item in value if isinstance(value, list) else [value]:
                    if type(item) in (str, int, bool) and item not in self.values[field] and len(self.values[field]) < 50:
                        self.values[field].append(item)
        self.values = {field: values for field, values in self.values.items() if values}

    def get_field_values(self, fields, limit=50, **kwargs):
        return {field: [self.display(field, value) for value in self.values.get(field, [])[:limit]] for field in fields}

    @staticmethod
    def display(field, value):
        if isinstance(value, list):
            return [StoredCatalog.display(field, item) for item in value]
        if field in ('file_name', 'source_file') and isinstance(value, str):
            return re.split(r'[/\\]', value)[-1]
        return value

    def validate(self, incoming):
        if not isinstance(incoming, dict):
            return {}
        result = {}
        for field, value in incoming.items():
            if field not in self.values:
                continue
            selected = []
            for item in value if isinstance(value, list) else [value]:
                for stored in self.values[field]:
                    if type(stored) is type(item) and (item.casefold().strip() in
                            (stored.casefold().strip(), self.display(field, stored).casefold().strip())
                                                       if isinstance(item, str) else stored == item):
                        if stored not in selected:
                            selected.append(stored)
                        break
            if selected:
                result[field] = selected if isinstance(value, list) else selected[0]
        return result


class ReadOnlyRAGWire(RAGWire):
    def __init__(self, vectorstore, catalog, completion):
        # Do not call the ingestion/index-creating RAGWire constructor.
        self.config = {'retriever': {'top_k': 5}}
        self.vectorstore, self.vectorstore_wrapper = vectorstore, catalog
        self.retriever = get_retriever(vectorstore, top_k=5, search_type='hybrid')
        self.reranker, self._rerank_config, self._auto_filter = None, {}, False
        self._filter_fields = list(catalog.values)
        self._field_types = {}
        self._stored_values_cache = catalog.get_field_values(self._filter_fields)
        self.metadata_extractor = SimpleNamespace(llm=RunnableLambda(completion))
        self.proposed_filters = {}

    def _normalize_filters(self, filters):
        # Preserve exact stored case, including filenames and cell references.
        return self.vectorstore_wrapper.validate(filters)

    def _extract_filters_from_query(self, query):
        criteria = requested_criteria(query)
        # Column aliases are explicit metadata intent; avoid a second LLM call.
        if criteria:
            proposed = {'so_tieu_chi': sorted(criteria)}
            text = ' ' + ' '.join(tokens(query)) + ' '
            for field in ('phan_nhom', 'loai_noi_dung', 'phuong_phap_gis'):
                matches = [value for value in self._stored_values.get(field, []) if isinstance(value, str)
                           and ' ' + ' '.join(tokens(value)) + ' ' in text]
                if matches:
                    proposed[field] = matches
        else:
            proposed = super()._extract_filters_from_query(query) or {}
        self.proposed_filters = self._normalize_filters(proposed)
        return self.proposed_filters


@lru_cache(maxsize=1)
def sparse_embedding():
    # Same sparse model as the reference RAGWire configuration.
    return FastEmbedSparse(model_name='Qdrant/bm25', cache_dir=tempfile.gettempdir() + '/map-predict-bm25', threads=1)


def filter_completion(config, prompt):
    from .assistant import call_model
    # The adapter normalizes provider JSON before it reaches RAGWire's parser.
    result = call_model([{'role': 'system', 'content':
        'Bạn chỉ chọn bộ lọc metadata để tìm tài liệu, không chỉnh dữ liệu. Trả một JSON object chứa các bộ lọc, '
        'không thêm answer, thao tác chỉnh sửa hoặc phần giải thích. '
        'Chỉ dùng tên trường và giá trị có trong dữ liệu, không tự suy diễn.'},
        {'role': 'user', 'content': prompt.to_string()}], {**config, 'ASSISTANT_CALL_TIMEOUT': 35}, response_kind='filters')
    filters = result.get('filters', result)
    return AIMessage(content=json.dumps(filters if isinstance(filters, dict) else {}, ensure_ascii=False))


def retrieve(query, config):
    base = config['ASSISTANT_QDRANT_URL'].rstrip('/')
    collection = config['ASSISTANT_QDRANT_COLLECTION']
    url = base + '/collections/' + quote(collection, safe='')
    key = config.get('ASSISTANT_QDRANT_KEY', '')
    info = json_request(url, key=key)['result']
    params = info['config']['params']
    vector_name = config.get('ASSISTANT_VECTOR_NAME', '')
    dimensions = params['vectors']['size'] if not vector_name else params['vectors'][vector_name]['size']
    points, offset = [], None
    for _ in range(4):
        body = {'limit': 50, 'with_payload': True, 'with_vector': False}
        if offset is not None:
            body['offset'] = offset
        page = json_request(url + '/points/scroll', body, key=key)['result']
        points.extend(page['points'])
        offset = page.get('next_page_offset')
        if offset is None:
            break
    catalog = StoredCatalog(points)
    client = QdrantClient(url=base, api_key=key or None, timeout=15, check_compatibility=False, trust_env=False)
    try:
        has_sparse = 'langchain-sparse' in (params.get('sparse_vectors') or {})
        store = QdrantVectorStore(client=client, collection_name=collection,
            embedding=OllamaQueryEmbedding(config, dimensions), vector_name=vector_name,
            sparse_embedding=sparse_embedding() if has_sparse else None,
            retrieval_mode=RetrievalMode.HYBRID if has_sparse else RetrievalMode.DENSE,
            validate_collection_config=False)
        rag = ReadOnlyRAGWire(store, catalog, lambda prompt: filter_completion(config, prompt))
        rag.get_filter_context(query)
        filters = rag.proposed_filters
        wanted = requested_criteria(query)
        semantic_query = query + ''.join(f'\nTiêu chí {number}: {TITLES[number]}' for number in sorted(wanted))
        documents = rag.retrieve(semantic_query, filters=filters)
        def convert(docs):
            return [{'id': str(doc.metadata['_id']), 'payload': {'page_content': doc.page_content,
                     'metadata': doc.metadata}} for doc in docs]
        found = convert(documents)
        selected = select_sources(found, query)
        found_criteria = {criterion for point in found for criterion, _ in source_sections(point)}
        expected_ids = {str(point['id']) for point in points if any(
            criterion in wanted for criterion, _ in source_sections(point))}
        relaxed = bool(filters) and (not selected or bool(wanted - found_criteria)
                                     or bool(expected_ids - {str(point['id']) for point in found}))
        if relaxed:
            # Existing chunks have coarse metadata covering several criteria.
            # Broaden safely, then validate against actual source sections.
            found = convert(rag.retrieve(semantic_query, top_k=min(50, max(5, info.get('points_count') or 5)), filters={}))
            selected = select_sources(found, query)
        records, used = [], 0
        for point in selected:
            payload = point['payload']
            content = payload['page_content']
            if not VERSION.search(content) or used + len(content) > 60000:
                continue
            metadata = payload.get('metadata') or {}
            records.append({'id': str(point['id']), 'content': content,
                'file': catalog.display('file_name', str(metadata.get('source_file') or metadata.get('file_name') or ''))[:150],
                'source_refs': list(dict.fromkeys(re.findall(r'sửa ngày 1509![A-Z]+\d+(?::[A-Z]+\d+)?', content, re.I)))[:40],
                'record_ids': list(dict.fromkeys(re.findall(r'S3-[A-Z]+\d+(?:-[A-Z]+)?', content)))[:40]})
            used += len(content)
        return {'mode': 'ragwire_hybrid' if has_sparse else 'ragwire_dense', 'engine': 'RAGWire',
                'collection': collection, 'records': records,
                'filters': {field: catalog.display(field, value) for field, value in filters.items()},
                'filters_relaxed': relaxed, 'filter_fields': list(catalog.values),
                'vector_dimensions': dimensions, 'total_points': info.get('points_count'),
                'scanned_points': len(points), 'catalog_truncated': offset is not None,
                'message': 'Tìm theo ngữ nghĩa và metadata đã đối chiếu từ Qdrant'}
    finally:
        client.close()
