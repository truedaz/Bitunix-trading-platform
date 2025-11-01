# Bitunix Trading GUI

A Flask web interface demonstrating all working functions of the Bitunix API client.

## DOCS
https://openapidoc.bitunix.com/doc/market/

## Features

- **Active Trades Table**: Display all active positions with professional trading columns and accurate futures calculations:
  - Symbol (e.g., XRP, ADA, SOL, BTC)
  - Position Size (contract quantity with 8 decimal precision)
  - Open Price (entry price with comma formatting)
  - Mark Price (current market price, real-time)
  - Liquidation Price (calculated based on leverage and maintenance margin)
  - Margin (collateral required: position_size × entry_price ÷ leverage)
  - Margin Rate (margin utilization percentage)
  - Unrealized PnL/ROI (profit/loss and return percentage on margin)
  - Actions (TP/SL/Close buttons for position management)

## Bitunix Model Functions Demonstrated

### ✅ Working Functions (Used in GUI)
- `place_market_order(symbol, side, quantity)` - Open BUY/SELL positions
- `get_pending_positions()` - Retrieve all active positions with positionId
- `get_ticker_price(symbol)` - Get current market price for calculations
- `set_take_profit_full_by_id(symbol, position_id, tp_price)` - Set TP for specific position
- `set_stop_loss_full_by_id(symbol, position_id, sl_price)` - Set SL for specific position
- `close_position_full_by_id(symbol, position_id)` - Close 100% of specific position
- `get_token_info(symbol)` - Get token configuration and minimum quantities

### ⚠️ Unstable Functions (Available but not used in GUI)
- `get_account(margin_coin)` - May return 'Signature Error'
- `get_all_positions()` - May return 'System error'
- `get_symbol_position(symbol, margin_coin)` - May return 'System error'
- `set_leverage(symbol, margin_coin, leverage)` - May return 'System error'
- `query_order(order_id, symbol)` - May return 'System error'

### ❌ Failed Functions (Not implemented)
- `flash_close_position` - Returns 'Network Error'
- `close_position (with positionId)` - Returns 'System error'
- `place_order with reduceOnly + tradeSide=CLOSE` - Parameter error

## Installation

1. Install dependencies:
```bash
pip install flask
```

2. Ensure all files are present:
- `app.py` - Flask web application
- `bitunix_model.py` - Bitunix API client
- `creds.py` - API credentials
- `test_config.py` - Test configuration and paper trading
- `templates/index.html` - Web interface template

## Usage

1. **Start the application**:
```bash
python app.py
```

2. **Open browser** to `http://127.0.0.1:5000`

3. **Collect Active Trades**: Click the button to load and display current positions in a professional table format with trading columns (Symbol, Position Size, Open Price, Mark Price, Liquidation Price, Margin, Margin Rate, Unrealized PnL/ROI, Actions)

4. **Manage Positions**:
   - **TP Button**: Sets take profit at +2% from current price
   - **SL Button**: Sets stop loss at -2% from current price
   - **Close Button**: Closes 100% of the position

5. **Open New Trades**:
   - Select SOL, ADA, or XRP from dropdown
   - Click "Buy Minimum Qty" to open position with minimum allowed quantity

## Test Mode vs Live Trading

### Test Mode (Default)
- Set `TEST_MODE = True` in `test_config.py`
- All trades are simulated (paper trading)
- No real money at risk
- Perfect for testing and development

### Live Trading
- Set `TEST_MODE = False` in `test_config.py`
- Uses real API credentials from `creds.py`
- Actual positions opened/closed on Bitunix
- **Use with caution - real money at risk**

## Configuration

### API Credentials (`creds.py`)
```python
BITUNIX_CONFIG = {
    "api_key": "your_api_key_here",
    "api_secret": "your_api_secret_here",
    "base_url": "https://fapi.bitunix.com",
    "testnet": False
}
```

### Trading Configuration (`test_config.py`)
- Position sizing limits
- Risk management parameters
- Supported tokens and minimum quantities
- Paper trading balance and simulation

## Security Notes

- Never commit API credentials to version control
- Test thoroughly in paper trading mode before live trading
- Use conservative position sizes for live trading
- Monitor positions regularly

## Architecture

- **Flask**: Web framework for the GUI
- **BitunixClient**: Main API client class with authentication
- **TestTradeManager**: Paper trading simulation
- **TokenConfigManager**: Token-specific configuration management
- **Bootstrap**: Responsive web interface styling

## Calculations

### Futures Trading Formulas Used:
- **Margin**: `(position_size × entry_price) ÷ leverage`
- **Unrealized PnL**: 
  - Long: `position_size × (mark_price - entry_price)`
  - Short: `position_size × (entry_price - mark_price)`
- **ROI**: `(PnL ÷ margin) × 100%`
- **Liquidation Price**: Based on leverage and 0.5% maintenance margin
- **Margin Rate**: Percentage of position value used as margin

All values are formatted with appropriate decimal precision for professional trading display.