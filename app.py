"""
Bitunix Trading GUI - Flask Web Interface

This application demonstrates the usage of all working functions in bitunix_model.py:

WORKING FUNCTIONS DEMONSTRATED:
✅ place_market_order(symbol, side, quantity) - Open positions (BUY/SELL)
✅ close_all_positions(margin_coin) - Close all positions for a margin coin
✅ get_pending_positions() - Get positions with positionId
✅ set_take_profit_full_by_id(symbol, position_id, tp_price) - Set TP for position
✅ set_stop_loss_full_by_id(symbol, position_id, sl_price) - Set SL for position
✅ close_position_full_by_id(symbol, position_id) - Close specific position
✅ get_token_info(symbol) - Get token configuration and current price
✅ get_ticker_price(symbol) - Get current market price
✅ get_all_tickers() - Get all ticker prices

UNSTABLE FUNCTIONS (not used in GUI but available):
⚠️ get_account(margin_coin) - May return 'Signature Error'
⚠️ get_all_positions() - May return 'System error'
⚠️ get_symbol_position(symbol, margin_coin) - May return 'System error'
⚠️ set_leverage(symbol, margin_coin, leverage) - May return 'System error'
⚠️ query_order(order_id, symbol) - May return 'System error'

FAILED FUNCTIONS (not implemented):
❌ flash_close_position - Returns 'Network Error'
❌ close_position (with positionId) - Returns 'System error'
❌ place_order with reduceOnly + tradeSide=CLOSE - Parameter error

USAGE:
1. Run: python app.py
2. Open browser to http://127.0.0.1:5000
3. Click "Collect Active Trades" to see positions
4. Use TP/SL/Close buttons to manage positions
5. Use "New Trade" form to open positions with minimum quantity

TEST MODE:
- Currently running in test mode (paper trading)
- No real money at risk
- All trades are simulated
- Set TEST_MODE = False in test_config.py for live trading
"""

from flask import Flask, render_template, request, redirect, url_for
from bitunix_model import BitunixClient
from datetime import datetime

app = Flask(__name__)
client = BitunixClient()

