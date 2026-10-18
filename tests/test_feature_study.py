"""Velas y paquetes FICTICIOS: no constituyen evidencia de mercado."""
import copy
import importlib.util
import json
import math
import tempfile
import unittest
from dataclasses import replace
from datetime import date,timedelta
from pathlib import Path

HAS_NUMPY = importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    import numpy as np
    from microtrade.feature_study import Candle,FAMILIES,NAMES,prepare,run_block,study,fit_scaler,transform
    from scripts.run_feature_study import load_extended
    from scripts.publish_feature_check import payload


def candles(n=270):
    result=[]; previous=100.
    for i in range(n):
        o=previous*math.exp(.001*math.cos(i)); c=o*math.exp(.015*math.sin(i*.3)+.002*math.cos(i))
        h=max(o,c)*1.01; l=min(o,c)*.99; v=100+10*math.sin(i*.2); q=v*(o+c)/2
        result.append(Candle((date(2022,1,1)+timedelta(days=i)).isoformat(),o,h,l,c,v,q,100+i%7,q*(.5+.1*math.sin(i))))
        previous=c
    return result


def spec_for(rows):
    s=json.loads(Path('experiments/feature_ablation.json').read_text())
    s.update({'epochs':1,'training_window':30,'minimum_training_rows':20})
    s['outer_blocks']=[{'name':f'fixture{k}','test':[rows[a].date,rows[a+5].date],
                       'inner':[[rows[a-35].date,rows[a-31].date],[rows[a-20].date,rows[a-15].date]]}
                      for k,a in enumerate((180,210,240))]
    return s


@unittest.skipUnless(HAS_NUMPY,'NumPy opcional: requirements-features.txt')
class FeatureStudyTests(unittest.TestCase):
    def test_exactly_24_features_and_causal_prefix(self):
        rows=candles(); full=prepare(rows)
        self.assertEqual(len(NAMES),24); self.assertEqual(len(set(NAMES)),24)
        np.testing.assert_array_equal(full['x'][90:180],prepare(rows[:180])['x'][90:])
        self.assertTrue(np.isfinite(full['x'][90:]).all())

    def test_training_scaler_and_empty_intercept_model(self):
        rows=candles(); s=spec_for(rows); data=prepare(rows)
        a=run_block(data,180,185,[],True,s)
        self.assertEqual(a['metrics']['n'],6); self.assertEqual(a['fit']['features'],[])
        center,scale=fit_scaler(np.ones((30,2)))
        np.testing.assert_array_equal(transform(np.ones((5,2)),center,scale)[:,1:],np.zeros((5,2)))
        changed=list(rows)
        changed[180:]=[replace(r,quote_volume=r.quote_volume*100) for r in changed[180:]]
        b=run_block(prepare(changed),180,185,NAMES,False,s)
        c=run_block(data,180,185,NAMES,False,s)
        self.assertEqual(b['fit'],c['fit'])
        self.assertEqual(b['records'][0]['p'],c['records'][0]['p'])
        self.assertEqual(c['fit']['last_training_label'],rows[178].date)

    def test_invalid_activity_is_rejected_not_imputed(self):
        rows=candles()
        for kwargs in ({'quote_volume':float('nan')},{'trades':0},{'taker_quote':1e30}):
            changed=list(rows); changed[100]=replace(rows[100],**kwargs)
            with self.assertRaises(ValueError):prepare(changed)

    def test_full_study_is_identical_and_budget_is_explicit(self):
        rows=candles(); s=spec_for(rows)
        a,b=study(rows,s),study(rows,s)
        self.assertEqual(a,b); self.assertEqual(a['fits_per_pass'],390)
        self.assertEqual(a['pooled']['fixed/all24']['n'],18)
        self.assertEqual(len(a['outer_predictions']),18*14)
        for choice in a['selections']:
            expected=[r['name'] for r in choice['feature_importance'] if r['positive_both_folds']][:6]
            self.assertEqual(choice['selected_features'],expected)
            self.assertEqual(len(choice['feature_importance']),24)
            self.assertEqual(len(choice['family_importance']),4)

    def test_outer_mutation_cannot_change_its_own_ranking_or_selection(self):
        rows=candles(); s=spec_for(rows); changed=list(rows)
        changed[180:]=[replace(r,open=r.high,close=r.low,quote_volume=r.quote_volume*2) for r in changed[180:]]
        a,b=study(rows,s),study(changed,s)
        self.assertEqual(a['selections'][:2],b['selections'][:2])
        with self.assertRaisesRegex(ValueError,'invade'):
            s['outer_blocks'][0]['inner'][1][1]=rows[180].date; study(rows,s)

    def test_extended_loader_uses_original_fields_on_fictitious_bundle(self):
        from test_primary_predictive import fixture
        with tempfile.TemporaryDirectory() as root:
            _,_,directory=fixture(Path(root)); plan=json.loads((directory/'BTCUSDT_plan.json').read_text())
            rows=load_extended(directory,plan)
            self.assertEqual(len(rows),110); self.assertEqual(rows[0].quote_volume,1000)
            self.assertEqual(rows[0].trades,20); self.assertEqual(rows[0].taker_quote,500)

    def test_publisher_fails_closed_without_results(self):
        with self.assertRaises(ValueError):payload({'experiment_id':'other'},'fixture')
        with self.assertRaises(ValueError):payload({'experiment_id':'FEATURE-ABLATION-001','reproduced':True,
                                                   'trading_backtest':True},'fixture')
