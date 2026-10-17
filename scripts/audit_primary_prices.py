"""Audita archivos originales importados y compara con el espejo histórico.

Uso: python -m scripts.audit_primary_prices --directory data/primary_import
No realiza descargas fuera de los hosts permitidos. Un checksum local no autentica
el origen: la verificación de procedencia se informa separada y no se autoaprueba.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


def read_archive(path):
    match = re.fullmatch(r'(BTCUSDT|ETHUSDT|SOLUSDT)-1d-(\d{4}-\d{2}(?:-\d{2})?)\.zip', path.name)
    if not match:
        raise ValueError('Nombre de archivo no admitido: solo spot diario BTC/ETH/SOL USDT.')
    raw = path.read_bytes()
    if len(raw) > 20_000_000:
        raise ValueError('Archivo demasiado grande.')
    checksum_file = Path(str(path)+'.CHECKSUM')
    fields = checksum_file.read_text().strip().split()
    if len(fields) != 2 or fields[1].lstrip('*') != path.name:
        raise ValueError('CHECKSUM debe identificar exactamente este archivo.')
    digest = hashlib.sha256(raw).hexdigest()
    if fields[0].lower() != digest:
        raise ValueError('Checksum incorrecto.')
    expected = path.stem+'.csv'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.namelist() != [expected] or z.getinfo(expected).file_size > 20_000_000:
            raise ValueError('Contenido ZIP inesperado o excesivo.')
        rows = list(csv.reader(io.StringIO(z.read(expected).decode('utf-8-sig'))))
    result = {}
    for row in rows:
        if len(row) != 12:
            raise ValueError('Kline debe tener 12 campos, sin cabecera.')
        stamp = int(row[0])
        divisor = 1_000_000 if stamp >= 10**15 else 1000
        if stamp % (86400*divisor):
            raise ValueError('Apertura no coincide con medianoche UTC.')
        day = datetime.fromtimestamp(stamp//divisor, timezone.utc).date().isoformat()
        if not day.startswith(match[2]):
            raise ValueError('Fecha fuera del archivo declarado.')
        if int(row[6]) != stamp+86400*divisor-1:
            raise ValueError('Cierre temporal no corresponde a vela diaria completa.')
        values = [Decimal(v) for v in row[1:6]]
        if any(not v.is_finite() or v <= 0 for v in values):
            raise ValueError('OHLC/volumen inválido.')
        o, h, l, c, volume = values
        if not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError('OHLC inconsistente.')
        if day in result:
            raise ValueError('Fecha duplicada.')
        result[day] = dict(zip(('open','high','low','close','volume'), map(str, values)))
    if not result:
        raise ValueError('Archivo vacío.')
    dates = sorted(result)
    for a, b in zip(dates, dates[1:]):
        if (datetime.fromisoformat(b)-datetime.fromisoformat(a)).days != 1:
            raise ValueError('Hueco diario dentro del archivo.')
    return {'symbol': match[1], 'sha256': digest, 'rows': result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path('data/primary_import'))
    args = parser.parse_args()
    output = Path('artifacts/primary_audit'); output.mkdir(parents=True, exist_ok=True)
    mirror_path = Path('data/btc_sma200/raw.csv')
    mirror = {r['open_time'][:10]: r for r in csv.DictReader(mirror_path.open())} if mirror_path.exists() else {}
    report = {'status': 'BLOCKED_NO_PRIMARY_PRICE_FILES', 'prices_verified': False,
              'provenance': 'Not automatically authenticated: retain official download URL, retrieval time and original CHECKSUM.',
              'files': [], 'errors': [], 'compared_rows': 0, 'mismatches': [],
              'note': 'Official GitHub correction logs contain archive checksums, not candles. No primary price verification can be inferred from those logs.'}
    seen = {}
    for path in sorted(args.directory.glob('*.zip')):
        try:
            archive = read_archive(path)
            for day, row in archive['rows'].items():
                key = archive['symbol'], day
                if key in seen and seen[key] != row:
                    raise ValueError('Archivos primarios con valores contradictorios para la misma fecha.')
                seen[key] = row
                if archive['symbol'] == 'BTCUSDT' and day in mirror:
                    report['compared_rows'] += 1
                    for field, value in row.items():
                        if Decimal(mirror[day][field]) != Decimal(value):
                            report['mismatches'].append({'date': day, 'field': field,
                                'mirror': mirror[day][field], 'imported_primary_claim': value})
            report['files'].append({'name': path.name, 'sha256': archive['sha256'],
                                    'symbol': archive['symbol'], 'rows': len(archive['rows'])})
        except (ValueError, OSError, zipfile.BadZipFile, ArithmeticError) as error:
            report['errors'].append({'file': path.name, 'error': str(error)})
    if report['errors']:
        report['status'] = 'BLOCKED_INVALID_IMPORT'
    elif report['files']:
        report['status'] = 'BLOCKED_MISMATCH' if report['mismatches'] else 'LOCAL_FILES_CONSISTENT_PROVENANCE_AND_COVERAGE_REVIEW_REQUIRED'
    (output/'price_audit.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('files','mismatches')}, indent=2))


if __name__ == '__main__':
    main()
