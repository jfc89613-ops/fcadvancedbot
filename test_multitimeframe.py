#!/usr/bin/env python3
"""
Script de prueba para el sistema multitimeframe
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from pro_bot.config import settings
from pro_bot.core.ws_multitimeframe import MultitimeframeWebSocket
from pro_bot.core.multitimeframe_manager import MultitimeframeDecisionManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("test_multitf")

class MultitimeframeTest:
    def __init__(self):
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.timeframes = ["1m", "3m", "5m"]
        self.min_confirmations = 2
        
        self.decision_manager = MultitimeframeDecisionManager(
            timeframes=self.timeframes,
            min_confirmations=self.min_confirmations
        )
        
        self.kline_count = 0
        
    def on_kline_received(self, symbol: str, timeframe: str, kline_data: dict):
        """Callback de prueba para klines"""
        self.kline_count += 1
        
        # Log cada 10 klines
        if self.kline_count % 10 == 0:
            price = float(kline_data.get('c', 0))
            log.info(f"📊 Received kline #{self.kline_count}: {symbol} {timeframe} @ {price}")
            
        # Simular decisión ML (aleatoria para prueba)
        import random
        signals = ['BUY', 'SELL', 'HOLD']
        signal = random.choice(signals)
        confidence = random.uniform(0.3, 0.9)
        price = float(kline_data.get('c', 0))
        
        # Agregar decisión al manager
        confirmed_signal = self.decision_manager.add_decision(
            symbol=symbol,
            timeframe=timeframe,
            signal=signal,
            confidence=confidence,
            price=price
        )
        
        if confirmed_signal:
            log.info(f"🎯 CONFIRMED SIGNAL: {confirmed_signal}")
            
    def test_websocket(self):
        """Probar el WebSocket multitimeframe"""
        log.info("🚀 Starting multitimeframe WebSocket test...")
        
        ws = MultitimeframeWebSocket(
            symbols=self.symbols,
            timeframes=self.timeframes,
            callback=self.on_kline_received
        )
        
        ws.start()
        
        try:
            # Ejecutar por 2 minutos
            import time
            for i in range(120):
                time.sleep(1)
                if i % 30 == 0:
                    stats = self.decision_manager.get_statistics()
                    log.info(f"📈 Test progress: {i}s, {stats['total_decisions']} decisions, {stats['confirmed_signals']} confirmed")
                    
        except KeyboardInterrupt:
            log.info("Test interrupted by user")
        finally:
            ws.stop()
            
        # Log estadísticas finales
        final_stats = self.decision_manager.get_statistics()
        log.info(f"✅ Test completed:")
        log.info(f"  └─ Klines received: {self.kline_count}")
        log.info(f"  └─ Decisions made: {final_stats['total_decisions']}")
        log.info(f"  └─ Confirmed signals: {final_stats['confirmed_signals']}")
        log.info(f"  └─ Confirmation rate: {final_stats['confirmation_rate']:.1f}%")

def main():
    """Función principal de prueba"""
    log.info("🔬 Multitimeframe System Test")
    
    # Verificar configuración
    if not settings.get('multitimeframe', {}).get('enabled', False):
        log.error("❌ Multitimeframe not enabled in config!")
        return
        
    test = MultitimeframeTest()
    test.test_websocket()

if __name__ == "__main__":
    main()
