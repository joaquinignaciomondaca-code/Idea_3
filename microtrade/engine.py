"""Simulación long/cash con señales al cierre y ejecución en la apertura siguiente.

Sin dependencias externas. CSV de un único instrumento: date,open,close.
Precios en USD, fracciones configurables y sin dividendos ni splits automáticos.
"""
from __future__ import annotations

import csv
import io
import math
import random
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_FLOOR
from datetime import date, timedelta
from .fees import PROFILES, REVIEWED


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    close: float


@dataclass(frozen=True)
class Config:
    capital: float = 20.0
    window: int = 30
    fee_pct: float = 0.8
    min_fee: float = 0.0
    spread_bps: float = 10.0
    slippage_bps: float = 5.0
    min_order: float = 1.0
    fractional: bool = True
    cadence: int = 5
    entry_fixed: float = 0.0
    entry_pct: float = 0.0
    exit_fixed: float = 0.0
    qty_step: float = 0.0
    min_qty: float = 0.0
    delay_bars: int = 0

    def validate(self):
        for name in ('capital', 'fee_pct', 'min_fee', 'spread_bps', 'slippage_bps', 'min_order', 'entry_fixed', 'entry_pct', 'exit_fixed', 'qty_step', 'min_qty'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f'{name}: se requiere un número finito.')
        if not 1 <= self.capital <= 1_000_000:
            raise ValueError('Capital permitido: USD 1 a 1.000.000.')
        if not isinstance(self.window, int) or isinstance(self.window, bool) or not 2 <= self.window <= 400:
            raise ValueError('La media debe tener entre 2 y 400 sesiones.')
        if not isinstance(self.cadence, int) or isinstance(self.cadence, bool) or not 1 <= self.cadence <= 60:
            raise ValueError('La revisión debe ser cada 1 a 60 sesiones.')
        if not isinstance(self.delay_bars, int) or isinstance(self.delay_bars, bool) or not 0 <= self.delay_bars <= 30:
            raise ValueError('Retraso debe ser un entero de 0 a 30 barras adicionales.')
        if not 0 <= self.qty_step <= 100 or not 0 <= self.min_qty <= 100:
            raise ValueError('Cantidad mínima o incremento fuera de rango.')
        if not isinstance(self.fractional, bool):
            raise ValueError('fractional debe ser booleano.')
        if not 0 <= self.fee_pct <= 10 or not 0 <= self.min_fee <= 100:
            raise ValueError('Comisiones fuera de rango.')
        if not 0 <= self.spread_bps <= 1000 or not 0 <= self.slippage_bps <= 1000:
            raise ValueError('Spread o deslizamiento fuera de rango.')
        if not 0 <= self.entry_pct <= 100 or not 0 <= self.entry_fixed <= 100000 or not 0 <= self.exit_fixed <= 100000:
            raise ValueError('Costos de acceso fuera de rango.')
        if self.entry_fixed + self.capital * self.entry_pct / 100 >= self.capital:
            raise ValueError('El costo de entrada consume todo el capital.')
        if not 0 <= self.min_order <= 100_000:
            raise ValueError('Orden mínima fuera de rango.')


def parse_csv(text: str) -> list[Bar]:
    if not isinstance(text, str) or len(text) > 2_000_000:
        raise ValueError('CSV demasiado grande (máximo 2 MB de texto).')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if reader.fieldnames != ['date', 'open', 'close']:
        raise ValueError('Cabecera exacta requerida: date,open,close (un instrumento, USD).')
    bars = []
    previous = None
    for index, row in enumerate(reader, 2):
        if len(bars) >= 5000:
            raise ValueError('Máximo 5.000 filas.')
        try:
            day = date.fromisoformat(row['date'])
            opening, closing = float(row['open']), float(row['close'])
            if not all(math.isfinite(p) and 0 < p <= 1e9 for p in (opening, closing)):
                raise ValueError()
            if previous is not None and day <= previous:
                raise ValueError()
            if None in row or any(v is None for v in row.values()):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ValueError(f'Fila {index}: fecha inválida/desordenada o precios no positivos.') from None
        bars.append(Bar(day.isoformat(), opening, closing))
        previous = day
    if len(bars) < 10:
        raise ValueError('Se necesitan al menos 10 sesiones.')
    return bars


def synthetic_bars(seed: int = 42, count: int = 504, scenario: str = 'mixed') -> list[Bar]:
    """Escenarios ficticios, sin calibración ni correspondencia con un activo real."""
    rng = random.Random(seed)
    bars = []
    day = date(2024, 1, 2)
    price = 100.0
    for i in range(count):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        if scenario == 'trend':
            drift, sigma = 0.0008, 0.009
        elif scenario == 'sideways':
            drift, sigma = 0.012 * math.log(100 / price), 0.012
        elif scenario == 'stress':
            drift, sigma = (-0.005, 0.025) if count * .4 < i < count * .55 else (0.0004, 0.012)
        else:
            phase = int(i / max(1, count / 4))
            drift, sigma = [(0.0008, .01), (-.0015, .017), (.0001, .012), (.001, .011)][min(phase, 3)]
        opening = price * math.exp(rng.gauss(0, sigma * .3))
        price = opening * math.exp(drift + rng.gauss(0, sigma * .85))
        bars.append(Bar(day.isoformat(), opening, price))
        day += timedelta(days=1)
    return bars


