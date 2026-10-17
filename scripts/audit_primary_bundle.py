"""Auditoría de cobertura, recibos, ZIP/checksum y comparación del paquete primario.

No autoaprueba procedencia local ni costos: un paquete coherente queda listo
para revisión, nunca aprobado para trading o replay de mercado por este script.
"""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from scripts.audit_primary_prices import read_archive
from scripts.collect_primary_archives import archive_plan


def audit_bundle(directory, plan, compare_mirror=True):
    directory = Path(directory)
    canonical_plan = archive_plan(plan['symbol'], date.fromisoformat(plan['start']), date.fromisoformat(plan['end']))
    if plan != canonical_plan:
        raise ValueError('Plan alterado: no coincide con el generador oficial restringido.')
    report = {'status': 'BLOCKED_MISSING_FILES', 'prices_verified': False, 'market_run_enabled': False,
              'symbol': plan['symbol'], 'start': plan['start'], 'end': plan['end'],
              'expected_archives': len(plan['entries']), 'valid_archives': 0, 'missing': [], 'errors': [],
              'missing_dates': [], 'extra_dates': [], 'compared_mirror_rows': 0,
              'mirror_mismatch_fields': 0, 'mirror_mismatch_examples': [],
              'provenance_review_required': True, 'costs_and_filters_review_required': True,
              'note': 'Direct-download receipts are local records, not authenticated exchange signatures. No automatic source approval.'}
    all_rows = {}
    for entry in plan['entries']:
        path = directory/entry['name']
        needed = [path, Path(str(path)+'.CHECKSUM'), Path(str(path)+'.receipt.json')]
        absent = [p.name for p in needed if not p.is_file()]
        if absent:
            report['missing'].extend(absent); continue
        try:
            parsed = read_archive(path)
            receipt = json.loads(needed[2].read_text())
            if not isinstance(receipt, dict):
                raise ValueError('Recibo debe ser un objeto JSON.')
            checksum_sha = hashlib.sha256(needed[1].read_bytes()).hexdigest()
            for field in ('name', 'symbol', 'url', 'checksum_url', 'start', 'end'):
                if receipt.get(field) != entry[field]:
                    raise ValueError(f'Recibo inconsistente en {field}.')
            if (receipt.get('sha256') != parsed['sha256'] or receipt.get('checksum_sha256') != checksum_sha or
                    receipt.get('rows') != len(parsed['rows']) or
                    receipt.get('acquisition') != 'direct_https_official_archive_no_redirect'):
                raise ValueError('Hash/conteo/método de adquisición del recibo inconsistente.')
            retrieved = datetime.fromisoformat(receipt['retrieved_at_utc'])
            if (retrieved.tzinfo is None or retrieved.astimezone(timezone.utc).date() <= date.fromisoformat(entry['end']) or
                    retrieved > datetime.now(timezone.utc)+timedelta(minutes=5)):
                raise ValueError('Tiempo de adquisición no válido para un archivo de sesiones completas.')
            expected_count = (date.fromisoformat(entry['end'])-date.fromisoformat(entry['start'])).days+1
            if len(parsed['rows']) != expected_count:
                raise ValueError('Archivo diario/mensual incompleto.')
            for day, row in parsed['rows'].items():
                if day in all_rows:
                    raise ValueError('Fecha duplicada entre archivos.')
                all_rows[day] = row
            report['valid_archives'] += 1
        except (ValueError, KeyError, OSError, ArithmeticError, UnicodeError, zipfile.BadZipFile) as error:
            report['errors'].append({'file': entry['name'], 'error': str(error)})
    expected_dates = set()
    current, end = date.fromisoformat(plan['start']), date.fromisoformat(plan['end'])
    while current <= end:
        expected_dates.add(current.isoformat()); current += timedelta(days=1)
    report['expected_rows'] = len(expected_dates)
    report['observed_rows'] = len(all_rows)
    report['missing_dates'] = sorted(expected_dates-set(all_rows))
    report['extra_dates'] = sorted(set(all_rows)-expected_dates)
    if report['errors']:
        report['status'] = 'BLOCKED_INVALID_PACKAGE'
    elif not report['missing'] and not report['missing_dates'] and not report['extra_dates']:
        report['status'] = 'CONSISTENT_PACKAGE_REQUIRES_PROVENANCE_COSTS_AND_FILTERS_REVIEW'
        # Candidato, no dataset aprobado. Nunca reemplaza la serie del espejo.
        text = io.StringIO(); writer = csv.writer(text, lineterminator='\n')
        writer.writerow(['date', 'open', 'close'])
        writer.writerows((d, all_rows[d]['open'], all_rows[d]['close']) for d in sorted(all_rows))
        candidate = directory/f'{plan["symbol"]}_candidate_daily.csv'
        from scripts.collect_primary_archives import atomic_new
        raw = text.getvalue().encode()
        atomic_new(candidate, raw)
        report['candidate_csv'] = str(candidate)
        report['candidate_csv_sha256'] = hashlib.sha256(raw).hexdigest()
        report['input_receipts_sha256'] = {e['name']: hashlib.sha256(
            (directory/(e['name']+'.receipt.json')).read_bytes()).hexdigest() for e in plan['entries']}
    mirror_path = Path('data/btc_sma200/raw.csv')
    if compare_mirror and plan['symbol'] == 'BTCUSDT' and mirror_path.exists():
        with mirror_path.open() as stream:
            for mirror in csv.DictReader(stream):
                day = mirror['open_time'][:10]
                if day not in all_rows:
                    continue
                report['compared_mirror_rows'] += 1
                for field, value in all_rows[day].items():
                    if Decimal(mirror[field]) != Decimal(value):
                        report['mirror_mismatch_fields'] += 1
                        if len(report['mirror_mismatch_examples']) < 30:
                            report['mirror_mismatch_examples'].append({'date': day, 'field': field,
                                'mirror': mirror[field], 'primary_candidate': value})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('data/primary_import'))
    parser.add_argument('--symbol', choices=('BTCUSDT', 'ETHUSDT', 'SOLUSDT'), default='BTCUSDT')
    args = parser.parse_args()
    plan_path = args.directory/f'{args.symbol}_plan.json'
    report = audit_bundle(args.directory, json.loads(plan_path.read_text()))
    output = Path('artifacts/primary_bundle'); output.mkdir(parents=True, exist_ok=True)
    path = output/f'{args.symbol}_report.json'
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ('status', 'expected_archives', 'valid_archives',
                                            'expected_rows', 'observed_rows', 'prices_verified', 'market_run_enabled')}, indent=2))
    print('Informe:', path)
    if report['status'].startswith('BLOCKED'):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
