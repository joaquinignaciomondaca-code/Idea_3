"""Validación offline de recepción sobre agregados ya registrados; no nuevo test de mercado."""
import copy
import json
import unittest
from pathlib import Path
from scripts.fetch_nested_result import CHECK_NAME, REVISION, validate_result


class NestedResultTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(Path('experiments/nested_optuna_predictive.json').read_text())
        self.summary = json.loads(Path('artifacts/nested_optuna/summary.json').read_text())
        self.run = {'head_sha': REVISION, 'conclusion': 'success', 'path': '.github/workflows/nested-optuna.yml'}
        self.check = {'head_sha': REVISION, 'name': CHECK_NAME, 'conclusion': 'success',
                      'app': {'slug': 'github-actions'}, 'output': {'text': self.text()}}

    def text(self):
        return '```json\n'+json.dumps(self.summary)+'\n```'

    def test_registered_summary_validates_without_new_computation(self):
        self.assertEqual(validate_result(self.check, self.run, self.spec, REVISION), self.summary)

    def test_rejects_different_app_head_or_workflow(self):
        for field in ('app', 'head_sha'):
            bad = copy.deepcopy(self.check)
            bad[field] = {'slug': 'other'} if field == 'app' else 'wrong'
            with self.assertRaises(ValueError):
                validate_result(bad, self.run, self.spec, REVISION)
        self.run['path'] = '.github/workflows/other.yml'
        with self.assertRaises(ValueError):
            validate_result(self.check, self.run, self.spec, REVISION)

    def test_rejects_omitted_trials_or_changed_selection_rule(self):
        self.summary['results']['selections'][0]['trials'].pop()
        self.check['output']['text'] = self.text()
        with self.assertRaises(ValueError):
            validate_result(self.check, self.run, self.spec, REVISION)
        self.setUp()
        self.summary['results']['selections'][0]['selected_params']['learning_rate'] += .01
        self.check['output']['text'] = self.text()
        with self.assertRaises(ValueError):
            validate_result(self.check, self.run, self.spec, REVISION)

    def test_rejects_pnl_or_changed_protocol(self):
        self.summary['trading_backtest'] = True; self.check['output']['text'] = self.text()
        with self.assertRaises(ValueError):
            validate_result(self.check, self.run, self.spec, REVISION)
        self.setUp(); self.spec['initial_training_epochs'] += 1
        with self.assertRaises(ValueError):
            validate_result(self.check, self.run, self.spec, REVISION)
