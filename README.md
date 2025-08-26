# Binance Futures Pro Trading Bot

🚀 **Bot de trading automatizado para Binance Futures con ML e inteligencia artificial**

## ✨ Características Principales

### 🤖 Trading Automatizado
- **19 símbolos fijos** de alta liquidez
- **Señales ML** con XGBoost + Optuna
- **Gestión de riesgo** tradicional optimizada
- **WebSocket real-time** para datos de mercado
- **🆕 Sistema Multitimeframe** con análisis 1m/3m/5m y confirmaciones

### 🛡️ Gestión de Riesgo Avanzada
- **SL/TP inteligente** con 3 niveles de take profit BASADO EN PORCENTAJES
- **Break-even** con cálculo de comisiones
- **Trailing stop dinámico** con factores ATR adaptativos
- **Sistema de cooldown** de 5 minutos anti-overtrading
- **Margen configurable** (0.5 USD con fallback a 1.0 USD)
- **🆕 MIN_NOTIONAL** compliance con buffer del 1%

### 🎯 Sistema Multitimeframe (NUEVO)
- **Análisis simultáneo** de 1m, 3m y 5m
- **Confirmaciones múltiples** (mínimo 2 timeframes coincidentes)  
- **Decisiones ML** por timeframe independiente
- **Validación cruzada** antes de ejecutar trades
- **Configuración flexible** de probabilidades por timeframe

### 📊 Características Técnicas
- **Python 3.11+** con dependencias modernas
- **Configuración YAML** flexible
- **Logging avanzado** con emojis y métricas R
- **Sistema de validación** robusto para órdenes TP
- **Detección automática** de cierre de posiciones

## 🔧 Configuración Rápida

### 1. Clonar y configurar
```bash
git clone https://github.com/[tu-usuario]/binance-futures-pro.git
cd binance-futures-pro
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Variables de entorno
```bash
# Crear .env con tus credenciales
BINANCE_API_KEY=tu_api_key
BINANCE_SECRET_KEY=tu_secret_key
TESTNET=false  # true para testnet
MAX_MARGIN_USDT=0.5
SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,XRPUSDT,...
```

### 3. Ejecutar

#### Bot Tradicional (1 timeframe)
```bash
python -m pro_bot.app.main_multi
```

#### 🆕 Bot Multitimeframe (RECOMENDADO)
```powershell
# Windows PowerShell
.\scripts\run_multitimeframe.ps1

# O directamente
python pro_bot\app\main_multitimeframe.py
```

#### 🔬 Probar Sistema Multitimeframe
```powershell
# Test de 2 minutos
.\scripts\test_multitimeframe.ps1
```

## 📈 Sistema de Trading

### 🎯 Estrategia

#### Estrategia Tradicional (1 timeframe)
- **Entrada**: Señales ML con umbral de probabilidad configurable
- **SL**: 2.5x ATR por defecto
- **TP**: 3 niveles basados en % del valor de la posición

#### 🆕 Estrategia Multitimeframe
- **Análisis**: 1m, 3m, 5m simultáneamente
- **Confirmación**: Mínimo 2 timeframes coincidentes
- **Entrada**: Solo cuando hay confirmación múltiple
- **Probabilidades**: Configuradas por timeframe:
  - **1m**: long≥0.57, short≤0.43
  - **3m**: long≥0.55, short≤0.45  
  - **5m**: long≥0.53, short≤0.47

#### Take Profit (Ambas estrategias)
- **TP1**: 50% del valor de posición (cierra 50% qty)
- **TP2**: 30% del valor de posición (cierra 25% qty)
- **TP3**: 20% del valor de posición (cierra 25% qty)
- **Break-even**: A 0.75R considerando comisiones
- **Trailing**: Activación dinámica con factores ATR

### 🔄 Cooldown System
- **5 minutos** tras abrir/cerrar posición
- **Detección universal** de cierres (SL/TP/manual/liquidación)
- **Prevención de overtrading** automática

### 📊 Gestión de Posición
- **Qty calculada**: MIN_NOTIONAL / ENTRY_PRICE (con buffer 1%)
- **Leverage automático**: Configurado por símbolo
- **Límite máximo**: 5 posiciones simultáneas

## 🎛️ Configuración

### `configs/ml.yaml`
```yaml
risk:
  stop_loss_atr_mult: 2.5
  # TP basado en % del valor de la posición en PnL USDT
  tp_pnl_percentages: [50.0, 30.0, 20.0]  # TP1: 50%, TP2: 30%, TP3: 20%
  tp_allocation: [0.5, 0.25, 0.25]        # Cantidad a cerrar: 50%, 25%, 25%
  break_even_r: 0.75
  commission_rate: 0.0008
  cooldown_minutes: 5
  trailing:
    activate_after_r: 0.5
    atr_mult: 0.5
    step_r: 0.1
    min_move: 0.05