def floor_quantity(qty: float, step: float) -> float:
    if step <= 0:
        return qty
    return float((Decimal(str(qty)) / Decimal(str(step))).to_integral_value(rounding=ROUND_FLOOR) * Decimal(str(step)))


def simulate(bars: list[Bar], config: Config, strategy: str = 'trend', costs: bool = True,
             start_date: str | None = None, end_date: str | None = None,
             signals: dict[str, bool] | None = None) -> dict:
    config.validate()
    if len(bars) <= config.window:
        raise ValueError('El CSV debe tener más sesiones que la ventana de la media.')
    if strategy not in ('trend', 'hold', 'external'):
        raise ValueError('Estrategia desconocida.')
    if strategy == 'external':
        if not isinstance(signals, dict) or any(type(v) is not bool for v in signals.values()):
            raise ValueError('Señales externas: mapa fecha de cierre → booleano requerido.')
        valid_dates = {b.date for b in bars}
        if any(k not in valid_dates for k in signals):
            raise ValueError('Fecha de señal externa fuera de las barras.')
    elif signals is not None:
        raise ValueError('Las señales externas requieren strategy=external.')
    entry_cost = config.entry_fixed + config.capital * config.entry_pct / 100 if costs else 0.0
    cash, units = config.capital - entry_cost, 0.0
    fees = friction = 0.0
    orders, curve, skipped = [], [], []
    closes = [b.close for b in bars]
    # La primera operación posible es posterior al warm-up, para ambos modelos.
    start = config.window + config.delay_bars
    for i in range(start, len(bars)):
        bar = bars[i]
        if start_date and bar.date < start_date:
            continue
        if end_date and bar.date > end_date:
            break
        signal_index = i - config.delay_bars
        if strategy == 'external':
            # Solo consume la decisión del cierre ya completo correspondiente.
            # Una fecha ausente no ordena vender: significa no revisar.
            signal_date = bars[signal_index - 1].date
            should_review = signal_date in signals
            desired = signals.get(signal_date, False)
        else:
            should_review = (i - start) % config.cadence == 0
            desired = strategy == 'hold' or closes[signal_index - 1] > sum(closes[signal_index-config.window:signal_index]) / config.window
        if should_review:
            side = 'buy' if desired and units == 0 else 'sell' if not desired and units > 0 else None
            if side:
                rate = config.fee_pct / 100 if costs else 0
                minimum = config.min_fee if costs else 0
                # spread_bps es spread completo; se paga medio spread en cada lado.
                adverse = (config.spread_bps / 2 + config.slippage_bps) / 10000 if costs else 0
                fill = bar.open * (1 + adverse if side == 'buy' else 1 - adverse)
                if side == 'buy':
                    # Solución de notional + max(mínimo, notional*tasa) <= caja.
                    budget = min(cash / (1 + rate), cash - minimum)
                    qty = max(0.0, budget / fill)
                    if not config.fractional:
                        qty = math.floor(qty)
                else:
                    qty = units
                qty = floor_quantity(qty, config.qty_step)
                notional = qty * fill
                fee = max(minimum, notional * rate) if qty else 0
                reason = None
                if qty <= 0 or qty + 1e-12 < config.min_qty or notional + 1e-9 < config.min_order:
                    reason = 'Cantidad insuficiente u orden menor al mínimo.'
                elif side == 'sell' and cash + notional - fee < -1e-8:
                    reason = 'Caja insuficiente para la comisión de salida.'
                if reason:
                    skipped.append({'date': bar.date, 'side': side, 'reason': reason})
                else:
                    cash += -notional - fee if side == 'buy' else notional - fee
                    units = qty if side == 'buy' else max(0.0, units - qty)
                    if abs(cash) < 1e-9:
                        cash = 0.0
                    fees += fee
                    friction += abs(fill - bar.open) * qty
                    orders.append({'date': bar.date, 'signal_date': bars[signal_index-1].date, 'side': side,
                                   'quantity': qty, 'price': fill, 'notional': notional, 'fee': fee})
        nav = cash + units * bar.close
        curve.append({'date': bar.date, 'equity': nav, 'cash': cash, 'units': units})
    if not curve:
        raise ValueError('Sin barras evaluables después del warm-up y las fechas solicitadas.')
    # Escenario de liquidación al último cierre: fill hipotético, no operación intradía observada.
    closing = bars[next(j for j in range(len(bars)-1, -1, -1) if bars[j].date == curve[-1]['date'])].close
    adverse = (config.spread_bps / 2 + config.slippage_bps) / 10000 if costs else 0
    exit_price = closing * (1 - adverse)
    exit_qty = floor_quantity(units, config.qty_step)
    exit_notional = exit_qty * exit_price
    exit_fee = max(config.min_fee, exit_notional * config.fee_pct / 100) if costs and exit_qty else 0
    exit_possible = (units == 0 or (exit_qty > 0 and exit_qty + 1e-12 >= config.min_qty and
                     exit_notional + 1e-9 >= config.min_order and cash + exit_notional >= exit_fee))
    terminal_cash = cash + exit_notional - exit_fee - (config.exit_fixed if costs else 0) if exit_possible else None
    dust = max(0.0, units - exit_qty) if exit_possible else units
    values = [config.capital] + [p['equity'] for p in curve]
    peak, max_dd = config.capital, 0.0
    for value in values:
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1)
    return {'terminal': {'executable_under_assumptions': exit_possible, 'cash_after_sale_and_withdrawal': terminal_cash,
                         'exit_fee': exit_fee if exit_possible else None, 'dust_units': dust,
                         'cash_only_return_pct': (terminal_cash / config.capital - 1) * 100 if terminal_cash is not None else None},
            'curve': curve, 'orders': orders, 'skipped': skipped,
            'final': values[-1], 'pnl': values[-1] - config.capital,
            'return_pct': (values[-1] / config.capital - 1) * 100,
            'max_drawdown_pct': max_dd * 100, 'fees': fees, 'friction': friction,
            'open_units': units, 'cash': cash, 'trades': len(orders),
            'entry_cost': entry_cost,
            'after_exit_fixed': max(0.0, values[-1] - (config.exit_fixed if costs else 0)),
            'exit_fixed': config.exit_fixed if costs else 0}


