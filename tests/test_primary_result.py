"""Recuperación de Checks con respuestas ficticias; sin red ni artifacts reales."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from microtrade.online import canonical
from scripts.fetch_primary_predictive_result import CHECK_NAME, validate_result


class ResultRecoveryTests(unittest.TestCase):
    def fixture(self):
        spec = json.loads(Path('experiments/binance_primary_predictive.json').read_text())
        summary = {'experiment_id': spec['id'], 'source': spec['source'],
                   'spec_sha256': hashlib.sha256(canonical(spec).encode()).hexdigest(),
                   'trading_backtest': False, 'market_run_enabled': False, 'repeated_metrics_equal': True}
        check = {'head_sha': 'fixture-sha', 'name': CHECK_NAME, 'conclusion': 'success',
                 'app': {'slug': 'github-actions'}, 'output': {'text': '```json\n'+json.dumps(summary)+'\n```'}}
        workflow = {'head_sha': 'fixture-sha', 'conclusion': 'success'}
        return spec, summary, check, workflow

    def test_matching_producer_commit_and_protocol(self):
        spec, summary, check, workflow = self.fixture()
        self.assertEqual(validate_result(check, workflow, spec, 'fixture-sha'), summary)

    def test_wrong_producer_commit_and_workflow_rejected(self):
        spec, _, check, workflow = self.fixture()
        changed = copy.deepcopy(check); changed['app']['slug'] = 'other'
        with self.assertRaises(ValueError):
            validate_result(changed, workflow, spec, 'fixture-sha')
        with self.assertRaises(ValueError):
            validate_result(check, {'head_sha': 'wrong', 'conclusion': 'success'}, spec, 'fixture-sha')
        with self.assertRaises(ValueError):
            validate_result(check, {'head_sha': 'fixture-sha', 'conclusion': 'failure'}, spec, 'fixture-sha')

    def test_changed_source_protocol_or_pnl_claim_rejected(self):
        spec, summary, check, workflow = self.fixture()
        for key, value in (('source', {}), ('spec_sha256', 'changed'), ('trading_backtest', True),
                           ('repeated_metrics_equal', False), ('observations', [])):
            changed = copy.deepcopy(summary); changed[key] = value
            check['output']['text'] = '```json\n'+json.dumps(changed)+'\n```'
            with self.assertRaises(ValueError):
                validate_result(check, workflow, spec, 'fixture-sha')
