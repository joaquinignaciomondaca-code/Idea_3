"""Recepción de agregados ya calculados: no inicia nuevos fits ni workflows."""
import copy
import json
import unittest
from pathlib import Path
from scripts.fetch_numerical_review import REVISION,CHECK_NAME,WEEKLY_CHECK_NAME,validate_audit,validate_weekly


class NumericalReviewResultTests(unittest.TestCase):
    def setUp(self):
        self.a=json.loads(Path('artifacts/numerical_review/audit_summary.json').read_text())
        self.w=json.loads(Path('artifacts/numerical_review/weekly_summary.json').read_text())
        self.sa=json.loads(Path('experiments/numerical_audit.json').read_text())
        self.sw=json.loads(Path('experiments/weekly_return_adaptation.json').read_text())
        self.run={'head_sha':REVISION,'conclusion':'success','path':'.github/workflows/numerical-audit.yml'}

    def check(self,s,name):
        return {'name':name,'head_sha':REVISION,'conclusion':'success','app':{'slug':'github-actions'},
                'output':{'text':'```json\n'+json.dumps(s)+'\n```'}}

    def test_both_registered_results_validate(self):
        self.assertEqual(validate_audit(self.check(self.a,CHECK_NAME),self.run,self.sa,REVISION),self.a)
        self.assertEqual(validate_weekly(self.check(self.w,WEEKLY_CHECK_NAME),self.run,self.sw,REVISION),self.w)

    def test_fake_convergence_or_solver_disagreement_rejected(self):
        bad=copy.deepcopy(self.a);bad['cases'][0]['epochs10_converged_at_gradient_1e7']=True
        with self.assertRaises(ValueError):validate_audit(self.check(bad,CHECK_NAME),self.run,self.sa,REVISION)
        bad=copy.deepcopy(self.a);bad['cases'][0]['solver_max_weight_difference']=1.
        with self.assertRaises(ValueError):validate_audit(self.check(bad,CHECK_NAME),self.run,self.sa,REVISION)

    def test_wrong_producer_protocol_or_scope_rejected(self):
        check=self.check(self.a,CHECK_NAME);check['app']['slug']='other'
        with self.assertRaises(ValueError):validate_audit(check,self.run,self.sa,REVISION)
        self.sw['ridge_alpha']=2
        with self.assertRaises(ValueError):validate_weekly(self.check(self.w,WEEKLY_CHECK_NAME),self.run,self.sw,REVISION)
        self.a['external_scores_recomputed']=True
        with self.assertRaises(ValueError):validate_audit(self.check(self.a,CHECK_NAME),self.run,self.sa,REVISION)

    def test_weekly_altered_skill_or_omitted_bootstrap_length_rejected(self):
        self.w['results']['pooled']['ridge4']['r2_oos_vs_historical_mean']=.99
        with self.assertRaises(ValueError):validate_weekly(self.check(self.w,WEEKLY_CHECK_NAME),self.run,self.sw,REVISION)
        self.setUp();del self.w['results']['paired_loss_ci']['ridge4']['12']
        with self.assertRaises(ValueError):validate_weekly(self.check(self.w,WEEKLY_CHECK_NAME),self.run,self.sw,REVISION)
