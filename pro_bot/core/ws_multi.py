import logging
import threading
import time
import json
import websocket
from ..config import settings

log = logging.getLogger("ws_multi")

def start_kline_multiplex(symbols, interval, callback):
    """
    Subscribe to kline close events for many symbols via futures multiplex socket.
    callback receives each message with 'data' that contains 's' (symbol), 'k' (kline).
    """
    
    # Preparar streams para klines
    streams = [f"{sym.lower()}@kline_{interval}" for sym in symbols]
    
    # URL del WebSocket de Binance Futures (mainnet)
    base_url = "wss://fstream.binance.com"
    
    # Crear URL para múltiples streams
    streams_param = "/".join(streams)
    ws_url = f"{base_url}/stream?streams={streams_param}"
    
    log.info(f"Connecting to WebSocket with {len(streams)} streams")
    
    # Variables de control
    ws_connected = threading.Event()
    ws_running = threading.Event()
    ws_running.set()
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            callback(data)
        except Exception as e:
            log.error(f"Error processing message: {e}")
    
    def on_error(ws, error):
        log.error(f"WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        log.warning("WebSocket connection closed")
        ws_connected.clear()
        
        # Intentar reconectar automáticamente
        if ws_running.is_set():
            log.info("Attempting to reconnect...")
            time.sleep(5)
            start_websocket()
    
    def on_open(ws):
        log.info("WebSocket connection established")
        ws_connected.set()
    
    def start_websocket():
        if not ws_running.is_set():
            return
            
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            ws.run_forever()
        except Exception as e:
            log.error(f"WebSocket connection failed: {e}")
            if ws_running.is_set():
                time.sleep(5)
                start_websocket()
    
    # Iniciar WebSocket en hilo separado
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()
    
    # Esperar a que se conecte
    if not ws_connected.wait(timeout=30):
        log.error("WebSocket connection timeout")
    
    # Clase wrapper para compatibilidad
    class SimpleSocketWrapper:
        def __init__(self, thread, running_event, connected_event):
            self.thread = thread
            self.running_event = running_event
            self.connected_event = connected_event
            
        def join(self):
            # Esperar indefinidamente hasta que se interrumpa
            try:
                while self.running_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                log.info("WebSocket interrupted by user")
                self.stop()
        
        def stop(self):
            log.info("Stopping WebSocket...")
            self.running_event.clear()
    
    return SimpleSocketWrapper(ws_thread, ws_running, ws_connected)