serving:
  prob_long: 0.57
  prob_short: 0.43
```

## 🚀 Arquitectura

```
pro_bot/
├── app/
│   └── main_multi.py      # Aplicación principal
├── core/
│   ├── sl_tp_manager.py   # Gestión SL/TP + Cooldown
│   ├── execution.py       # Ejecución de órdenes
│   ├── risk.py           # Gestión de riesgo
│   └── ws_multi.py       # WebSocket multi-símbolo
└── config.py             # Configuración central

pro_ml/
├── core/
│   ├── features/         # Ingeniería de características
│   ├── models/          # Modelos ML
│   └── live/            # Inferencia en vivo
└── tools/               # Scripts de entrenamiento
```

## 📊 Monitoreo

### Logs del Sistema
```
[BTCUSDT] 🚀 Abrir LONG: entry=43250.50 qty=0.023, SL@42680.75, R=569.75
[BTCUSDT] ✅ TP1 @ 1.0R: qty=0.012 price=43820.25 mode=PARTIAL
[BTCUSDT] 📍 Break-even: SL @ 43285.12 (comisiones: +34.62)
[BTCUSDT] 🏁 Posición cerrada detectada - Activando cooldown
[BTCUSDT] 🕒 Cooldown iniciado: 5m tras cierre
```

### Métricas Clave
- **R tracking**: Seguimiento en tiempo real
- **Comisiones**: Cálculo preciso en break-even
- **Cooldown status**: Estado y tiempo restante
- **TP validation**: Verificación de órdenes

## ⚠️ Importante

### 🔐 Seguridad
- **API keys** en variables de entorno
- **Permisos mínimos**: Solo Futures Trading
- **IP whitelist** recomendada
- **Testnet** para pruebas

### ⚡ Rendimiento
- **1 minuto** interval para datos
- **150+ klines** de histórico necesario
- **WebSocket** para latencia mínima
- **Validación** robusta de órdenes

### 🛡️ Riesgo
- **Máximo 5 posiciones** simultáneas
- **0.5 USD margen** por defecto
- **Cooldown obligatorio** entre trades
- **Stop loss** siempre activo

## 📚 Documentación Adicional

- [`COOLDOWN_SYSTEM.md`](COOLDOWN_SYSTEM.md) - Sistema de cooldown detallado
- [`configs/ml.yaml`](configs/ml.yaml) - Configuración completa
- [`requirements.txt`](requirements.txt) - Dependencias

## 🤝 Contribuir

1. Fork el proyecto
2. Crear feature branch (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -m 'Agregar nueva característica'`)
4. Push al branch (`git push origin feature/nueva-caracteristica`)
5. Abrir Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver [LICENSE](LICENSE) para detalles.

## ⚠️ Disclaimer

**Trading de criptomonedas involucra riesgo significativo. Use este bot bajo su propia responsabilidad. Los autores no se hacen responsables por pérdidas financieras.**

---

🚀 **Happy Trading!** 📈
