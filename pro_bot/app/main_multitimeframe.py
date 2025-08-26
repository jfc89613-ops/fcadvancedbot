#!/usr/bin/env python3
"""
Main multitimeframe bot - Análisis de múltiples timeframes con confirmaciones
"""

import asyncio
import logging
import signal
import sys
import time
import threading
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from pro_bot.config import settings
from pro_bot.core.client import get_client
from pro_bot.core.symbols import get_trading_symbols
from pro_bot.core.execution import TradingEngine
from pro_bot.core.ws_multitimeframe import start_multitimeframe_websocket
from pro_bot.core.multitimeframe_manager import MultitimeframeDecisionManager
from pro_ml.live.inference_multi import MLInferenceEngine

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("main_multitf")

class MultitimeframeTradingBot:
    """Bot de trading con análisis multitimeframe"""
    
    def __init__(self):
        self.client = get_client()
        self.running = False
        
        # Configuración multitimeframe
        self.timeframes = settings.get('multitimeframe', {}).get('timeframes', ['1m', '3m', '5m'])
        self.min_confirmations = settings.get('multitimeframe', {}).get('min_confirmations', 2)
        self.enabled = settings.get('multitimeframe', {}).get('enabled', True)
        
        if not self.enabled:
            log.error("❌ Multitimeframe not enabled in config!")
            sys.exit(1)
            
        log.info(f"🎯 Multitimeframe Bot Configuration:")
        log.info(f"  └─ Timeframes: {self.timeframes}")
        log.info(f"  └─ Min confirmations: {self.min_confirmations}")
        
        # Componentes principales
        self.symbols = []
        self.trading_engine = None
        self.ml_engine = None
        self.decision_manager = None
        self.websocket = None
        
        # Buffers de datos por timeframe
        self.kline_buffers = {}
        
        # Estadísticas
        self.stats = {
            'klines_received': 0,
            'ml_predictions': 0,
            'confirmed_signals': 0,
            'trades_executed': 0,
            'start_time': time.time()
        }
        
    async def initialize(self):
        """Inicializar todos los componentes"""
        log.info("🚀 Initializing Multitimeframe Trading Bot...")
        
        # 1. Obtener símbolos
        self.symbols = get_trading_symbols(self.client)
        log.info(f"📊 Loaded {len(self.symbols)} trading symbols")
        
        # 2. Inicializar trading engine
        self.trading_engine = TradingEngine(self.client)
        await self.trading_engine.initialize()
        log.info("✅ Trading engine initialized")
        
        # 3. Inicializar ML inference engine
        self.ml_engine = MLInferenceEngine()
        await self.ml_engine.initialize()
        log.info("✅ ML inference engine initialized")
        
        # 4. Inicializar decision manager
        self.decision_manager = MultitimeframeDecisionManager(
            timeframes=self.timeframes,
            min_confirmations=self.min_confirmations
        )
        log.info("✅ Multitimeframe decision manager initialized")
        
        # 5. Inicializar buffers de klines
        for symbol in self.symbols:
            self.kline_buffers[symbol] = {}
            for tf in self.timeframes:
                self.kline_buffers[symbol][tf] = []
        log.info("✅ Kline buffers initialized")
        
        log.info("🎉 All components initialized successfully!")
        
    def start_websocket(self):
        """Iniciar el WebSocket multitimeframe"""
        log.info("📡 Starting multitimeframe WebSocket...")
        
        self.websocket = start_multitimeframe_websocket(
            symbols=self.symbols,
            timeframes=self.timeframes,
            callback=self._on_kline_received
        )
        
        log.info("✅ WebSocket started!")
        
    def _on_kline_received(self, symbol: str, timeframe: str, kline_data: dict):
        """
        Callback cuando se recibe un kline de cualquier timeframe
        
        Args:
            symbol: Símbolo del activo
            timeframe: Timeframe del kline
            kline_data: Datos del kline
        """
        try:
            self.stats['klines_received'] += 1
            
            # Agregar kline al buffer
            if symbol in self.kline_buffers and timeframe in self.kline_buffers[symbol]:
                buffer = self.kline_buffers[symbol][timeframe]
                buffer.append(kline_data)
                
                # Mantener solo los últimos 100 klines
                if len(buffer) > 100:
                    buffer.pop(0)
                    
            # Log cada 100 klines recibidos
            if self.stats['klines_received'] % 100 == 0:
                log.debug(f"📈 Received {self.stats['klines_received']} klines")
                
            # Procesar con ML si tenemos suficientes datos
            asyncio.create_task(self._process_ml_prediction(symbol, timeframe))
            
        except Exception as e:
            log.error(f"❌ Error processing kline for {symbol} {timeframe}: {e}")
            
    async def _process_ml_prediction(self, symbol: str, timeframe: str):
        """Procesar predicción ML para un símbolo y timeframe"""
        try:
            # Verificar que tenemos suficientes datos
            buffer = self.kline_buffers.get(symbol, {}).get(timeframe, [])
            if len(buffer) < 20:  # Necesitamos al menos 20 klines
                return
                
            # Obtener predicción del ML
            prediction = await self.ml_engine.predict(symbol, timeframe, buffer)
            if not prediction:
                return
                
            self.stats['ml_predictions'] += 1
            
            # Extraer información de la predicción
            signal = prediction.get('signal', 'HOLD')
            confidence = prediction.get('confidence', 0.0)
            price = float(buffer[-1].get('c', 0))  # Precio de cierre del último kline
            
            # Agregar decisión al manager
            confirmed_signal = self.decision_manager.add_decision(
                symbol=symbol,
                timeframe=timeframe,
                signal=signal,
                confidence=confidence,
                price=price
            )
            
            # Si hay señal confirmada, ejecutar trade
            if confirmed_signal:
                self.stats['confirmed_signals'] += 1
                await self._execute_confirmed_signal(confirmed_signal)
                
        except Exception as e:
            log.error(f"❌ Error in ML prediction for {symbol} {timeframe}: {e}")
            
    async def _execute_confirmed_signal(self, confirmed_signal: dict):
        """Ejecutar una señal confirmada"""
        try:
            symbol = confirmed_signal['symbol']
            signal = confirmed_signal['signal']
            avg_price = confirmed_signal['avg_price']
            confirmations = confirmed_signal['confirmations']
            
            log.info(f"🎯 Executing {signal} for {symbol}")
            log.info(f"  └─ Confirmations: {confirmations}/{len(self.timeframes)}")
            log.info(f"  └─ Avg price: {avg_price}")
            log.info(f"  └─ Confirming TFs: {', '.join(confirmed_signal['confirming_tfs'])}")
            
            # Verificar si ya tenemos posición
            position = await self.trading_engine.get_position(symbol)
            if position and position.get('positionAmt', 0) != 0:
                log.info(f"⚠️ Already have position in {symbol}, skipping")
                return
                
            # Ejecutar la entrada
            if signal == 'BUY':
                result = await self.trading_engine.enter_long_position(symbol)
            elif signal == 'SELL':
                result = await self.trading_engine.enter_short_position(symbol)
            else:
                return
                
            if result and result.get('success'):
                self.stats['trades_executed'] += 1
                log.info(f"✅ Trade executed successfully for {symbol}")
            else:
                log.error(f"❌ Failed to execute trade for {symbol}")
                
        except Exception as e:
            log.error(f"❌ Error executing confirmed signal: {e}")
            
    def start_statistics_thread(self):
        """Iniciar hilo de estadísticas"""
        def log_stats():
            while self.running:
                try:
                    time.sleep(300)  # Log cada 5 minutos
                    
                    runtime = time.time() - self.stats['start_time']
                    hours = runtime / 3600
                    
                    log.info(f"📊 Multitimeframe Bot Statistics ({hours:.1f}h runtime):")
                    log.info(f"  └─ Klines received: {self.stats['klines_received']}")
                    log.info(f"  └─ ML predictions: {self.stats['ml_predictions']}")
                    log.info(f"  └─ Confirmed signals: {self.stats['confirmed_signals']}")
                    log.info(f"  └─ Trades executed: {self.stats['trades_executed']}")
                    
                    # Log estadísticas del decision manager
                    self.decision_manager.log_status()
                    
                    # Cleanup de decisiones antiguas
                    self.decision_manager.cleanup_old_decisions()
                    
                except Exception as e:
                    log.error(f"❌ Error in statistics thread: {e}")
                    
        stats_thread = threading.Thread(target=log_stats, daemon=True)
        stats_thread.start()
        
    def setup_signal_handlers(self):
        """Configurar manejadores de señales para cierre graceful"""
        def signal_handler(signum, frame):
            log.info(f"🛑 Received signal {signum}, shutting down...")
            self.running = False
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def run(self):
        """Ejecutar el bot principal"""
        try:
            self.running = True
            self.setup_signal_handlers()
            
            # Inicializar componentes
            await self.initialize()
            
            # Iniciar WebSocket
            self.start_websocket()
            
            # Iniciar hilo de estadísticas
            self.start_statistics_thread()
            
            log.info("🚀 Multitimeframe Trading Bot is running!")
            log.info("Press Ctrl+C to stop...")
            
            # Loop principal
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            log.error(f"❌ Critical error in main loop: {e}")
        finally:
            await self.cleanup()
            
    async def cleanup(self):
        """Limpieza al cerrar"""
        log.info("🧹 Cleaning up...")
        
        if self.websocket:
            self.websocket.stop()
            
        if self.trading_engine:
            await self.trading_engine.cleanup()
            
        if self.ml_engine:
            await self.ml_engine.cleanup()
            
        log.info("✅ Cleanup completed")

async def main():
    """Función principal"""
    log.info("🎯 Starting Multitimeframe Trading Bot...")
    
    bot = MultitimeframeTradingBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("👋 Bot stopped by user")
    except Exception as e:
        log.error(f"❌ Fatal error: {e}")
        sys.exit(1)
