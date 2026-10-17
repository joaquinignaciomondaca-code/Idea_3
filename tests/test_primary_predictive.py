"""Paquetes y metadatos FICTICIOS para probar el adaptador sin red ni mercado real."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts.collect_primary_archives import archive_plan
from scripts.publish_predictive_check import check_payload
from scripts.run_primary_predictive import run, validate_artifact


def fixture(root):
    spec = json.loads(Path('experiments/binance_primary_predictive.json').read_text())
    start, end = date(2022, 1, 1), date(2022, 4, 20)
    spec.update({'data_window': [start.isoformat(), end.isoformat()],
                 'initial_training_through': (start+timedelta(days=60)).isoformat(),
                 'forecast_cutoff_start': (start+timedelta(days=61)).isoformat(),
                 'initial_training_epochs': 2,
                 'report_label_epochs': {'fixture': [start.isoformat(), end.isoformat()]}})
    directory = root/'package/data/primary_import'; directory.mkdir(parents=True)
    plan = archive_plan('BTCUSDT', start, end)
    (directory/'BTCUSDT_plan.json').write_text(json.dumps(plan))
    for entry in plan['entries']:
        day = date.fromisoformat(entry['start']); lines = []
        while day <= date.fromisoformat(entry['end']):
            stamp = int(datetime.combine(day, datetime.min.time(), timezone.utc).timestamp())*1000
            close = 102 if day.toordinal()%2 else 98
            lines.append(f'{stamp},100,110,90,{close},10,{stamp+86400000-1},1000,20,5,500,0\n')
            day += timedelta(days=1)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as z:
            z.writestr(entry['name'][:-4]+'.csv', ''.join(lines))
        raw = buffer.getvalue(); path = directory/entry['name']; path.write_bytes(raw)
        sha = hashlib.sha256(raw).hexdigest(); checksum = (sha+'  '+entry['name']+'\n').encode()
        Path(str(path)+'.CHECKSUM').write_bytes(checksum)
        Path(str(path)+'.receipt.json').write_text(json.dumps({**entry, 'sha256': sha,
            'checksum_sha256': hashlib.sha256(checksum).hexdigest(), 'rows': len(lines),
            'acquisition': 'direct_https_official_archive_no_redirect',
            'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}))
    for name in ('BINANCE_TERMS.md', 'ATTRIBUTION.txt'):
        (directory/name).write_text('SYNTHETIC TEST FIXTURE, not a provider document')
    source = spec['source']
    metadata = {'id': source['artifact_id'], 'name': source['artifact_name'], 'digest': source['artifact_digest'],
                'expired': False, 'workflow_run': {'id': source['acquisition_run_id'], 'head_sha': source['revision']}}
    return spec, metadata, directory


class PrimaryPredictiveTests(unittest.TestCase):
    def test_fictitious_package_replay_is_reproducible_without_accounts(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); spec, meta, _ = fixture(root)
            result = run(root/'package', meta, spec, root/'result')
            self.assertTrue(result['repeated_metrics_equal'])
            self.assertEqual(result['data_rows'], 110)
            self.assertEqual(result['metrics']['fixture']['fixed']['n'], 47)
            self.assertEqual(result['audit']['predictions'], 94)
            self.assertEqual(result['audit']['adaptive_updates'], 47)
            self.assertFalse(result['trading_backtest'])
            self.assertFalse(result['market_run_enabled'])
            self.assertNotIn('accounts', result)
            self.assertFalse(result['execution_costs_verified'])
            self.assertFalse(result['mirror_comparison_performed'])

    def test_pinned_artifact_identity_digest_run_and_expiry(self):
        with tempfile.TemporaryDirectory() as root:
            spec, meta, _ = fixture(Path(root))
            for key, value in (('id', 0), ('digest', 'changed'), ('expired', True)):
                changed = copy.deepcopy(meta); changed[key] = value
                with self.assertRaises(ValueError):
                    validate_artifact(changed, spec['source'])
            changed = copy.deepcopy(meta); changed['workflow_run']['head_sha'] = 'unknown'
            with self.assertRaises(ValueError):
                validate_artifact(changed, spec['source'])

    def test_checksum_tampering_blocks_before_prediction(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); spec, meta, directory = fixture(root)
            path = next(directory.glob('*.zip')); path.write_bytes(path.read_bytes()+b'tampered')
            with self.assertRaisesRegex(ValueError, 'reauditoría'):
                run(root/'package', meta, spec, root/'result')
            self.assertFalse((root/'result').exists())

    def test_missing_file_and_attribution_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); spec, meta, directory = fixture(root)
            (directory/'ATTRIBUTION.txt').unlink()
            with self.assertRaisesRegex(ValueError, 'atribución'):
                run(root/'package', meta, spec, root/'result')
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); spec, meta, directory = fixture(root)
            next(directory.glob('*.CHECKSUM')).unlink()
            with self.assertRaisesRegex(ValueError, 'reauditoría'):
                run(root/'package', meta, spec, root/'result')

    def test_output_exclusive_creation(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); spec, meta, _ = fixture(root); (root/'result').mkdir()
            with self.assertRaises(FileExistsError):
                run(root/'package', meta, spec, root/'result')

    def test_check_publication_rejects_nonaggregate_or_wrong_results(self):
        with self.assertRaises(ValueError):
            check_payload({'experiment_id': 'other', 'trading_backtest': False}, 'sha', 'https://github.com/')
        with self.assertRaises(ValueError):
            check_payload({'experiment_id': 'BINANCE-PRIMARY-PREDICTIVE-001', 'trading_backtest': False,
                           'observations': [1]}, 'sha', 'https://github.com/')
        with self.assertRaises(ValueError):
            check_payload({'experiment_id': 'BINANCE-PRIMARY-PREDICTIVE-001', 'trading_backtest': False,
                           'metrics': 'x'*61000}, 'sha', 'https://github.com/')

    def test_fictitious_summary_can_be_encoded_but_is_never_posted_by_tests(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); spec, meta, _ = fixture(root)
            summary = run(root/'package', meta, spec, root/'result')
            payload = check_payload(summary, 'fixture-sha', 'https://github.com/fixture')
            self.assertEqual(payload['head_sha'], 'fixture-sha')
            text = payload['output']['text']
            self.assertTrue(text.startswith('```json\n'))
            self.assertNotIn('observations', text)
