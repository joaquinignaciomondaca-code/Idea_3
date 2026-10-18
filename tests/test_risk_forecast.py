"""Tests FICTICIOS: causalidad/registro temporal, no evidencia financiera."""
import importlib.util,json,math,tempfile,unittest
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
HAS_NUMPY=importlib.util.find_spec('numpy') is not None
if HAS_NUMPY:
    from test_feature_study import candles
    from microtrade.risk_forecast import series,forecasts,loss,study,prospective_record


@unittest.skipUnless(HAS_NUMPY,'NumPy opcional')
class RiskForecastTests(unittest.TestCase):
    def test_prefix_invariance_and_ewma_formula(self):
        rows=candles(400);a=forecasts(rows,200,.001);b=forecasts(rows[:201],200,.001)
        self.assertEqual(a,b)
        r2,_=series(rows);v=float(sum(r2[1:61])/60)
        for i in range(61,201):v=.94*v+.06*float(r2[i])
        self.assertAlmostEqual(a['ewma94'],v,places=15)
        self.assertEqual(loss(.001,0),math.log(.001))
        with self.assertRaises(ValueError):loss(0,.001)

    def test_study_repeats_all_models_and_missing_dates_fail(self):
        rows=candles(400);s=json.loads(Path('experiments/risk_persistence.json').read_text())
        s['test']=[rows[200].date,rows[399].date];s['blocks']=[[rows[a].date,rows[b].date] for a,b in ((200,259),(260,319),(320,399))]
        a,b=study(rows,s),study(rows,s);self.assertEqual(a,b)
        self.assertEqual(a['metrics']['ewma94']['n'],200);self.assertEqual(len(a['records']),200)
        with self.assertRaises(ValueError):series(rows[:100]+rows[101:])

    def test_forward_rejects_late_stale_overwrite_and_outside_reserve(self):
        rows=candles(200);cutoff=date(2026,10,30)
        rows=[replace(r,date=(cutoff-timedelta(days=199-i)).isoformat()) for i,r in enumerate(rows)]
        s=json.loads(Path('experiments/risk_forward_reserved.json').read_text());now=datetime(2026,10,31,12,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'forecast.json';r=prospective_record(rows,now,s,p,.001)
            self.assertEqual(r['target'],'2026-11-01');self.assertFalse(r['target_observed'])
            with self.assertRaises(FileExistsError):prospective_record(rows,now,s,p,.001)
            for bad in (datetime(2026,11,1,tzinfo=timezone.utc),datetime(2026,10,30,tzinfo=timezone.utc)):
                with self.assertRaises(ValueError):prospective_record(rows,bad,s,Path(tmp)/'bad.json',.001)
            with self.assertRaises(ValueError):prospective_record(rows[:-1],now,s,Path(tmp)/'stale.json',.001)
