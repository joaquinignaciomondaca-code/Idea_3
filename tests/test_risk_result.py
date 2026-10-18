"""Recepción de agregados ya calculados, sin nuevo backtest."""
import copy,json,unittest
from pathlib import Path
from scripts.fetch_risk_result import validate,REVISION,CHECK_NAME


class RiskResultTests(unittest.TestCase):
    def setUp(self):
        self.s=json.loads(Path('artifacts/risk_persistence/summary.json').read_text());self.spec=json.loads(Path('experiments/risk_persistence.json').read_text())
        self.run={'head_sha':REVISION,'conclusion':'success','path':'.github/workflows/risk-persistence.yml'}
    def check(self,s):
        return {'name':CHECK_NAME,'head_sha':REVISION,'conclusion':'success','app':{'slug':'github-actions'},'output':{'text':'```json\n'+json.dumps(s)+'\n```'}}
    def test_registered_result_validates(self):
        self.assertEqual(validate(self.check(self.s),self.run,self.spec,REVISION),self.s)
    def test_altered_metric_missing_interval_or_scope_rejected(self):
        bad=copy.deepcopy(self.s);bad['results']['metrics']['ewma94']['qlike']-=1
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)
        bad=copy.deepcopy(self.s);del bad['results']['paired_ci_vs_rolling20']['ewma94']['60']
        with self.assertRaises(ValueError):validate(self.check(bad),self.run,self.spec,REVISION)
        self.s['forward_started']=True
        with self.assertRaises(ValueError):validate(self.check(self.s),self.run,self.spec,REVISION)
    def test_wrong_producer_or_protocol_rejected(self):
        c=self.check(self.s);c['app']['slug']='other'
        with self.assertRaises(ValueError):validate(c,self.run,self.spec,REVISION)
        self.spec['hpo_trials']=1
        with self.assertRaises(ValueError):validate(self.check(self.s),self.run,self.spec,REVISION)
