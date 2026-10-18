"""Comparación causal sobre velas FICTICIAS, no evidencia financiera."""
import importlib.util
import json
import unittest
from dataclasses import replace
from pathlib import Path
HAS_DEPS=importlib.util.find_spec('numpy') is not None and importlib.util.find_spec('scipy') is not None
if HAS_DEPS:
    from test_feature_study import candles
    from microtrade.converged_classifier import study,fit_predict
    from microtrade.feature_study import prepare,run_block,NAMES


def fixture():
    rows=candles(400);s=json.loads(Path('experiments/converged_classifier.json').read_text())
    s['outer_blocks']=[{'name':f'fixture{k}','test':[rows[i].date,rows[i+5].date],
                       'inner':[[rows[i-35].date,rows[i-30].date],[rows[i-20].date,rows[i-15].date]]}
                      for k,i in enumerate((240,300,360))]
    return rows,s


@unittest.skipUnless(HAS_DEPS,'Dependencias opcionales: requirements-audit.txt')
class ConvergedClassifierTests(unittest.TestCase):
    def test_old_sgd_recipe_reproduced_and_labels_purged(self):
        rows,s=fixture();data=prepare(rows)
        old=run_block(data,240,245,NAMES,False,{'epochs':10,'training_window':365,'minimum_training_rows':60,'learning_rate':.001,'l2':.01})
        new=fit_predict(data,240,245,NAMES,.01,s,sgd=True)
        self.assertLess(max(abs(a-b) for a,b in zip(old['fit']['weights'],new['fit']['weights'])),1e-14)
        self.assertAlmostEqual(old['metrics']['log_loss'],new['metrics']['log_loss'],places=14)
        self.assertEqual(new['fit']['last_training_label'],rows[238].date)

    def test_search_budget_convergence_and_complete_repetition(self):
        rows,s=fixture();a,b=study(rows,s),study(rows,s)
        self.assertEqual(a,b);self.assertEqual(a['fits_per_pass'],54);self.assertEqual(a['search_candidates'],18)
        self.assertEqual(a['pooled']['historical_prior']['n'],18)
        for f in a['fit_audit']:
            if not f['model'].endswith('/sgd10'):
                self.assertLess(f['gradient_inf'],1e-7);self.assertLess(f['scipy_weight_max_difference'],1e-4)
        for c in a['selections']:
            self.assertEqual(c['alpha'],min(c['trials'],key=lambda t:(t['value'],t['alpha']))['alpha'])

    def test_future_mutation_does_not_change_selection_or_initial_forecast(self):
        rows,s=fixture();changed=[r if i<240 else replace(r,open=r.high,close=r.low) for i,r in enumerate(rows)]
        a,b=study(rows,s),study(changed,s)
        self.assertEqual(a['selections'][:2],b['selections'][:2])
        self.assertEqual(a['fit_audit'][:6],b['fit_audit'][:6])
        self.assertEqual(a['predictions']['all24/converged_selected'][0]['p'],b['predictions']['all24/converged_selected'][0]['p'])
        s['outer_blocks'][0]['inner'][0][1]=rows[240].date
        with self.assertRaises(ValueError):study(rows,s)
