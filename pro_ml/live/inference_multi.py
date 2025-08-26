#!/usr/bin/env python3
"""
ML Inference Engine para multitimeframe - Usando LiveModel existente
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# Agregar directorios al path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

# Importar directamente el archivo para evitar conflictos circulares
import importlib.util
spec = importlib.util.spec_from_file_location("live_model", str(Path(__file__).parent.parent / "core" / "live" / "inference_multi.py"))
live_model_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_model_module)
LiveModel = live_model_module.LiveModel

from pro_ml.core.features.microstructure import create_features_from_klines

log = logging.getLogger("ml_inference")

class MLInferenceEngine:
    """Engine de inferencia ML para múltiples timeframes"""
    
    def __init__(self, base_model_dir: str = "outputs/models"):
        """
        Args:
            base_model_dir: Directorio base donde están los modelos por símbolo
        """
        self.base_model_dir = base_model_dir
        self.live_model = None
        
        # Configuración de probabilidades por timeframe
        self.timeframe_config = {
            '1m': {'prob_long': 0.57, 'prob_short': 0.43},
            '3m': {'prob_long': 0.55, 'prob_short': 0.45}, 
            '5m': {'prob_long': 0.53, 'prob_short': 0.47}
        }
        
        # Cache de features por símbolo/timeframe
        self.feature_cache = {}
        
        # Estadísticas
        self.stats = {
            'predictions_made': 0,
            'by_timeframe': {},
            'by_symbol': {},
            'signal_distribution': {'LONG': 0, 'SHORT': 0, 'NEUTRAL': 0}
        }
        
        log.info(f"🧠 MLInferenceEngine initialized")
        log.info(f"📁 Model directory: {base_model_dir}")
        
    async def initialize(self):
        """Inicializar el engine"""
        try:
            # Crear el LiveModel con configuración base
            self.live_model = LiveModel(
                base_dir=self.base_model_dir,
                prob_long=0.55,
                prob_short=0.45
            )
            
            log.info("✅ LiveModel initialized successfully")
            
            # Verificar si existen algunos modelos
            model_dir = Path(self.base_model_dir)
            if model_dir.exists():
                symbol_dirs = [d for d in model_dir.iterdir() if d.is_dir()]
                log.info(f"📊 Found {len(symbol_dirs)} symbol directories")
                
                # Log primeros directorios como ejemplo
                for symbol_dir in list(symbol_dirs)[:3]:
                    model_file = symbol_dir / "best_model.joblib"
                    meta_file = symbol_dir / "metadata.joblib"
                    status = "✅" if model_file.exists() and meta_file.exists() else "❌"
                    log.info(f"  {status} {symbol_dir.name}")
            else:
                log.warning(f"⚠️ Model directory {model_dir} does not exist")
                
        except Exception as e:
            log.error(f"❌ Error initializing MLInferenceEngine: {e}")
            raise
            
    async def predict(self, symbol: str, timeframe: str, kline_buffer: List[Dict]) -> Optional[Dict]:
        """
        Hacer predicción para un símbolo y timeframe
        
        Args:
            symbol: Símbolo del activo
            timeframe: Timeframe ('1m', '3m', '5m')
            kline_buffer: Lista de klines históricos
            
        Returns:
            Dict con 'signal', 'confidence', 'probability' o None si no se puede predecir
        """
        try:
            # Verificar que tenemos suficientes datos
            if len(kline_buffer) < 20:
                return None
                
            # Crear features a partir de los klines
            features = self._create_features_from_klines(kline_buffer)
            if features is None or features.empty:
                return None
                
            # Obtener la última fila de features
            latest_features = features.iloc[-1]
            
            # Obtener configuración específica del timeframe
            tf_config = self.timeframe_config.get(timeframe, {
                'prob_long': 0.55, 
                'prob_short': 0.45
            })
            
            # Actualizar probabilidades del modelo temporalmente
            original_long = self.live_model.prob_long
            original_short = self.live_model.prob_short
            
            self.live_model.prob_long = tf_config['prob_long']
            self.live_model.prob_short = tf_config['prob_short']
            
            try:
                # Hacer la predicción
                signal, probability = self.live_model.decide(symbol, latest_features)
                
                # Mapear señales
                if signal == "LONG":
                    mapped_signal = "BUY"
                elif signal == "SHORT":
                    mapped_signal = "SELL"
                else:
                    mapped_signal = "HOLD"
                    
                # Calcular confianza basada en qué tan lejos está la probabilidad del umbral
                if signal == "LONG":
                    confidence = min(1.0, (probability - tf_config['prob_long']) / (1.0 - tf_config['prob_long']))
                elif signal == "SHORT":
                    confidence = min(1.0, (tf_config['prob_short'] - probability) / tf_config['prob_short'])
                else:
                    # Para NEUTRAL, confianza basada en qué tan cerca está del centro
                    center = (tf_config['prob_long'] + tf_config['prob_short']) / 2
                    distance_from_center = abs(probability - center)
                    max_distance = max(abs(tf_config['prob_long'] - center), abs(tf_config['prob_short'] - center))
                    confidence = 1.0 - (distance_from_center / max_distance)
                    
                confidence = max(0.0, min(1.0, confidence))
                
                # Actualizar estadísticas
                self.stats['predictions_made'] += 1
                if timeframe not in self.stats['by_timeframe']:
                    self.stats['by_timeframe'][timeframe] = 0
                self.stats['by_timeframe'][timeframe] += 1
                
                if symbol not in self.stats['by_symbol']:
                    self.stats['by_symbol'][symbol] = 0
                self.stats['by_symbol'][symbol] += 1
                
                self.stats['signal_distribution'][mapped_signal] += 1
                
                log.debug(f"🎯 {symbol} {timeframe}: {mapped_signal} (p={probability:.3f}, conf={confidence:.3f})")
                
                return {
                    'signal': mapped_signal,
                    'confidence': confidence,
                    'probability': probability,
                    'timeframe': timeframe,
                    'symbol': symbol
                }
                
            finally:
                # Restaurar probabilidades originales
                self.live_model.prob_long = original_long
                self.live_model.prob_short = original_short
                
        except FileNotFoundError:
            # Modelo no existe para este símbolo
            log.debug(f"📭 No model found for {symbol}")
            return None
        except Exception as e:
            log.error(f"❌ Error in prediction for {symbol} {timeframe}: {e}")
            return None
            
    def _create_features_from_klines(self, kline_buffer: List[Dict]) -> Optional[pd.DataFrame]:
        """
        Crear features a partir de los klines usando el módulo existente
        
        Args:
            kline_buffer: Lista de diccionarios con datos de klines
            
        Returns:
            DataFrame con features o None si hay error
        """
        try:
            # Convertir klines a DataFrame
            df_data = []
            for kline in kline_buffer:
                df_data.append({
                    'timestamp': int(kline.get('t', 0)),  # Timestamp de apertura
                    'open': float(kline.get('o', 0)),
                    'high': float(kline.get('h', 0)),
                    'low': float(kline.get('l', 0)),
                    'close': float(kline.get('c', 0)),
                    'volume': float(kline.get('v', 0)),
                    'close_time': int(kline.get('T', 0)),
                    'quote_volume': float(kline.get('q', 0)),
                    'trades': int(kline.get('n', 0)),
                    'taker_buy_base': float(kline.get('V', 0)),
                    'taker_buy_quote': float(kline.get('Q', 0))
                })
                
            if not df_data:
                return None
                
            df = pd.DataFrame(df_data)
            
            # Convertir timestamp a datetime si es necesario
            if 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('datetime', inplace=True)
                
            # Usar la función existente para crear features
            features_df = create_features_from_klines(df)
            
            return features_df
            
        except Exception as e:
            log.error(f"❌ Error creating features from klines: {e}")
            return None
            
    def get_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas del engine"""
        return {
            'predictions_made': self.stats['predictions_made'],
            'by_timeframe': dict(self.stats['by_timeframe']),
            'top_symbols': dict(list(sorted(
                self.stats['by_symbol'].items(), 
                key=lambda x: x[1], 
                reverse=True
            ))[:5]),
            'signal_distribution': dict(self.stats['signal_distribution'])
        }
        
    def log_statistics(self):
        """Log de estadísticas"""
        stats = self.get_statistics()
        log.info(f"🧠 ML Engine Statistics:")
        log.info(f"  └─ Total predictions: {stats['predictions_made']}")
        
        if stats['by_timeframe']:
            tf_stats = ", ".join([f"{tf}:{count}" for tf, count in stats['by_timeframe'].items()])
            log.info(f"  └─ By timeframe: {tf_stats}")
            
        if stats['signal_distribution']:
            sig_stats = ", ".join([f"{sig}:{count}" for sig, count in stats['signal_distribution'].items()])
            log.info(f"  └─ Signals: {sig_stats}")
            
    async def cleanup(self):
        """Limpieza del engine"""
        log.info("🧹 Cleaning up ML Inference Engine...")
        
        # Log estadísticas finales
        self.log_statistics()
        
        # Limpiar cache
        self.feature_cache.clear()
        
        log.info("✅ ML Inference Engine cleanup completed")
