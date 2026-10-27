import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler

from backend.map_predict import create_app
from backend.map_predict.config import ROOT
from predict_pkl import FEATURES

CSV = b'id,x1,x2,x3,x4,x5,x6,x7,x8,x9\nlot-1,0,0,0,0,0,0,0,0,0\n'


class FixedPredictionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.directory = Path(self.folder.name)
        shutil.copy2(ROOT / 'models' / 'rf_model_rating_pipeline.pkl', self.directory / 'rf_model_rating_pipeline.pkl')
        self.app = create_app({'TESTING': True, 'MODEL_DIRECTORY': self.directory})
        self.client = self.app.test_client()

    def tearDown(self):
        self.folder.cleanup()

    def upload(self, path='', data=CSV, **kwargs):
        return self.client.post('/api/v1/predictions' + path, data={'csv': (io.BytesIO(data), 'input.csv')}, **kwargs)

    def test_fixed_model_matches_existing_algorithm_and_records_version_without_writes(self):
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        status = self.client.get('/api/v1/predictions/model').json['data']
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.json)
        output = response.json['data']
        pipeline = joblib.load(ROOT / 'models' / 'rf_model_rating_pipeline.pkl')
        expected_y = int(pipeline.predict(pd.DataFrame([[0] * 9], columns=FEATURES))[0])
        self.assertEqual(output['rows'][0]['Y'], expected_y)
        self.assertEqual(output['rows'][0]['id'], 'lot-1')
        self.assertEqual(output['model_version'], status['model_version'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.directory.iterdir()})
        self.assertNotIn(str(self.directory), response.get_data(as_text=True))

    def test_status_and_preview_never_execute_model(self):
        data = ('id,x1\n' + ''.join(f'lot-{i},1\n' for i in range(250))).encode()
        with patch('backend.map_predict.services.prediction.predict_rows') as predict:
            self.assertTrue(self.client.get('/api/v1/predictions/model').json['data']['ready'])
            response = self.upload('/preview', data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['data']['count'], 250)
            self.assertEqual(len(response.json['data']['rows']), 200)
            predict.assert_not_called()

    def test_model_upload_and_path_overrides_are_rejected_before_execution(self):
        for field in ('model', 'scaler', 'model_path', 'MODEL_DIRECTORY'):
            with patch('backend.map_predict.services.prediction.predict_rows') as predict:
                response = self.client.post('/api/v1/predictions', data={
                    'csv': (io.BytesIO(CSV), 'input.csv'), field: (io.BytesIO(b'not a trusted model'), 'model.pkl')})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error']['code'], 'MODEL_UPLOAD_DISABLED')
                predict.assert_not_called()
        response = self.client.post('/api/v1/predictions', data={
            'csv': (io.BytesIO(CSV), 'input.csv'), 'model_path': str(ROOT / 'rf_model_rating.pkl')})
        self.assertEqual(response.status_code, 400)

    def test_missing_or_incompatible_bundle_has_clear_safe_error(self):
        (self.directory / 'rf_model_rating_pipeline.pkl').unlink()
        self.assertFalse(self.client.get('/api/v1/predictions/model').json['data']['ready'])
        with self.assertLogs(self.app.logger, level='WARNING'):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error']['code'], 'MODEL_UNAVAILABLE')
        (self.directory / 'rf_model_rating_pipeline.pkl').write_bytes(b'invalid trusted file')
        with self.assertLogs(self.app.logger, level='WARNING'):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error']['code'], 'MODEL_INCOMPATIBLE')
        self.assertNotIn(str(self.directory), response.get_data(as_text=True))

    def test_bad_csv_nonfinite_values_and_limits_are_rejected(self):
        for data in (b'', b'id,id\na,b\n', b'id,x1\na,1,2\n', b'id,x1\na,NaN\n', b'id,x1\na,inf\n', b'id,x1\na,text\n'):
            self.assertEqual(self.upload(data=data).status_code, 422, data)
        self.app.config['PREDICTION_MAX_ROWS'] = 1
        self.assertEqual(self.upload('/preview', b'id,x1\na,0\nb,1\n').status_code, 413)
        self.app.config['PREDICTION_MAX_CSV_BYTES'] = 5
        self.assertEqual(self.upload().status_code, 413)
        self.app.config['PREDICTION_MAX_REQUEST_BYTES'] = 10
        self.assertEqual(self.upload().status_code, 413)

    def test_requests_are_independent_and_foreign_browser_origin_is_rejected(self):
        second = self.app.test_client()
        first_output = self.upload().json['data']
        second_output = second.post('/api/v1/predictions', data={
            'csv': (io.BytesIO(CSV.replace(b'lot-1', b'lot-2')), 'input.csv')}).json['data']
        self.assertEqual(first_output['rows'][0]['id'], 'lot-1')
        self.assertEqual(second_output['rows'][0]['id'], 'lot-2')
        self.assertEqual(self.client.get('/api/v1/predictions/results').status_code, 405)
        self.assertEqual(self.upload(headers={'Origin': 'https://elsewhere.example'}).status_code, 403)
        self.assertEqual(self.upload('/preview', headers={'Origin': 'http://localhost'}).status_code, 200)

    def test_model_bundle_is_private_and_version_changes_with_content(self):
        first = self.client.get('/api/v1/predictions/model').json['data']['model_version']
        with (self.directory / 'rf_model_rating_pipeline.pkl').open('ab') as output:
            output.write(b'changed')
        second = self.client.get('/api/v1/predictions/model').json['data']['model_version']
        self.assertNotEqual(first, second)
        for path in ('/models/rf_model_rating_pipeline.pkl', '/static/models/rf_model_rating_pipeline.pkl', '/portal/assets/../../models/scaler_bds.pkl'):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_pipeline_runs_scaler_once_and_needs_no_separate_scaler_file(self):
        calls = []
        transform = StandardScaler.transform
        def track(scaler, values, *args, **kwargs):
            calls.append(values.copy())
            return transform(scaler, values, *args, **kwargs)
        with patch.object(StandardScaler, 'transform', track):
            response = self.upload(data=b'id,x1,x2,x3,x4,x5,x6,x7,x8,x9\nA,1,2,3,4,5,6,7,8,9\n')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(len(calls), 1)
        self.assertEqual(list(calls[0].iloc[0]), list(range(1, 10)))
        self.assertEqual([path.name for path in self.directory.iterdir()], ['rf_model_rating_pipeline.pkl'])
        pipeline = joblib.load(ROOT / 'models' / 'rf_model_rating_pipeline.pkl')
        joblib.dump(pipeline.named_steps['rf'], self.directory / 'rf_model_rating_pipeline.pkl')
        with self.assertLogs(self.app.logger, level='WARNING'):
            incompatible = self.upload()
        self.assertEqual(incompatible.status_code, 503)
        self.assertEqual(incompatible.json['error']['code'], 'MODEL_INCOMPATIBLE')

    def test_result_csv_import_does_not_run_model_or_impute_missing_labels(self):
        with patch('backend.map_predict.services.prediction.predict_rows') as predict:
            response = self.upload('/results', b'id,Y,note\n001,2,first\nA2,,missing\nA3,1.0,decimal\n')
            self.assertEqual(response.status_code, 200, response.json)
            data = response.json['data']
            self.assertEqual([row['Y'] for row in data['rows']], [2, '', 1])
            self.assertEqual(data['rows'][0]['id'], '001')
            self.assertEqual(data['source'], 'uploaded')
            self.assertIsNone(data['model_version'])
            predict.assert_not_called()
        for invalid in (b'id,value\n1,2\n', b'id,Y\n1,3\n', b'id,Y\n1,NaN\n', b'id,Y\n1,text\n'):
            self.assertEqual(self.upload('/results', invalid).status_code, 422)
        self.assertEqual(self.client.get('/api/v1/predictions/results').status_code, 405)


if __name__ == '__main__':
    unittest.main()
