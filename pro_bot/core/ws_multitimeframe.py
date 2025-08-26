import logging
import time
import threading
from collections import defaultdict
from unicorn_binance_websocket_api import BinanceWebSocketApiManager
from ..config import settings

log = logging.getLogger("ws_multitf")

class MultitimeframeWebSocket:
    def __init__(self, symbols, timeframes, callback):
        """
        WebSocket manager para múltiples timeframes
        
        Args:
            symbols: Lista de símbolos a seguir
            timeframes: Lista de timeframes ["1m", "3m", "5m"]
            callback: Función que recibe (symbol, timeframe, kline_data)
        """
        self.symbols = symbols
        self.timeframes = timeframes
        self.callback = callback
        
        # Exchange para mainnet
        self.exchange = "binance.com-futures"
        
        # Crear el WebSocket manager
        self.ubwa = BinanceWebSocketApiManager(
            exchange=self.exchange,
            warn_on_update=False
        )
        
        # Contadores para estadísticas
        self.message_counts = defaultdict(lambda: defaultdict(int))
        self.total_messages = 0
        
        log.info(f"🔄 Initializing MultitimeframeWebSocket")
        log.info(f"📊 Symbols: {len(symbols)} | Timeframes: {timeframes}")
        
    def start(self):
        """Iniciar el WebSocket multitimeframe"""
        # Crear streams para cada combinación símbolo-timeframe
        all_streams = []
        for symbol in self.symbols:
            for tf in self.timeframes:
                stream = f"{symbol.lower()}@kline_{tf}"
                all_streams.append(stream)
        
        # Crear el stream único con todos los canales
        self.stream_id = self.ubwa.create_stream(
            channels=all_streams,
            stream_label="multitimeframe_stream"
        )
        
        log.info(f"✅ Created stream {self.stream_id} for {len(all_streams)} channels")
        log.info(f"🎯 Total combinations: {len(self.symbols)} symbols × {len(self.timeframes)} TF = {len(all_streams)}")
        
        # Iniciar el hilo de procesamiento de mensajes
        self.processing_thread = threading.Thread(target=self._process_messages, daemon=True)
        self.processing_thread.start()
        
        # Iniciar hilo de estadísticas
        self.stats_thread = threading.Thread(target=self._log_statistics, daemon=True)
        self.stats_thread.start()
        
        log.info("🚀 MultitimeframeWebSocket started!")
        
    def _process_messages(self):
        """Procesar mensajes del WebSocket en hilo separado"""
        log.info("📡 Starting multitimeframe message processing...")
        
        while True:
            try:
                # Obtener mensaje del buffer
                oldest_data = self.ubwa.pop_stream_data_from_stream_buffer()
                if oldest_data:
                    self._handle_message(oldest_data)
                else:
                    # Pequeña pausa si no hay datos
                    time.sleep(0.01)
            except Exception as e:
                log.error(f"❌ Error processing multitimeframe message: {e}")
                time.sleep(1)
                
    def _handle_message(self, data):
        """Manejar un mensaje individual"""
        try:
            self.total_messages += 1
            
            # Validar estructura del mensaje
            if not data or 'data' not in data:
                return
                
            msg_data = data['data']
            event_type = msg_data.get('e')
            
            if event_type != 'kline':
                return
                
            k = msg_data.get('k')
            if not k:
                return
                
            # Solo procesar klines cerradas
            if not k.get('x'):
                return
                
            symbol = k.get('s')
            interval = k.get('i')  # Timeframe del kline
            
            if not symbol or not interval:
                return
                
            # Actualizar contadores
            self.message_counts[symbol][interval] += 1
            
            # Llamar al callback con símbolo, timeframe y datos del kline
            self.callback(symbol, interval, k)
            
        except Exception as e:
            log.error(f"❌ Error handling message: {e}")
            
    def _log_statistics(self):
        """Log periódico de estadísticas"""
        while True:
            try:
                time.sleep(60)  # Log cada minuto
                
                if self.total_messages > 0:
                    log.info(f"📈 MultitimeframeWS Stats: {self.total_messages} total messages")
                    
                    # Log por símbolo y timeframe
                    for symbol, tf_counts in list(self.message_counts.items())[:3]:  # Solo primeros 3 símbolos
                        tf_stats = ", ".join([f"{tf}:{count}" for tf, count in tf_counts.items()])
                        log.info(f"  └─ {symbol}: {tf_stats}")
                        
            except Exception as e:
                log.error(f"❌ Error in statistics thread: {e}")
                
    def stop(self):
        """Detener el WebSocket"""
        try:
            if hasattr(self, 'ubwa'):
                self.ubwa.stop_manager_with_all_streams()
            log.info("🛑 MultitimeframeWebSocket stopped")
        except Exception as e:
            log.error(f"❌ Error stopping WebSocket: {e}")
            
def start_multitimeframe_websocket(symbols, timeframes, callback):
    """
    Función de conveniencia para iniciar WebSocket multitimeframe
    
    Args:
        symbols: Lista de símbolos
        timeframes: Lista de timeframes ["1m", "3m", "5m"] 
        callback: Función callback(symbol, timeframe, kline_data)
    """
    ws = MultitimeframeWebSocket(symbols, timeframes, callback)
    ws.start()
    return ws
