import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("multitf_manager")

@dataclass
class TimeframeDecision:
    """Decisión de un timeframe específico"""
    symbol: str
    timeframe: str
    signal: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    timestamp: float
    price: float

class MultitimeframeDecisionManager:
    """Gestor de decisiones multitimeframe"""
    
    def __init__(self, timeframes: List[str], min_confirmations: int = 2, 
                 decision_window: int = 300):  # 5 minutos de ventana
        """
        Args:
            timeframes: Lista de timeframes ["1m", "3m", "5m"]
            min_confirmations: Mínimo de timeframes que deben coincidir
            decision_window: Ventana de tiempo en segundos para considerar decisiones válidas
        """
        self.timeframes = timeframes
        self.min_confirmations = min_confirmations
        self.decision_window = decision_window
        
        # Almacenar las últimas decisiones por símbolo y timeframe
        self.decisions: Dict[str, Dict[str, TimeframeDecision]] = defaultdict(dict)
        
        # Historia de decisiones para análisis
        self.decision_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Estadísticas
        self.stats = {
            'total_decisions': 0,
            'confirmed_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'by_timeframe': defaultdict(int)
        }
        
        log.info(f"🎯 MultitimeframeDecisionManager initialized")
        log.info(f"📊 Timeframes: {timeframes} | Min confirmations: {min_confirmations}")
        
    def add_decision(self, symbol: str, timeframe: str, signal: str, 
                    confidence: float, price: float):
        """
        Agregar una nueva decisión de timeframe
        
        Args:
            symbol: Símbolo del activo
            timeframe: Timeframe de la decisión
            signal: 'BUY', 'SELL', 'HOLD'
            confidence: Nivel de confianza [0-1]
            price: Precio actual
        """
        timestamp = time.time()
        
        decision = TimeframeDecision(
            symbol=symbol,
            timeframe=timeframe,
            signal=signal,
            confidence=confidence,
            timestamp=timestamp,
            price=price
        )
        
        # Almacenar la decisión
        self.decisions[symbol][timeframe] = decision
        
        # Agregar a la historia
        self.decision_history[symbol].append(decision)
        
        # Actualizar estadísticas
        self.stats['total_decisions'] += 1
        self.stats['by_timeframe'][timeframe] += 1
        if signal == 'BUY':
            self.stats['buy_signals'] += 1
        elif signal == 'SELL':
            self.stats['sell_signals'] += 1
            
        log.debug(f"📝 {symbol} {timeframe}: {signal} (conf={confidence:.2f}, price={price})")
        
        # Verificar si hay una señal confirmada
        confirmed_signal = self._check_confirmation(symbol)
        if confirmed_signal:
            self.stats['confirmed_signals'] += 1
            log.info(f"✅ {symbol}: CONFIRMED {confirmed_signal['signal']} signal!")
            log.info(f"  └─ Confirmations: {confirmed_signal['confirmations']}/{len(self.timeframes)}")
            log.info(f"  └─ Timeframes: {', '.join(confirmed_signal['confirming_tfs'])}")
            return confirmed_signal
            
        return None
        
    def _check_confirmation(self, symbol: str) -> Optional[Dict]:
        """
        Verificar si hay confirmación suficiente para una señal
        
        Returns:
            Dict con información de la señal confirmada o None
        """
        current_time = time.time()
        symbol_decisions = self.decisions.get(symbol, {})
        
        # Filtrar decisiones recientes y válidas
        valid_decisions = {}
        for tf, decision in symbol_decisions.items():
            if (current_time - decision.timestamp) <= self.decision_window:
                if decision.signal in ['BUY', 'SELL']:  # Ignorar HOLD
                    valid_decisions[tf] = decision
                    
        if len(valid_decisions) < self.min_confirmations:
            return None
            
        # Contar señales por tipo
        signal_counts = defaultdict(list)
        for tf, decision in valid_decisions.items():
            signal_counts[decision.signal].append((tf, decision))
            
        # Verificar si alguna señal tiene suficientes confirmaciones
        for signal, decisions_list in signal_counts.items():
            if len(decisions_list) >= self.min_confirmations:
                # Calcular confianza promedio y precio promedio
                avg_confidence = sum(d[1].confidence for d in decisions_list) / len(decisions_list)
                avg_price = sum(d[1].price for d in decisions_list) / len(decisions_list)
                confirming_tfs = [d[0] for d in decisions_list]
                
                return {
                    'symbol': symbol,
                    'signal': signal,
                    'confirmations': len(decisions_list),
                    'avg_confidence': avg_confidence,
                    'avg_price': avg_price,
                    'confirming_tfs': confirming_tfs,
                    'timestamp': current_time
                }
                
        return None
        
    def get_current_status(self, symbol: str) -> Dict:
        """Obtener el estado actual de las decisiones para un símbolo"""
        symbol_decisions = self.decisions.get(symbol, {})
        current_time = time.time()
        
        status = {
            'symbol': symbol,
            'timeframes': {},
            'summary': {
                'total_tfs': len(self.timeframes),
                'active_tfs': 0,
                'buy_count': 0,
                'sell_count': 0,
                'hold_count': 0
            }
        }
        
        for tf in self.timeframes:
            if tf in symbol_decisions:
                decision = symbol_decisions[tf]
                age = current_time - decision.timestamp
                
                if age <= self.decision_window:
                    status['timeframes'][tf] = {
                        'signal': decision.signal,
                        'confidence': decision.confidence,
                        'price': decision.price,
                        'age_seconds': age
                    }
                    status['summary']['active_tfs'] += 1
                    
                    if decision.signal == 'BUY':
                        status['summary']['buy_count'] += 1
                    elif decision.signal == 'SELL':
                        status['summary']['sell_count'] += 1
                    else:
                        status['summary']['hold_count'] += 1
                        
        return status
        
    def get_statistics(self) -> Dict:
        """Obtener estadísticas del manager"""
        total_decisions = self.stats['total_decisions']
        confirmed_ratio = (self.stats['confirmed_signals'] / max(total_decisions, 1)) * 100
        
        return {
            'total_decisions': total_decisions,
            'confirmed_signals': self.stats['confirmed_signals'],
            'confirmation_rate': confirmed_ratio,
            'buy_signals': self.stats['buy_signals'],
            'sell_signals': self.stats['sell_signals'],
            'by_timeframe': dict(self.stats['by_timeframe']),
            'active_symbols': len(self.decisions)
        }
        
    def cleanup_old_decisions(self):
        """Limpiar decisiones antiguas"""
        current_time = time.time()
        cleanup_count = 0
        
        for symbol in list(self.decisions.keys()):
            for tf in list(self.decisions[symbol].keys()):
                decision = self.decisions[symbol][tf]
                if (current_time - decision.timestamp) > (self.decision_window * 2):
                    del self.decisions[symbol][tf]
                    cleanup_count += 1
                    
            # Si no quedan decisiones para el símbolo, eliminarlo
            if not self.decisions[symbol]:
                del self.decisions[symbol]
                
        if cleanup_count > 0:
            log.debug(f"🧹 Cleaned up {cleanup_count} old decisions")
            
    def log_status(self):
        """Log del estado actual"""
        stats = self.get_statistics()
        log.info(f"📊 Multitimeframe Stats:")
        log.info(f"  └─ Total decisions: {stats['total_decisions']}")
        log.info(f"  └─ Confirmed signals: {stats['confirmed_signals']} ({stats['confirmation_rate']:.1f}%)")
        log.info(f"  └─ Active symbols: {stats['active_symbols']}")
        
        if stats['by_timeframe']:
            tf_stats = ", ".join([f"{tf}:{count}" for tf, count in stats['by_timeframe'].items()])
            log.info(f"  └─ By timeframe: {tf_stats}")
