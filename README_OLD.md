# Binance Futures Pro Trading Bot

🚀 **Bot de trading automatizado para Binance Futures con ML e inteligencia artificial**

## ✨ Características Principales

### 🤖 Trading Automatizado
- **19 símbolos fijos** de alta liquidez
- **Señales ML** con XGBoost + Optuna
- **Gestión de riesgo** tradicional optimizada
- **WebSocket real-time** para datos de mercado

### 🛡️ Gestión de Riesgo Avanzada
- **SL/TP inteligente** con 3 niveles de take profit
- **Break-even** con cálculo de comisiones
- **Trailing stop dinámico** con factores ATR adaptativos
- **Sistema de cooldown** de 5 minutos anti-overtrading
- **Margen configurable** (0.5 USD con fallback a 1.0 USD)

### 📊 Características Técnicas
- **Python 3.11+** con dependencias modernas
- **Configuración YAML** flexible
- **Logging avanzado** con emojis y métricas R
- **Sistema de validación** robusto para órdenes TP
- **Detección automática** de cierre de posiciones

- **Real-time Trading**: WebSocket integration for instant market data processing
- **Machine Learning**: XGBoost models with Optuna optimization for entry signals
- **Multi-symbol Support**: Trade up to 19 cryptocurrency pairs simultaneously
- **Advanced Risk Management**: SL/TP, break-even, trailing stops with commission considerations
- **Configurable Margin**: Dynamic margin allocation with fallback systems
- **Live Monitoring**: Real-time position tracking and performance logging

## 🏗️ Architecture

```
binance_futures_pro/
├── pro_bot/           # Core trading engine
│   ├── app/           # Main application
│   ├── core/          # Trading logic
│   └── config.py      # Configuration management
├── pro_ml/            # Machine learning pipeline
│   ├── core/          # ML modules
│   └── tools/         # Training utilities
├── outputs/           # Models and reports
├── configs/           # Configuration files
└── scripts/           # Deployment and utility scripts
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Binance Futures account
- API keys with futures trading permissions

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/binance_futures_pro.git
   cd binance_futures_pro
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Binance API credentials
   ```

### Configuration

Create a `.env` file with your settings:

```env
# Binance API (REQUIRED)
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
BOT_TESTNET=false

# Trading Parameters
LEVERAGE=20
MARGIN_TYPE=ISOLATED
MAX_MARGIN_USDT=0.5
MAX_OPEN_POSITIONS=5
RISK_PER_TRADE=0.01

# Symbols (19 supported pairs)
SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,XRPUSDT,...
```

### Running the Bot

1. **Train ML models** (optional - pre-trained models included)
   ```bash
   python -m pro_ml.tools.train_batch_binance
   ```

2. **Start trading**
   ```bash
   python -m pro_bot.app.main_multi
   ```

## 🎯 Trading Strategy

### Entry Signals
- **Machine Learning**: XGBoost models with microstructure features
- **Technical Analysis**: ATR, RSI, Bollinger Bands, volume indicators
- **Risk Filtering**: Position limits and margin management

### Risk Management
- **Stop Loss**: Dynamic ATR-based stops
- **Take Profit**: 3-level system (50%/25%/25% at 1R/2R/3R)
- **Break-even**: Commission-aware break-even at 0.75R
- **Trailing Stop**: Dynamic trailing with ATR factors

### Position Sizing
- **Fixed Risk**: 1% per trade (configurable)
- **Margin Control**: 0.5 USDT base with 1.0 USDT fallback
- **Leverage**: Isolated 20x (configurable)

## 📊 Supported Symbols

The bot supports 19 major cryptocurrency futures pairs:

`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `ADAUSDT`, `XRPUSDT`, `SOLUSDT`, `DOGEUSDT`, `AVAXUSDT`, `LINKUSDT`, `LTCUSDT`, `SUIUSDT`, `WIFUSDT`, `1000PEPEUSDT`, `ENAUSDT`, `BIOUSDT`, `ONTUSDT`, `HYPEUSDT`, `FARTCOINUSDT`, `PROMPTUSDT`

## ⚙️ Configuration

### Risk Parameters
```yaml
# configs/ml.yaml
risk:
  tp_levels: [1.0, 2.0, 3.0]
  tp_portions: [0.5, 0.25, 0.25]
  sl_rr: 1.0
  break_even_r: 0.75
  commission_rate: 0.0008
```

### ML Configuration
```yaml
# configs/ml.yaml
serving:
  prob_long: 0.57
  prob_short: 0.43
```

## 🛡️ Safety Features

- **Position Limits**: Maximum 5 concurrent positions
- **Margin Protection**: Automatic margin fallback system
- **Commission Awareness**: Break-even calculations include trading fees
- **Error Handling**: Comprehensive exception management
- **Logging**: Detailed operation logs with emoji indicators

## 📈 Performance Monitoring

The bot provides real-time monitoring through:

- **Console Logs**: Real-time trade execution and R-multiple tracking
- **Position Status**: Active position monitoring with P&L
- **Risk Metrics**: Current exposure and available margin
- **ML Signals**: Model predictions and probability scores

## 🔧 Development

### Project Structure
- `pro_bot/core/execution.py`: Order execution logic
- `pro_bot/core/sl_tp_manager.py`: Risk management engine
- `pro_bot/core/ws_multi.py`: WebSocket data handling
- `pro_ml/core/`: Machine learning pipeline
- `scripts/`: Deployment and utility scripts

### Adding New Features
1. Create feature branch: `git checkout -b feature/new-feature`
2. Implement changes with tests
3. Update documentation
4. Submit pull request

## ⚠️ Disclaimer

**IMPORTANT**: This software is for educational and research purposes. Cryptocurrency trading involves substantial risk of loss. Use at your own risk and never trade with money you cannot afford to lose.

- **No Financial Advice**: This bot does not provide financial advice
- **Risk Warning**: Past performance does not guarantee future results
- **Testing Required**: Always test thoroughly before live trading
- **API Security**: Keep your API keys secure and use IP restrictions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests for any improvements.

## 📧 Support

For questions and support:
- Open an issue on GitHub
- Check existing documentation
- Review configuration examples

---

**⚡ Happy Trading!** 🚀
