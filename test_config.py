"""
Test Configuration for Safe Trading
Includes paper trading, small position sizing, and comprehensive logging.
"""

import os
from typing import Dict, List
from datetime import datetime
import json

# Test mode configuration - using global variables instead of dataclass to avoid validation issues
TEST_MODE = False
PAPER_TRADING = True  # Simulate trades without real money

# Position sizing for $25 balance
MAX_POSITION_SIZE_USD = 5.0  # Max $5 per position
MAX_TOTAL_EXPOSURE_USD = 20.0  # Max $20 total exposure
MIN_POSITION_SIZE_USD = 1.0  # Min $1 per position

# Risk management
MAX_LEVERAGE = 2  # Conservative leverage for testing
STOP_LOSS_PERCENTAGE = 2.0  # 2% stop loss
TAKE_PROFIT_PERCENTAGE = 3.0  # 3% take profit
MAX_DAILY_TRADES = 10  # Limit trades per day

# Tokens to trade - Updated for Bitunix Futures availability
SUPPORTED_TOKENS = ['XRP', 'ADA', 'SUI', 'UNI', 'LINK', 'SOL', 'AVAX', 'DOT']

# Minimum quantities (to be fetched from exchange)
MIN_QUANTITIES = {
    'XRPUSDT': 1.0,
    'ADAUSDT': 1.0,
    'SUIUSDT': 0.1,
    'UNIUSDT': 0.1,
    'LINKUSDT': 0.1,
    'SOLUSDT': 0.01,
    'AVAXUSDT': 0.1,
    'DOTUSDT': 0.1
}

# Sentiment thresholds
SENTIMENT_BUY_THRESHOLD = 0.3
SENTIMENT_SELL_THRESHOLD = -0.3
MIN_CONFIDENCE_THRESHOLD = 0.4

# Trading timeframes
ANALYSIS_INTERVAL_MINUTES = 15  # Analyze every 15 minutes
MAX_POSITION_HOLD_HOURS = 24  # Close positions after 24 hours max

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "logs/trading_bot.log"
TRADE_LOG_FILE = "logs/trades.json"