def run_experiment(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('Se requiere un objeto JSON.')
    config_raw = payload.get('config', {})
    if not isinstance(config_raw, dict):
        raise ValueError('Configuración inválida.')
    config_raw = dict(config_raw)
    profile_id = payload.get('profile', 'kraken_spot_taker')
    if profile_id != 'custom' and profile_id not in PROFILES:
        raise ValueError('Perfil de comisiones desconocido.')
    if profile_id != 'custom':
        config_raw.update({k: PROFILES[profile_id][k] for k in ('fee_pct', 'min_fee')})
    try:
        config = Config(**config_raw)
    except TypeError:
        raise ValueError('Parámetros de configuración desconocidos.') from None
    config.validate()
    source = payload.get('source', 'synthetic')
    if source == 'csv':
        bars = parse_csv(payload.get('csv', ''))
        label = 'CSV del usuario · procedencia no verificada'
    elif source == 'synthetic':
        seed = payload.get('seed', 42)
        scenario = payload.get('scenario', 'mixed')
        if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 1_000_000:
            raise ValueError('Semilla: entero entre 0 y 1.000.000.')
        if scenario not in ('mixed', 'trend', 'sideways', 'stress'):
            raise ValueError('Escenario desconocido.')
        bars = synthetic_bars(seed=seed, scenario=scenario)
        label = 'Datos sintéticos · no son evidencia de rentabilidad'
    else:
        raise ValueError('Fuente desconocida.')
    net = simulate(bars, config)
    gross = simulate(bars, config, costs=False)
    benchmark = simulate(bars, config, strategy='hold')
    return {'profile': profile_id, 'fee_reviewed': REVIEWED, 'source': source, 'label': label, 'config': asdict(config),
            'seed': payload.get('seed', 42) if source == 'synthetic' else None,
            'scenario': payload.get('scenario', 'mixed') if source == 'synthetic' else None,
            'start': bars[config.window].date, 'end': bars[-1].date, 'sessions': len(net['curve']),
            'net': net, 'gross': gross, 'benchmark': benchmark,
            'warnings': [
                'Solo simulación. Sin órdenes reales ni conexión a un broker.',
                'Tarifas actuales estáticas: no son el histórico de tarifas del período simulado.',
                'Sin precisión de lotes/fees por venue; calendario sintético de lunes a viernes, no mercado cripto 24/7.',
                'Tarifa publicada ≠ costo total. Spread, slippage y mínimos son supuestos editables, no mediciones.',
                'Acceso/FX/retiro en cero significa no estimados; no confirma que sean gratis. Sin elegibilidad por país verificada.',
                'Una serie en USD. Sin dividendos, splits, impuestos, FX ni interés sobre caja.',
                'Valoración al último cierre; la posición final no se liquida ni se cobra su salida.',
                'Fills supuestos en la apertura siguiente. Sin colas, liquidez, parciales ni impacto variable.',
                'Bruto es una corrida sin costos: puede cambiar cantidades, operaciones y órdenes rechazadas.',
                'Fracciones y mínimos son supuestos; deben comprobarse para cada intermediario.',
            ]}
