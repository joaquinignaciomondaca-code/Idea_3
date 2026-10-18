"""Valida agregados ya registrados, sin iniciar nuevos cálculos."""
import copy
import json
import unittest
from pathlib import Path
from scripts.fetch_converged_result import REVISION,CHECK_NAME,validate


class ConvergedResultTests(unittest.TestCase):
    def setUp(self):
        self.s=json.loads(Path('artifacts/converged_classifier/summary.json').read_text())
        self.spec=json.loads(Path('experiments/converged_classifier.json').read_text())
        self.run={'head_sha':REVISION,'conclusion':'success','path':'.github/workflows/converged-classifier.yml'}

    def check(self,s):
        return {'name':CHECK_NAME,'head_sha':REVISION,'conclusion':'success','app':{'slug':'github-actions'},'output':{'text':'```json\n'+json.dumps(s)+'\n```'}}

    def test_registered_result_validates(self):
        self.assertEqual(validate(self.check(self.s),self.run,self.spec,REVISION),self.s)

    def test_changed_selection_or_gradient_rejected(self):
        bad=copy.deepcopy(self.s);bad['results']['selections'][0]['alpha']=123
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)
        bad=copy.deepcopy(self.s)
        f=next(f for f in bad['results']['fit_audit'] if not f['model'].endswith('/sgd10'));f['gradient_inf']=1.
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)

    def test_missing_candidate_model_or_interval_rejected(self):
        bad=copy.deepcopy(self.s);bad['results']['selections'][0]['trials'].pop()
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)
        bad=copy.deepcopy(self.s);del bad['results']['pooled']['historical_prior']
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)
        bad=copy.deepcopy(self.s);del bad['results']['paired_loss_ci']['baseline3/converged_selected']['historical_prior']['60']
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)

    def test_wrong_app_or_scope_rejected(self):
        c=self.check(self.s);c['app']['slug']='other'
        with self.assertRaises(ValueError):validate(c,self.run,self.spec,REVISION)
        self.s['market_run_enabled']=True
        with self.assertRaises(ValueError):validate(self.check(self.s),self.run,self.spec,REVISION)
