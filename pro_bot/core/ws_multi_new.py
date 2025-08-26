import logging
import time
import threading
from unicorn_binance_websocket_api import BinanceWebSocketApiManager
from ..config import settings

log = logging.getLogger("ws_multi")

def start_kline_multiplex(symbols, interval, callback):
    """
    Subscribe to kline close events for many symbols via unicorn websocket manager.
    callback receives each message with 'data' that contains 's' (symbol), 'k' (kline).
    """
    # Determinar la URL del exchange basado en testnet
    if settings.testnet:
        exchange = "binance.com-futures-testnet"
    else:
        exchange = "binance.com-futures"
    
    # Crear el WebSocket manager
    ubwa = BinanceWebSocketApiManager(
        exchange=exchange,
        warn_on_update=False
    )
    
    # Preparar streams para klines (sin markets, solo channels)
    streams = [f"{sym.lower()}@kline_{interval}" for sym in symbols]
    
    # Crear el stream sin pasar markets para evitar duplicación
    stream_id = ubwa.create_stream(
        channels=streams,
        stream_label="kline_stream"
    )
    
    log.info(f"Created stream {stream_id} for {len(streams)} futures kline streams")
    
    # Función para procesar mensajes en un hilo separado
    def process_messages():
        log.info("Starting message processing thread...")
        while True:
            try:
                # Obtener el mensaje más antiguo del buffer (sin stream_id)
                oldest_data = ubwa.pop_stream_data_from_stream_buffer()
                if oldest_data:
                    # Llamar al callback con el mensaje
                    callback(oldest_data)
                else:
                    # Pequeña pausa si no hay datos
                    time.sleep(0.1)
            except Exception as e:
                log.error(f"Error processing WebSocket message: {e}")
                time.sleep(1)
    
    # Iniciar hilo de procesamiento
    thread = threading.Thread(target=process_messages, daemon=True)
    thread.start()
    
    # Clase wrapper para compatibilidad
    class UnicornSocketWrapper:
        def __init__(self, ubwa, stream_id, thread):
            self.ubwa = ubwa
            self.stream_id = stream_id
            self.thread = thread
            self._running = True
            
        def join(self):
            # Procesar mensajes en el hilo principal
            log.info("WebSocket is running. Press Ctrl+C to stop...")
            try:
                while self._running:
                    time.sleep(1)
                    # Verificar el estado del stream
                    if not self.ubwa.is_manager_stopping():
                        continue
                    else:
                        log.warning("WebSocket manager is stopping")
                        break
            except KeyboardInterrupt:
                log.info("WebSocket interrupted by user")
            except Exception as e:
                log.error(f"WebSocket error: {e}")
            finally:
                self.stop()
                
        def stop(self):
            # Detener el stream y el manager
            if self._running:
                self._running = False
                try:
                    self.ubwa.stop_stream(self.stream_id)
                    self.ubwa.stop_manager_with_all_streams()
                    log.info("WebSocket manager stopped")
                except Exception as e:
                    log.error(f"Error stopping WebSocket: {e}")
    
    return UnicornSocketWrapper(ubwa, stream_id, thread)
