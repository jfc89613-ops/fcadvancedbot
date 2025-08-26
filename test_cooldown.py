#!/usr/bin/env python3
"""
Script de prueba para verificar el sistema de cooldown
"""

import time
import yaml
from datetime import datetime, timedelta
from pro_bot.core.sl_tp_manager import SLTPManager

# Cargar configuración
with open('configs/ml.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

def test_cooldown():
    print("🧪 Prueba del sistema de cooldown")
    print("=" * 50)
    
    # Crear manager para BTCUSDT
    pm = SLTPManager(cfg, "BTCUSDT")
    
    print(f"⚙️  Cooldown configurado: {pm.cooldown_minutes} minutos")
    print()
    
    # Test 1: Verificar que no hay cooldown inicial
    in_cooldown, reason = pm.is_in_cooldown()
    print(f"1️⃣  Cooldown inicial: {in_cooldown}")
    assert not in_cooldown, "No debería haber cooldown inicial"
    
    # Test 2: Simular apertura de posición
    print("2️⃣  Simulando apertura de posición...")
    pm._set_cooldown_open()
    
    in_cooldown, reason = pm.is_in_cooldown()
    print(f"   Cooldown tras apertura: {in_cooldown} - {reason}")
    assert in_cooldown, "Debería haber cooldown tras apertura"
    
    # Test 3: Simular cierre de posición
    print("3️⃣  Simulando cierre de posición...")
    pm._set_cooldown_close()
    
    in_cooldown, reason = pm.is_in_cooldown()
    print(f"   Cooldown tras cierre: {in_cooldown} - {reason}")
    assert in_cooldown, "Debería haber cooldown tras cierre"
    
    # Test 4: Simular tiempo transcurrido
    print("4️⃣  Simulando tiempo transcurrido...")
    # Simular que pasó el tiempo modificando manualmente
    past_time = datetime.now() - timedelta(minutes=6)
    pm.last_close_time = past_time
    pm.last_open_time = past_time
    
    in_cooldown, reason = pm.is_in_cooldown()
    print(f"   Cooldown tras 6 minutos: {in_cooldown}")
    assert not in_cooldown, "No debería haber cooldown tras 6 minutos"
    
    print()
    print("✅ Todas las pruebas de cooldown pasaron correctamente!")
    print()
    
    # Mostrar configuración
    print("📋 Configuración de cooldown:")
    print(f"   - Duración: {pm.cooldown_minutes} minutos")
    print(f"   - Se activa tras: Apertura y Cierre de posiciones")
    print(f"   - Bloquea: Nuevas aperturas durante el período")

if __name__ == "__main__":
    test_cooldown()
