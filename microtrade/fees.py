"""Tarifas documentadas, no cotización ni catálogo completo de un broker."""
REVIEWED = '2026-10-17'
PROFILES = {
    'kraken_spot_taker': {
        'name': 'Kraken Pro · spot · Tier 1 taker',
        'fee_pct': 0.80, 'min_fee': 0.0,
        'url': 'https://www.kraken.com/features/fee-schedule',
        'scope': 'Comisión spot de entrada: 0,80% por lado. No Instant Buy, futuros ni tarifas maker.',
    },
    'binance_spot_standard': {
        'name': 'Binance · spot · estándar sin descuento',
        'fee_pct': 0.10, 'min_fee': 0.0,
        'url': 'https://www.binance.com/en/support/faq/fee-structure-on-binance-115000429332',
        'scope': '0,10% por lado. Sin BNB, promociones ni VIP. USD/USDT no son equivalentes sin riesgo.',
    },
    'ibkr_fractional_reference': {
        'name': 'IBKR · referencia fraccionaria (simplificada)',
        'fee_pct': 1.0, 'min_fee': 0.01,
        'url': 'https://www.interactivebrokers.com/en/pricing/commissions-stocks.php',
        'scope': 'Solo fórmula fraccionaria de la nota publicada: mayor entre 1% y USD 0,01. No reproduce todas las rutas, planes ni tasas regulatorias.',
    },
}


def catalog():
    return [{'id': key, **value, 'reviewed': REVIEWED} for key, value in PROFILES.items()]
