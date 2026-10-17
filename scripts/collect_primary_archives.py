"""Kit portable de adquisición PRIMARIA: solo Binance spot oficial, nunca espejos.

Por defecto genera un plan sin hacer peticiones de red. --download es para un
entorno que permita data.binance.vision; NO se ejecuta desde esta sesión Arena.
Ejecutar desde la raíz del repo/kit: python -m scripts.collect_primary_archives.
"""
import argparse
import calendar
import hashlib
import json
import os
import tempfile
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

HOST = 'data.binance.vision'
SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')


def archive_plan(symbol, start, end):
    if symbol not in SYMBOLS or start > end:
        raise ValueError('Símbolo o rango no permitido.')
    entries = []
    current = start
    while current <= end:
        month_end = date(current.year, current.month, calendar.monthrange(current.year, current.month)[1])
        monthly = current.day == 1 and month_end <= end
        period = current.strftime('%Y-%m' if monthly else '%Y-%m-%d')
        name = f'{symbol}-1d-{period}.zip'
        frequency = 'monthly' if monthly else 'daily'
        url = f'https://{HOST}/data/spot/{frequency}/klines/{symbol}/1d/{name}'
        entries.append({'name': name, 'symbol': symbol, 'url': url, 'checksum_url': url+'.CHECKSUM',
                        'start': current.isoformat(), 'end': (month_end if monthly else current).isoformat()})
        current = (month_end if monthly else current)+timedelta(days=1)
    return {'schema_version': 1, 'source': 'Binance official spot archive', 'symbol': symbol,
            'start': start.isoformat(), 'end': end.isoformat(), 'entries': entries,
            'network_requests_if_uncached': len(entries)*2,
            'note': 'Plan is not acquired data and does not establish provenance or accuracy.'}


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != HOST or parsed.netloc != HOST or
            parsed.query or parsed.fragment or not parsed.path.startswith('/data/spot/') or
            '..' in parsed.path or '%' in parsed.path):
        raise ValueError('Solo HTTPS directo al archivo oficial spot está permitido.')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirección rechazada: no se permite cambiar de origen.')


def fetch_official(url, maximum):
    validate_url(url)
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': 'PrimaryResearchCollector/1.0'})
    with opener.open(request, timeout=60) as response:
        if response.geturl() != url or response.status != 200:
            raise ValueError('Respuesta oficial inesperada.')
        data = response.read(maximum+1)
        if len(data) > maximum:
            raise ValueError('Respuesta demasiado grande.')
    return data


def atomic_new(path, data):
    """Publica un archivo completo sin sobreescribir evidencia preexistente."""
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f'Archivo existente diferente: {path.name}. Usar directorio nuevo; no borrar evidencia.')
        return
    fd, temp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.link(temp, path)  # falla si otro proceso publicó ese destino
    finally:
        Path(temp).unlink(missing_ok=True)


def collect_entry(entry, directory):
    from scripts.audit_primary_prices import read_archive
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    archive = directory/entry['name']
    checksum_path = directory/(entry['name']+'.CHECKSUM')
    receipt_path = directory/(entry['name']+'.receipt.json')
    validate_url(entry['url']); validate_url(entry['checksum_url'])
    # Reutiliza solo un paquete completo y consistente; no fabrica recibos para archivos antiguos.
    if archive.exists() and checksum_path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        parsed = read_archive(archive)
        if (receipt.get('url') != entry['url'] or receipt.get('sha256') != parsed['sha256'] or
                receipt.get('checksum_sha256') != hashlib.sha256(checksum_path.read_bytes()).hexdigest() or
                receipt.get('acquisition') != 'direct_https_official_archive_no_redirect'):
            raise ValueError('Paquete previo no coincide con plan/recibo.')
        return receipt
    checksum = fetch_official(entry['checksum_url'], 4096)
    raw = fetch_official(entry['url'], 20_000_000)
    fields = checksum.decode().strip().split()
    sha = hashlib.sha256(raw).hexdigest()
    if len(fields) != 2 or fields[1].lstrip('*') != entry['name'] or fields[0].lower() != sha:
        raise ValueError('El checksum publicado no coincide: no se guarda como válido.')
    atomic_new(archive, raw); atomic_new(checksum_path, checksum)
    parsed = read_archive(archive)
    receipt = {**entry, 'sha256': sha, 'checksum_sha256': hashlib.sha256(checksum).hexdigest(),
               'acquisition': 'direct_https_official_archive_no_redirect',
               'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'rows': len(parsed['rows']),
               'attestation': 'Local receipt of direct HTTPS acquisition; not an exchange signature or external timestamp.'}
    atomic_new(receipt_path, json.dumps(receipt, indent=2).encode())
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', choices=SYMBOLS, default='BTCUSDT')
    parser.add_argument('--start', type=date.fromisoformat, default=date(2022, 1, 1))
    parser.add_argument('--end', type=date.fromisoformat, default=date(2026, 9, 26))
    parser.add_argument('--directory', type=Path, default=Path('data/primary_import'))
    parser.add_argument('--download', action='store_true', help='Realiza red oficial; ejecutar fuera de Arena donde esté permitido.')
    args = parser.parse_args()
    if args.end >= datetime.now(timezone.utc).date():
        parser.error('Solo días UTC completos anteriores a hoy.')
    plan = archive_plan(args.symbol, args.start, args.end)
    args.directory.mkdir(parents=True, exist_ok=True)
    plan_path = args.directory/f'{args.symbol}_plan.json'
    atomic_new(plan_path, json.dumps(plan, indent=2).encode())
    if not args.download:
        print(json.dumps({'status': 'PLAN_ONLY_NO_NETWORK', 'plan_path': str(plan_path),
                          'archives': len(plan['entries']), 'requests': plan['network_requests_if_uncached']}, indent=2))
        return
    for entry in plan['entries']:
        receipt = collect_entry(entry, args.directory)
        print(entry['name'], receipt['sha256'], flush=True)
    print('Descarga completa. Ejecutar audit_primary_bundle; NO habilita trading ni valida costos/filtros.')


if __name__ == '__main__':
    main()