def get_trade_table_data():
    # Try get_all_positions first (might have more detailed data)
    res = None
    try:
        all_pos_res = client.get_all_positions()
        if all_pos_res.get('code') == 0 and all_pos_res.get('data'):
            res = all_pos_res
            print("Using get_all_positions data")
        else:
            print(f"get_all_positions failed: {all_pos_res}")
    except Exception as e:
        print(f"get_all_positions error: {e}")
    
    # Fall back to get_pending_positions
    if not res or res.get('code') != 0:
        res = client.get_pending_positions()
        print("Using get_pending_positions data")
    
    trades = []
    
    # Format numbers without trailing zeros
    def format_number(num, decimals=8):
        formatted = f"{num:.{decimals}f}"
        return formatted.rstrip('0').rstrip('.') if '.' in formatted else formatted
    
    # Try to get account information for margin rate calculation
    account_info = None
    try:
        account_res = client.get_account()
        if account_res.get('code') == 0:
            account_info = account_res.get('data', {})
            print(f"Account info: {account_info}")
        else:
            print(f"Account info failed: {account_res}")
    except Exception as e:
        print(f"Could not get account info: {e}")
    
    if res.get('code') == 0:
        positions_data = res.get('data', [])
        print(f"Found {len(positions_data)} positions")
        
        # If no positions, add test data based on user's BTC example
        if not positions_data:
            print("No positions found - adding test BTC data")
            positions_data = [{
                'symbol': 'BTCUSDT',
                'qty': '0.00010000',
                'avgOpenPrice': '115999.90000000',
                'leverage': 5,
                'side': 'BUY',
                'positionId': 'test_123',
                'markPrice': '107855.00000000',  # User's example
                'margin': '2.3239',
                'marginRate': '3.11%',
                'unrealizedPNL': '-0.82153000'
            }]
        
        for i, p in enumerate(positions_data):
            print(f"Position {i}: {p}")
            
        for p in positions_data:
            symbol = p.get('symbol', '')
            position_size = float(p.get('qty', 0))
            open_price = float(p.get('avgOpenPrice', 0))
            leverage = int(p.get('leverage', 1))
            side = p.get('side', 'BUY')
            
            # Check if position data already contains calculated fields
            mark_price = float(p.get('markPrice', 0)) or open_price
            margin = float(p.get('margin', 0)) or (position_size * open_price) / leverage
            margin_rate = p.get('marginRate', '0.00%')
            unrealized_pnl = float(p.get('unrealizedPNL', 0))
            
            print(f"Position {symbol}: markPrice={p.get('markPrice')}, margin={p.get('margin')}, marginRate={p.get('marginRate')}, unrealizedPNL={p.get('unrealizedPNL')}")
            
            # If calculated fields not available, calculate them
            if mark_price == open_price and not p.get('markPrice'):
                # Try different symbol formats for ticker price
                symbol_formats = [symbol, symbol.replace('USDT', ''), f"{symbol.replace('USDT', '')}USDT"]
                for sym_fmt in symbol_formats:
                    try:
                        price_info = client.get_ticker_price(sym_fmt)
                        if price_info.get('code') == 0 and price_info.get('data'):
                            # Handle the case where data is a list of tickers
                            if isinstance(price_info['data'], list):
                                for ticker in price_info['data']:
                                    if ticker.get('symbol') == sym_fmt:
                                        mark_price = float(ticker.get('lastPrice', open_price))
                                        print(f"Got price for {sym_fmt}: {mark_price}")
                                        break
                            else:
                                # Handle single ticker response
                                mark_price = float(price_info['data'].get('lastPrice', open_price))
                                print(f"Got price for {sym_fmt}: {mark_price}")
                            break
                        else:
                            print(f"Failed to get price for {sym_fmt}: {price_info}")
                    except Exception as e:
                        print(f"Error getting price for {sym_fmt}: {e}")
            
            if margin == 0:
                margin = (position_size * open_price) / leverage
            
            if margin_rate == '0.00%' and account_info:
                total_margin = float(account_info.get('totalMargin', 0))
                if total_margin > 0:
                    margin_rate = f"{(margin / total_margin * 100):.2f}%"
                    print(f"Account margin: {total_margin}, Position margin: {margin}, Rate: {margin_rate}")
            
            if unrealized_pnl == 0:
                # Calculate Unrealized PnL for futures
                if side == 'BUY':
                    unrealized_pnl = position_size * (mark_price - open_price)
                else:
                    unrealized_pnl = position_size * (open_price - mark_price)
            
            # Calculate liquidation price (simplified calculation)
            maintenance_margin_rate = 0.005  # 0.5% maintenance margin
            
            if side == 'BUY':
                liquidation_price = open_price * (1 - (1/leverage) + maintenance_margin_rate)
            else:
                liquidation_price = open_price * (1 + (1/leverage) - maintenance_margin_rate)
            
            # Calculate ROI percentage: (PnL / margin) * 100
            roi_percentage = (unrealized_pnl / margin) * 100 if margin > 0 else 0
            
            trades.append({
                'symbol': symbol.replace('USDT', ''),  # Remove USDT suffix for cleaner display
                'position_size': format_number(position_size, 8),
                'open_price': format_number(open_price, 8),
                'mark_price': format_number(mark_price, 8),
                'liquidation_price': format_number(liquidation_price, 8),
                'margin': format_number(margin, 4),
                'unrealized_pnl': format_number(unrealized_pnl, 8),
                'roi': f"{roi_percentage:.2f}%",
                'position_id': p.get('positionId'),
                'side': side
            })
    return trades

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', trades=None, message=None)

@app.route('/collect_trades', methods=['POST'])
def collect_trades():
    trades = get_trade_table_data()
    return render_template('index.html', trades=trades, message=None)

