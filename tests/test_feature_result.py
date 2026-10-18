"""Recepción offline de agregados registrados; no nuevos fits ni pruebas de mercado."""
import copy
import json
import unittest
from pathlib import Path
from scripts.fetch_feature_result import CHECK_NAME,REVISION,validate_result


class FeatureResultTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads(Path('experiments/feature_ablation.json').read_text())
        self.s=json.loads(Path('artifacts/feature_ablation/summary.json').read_text())
        self.run={'head_sha':REVISION,'conclusion':'success','path':'.github/workflows/feature-ablation.yml'}
        self.check={'head_sha':REVISION,'name':CHECK_NAME,'conclusion':'success','app':{'slug':'github-actions'},'output':{}}
        self.encode()

    def encode(self):
        self.check['output']['text']='```json\n'+json.dumps(self.s)+'\n```'

    def test_registered_aggregates_validate(self):
        self.assertEqual(validate_result(self.check,self.run,self.spec,REVISION),self.s)

    def test_changed_producer_or_protocol_rejected(self):
        bad=copy.deepcopy(self.check);bad['app']['slug']='other'
        with self.assertRaises(ValueError):validate_result(bad,self.run,self.spec,REVISION)
        self.spec['max_selected_features']=7
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)

    def test_rank_or_selection_tampering_rejected(self):
        self.s['selections'][0]['feature_importance'][0]['delta_log_loss']+=.1;self.encode()
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)
        self.setUp(); self.s['selections'][0]['selected_features']=[];self.encode()
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)

    def test_omitted_model_or_altered_pooled_metric_rejected(self):
        del self.s['pooled']['adaptive/without_activity'];self.encode()
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)
        self.setUp();self.s['pooled']['fixed/all24']['log_loss']+=.01;self.encode()
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)

    def test_future_selection_or_live_gate_rejected(self):
        self.s['selections'][0]['selection_data_end']='2023-01-01';self.encode()
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)
        self.setUp();self.s['market_run_enabled']=True;self.encode()
        with self.assertRaises(ValueError):validate_result(self.check,self.run,self.spec,REVISION)
