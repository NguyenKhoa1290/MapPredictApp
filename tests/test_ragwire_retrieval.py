"""Real RAGWire + in-memory Qdrant, without model downloads or external calls."""
import json
import unittest
from unittest.mock import patch

try:
    from langchain_core.embeddings import Embeddings
    from langchain_core.messages import AIMessage
    from langchain_qdrant import QdrantVectorStore, RetrievalMode
    from langchain_qdrant.sparse_embeddings import SparseEmbeddings, SparseVector
    from qdrant_client import QdrantClient, models
    from backend.map_predict.services import ragwire_search as search
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, 'RAGWire is installed in the AI dependency set')
class RagwireRetrievalTests(unittest.TestCase):
    def setUp(self):
        class Dense(Embeddings):
            def embed_documents(self, texts): return [[1., .2, .3] for _ in texts]
            def embed_query(self, text): return [1., .2, .3]
        class Sparse(SparseEmbeddings):
            def embed_documents(self, texts): return [self.embed_query(text) for text in texts]
            def embed_query(self, text): return SparseVector(indices=[1], values=[1.])
        self.client = QdrantClient(':memory:')
        self.addCleanup(self.client.close)
        self.client.create_collection('test', vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE),
            sparse_vectors_config={'langchain-sparse': models.SparseVectorParams(modifier=models.Modifier.IDF)})
        self.points = [
            {'id': '59929946-642c-45bb-a3a0-5b7a4e8394cd', 'payload': {
                'page_content': '### sửa ngày 1509 | 1. Cao độ nền địa hình | ĐỒNG BẰNG\n'
                    '- **record_id:** `S3-R3`\n- **source_ref:** `sửa ngày 1509!A3:T3`\n'
                    '| 1 / 2 / 3 | `D3:F3` | <2m |',
                'metadata': {'so_tieu_chi': 7, 'file_name': 'Tieuchi.md', 'loai_noi_dung': 'dinh_luong'}}},
            {'id': 'b6379980-36b0-4b5c-935a-4dbf0a2d206a', 'payload': {
                'page_content': '### sửa ngày 1509 | 4. Hiện trạng sử dụng đất\n'
                    '- **record_id:** `S3-L9`\n| 9 | `L9` | Đất nông nghiệp xen kẹt |',
                'metadata': {'so_tieu_chi': 1, 'file_name': 'Tieuchi.md', 'loai_noi_dung': 'dinh_luong'}}},
        ]
        self.client.upsert('test', [models.PointStruct(id=point['id'], payload=point['payload'], vector={
            '': [1., .2, .3], 'langchain-sparse': models.SparseVector(indices=[1], values=[1.])}) for point in self.points])
        self.store = QdrantVectorStore(client=self.client, collection_name='test', embedding=Dense(),
            sparse_embedding=Sparse(), retrieval_mode=RetrievalMode.HYBRID, validate_collection_config=False)
        self.catalog = search.StoredCatalog(self.points)

    def test_actual_ragwire_filter_context_and_hybrid_search_return_documents(self):
        rag = search.ReadOnlyRAGWire(self.store, self.catalog,
            lambda prompt: AIMessage(content='```json\n{"loai_noi_dung":"dinh_luong","invented":"bad"}\n```'))
        with patch.object(self.client, 'create_payload_index', side_effect=AssertionError('Read-only')):
            context = rag.get_filter_context('Tìm ngưỡng GIS trong tài liệu')
            docs = rag.retrieve('GIS', filters=rag.proposed_filters)
        self.assertIn('RAGWire Filter Context', context)
        self.assertEqual(rag.proposed_filters, {'loai_noi_dung': 'dinh_luong'})
        self.assertEqual({str(doc.metadata['_id']) for doc in docs}, {point['id'] for point in self.points})

    def test_stored_values_preserve_case_and_reject_fabricated_filters(self):
        result = self.catalog.validate({'file_name': 'tieuchi.MD', 'so_tieu_chi': '1', 'diem': 9, 'source': '/private'})
        self.assertEqual(result, {'file_name': 'Tieuchi.md'})
        catalog = search.StoredCatalog([{'payload': {'metadata': {'source_file': 'C:\\private\\rubric.xlsx'}}}])
        self.assertEqual(catalog.get_field_values(['source_file']), {'source_file': ['rubric.xlsx']})
        self.assertEqual(catalog.validate({'source_file': 'rubric.xlsx'}), {'source_file': 'C:\\private\\rubric.xlsx'})

    def test_empty_invalid_filter_json_does_not_break_retrieval(self):
        rag = search.ReadOnlyRAGWire(self.store, self.catalog, lambda prompt: AIMessage(content='not valid JSON'))
        rag.get_filter_context('Một truy vấn chung')
        self.assertEqual(rag.proposed_filters, {})
        self.assertEqual(len(rag.retrieve('GIS', filters={})), 2)

    def test_coarse_metadata_relaxes_filters_and_keeps_correct_original_source_id(self):
        config = {'ASSISTANT_QDRANT_URL': 'http://qdrant:6333', 'ASSISTANT_QDRANT_COLLECTION': 'test',
                  'ASSISTANT_EMBEDDING_URL': 'http://embedding:11434', 'ASSISTANT_EMBEDDING_MODEL': 'same-model'}
        info = {'result': {'config': {'params': {'vectors': {'size': 3},
            'sparse_vectors': {'langchain-sparse': {}}}}, 'points_count': 2}}
        page = {'result': {'points': self.points, 'next_page_offset': None}}
        def response(url, body=None, **kwargs):
            if url.endswith('/api/embed'): return {'embeddings': [[1., .2, .3]]}
            return page if url.endswith('/points/scroll') else info
        with patch.object(search, 'json_request', side_effect=response), \
                patch.object(search, 'QdrantClient', return_value=self.client), \
                patch.object(search, 'sparse_embedding', return_value=self.store.sparse_embeddings), \
                patch.object(self.client, 'close'), \
                patch.object(self.client, 'create_payload_index', side_effect=AssertionError('Read-only')):
            result = search.retrieve('x1', config)
        self.assertEqual(result['mode'], 'ragwire_hybrid')
        self.assertTrue(result['filters_relaxed'])
        self.assertEqual(result['filters'], {'so_tieu_chi': [1]})
        self.assertEqual([record['id'] for record in result['records']], [self.points[0]['id']])
        self.assertIn('<2m', result['records'][0]['content'])
        self.assertNotIn('Hiện trạng sử dụng đất', result['records'][0]['content'])

    def test_embedding_uses_existing_model_and_unloads_it_after_each_query(self):
        config = {'ASSISTANT_EMBEDDING_URL': 'http://embedding:11434', 'ASSISTANT_EMBEDDING_MODEL': 'qwen3-embedding:0.6b'}
        embedding = search.OllamaQueryEmbedding(config, 3)
        with patch.object(search, 'json_request', return_value={'embeddings': [[.1, .2, .3]]}) as call:
            self.assertEqual(embedding.embed_query('query'), [.1, .2, .3])
        self.assertEqual(call.call_args.args[1]['keep_alive'], '0s')
        self.assertEqual(call.call_args.args[1]['model'], 'qwen3-embedding:0.6b')
        with patch.object(search, 'json_request', return_value={'embeddings': [[.1, .2]]}):
            with self.assertRaises(ValueError): embedding.embed_query('query')