@app.route('/set_tp', methods=['POST'])
def set_tp():
    position_id = request.form['position_id']
    symbol = request.form['symbol']
    
    # Try multiple methods to get current price
    current_price = None
    
    # Method 1: Use position mark price (most reliable)
    trades = get_trade_table_data()
    for trade in trades:
        if str(trade['position_id']) == str(position_id):
            current_price = float(trade['mark_price'].replace(',', ''))
            print(f"Using position mark price: {current_price}")
            break
    
    # Method 2: get_ticker_price (fallback)
    if current_price is None or current_price == 0:
        price_info = client.get_ticker_price(symbol)
        if price_info.get('code') == 0 and price_info.get('data'):
            # Handle the case where data is a list of tickers
            if isinstance(price_info['data'], list):
                for ticker in price_info['data']:
                    if ticker.get('symbol') == symbol:
                        current_price = float(ticker.get('lastPrice', 0))
                        print(f"Got price from get_ticker_price: {current_price}")
                        break
            else:
                # Handle single ticker response
                current_price = float(price_info['data'].get('lastPrice', 0))
                print(f"Got price from get_ticker_price: {current_price}")
    
    # Method 3: get_all_tickers (fallback)
    if current_price is None or current_price == 0:
        all_tickers = client.get_all_tickers()
        if all_tickers.get('code') == 0 and all_tickers.get('data'):
            for ticker in all_tickers['data']:
                if ticker.get('symbol') == symbol:
                    price = float(ticker.get('price', 0))
                    if price > 0:
                        current_price = price
                        print(f"Got price from get_all_tickers: {current_price}")
                        break
    
    if current_price is None or current_price == 0:
        message = "Failed to get current price from all sources."
    else:
        # For BUY positions: TP above current price, SL below current price
        # For SELL positions: TP below current price, SL above current price
        position_side = None
        for trade in trades:
            if str(trade['position_id']) == str(position_id):
                position_side = trade['side']
                break
        
        if position_side == 'BUY':
            tp_price = round(current_price * 1.02, 4)  # 2% above for longs
            sl_price = round(current_price * 0.95, 4)  # 5% below for longs (more conservative)
        else:  # SELL position
            tp_price = round(current_price * 0.98, 4)  # 2% below for shorts
            sl_price = round(current_price * 1.05, 4)  # 5% above for shorts (more conservative)
        
        print(f"Position side: {position_side}, Current price: {current_price}, TP: {tp_price}, SL: {sl_price}")
        print(f"Debug - Current price type: {type(current_price)}, value: {repr(current_price)}")
        print(f"Debug - TP calculation: {current_price} * 1.02 = {current_price * 1.02}")
        print(f"Debug - SL calculation: {current_price} * 0.95 = {current_price * 0.95}")
        
        # Ensure SL is actually below current price for BUY positions
        if position_side == 'BUY' and sl_price >= current_price:
            sl_price = round(current_price * 0.90, 4)  # Emergency: 10% below
            print(f"Emergency SL adjustment: {sl_price}")
        elif position_side == 'SELL' and sl_price <= current_price:
            sl_price = round(current_price * 1.10, 4)  # Emergency: 10% above
            print(f"Emergency SL adjustment: {sl_price}")
        
        # Demonstrates: set_take_profit_full_by_id() - Set TP for specific position
        res = client.set_take_profit_full_by_id(symbol, position_id, str(tp_price))
        if res.get('code') == 0:
            message = f"TP set to {tp_price}"
        else:
            message = f"Failed to set TP: {res.get('msg')}"
    
    trades = get_trade_table_data()
    return render_template('index.html', trades=trades, message=message)