class TestTradeManager:
    """Manages test mode trading and paper trading simulation"""
    
    def __init__(self):
        self.paper_balance = 25.0  # Starting balance
        self.paper_positions = {}  # symbol -> position data
        self.trade_history = []
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        
        # Create log directory
        os.makedirs("logs", exist_ok=True)
        
        # Load existing paper trading data
        self._load_paper_data()
    
    def can_open_position(self, symbol: str, side: str, size_usd: float) -> bool:
        """Check if we can open a new position"""
        
        # Reset daily counter if new day
        if datetime.now().date() > self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = datetime.now().date()
        
        # Check daily trade limit
        if self.daily_trade_count >= MAX_DAILY_TRADES:
            return False
        
        # Check position size limits
        if size_usd > MAX_POSITION_SIZE_USD:
            return False
        
        if size_usd < MIN_POSITION_SIZE_USD:
            return False
        
        # Check total exposure
        current_exposure = sum(pos['size_usd'] for pos in self.paper_positions.values())
        if current_exposure + size_usd > MAX_TOTAL_EXPOSURE_USD:
            return False
        
        # Check available balance
        if size_usd > self.paper_balance * 0.8:  # Leave some buffer
            return False
        
        return True
    
    def calculate_position_size(self, symbol: str, price: float, confidence: float) -> float:
        """Calculate appropriate position size based on confidence and balance"""
        
        # Base position size (1-5 USD based on confidence)
        base_size = MIN_POSITION_SIZE_USD + (confidence * 4.0)
        
        # Limit to max position size
        size_usd = min(base_size, MAX_POSITION_SIZE_USD)
        
        # Convert to quantity
        quantity = size_usd / price
        
        # Round to minimum quantity
        min_qty = MIN_QUANTITIES.get(symbol, 0.01)
        quantity = max(quantity, min_qty)
        
        return quantity
    
    def simulate_trade(self, symbol: str, side: str, quantity: float, price: float, 
                      trade_type: str = "market") -> Dict:
        """Simulate a trade in paper trading mode"""
        
        size_usd = quantity * price
        
        if not self.can_open_position(symbol, side, size_usd):
            return {
                'success': False,
                'error': 'Position limits exceeded',
                'orderId': None
            }
        
        # Generate fake order ID
        order_id = f"PAPER_{int(datetime.now().timestamp())}"
        
        # Calculate fees (0.1% typical)
        fee_usd = size_usd * 0.001
        
        # Record position
        position_data = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_price': price,
            'size_usd': size_usd,
            'fee_usd': fee_usd,
            'timestamp': datetime.now().isoformat(),
            'order_id': order_id,
            'status': 'open'
        }
        
        self.paper_positions[order_id] = position_data
        self.paper_balance -= (size_usd + fee_usd)
        self.daily_trade_count += 1
        
        # Log trade
        self._log_trade(position_data)
        
        return {
            'success': True,
            'orderId': order_id,
            'quantity': quantity,
            'price': price,
            'size_usd': size_usd,
            'fee_usd': fee_usd
        }
    
    def close_paper_position(self, order_id: str, exit_price: float, reason: str = "manual") -> Dict:
        """Close a paper trading position"""
        
        if order_id not in self.paper_positions:
            return {'success': False, 'error': 'Position not found'}
        
        position = self.paper_positions[order_id]
        
        if position['status'] != 'open':
            return {'success': False, 'error': 'Position already closed'}
        
        # Calculate P&L
        entry_price = position['entry_price']
        quantity = position['quantity']
        
        if position['side'] == 'BUY':
            pnl_usd = (exit_price - entry_price) * quantity
        else:
            pnl_usd = (entry_price - exit_price) * quantity
        
        # Calculate fees
        exit_size_usd = quantity * exit_price
        exit_fee_usd = exit_size_usd * 0.001
        
        # Net P&L after fees
        net_pnl = pnl_usd - position['fee_usd'] - exit_fee_usd
        
        # Update balance
        self.paper_balance += exit_size_usd - exit_fee_usd
        
        # Update position
        position.update({
            'status': 'closed',
            'exit_price': exit_price,
            'exit_timestamp': datetime.now().isoformat(),
            'pnl_usd': net_pnl,
            'exit_fee_usd': exit_fee_usd,
            'close_reason': reason
        })
        
        # Log trade closure
        self._log_trade_close(position)
        
        return {
            'success': True,
            'pnl_usd': net_pnl,
            'exit_price': exit_price,
            'position': position
        }
    
    def get_paper_balance(self) -> Dict:
        """Get current paper trading balance and statistics"""
        
        # Calculate unrealized P&L (would need current prices)
        open_positions = [p for p in self.paper_positions.values() if p['status'] == 'open']
        total_exposure = sum(p['size_usd'] for p in open_positions)
        
        # Calculate total P&L from closed positions
        closed_positions = [p for p in self.paper_positions.values() if p['status'] == 'closed']
        total_realized_pnl = sum(p.get('pnl_usd', 0) for p in closed_positions)
        
        return {
            'balance': self.paper_balance,
            'total_exposure': total_exposure,
            'available_balance': self.paper_balance,
            'open_positions': len(open_positions),
            'total_trades': len(self.paper_positions),
            'realized_pnl': total_realized_pnl,
            'win_rate': self._calculate_win_rate(),
            'daily_trades': self.daily_trade_count
        }
    
    def _calculate_win_rate(self) -> float:
        """Calculate win rate from closed positions"""
        closed_positions = [p for p in self.paper_positions.values() if p['status'] == 'closed']
        
        if not closed_positions:
            return 0.0
        
        winning_trades = len([p for p in closed_positions if p.get('pnl_usd', 0) > 0])
        return winning_trades / len(closed_positions) * 100
    
    def _log_trade(self, trade_data: Dict):
        """Log trade to file"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'action': 'open_position',
                'data': trade_data
            }
            
            # Append to trade log
            with open(TRADE_LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            print(f"Error logging trade: {e}")
    
    def _log_trade_close(self, trade_data: Dict):
        """Log trade closure to file"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'action': 'close_position',
                'data': trade_data
            }
            
            # Append to trade log
            with open(TRADE_LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            print(f"Error logging trade close: {e}")
    
    def _load_paper_data(self):
        """Load existing paper trading data"""
        try:
            if os.path.exists('paper_trading_data.json'):
                with open('paper_trading_data.json', 'r') as f:
                    data = json.load(f)
                    self.paper_balance = data.get('balance', 25.0)
                    self.paper_positions = data.get('positions', {})
                    self.daily_trade_count = data.get('daily_trade_count', 0)
                    
        except Exception as e:
            print(f"Error loading paper data: {e}")
    
    def save_paper_data(self):
        """Save paper trading data"""
        try:
            data = {
                'balance': self.paper_balance,
                'positions': self.paper_positions,
                'daily_trade_count': self.daily_trade_count,
                'last_update': datetime.now().isoformat()
            }
            
            with open('paper_trading_data.json', 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving paper data: {e}")

class TokenConfigManager:
    """Manages token-specific configuration and minimum quantities"""
    
    def __init__(self):
        self.token_configs = {
            'XRP': {
                'symbol': 'XRPUSDT',
                'min_qty': 2.0,  # Updated to match API requirement
                'price_decimals': 4,
                'qty_decimals': 1,
                'sentiment_weight': 1.0
            },
            'ADA': {
                'symbol': 'ADAUSDT',
                'min_qty': 1.0,
                'price_decimals': 4,
                'qty_decimals': 1,
                'sentiment_weight': 1.0
            },
            'SUI': {
                'symbol': 'SUIUSDT',
                'min_qty': 0.1,
                'price_decimals': 4,
                'qty_decimals': 2,
                'sentiment_weight': 1.2  # Higher weight for newer tokens
            },
            'UNI': {
                'symbol': 'UNIUSDT',
                'min_qty': 0.1,
                'price_decimals': 3,
                'qty_decimals': 2,
                'sentiment_weight': 1.0
            },
            'LINK': {
                'symbol': 'LINKUSDT',
                'min_qty': 0.1,
                'price_decimals': 3,
                'qty_decimals': 2,
                'sentiment_weight': 1.0
            },
            'SOL': {
                'symbol': 'SOLUSDT',
                'min_qty': 0.01,
                'price_decimals': 2,
                'qty_decimals': 3,
                'sentiment_weight': 1.1
            }
        }
    
    def get_token_config(self, symbol: str) -> Dict:
        """Get configuration for a specific token"""
        return self.token_configs.get(symbol, {})
    
    def get_trading_symbol(self, symbol: str) -> str:
        """Get the trading pair symbol (e.g., XRP -> XRPUSDT)"""
        config = self.get_token_config(symbol)
        return config.get('symbol', f'{symbol}USDT')
    
    def format_quantity(self, symbol: str, quantity: float) -> float:
        """Format quantity according to token specifications"""
        config = self.get_token_config(symbol)
        decimals = config.get('qty_decimals', 3)
        return round(quantity, decimals)
    
    def format_price(self, symbol: str, price: float) -> float:
        """Format price according to token specifications"""
        config = self.get_token_config(symbol)
        decimals = config.get('price_decimals', 4)
        return round(price, decimals)

# Global test trade manager instance
TEST_TRADE_MANAGER = TestTradeManager()

# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("TEST CONFIGURATION - Safe Trading Setup")
    print("=" * 70)
    
    # Initialize test manager
    test_manager = TestTradeManager()
    
    print(f"\n💰 Paper Trading Balance: ${test_manager.paper_balance:.2f}")
    print(f"📊 Max Position Size: ${MAX_POSITION_SIZE_USD}")
    print(f"🔒 Max Total Exposure: ${MAX_TOTAL_EXPOSURE_USD}")
    print(f"📈 Max Leverage: {MAX_LEVERAGE}x")
    
    print(f"\n🎯 Supported Tokens:")
    for symbol in SUPPORTED_TOKENS:
        trading_symbol = symbol + 'USDT'
        min_qty = MIN_QUANTITIES.get(trading_symbol, 0.01)
        print(f"  {symbol:4} -> {trading_symbol:8} (min: {min_qty})")
    
    print(f"\n📊 Sentiment Thresholds:")
    print(f"  Buy Signal:  > {SENTIMENT_BUY_THRESHOLD}")
    print(f"  Sell Signal: < {SENTIMENT_SELL_THRESHOLD}")
    print(f"  Min Confidence: {MIN_CONFIDENCE_THRESHOLD}")
    
    # Test paper trading
    print(f"\n🧪 Testing Paper Trading...")
    
    # Simulate a trade
    result = test_manager.simulate_trade('XRPUSDT', 'BUY', 2.0, 0.75)
    if result['success']:
        print(f"✅ Paper trade executed: {result['orderId']}")
        print(f"   Size: ${result['size_usd']:.2f}, Fee: ${result['fee_usd']:.3f}")
        
        # Check balance
        balance_info = test_manager.get_paper_balance()
        print(f"   New balance: ${balance_info['balance']:.2f}")
        print(f"   Open positions: {balance_info['open_positions']}")
    else:
        print(f"❌ Paper trade failed: {result['error']}")
    
    print("\n" + "=" * 70)
    print("✅ Test configuration ready!")
    print("💡 Paper trading mode enabled - no real money at risk")
    print("📝 All trades logged to:", TRADE_LOG_FILE)
    print("=" * 70)