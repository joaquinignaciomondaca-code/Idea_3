"""Serie FICTICIA para fechas, purga, ajuste cerrado y reproducción; no mercado."""
import importlib.util
import json
import unittest
from dataclasses import replace
from datetime import date,timedelta
from pathlib import Path
HAS_NUMPY=importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    from microtrade.weekly_reference import examples,run
    from test_feature_study import candles


@unittest.skipUnless(HAS_NUMPY,'NumPy opcional')
class WeeklyAdaptationTests(unittest.TestCase):
    def setUp(self):
        self.rows=candles(1730);self.spec=json.loads(Path('experiments/weekly_return_adaptation.json').read_text())

    def test_signal_entry_target_dates_and_no_overlapping_holding_intervals(self):
        values=examples(self.rows)
        for r in values:
            signal=date.fromisoformat(r['signal'])
            self.assertEqual(signal.weekday(),6)
            self.assertEqual(r['entry'],(signal+timedelta(days=2)).isoformat())
            self.assertEqual(r['end'],(signal+timedelta(days=8)).isoformat())
            i=r['index'];self.assertEqual(r['y'],self.rows[i+8].close/self.rows[i+2].open-1)
        self.assertTrue(all(a['end']<b['entry'] for a,b in zip(values,values[1:])))

    def test_complete_repetition_budget_and_training_label_purge(self):
        a,b=run(self.rows,self.spec),run(self.rows,self.spec)
        self.assertEqual(a,b);self.assertEqual(a['model_fits_per_pass'],6)
        self.assertEqual(a['pooled']['zero']['n'],141)
        self.assertEqual(a['pooled']['historical_mean']['r2_oos_vs_historical_mean'],0)
        self.assertEqual(set(a['paired_loss_ci']['ridge4']),{'4','12'})
        for f in a['fits']:
            self.assertLessEqual(f['last_training_target'],f['cutoff'])
            self.assertLess(f['ridge_normal_equation_error'],1e-10)

    def test_future_changes_do_not_change_first_fit_or_prediction(self):
        a=run(self.rows,self.spec);cutoff=a['fits'][0]['cutoff']
        changed=[r if r.date<=cutoff else replace(r,open=r.high,close=r.low) for r in self.rows]
        b=run(changed,self.spec)
        self.assertEqual(a['fits'][0],b['fits'][0])
        self.assertEqual(a['predictions']['ridge4'][0]['prediction'],b['predictions']['ridge4'][0]['prediction'])