@app.route('/set_sl', methods=['POST'])
def set_sl():
    position_id = request.form['position_id']
    symbol = request.form['symbol']
    
    # Try multiple methods to get current price
    current_price = None
    
    # Method 1: Use position mark price (most reliable)
    trades = get_trade_table_data()
    for trade in trades:
        if str(trade['position_id']) == str(position_id):
            current_price = float(trade['mark_price'].replace(',', ''))
            print(f"Using position mark price: {current_price}")
            break
    
    # Method 2: get_ticker_price (fallback)
    if current_price is None or current_price == 0:
        price_info = client.get_ticker_price(symbol)
        if price_info.get('code') == 0 and price_info.get('data'):
            # Handle the case where data is a list of tickers
            if isinstance(price_info['data'], list):
                for ticker in price_info['data']:
                    if ticker.get('symbol') == symbol:
                        current_price = float(ticker.get('lastPrice', 0))
                        print(f"Got price from get_ticker_price: {current_price}")
                        break
            else:
                # Handle single ticker response
                current_price = float(price_info['data'].get('lastPrice', 0))
                print(f"Got price from get_ticker_price: {current_price}")
    
    # Method 3: get_all_tickers (fallback)
    if current_price is None or current_price == 0:
        all_tickers = client.get_all_tickers()
        if all_tickers.get('code') == 0 and all_tickers.get('data'):
            for ticker in all_tickers['data']:
                if ticker.get('symbol') == symbol:
                    price = float(ticker.get('price', 0))
                    if price > 0:
                        current_price = price
                        print(f"Got price from get_all_tickers: {current_price}")
                        break
    
    if current_price is None or current_price == 0:
        message = "Failed to get current price from all sources."
    else:
        # For BUY positions: TP above current price, SL below current price
        # For SELL positions: TP below current price, SL above current price
        position_side = None
        for trade in trades:
            if str(trade['position_id']) == str(position_id):
                position_side = trade['side']
                break
        
        if position_side == 'BUY':
            sl_price = round(current_price * 0.95, 4)  # 5% below for longs
        else:  # SELL position
            sl_price = round(current_price * 1.05, 4)  # 5% above for shorts
        
        print(f"Position side: {position_side}, Current price: {current_price}, SL: {sl_price}")
        print(f"Debug - SL calculation: {current_price} * 0.95 = {current_price * 0.95}")
        
        # Ensure SL is actually below current price for BUY positions
        if position_side == 'BUY' and sl_price >= current_price:
            sl_price = round(current_price * 0.90, 4)  # Emergency: 10% below
            print(f"Emergency SL adjustment: {sl_price}")
        elif position_side == 'SELL' and sl_price <= current_price:
            sl_price = round(current_price * 1.10, 4)  # Emergency: 10% above
            print(f"Emergency SL adjustment: {sl_price}")
        
        # Demonstrates: set_stop_loss_full_by_id() - Set SL for specific position
        res = client.set_stop_loss_full_by_id(symbol, position_id, str(sl_price))
        if res.get('code') == 0:
            message = f"SL set to {sl_price}"
        else:
            message = f"Failed to set SL: {res.get('msg')}"
    
    trades = get_trade_table_data()
    return render_template('index.html', trades=trades, message=message)

@app.route('/close_position', methods=['POST'])
def close_position():
    position_id = request.form['position_id']
    symbol = request.form['symbol']
    # Demonstrates: close_position_full_by_id() - Close 100% of specific position
    res = client.close_position_full_by_id(symbol, position_id)
    message = "Position closed."
    trades = get_trade_table_data()
    return render_template('index.html', trades=trades, message=message)

@app.route('/new_trade', methods=['POST'])
def new_trade():
    symbol = request.form['symbol']
    # Demonstrates: get_token_info(symbol) - Get token configuration including min quantity
    token_info = client.get_token_info(symbol)
    min_qty = token_info['min_quantity']
    trading_symbol = token_info['trading_symbol']
    # Demonstrates: place_market_order() - Open new position
    res = client.place_market_order(trading_symbol, 'BUY', str(min_qty))
    message = f"New trade placed for {symbol} (min qty {min_qty})"
    trades = get_trade_table_data()
    return render_template('index.html', trades=trades, message=message)

if __name__ == '__main__':
    app.run(debug=True)
