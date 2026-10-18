"""Fixtures sintéticos: prueban separación temporal, búsqueda y ledger; nunca rentabilidad."""
import copy
import importlib.util
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from microtrade.engine import synthetic_bars
from microtrade.nested_search import prepare, regularized_step, run_block, run_nested
from microtrade.nested_audit import verify_nested_ledger
from microtrade.online import Ledger


def fixture_spec(bars):
    s = json.loads(Path('experiments/nested_optuna_predictive.json').read_text())
    s['initial_training_epochs'] = 2; s['minimum_training_rows'] = 20
    s['search_space']['window'] = [20, 30]
    s['trial_budget'].update({'total': 8, 'per_model_per_outer_block': 2})
    s['outer_blocks'] = [
        {'name': 'fixtureA', 'test': [bars[80].date, bars[89].date],
         'inner': [[bars[50].date, bars[59].date], [bars[60].date, bars[70].date]]},
        {'name': 'fixtureB', 'test': [bars[100].date, bars[109].date],
         'inner': [[bars[70].date, bars[79].date], [bars[80].date, bars[90].date]]}]
    return s


class NestedCoreTests(unittest.TestCase):
    def test_l2_does_not_regularize_intercept(self):
        weights, x = [1., 2., 0., 0.], [1., 0., 0., 0.]
        unreg = regularized_step(weights, x, 1, .02, 0)
        reg = regularized_step(weights, x, 1, .02, .1)
        self.assertEqual(reg[0], unreg[0])
        self.assertAlmostEqual(reg[1], 2-.02*.1*2)

    def test_fit_purges_incomplete_labels_and_window_caps_rows(self):
        bars = synthetic_bars(count=120); data = prepare(bars)
        r = run_block(data, 80, 89, {'learning_rate': .02, 'l2': .01, 'window': 30}, True, 2, 20)
        self.assertEqual(r['fit']['forecast_cutoff'], bars[78].date)
        self.assertEqual(r['fit']['last_training_feature'], bars[76].date)
        self.assertEqual(r['fit']['last_training_label'], bars[78].date)
        self.assertEqual(r['fit']['effective_training_rows'], 30)
        self.assertEqual(r['metrics']['n'], 10)

    def test_future_mutation_cannot_change_predictions_scored_before_cut(self):
        bars = synthetic_bars(count=120)
        changed = [b if i <= 85 else replace(b, close=b.close*.2, open=b.open*2) for i, b in enumerate(bars)]
        params = {'learning_rate': .02, 'l2': .01, 'window': 30}
        a = run_block(prepare(bars), 80, 89, params, True, 2, 20)
        b = run_block(prepare(changed), 80, 89, params, True, 2, 20)
        self.assertEqual(a['records'][:6], b['records'][:6])
        self.assertEqual(a['fit'], b['fit'])

    def test_ledger_semantics_detects_modified_input_and_no_early_update(self):
        bars = synthetic_bars(count=120)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'events.jsonl'; ledger = Ledger(path)
            try:
                run_block(prepare(bars), 80, 89, {'learning_rate': .02, 'l2': .01, 'window': 30}, True, 2, 20, ledger, 'fixture')
            finally:
                ledger.close()
            audit = verify_nested_ledger(path, bars)
            self.assertEqual(audit['predictions'], 10); self.assertEqual(audit['updates'], 10)
            changed = list(bars); b = changed[80]
            changed[80] = replace(b, close=b.open*(.5 if b.close>b.open else 2))
            with self.assertRaises(ValueError):
                verify_nested_ledger(path, changed)


@unittest.skipUnless(importlib.util.find_spec('optuna'), 'Optuna opcional: requirements-optuna.txt')
class NestedSearchTests(unittest.TestCase):
    def test_search_repeats_all_trials_and_pooled_metrics(self):
        bars = synthetic_bars(count=120); spec = fixture_spec(bars)
        a, b = run_nested(bars, spec), run_nested(bars, spec)
        self.assertEqual(a, b)
        self.assertEqual(a['total_trials'], 8)
        self.assertEqual(len(a['selections']), 4)
        self.assertEqual(a['pooled_outer_metrics']['fixed_tuned']['n'], 20)
        self.assertEqual(a['pooled_outer_metrics']['constant_p0_5']['brier'], .25)
        self.assertFalse(a['winner_promoted'])
        for selection in a['selections']:
            best = min(selection['trials'], key=lambda t: (t['value'], t['number']))
            self.assertEqual(selection['selected_trial'], best['number'])
            for trial in selection['trials']:
                expected = sum(n*loss for n, loss in zip(trial['fold_n'], trial['fold_losses']))/sum(trial['fold_n'])
                self.assertEqual(trial['value'], expected)

    def test_first_outer_labels_cannot_affect_its_own_selection(self):
        bars = synthetic_bars(count=120); spec = fixture_spec(bars)
        changed = [b if i < 80 else replace(b, close=b.close*.2, open=b.open*2) for i, b in enumerate(bars)]
        a, b = run_nested(bars, spec), run_nested(changed, spec)
        self.assertEqual(a['selections'][:2], b['selections'][:2])

    def test_inner_validation_must_end_before_first_outer_forecast(self):
        bars = synthetic_bars(count=120); spec = fixture_spec(bars)
        spec['outer_blocks'][0]['inner'][-1][-1] = bars[80].date
        with self.assertRaisesRegex(ValueError, 'invade'):
            run_nested(bars, spec)

    def test_budget_guard_precedes_any_search(self):
        bars = synthetic_bars(count=120); spec = fixture_spec(bars)
        spec['trial_budget']['total'] = 300
        with self.assertRaisesRegex(ValueError, 'máximo 30'):
            run_nested(bars, spec)
