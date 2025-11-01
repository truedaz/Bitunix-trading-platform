"""
BITUNIX API Client - Working Methods Only
Consolidated client with all verified working endpoints.

Working Endpoints (✅):
- place_market_order: Open positions (BUY/SELL)
- close_all_positions: Close all positions for a margin coin (RELIABLE)
- get_pending_positions: Get positions with positionId (STABLE)

Unstable Endpoints (⚠️):
- get_account: Returns 'Signature Error' intermittently
- get_all_positions: Returns 'System error' intermittently  
- get_symbol_position: Returns 'System error' intermittently
- set_leverage: Returns 'System error' intermittently
- query_order: Returns 'System error' intermittently

Failed Endpoints (❌):
- flash_close_position: Returns 'Network Error' (code 1)
- close_position (with positionId): Returns 'System error'
- place_order with reduceOnly + tradeSide=CLOSE: Parameter error

Authentication:
- Dual SHA256 signature scheme
- Stage 1: digest = SHA256(nonce + timestamp + api_key + query_string + body)
- Stage 2: signature = SHA256(digest + secret_key)
"""

import requests
import time
import hashlib
import json
import uuid
from typing import Dict, Optional, Any, List
from creds import BITUNIX_CONFIG
from test_config import (
    TEST_MODE, SUPPORTED_TOKENS, MAX_POSITION_SIZE_USD, MAX_TOTAL_EXPOSURE_USD,
    MAX_DAILY_TRADES, MAX_LEVERAGE, MIN_QUANTITIES, SENTIMENT_BUY_THRESHOLD,
    SENTIMENT_SELL_THRESHOLD, MIN_CONFIDENCE_THRESHOLD, TAKE_PROFIT_PERCENTAGE,
    STOP_LOSS_PERCENTAGE, TestTradeManager, TokenConfigManager
)


# ==================== AUTHENTICATION HELPERS ====================

def get_nonce() -> str:
    """Generate a random string as nonce"""
    return str(uuid.uuid4()).replace('-', '')


def get_timestamp() -> str:
    """Get current timestamp in milliseconds"""
    return str(int(time.time() * 1000))


def sort_params(params: Dict[str, Any]) -> str:
    """Sort parameters and create query string"""
    if not params:
        return ""
    sorted_params = sorted(params.items())
    return "&".join([f"{k}={v}" for k, v in sorted_params])


def get_auth_headers(api_key: str, secret_key: str, query_string: str, body: str = "") -> Dict[str, str]:
    """
    Generate authentication headers using dual SHA256 signature
    
    Steps:
    1. digest = SHA256(nonce + timestamp + api_key + query_string + body)
    2. signature = SHA256(digest + secret_key)
    """
    nonce = get_nonce()
    timestamp = get_timestamp()
    
    # Stage 1: Create digest
    digest_input = nonce + timestamp + api_key + query_string + body
    digest = hashlib.sha256(digest_input.encode('utf-8')).hexdigest()
    
    # Stage 2: Create signature
    sign_input = digest + secret_key
    signature = hashlib.sha256(sign_input.encode('utf-8')).hexdigest()
    
    return {
        'api-key': api_key,
        'nonce': nonce,
        'timestamp': timestamp,
        'sign': signature,
        'Content-Type': 'application/json'
    }


# ==================== BITUNIX CLIENT ====================

class BitunixClient:
    """
    Bitunix Futures API Client with Multi-Token Support and Test Mode
    
    Enhanced Features:
    - Support for XRP, ADA, SUI, UNI, LINK, SOL
    - Test mode with paper trading
    - Automatic minimum quantity detection
    - Risk management for small accounts
    """
    
    def __init__(self, test_mode: bool = None):
        self.api_key = BITUNIX_CONFIG["api_key"]
        self.secret_key = BITUNIX_CONFIG["api_secret"]
        self.base_url = BITUNIX_CONFIG["base_url"]
        self.session = requests.Session()
        
        # Test mode configuration
        # Test mode setup
        self.test_mode = test_mode if test_mode is not None else TEST_MODE
        self.test_manager = TestTradeManager() if self.test_mode else None
        self.token_manager = TokenConfigManager()
        
        # Default lightweight retry settings for flaky endpoints
        self._default_retries = 2
        self._default_retry_delay = 0.5
        
        print(f"Initialized BitunixClient (Test Mode: {self.test_mode})")
    
    def get_supported_tokens(self) -> List[str]:
        """Get list of supported tokens for trading"""
        return SUPPORTED_TOKENS
    
    def get_token_info(self, symbol: str) -> Dict[str, Any]:
        """Get detailed information about a token"""
        config = self.token_manager.get_token_config(symbol)
        trading_symbol = self.token_manager.get_trading_symbol(symbol)
        
        # Get current price (if not in test mode)
        current_price = 0.0
        if not self.test_mode:
            try:
                price_data = self.get_ticker_price(trading_symbol)
                if price_data and price_data.get('code') == 0:
                    current_price = float(price_data.get('data', {}).get('price', 0))
            except Exception:
                pass
        else:
            # Mock prices for testing
            mock_prices = {
                'XRPUSDT': 0.75, 'ADAUSDT': 0.45, 'SUIUSDT': 1.85,
                'UNIUSDT': 8.50, 'LINKUSDT': 15.20, 'SOLUSDT': 125.50
            }
            current_price = mock_prices.get(trading_symbol, 1.0)
        
        return {
            'symbol': symbol,
            'trading_symbol': trading_symbol,
            'current_price': current_price,
            'min_quantity': config.get('min_qty', 0.01),
            'price_decimals': config.get('price_decimals', 4),
            'qty_decimals': config.get('qty_decimals', 3),
            'sentiment_weight': config.get('sentiment_weight', 1.0)
        }
    
    def get_all_tokens_info(self) -> Dict[str, Dict]:
        """Get information for all supported tokens"""
        tokens_info = {}
        for symbol in self.get_supported_tokens():
            tokens_info[symbol] = self.get_token_info(symbol)
        return tokens_info
    
    def calculate_position_size(self, symbol: str, sentiment_confidence: float = 0.5, 
                              max_risk_usd: float = None) -> Dict[str, float]:
        """
        Calculate appropriate position size based on account balance and risk management
        
        Args:
            symbol: Token symbol (e.g., 'XRP')
            sentiment_confidence: Confidence level 0-1
            max_risk_usd: Maximum risk in USD (overrides config)
        
        Returns:
            Dict with quantity, size_usd, and risk info
        """
        token_info = self.get_token_info(symbol)
        current_price = token_info['current_price']
        min_quantity = token_info['min_quantity']
        
        if self.test_mode:
            # Use test manager for position sizing
            max_risk = max_risk_usd or MAX_POSITION_SIZE_USD
            quantity = self.test_manager.calculate_position_size(
                token_info['trading_symbol'], current_price, sentiment_confidence
            )
        else:
            # Real trading position sizing
            max_risk = max_risk_usd or MAX_POSITION_SIZE_USD
            
            # Calculate quantity based on risk and confidence
            risk_adjusted_size = max_risk * sentiment_confidence
            quantity = risk_adjusted_size / current_price
            
            # Ensure minimum quantity
            quantity = max(quantity, min_quantity)
        
        # Format quantity
        quantity = self.token_manager.format_quantity(symbol, quantity)
        size_usd = quantity * current_price
        
        return {
            'quantity': quantity,
            'size_usd': size_usd,
            'price': current_price,
            'min_quantity': min_quantity,
            'risk_percentage': (size_usd / 25.0) * 100  # Assuming $25 account
        }
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and return parsed JSON"""
        try:
            response.raise_for_status()
            result = response.json()
            # Normalize non-dict payloads into a standard {code,data,msg} shape
            if isinstance(result, list):
                return {"code": 0, "data": result, "msg": "Success"}
            if not isinstance(result, dict):
                return {"code": 0, "data": result, "msg": "Success"}

            # Print API errors but return the response for caller to handle
            if result.get('code') != 0:
                error_msg = result.get('msg', 'Unknown error')
                error_code = result.get('code', -1)
                # Suppress "System error" (code 2) in test mode - these are expected
                if not (self.test_mode and error_code == 2):
                    print(f"API Error {error_code}: {error_msg}")

            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response text: {e.response.text}")
            raise
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response text: {response.text}")
            raise

    def _post_json(self, path: str, body_dict: Dict[str, Any], retries: Optional[int] = None,
                   retry_delay: Optional[float] = None) -> Dict[str, Any]:
        """
        Helper to POST JSON with signing and lightweight retry on transient errors.
        Retries when API returns non-zero code, up to retries.
        """
        if retries is None:
            retries = self._default_retries
        if retry_delay is None:
            retry_delay = self._default_retry_delay

        url = f"{self.base_url}{path}"
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)

        last_res: Dict[str, Any] = {}
        for attempt in range(retries + 1):
            response = self.session.post(url, data=body, headers=headers)
            res = self._handle_response(response)
            # Success
            if isinstance(res, dict) and res.get('code') == 0:
                return res
            last_res = res
            # Backoff before next try
            if attempt < retries:
                try:
                    time.sleep(retry_delay)
                except Exception:
                    pass
        return last_res
    
    # ==================== WORKING ENDPOINTS (✅) ====================
    
    def place_market_order(self, symbol: str, side: str, quantity: str) -> Dict[str, Any]:
        """
        Place a market order to OPEN a position with test mode support.
        
        ✅ VERIFIED WORKING - Reliable for opening positions
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT", "SOLUSDT", "BTCUSDT") 
            side: "BUY" or "SELL"
            quantity: Order quantity as string (e.g., "2" for 2 XRP)
        
        Returns:
            API response with order details including orderId
        """
        if self.test_mode:
            # Use paper trading
            price = self.get_mock_price(symbol)
            return self.test_manager.simulate_trade(symbol, side, float(quantity), price)
        
        url = f"{self.base_url}/api/v1/futures/trade/place_order"
        body_dict = {
            "symbol": symbol,
            "side": side,
            "orderType": "MARKET",
            "qty": quantity,
            "tradeSide": "OPEN"
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def place_multi_token_order(self, token_symbol: str, side: str, 
                               sentiment_confidence: float = 0.5) -> Dict[str, Any]:
        """
        Place an order for any supported token with automatic sizing
        
        Args:
            token_symbol: Token symbol (e.g., 'XRP', 'SOL')
            side: "BUY" or "SELL" 
            sentiment_confidence: Confidence level for position sizing
        
        Returns:
            API response with order details
        """
        # Get token configuration
        token_info = self.get_token_info(token_symbol)
        trading_symbol = token_info['trading_symbol']
        
        # Calculate position size
        position_info = self.calculate_position_size(token_symbol, sentiment_confidence)
        quantity = str(position_info['quantity'])
        
        print(f"Placing {side} order for {token_symbol}:")
        print(f"  Trading Symbol: {trading_symbol}")
        print(f"  Quantity: {quantity}")
        print(f"  Size: ${position_info['size_usd']:.2f}")
        print(f"  Risk: {position_info['risk_percentage']:.1f}%")
        
        # Place the order
        return self.place_market_order(trading_symbol, side, quantity)
    
    def get_mock_price(self, symbol: str) -> float:
        """Get mock price for test mode"""
        mock_prices = {
            'XRPUSDT': 0.75, 'ADAUSDT': 0.45, 'SUIUSDT': 1.85,
            'UNIUSDT': 8.50, 'LINKUSDT': 15.20, 'SOLUSDT': 125.50
        }
        return mock_prices.get(symbol, 1.0)
    
    def get_ticker_price(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker price for a symbol"""
        try:
            # url = f"{self.base_url}/api/v1/futures/market/tickers?symbols=BTCUSDT,ETHUSDT"
            # params = {}
            url = f"{self.base_url}/api/v1/futures/market/tickers"
            params = {"symbol": symbol}
            
            response = self.session.get(url, params=params, timeout=10)
            return self._handle_response(response)
            
        except Exception as e:
            print(f"Error getting ticker price for {symbol}: {e}")
            return {"code": -1, "msg": str(e)}
    
    def get_all_tickers(self) -> Dict[str, Any]:
        """Get all ticker prices"""
        try:
            url = f"{self.base_url}/api/v1/futures/market/tickers"
            
            response = self.session.get(url, timeout=10)
            return self._handle_response(response)
            
        except Exception as e:
            print(f"Error getting all tickers: {e}")
            return {"code": -1, "msg": str(e)}
    
    def place_limit_order(self, symbol: str, side: str, quantity: str, price: str,
                         trade_side: str = "OPEN") -> Dict[str, Any]:
        """
        Place a limit order.
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity as string
            price: Limit price as string
            trade_side: "OPEN" or "CLOSE" (default: "OPEN")
        
        Returns:
            API response with order details
        """
        url = f"{self.base_url}/api/v1/futures/trade/place_order"
        body_dict = {
            "symbol": symbol,
            "side": side,
            "orderType": "LIMIT",
            "qty": quantity,
            "price": price,
            "tradeSide": trade_side
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def place_stop_loss(self, symbol: str, side: str, quantity: str, sl_price: str) -> Dict[str, Any]:
        """
        Place a stop loss order (LIMIT order to close at SL price).
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT")
            side: "BUY" or "SELL" (opposite of position side)
            quantity: Order quantity as string
            sl_price: Stop loss price as string
        
        Returns:
            API response with order details
        """
        url = f"{self.base_url}/api/v1/futures/trade/place_order"
        body_dict = {
            "symbol": symbol,
            "side": side,
            "orderType": "LIMIT",
            "qty": quantity,
            "price": sl_price,
            "tradeSide": "CLOSE",
            "effect": "GTC",
            "reduceOnly": True
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def place_take_profit(self, symbol: str, side: str, quantity: str, tp_price: str) -> Dict[str, Any]:
        """
        Place a take profit order (LIMIT order to close at TP price).
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT")
            side: "BUY" or "SELL" (opposite of position side)
            quantity: Order quantity as string
            tp_price: Take profit price as string
        
        Returns:
            API response with order details
        """
        url = f"{self.base_url}/api/v1/futures/trade/place_order"
        body_dict = {
            "symbol": symbol,
            "side": side,
            "orderType": "LIMIT",
            "qty": quantity,
            "price": tp_price,
            "tradeSide": "CLOSE",
            "effect": "GTC",
            "reduceOnly": True
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)

    def place_position_tp_sl_order(
        self,
        symbol: str,
        tp_price: str = None,
        sl_price: str = None,
        tp_stop_type: str = "MARK",
        sl_stop_type: str = "MARK",
        tp_order_type: str = "MARKET",
        sl_order_type: str = "MARKET",
        tp_qty: str = None,
        sl_qty: str = None,
    ) -> Dict[str, Any]:
        """
        Place TP/SL for current position without positionId using
        /api/v1/futures/trade/place_position_tp_sl_order

        Any of TP or SL parts can be omitted by passing None.
        """
        url = f"{self.base_url}/api/v1/futures/trade/place_position_tp_sl_order"
        body_dict: Dict[str, Any] = {"symbol": symbol}
        if tp_price is not None:
            body_dict.update({
                "tpPrice": str(tp_price),
                "tpStopType": tp_stop_type,
                "tpOrderType": tp_order_type,
            })
            if tp_qty is not None:
                body_dict["tpQty"] = str(tp_qty)
        if sl_price is not None:
            body_dict.update({
                "slPrice": str(sl_price),
                "slStopType": sl_stop_type,
                "slOrderType": sl_order_type,
            })
            if sl_qty is not None:
                body_dict["slQty"] = str(sl_qty)
        # Use retry helper due to occasional transient API errors
        return self._post_json("/api/v1/futures/trade/place_position_tp_sl_order", body_dict)

    def close_all_positions(self, margin_coin: str = "USDT") -> Dict[str, Any]:
        """
        Close ALL positions for the given margin coin at market price.
        
        ✅ VERIFIED WORKING - Most reliable close method
        
        WARNING: This closes ALL positions (all symbols, all directions) using
        the specified margin coin. Use with caution.
        
        Args:
            margin_coin: Margin currency (default: "USDT")
        
        Returns:
            API response indicating success/failure
            
        Example:
            >>> client.close_all_positions("USDT")
            {'code': 0, 'data': '', 'msg': 'Success'}
        """
        url = f"{self.base_url}/api/v1/futures/trade/close_all_position"
        body_dict = {"marginCoin": margin_coin}
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def close_position_market(self, symbol: str, side: str, quantity: str) -> Dict[str, Any]:
        """
        Close a position using a market order.
        
        ⚠️ UNTESTED - Individual position close may have API issues
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT")
            side: "BUY" or "SELL" (opposite of position side to close)
            quantity: Quantity to close as string
        
        Returns:
            API response with order details
            
        Example:
            >>> # To close a BUY position, use SELL
            >>> client.close_position_market("XRPUSDT", "SELL", "2")
        """
        url = f"{self.base_url}/api/v1/futures/trade/place_order"
        body_dict = {
            "symbol": symbol,
            "side": side,
            "orderType": "MARKET",
            "qty": quantity,
            "tradeSide": "CLOSE"
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def close_position_by_id(self, position_id: str, symbol: str, margin_coin: str = "USDT") -> Dict[str, Any]:
        """
        Close a position using positionId via the close_position endpoint.
        
        Note: This endpoint has been unreliable historically (System error),
        but when it works it's the cleanest way to close a specific position.
        
        Args:
            position_id: The positionId returned by get_pending_positions
            symbol: Trading pair (e.g., "XRPUSDT")
            margin_coin: Margin currency (default: "USDT")
        
        Returns:
            API response indicating success/failure
        """
        url = f"{self.base_url}/api/v1/futures/trade/close_position"
        body_dict = {
            "positionId": position_id,
            "symbol": symbol,
            "marginCoin": margin_coin
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)

    def close_position_via_place_order(
        self,
        symbol: str,
        position_id: str,
        side: str,
        quantity: str,
        reduce_only: bool = True,
    ) -> Dict[str, Any]:
        """
        Close position using the documented place_order endpoint with tradeSide=CLOSE.

        Docs note: When tradeSide is CLOSE, positionId is required. Side should match the
        original direction (close long: side=BUY; close short: side=SELL) and tradeSide=CLOSE.
        """
        url = f"{self.base_url}/api/v1/futures/trade/place_order"
        body_dict = {
            "symbol": symbol,
            "qty": str(quantity),
            "side": side,
            "tradeSide": "CLOSE",
            "positionId": position_id,
            "orderType": "MARKET",
            "reduceOnly": bool(reduce_only),
        }
        # Use retry helper due to occasional transient API errors
        return self._post_json("/api/v1/futures/trade/place_order", body_dict)

    def close_position_full_by_id(self, symbol: str, position_id: str) -> Dict[str, Any]:
        """
        Close 100% of a specific position by fetching its side and quantity, then
        submitting a MARKET CLOSE via place_order with required positionId.
        """
        # Fetch current pending positions and locate this one
        pos_res = self.get_pending_positions()
        if pos_res.get("code") != 0:
            return pos_res
        target = None
        for p in pos_res.get("data", []) or []:
            if str(p.get("positionId")) == str(position_id) and p.get("symbol") == symbol:
                target = p
                break
        if not target:
            return {"code": -1, "msg": "Position not found for given positionId/symbol"}
        # Try both interpretations to maximize compatibility across modes
        # Variant A (intuitive): close long => SELL, close short => BUY
        side_intuitive = "SELL" if target.get("side") == "BUY" else "BUY"
        # Variant B (per docs note): close long => BUY, close short => SELL
        side_docs = "BUY" if target.get("side") == "BUY" else "SELL"
        qty = target.get("qty") if isinstance(target.get("qty"), str) else str(target.get("qty"))
        # Attempt Variant A first
        res_a = self.close_position_via_place_order(
            symbol=symbol,
            position_id=position_id,
            side=side_intuitive,
            quantity=qty,
            reduce_only=True,
        )
        if res_a and res_a.get("code") == 0:
            return res_a
        # Attempt Variant B if A failed
        res_b = self.close_position_via_place_order(
            symbol=symbol,
            position_id=position_id,
            side=side_docs,
            quantity=qty,
            reduce_only=True,
        )
        return res_b

    def place_position_tpsl_by_id(
        self,
        symbol: str,
        position_id: str,
        tp_price: Optional[str] = None,
        sl_price: Optional[str] = None,
        tp_stop_type: str = "LAST_PRICE",
        sl_stop_type: str = "LAST_PRICE",
    ) -> Dict[str, Any]:
        """
        Set TP/SL on a specific position using the official endpoint:
        POST /api/v1/futures/tpsl/position/place_order

        Pass only the fields you want to set (e.g., TP only).
        """
        body_dict: Dict[str, Any] = {
            "symbol": symbol,
            "positionId": position_id,
        }
        if tp_price is not None:
            body_dict["tpPrice"] = str(tp_price)
            body_dict["tpStopType"] = tp_stop_type
        if sl_price is not None:
            body_dict["slPrice"] = str(sl_price)
            body_dict["slStopType"] = sl_stop_type

        # Use retry helper due to occasional transient API errors
        return self._post_json("/api/v1/futures/tpsl/position/place_order", body_dict)

    def place_tpsl_order_with_qty(
        self,
        symbol: str,
        position_id: str,
        tp_price: Optional[str] = None,
        sl_price: Optional[str] = None,
        tp_qty: Optional[str] = None,
        sl_qty: Optional[str] = None,
        tp_stop_type: str = "LAST_PRICE",
        sl_stop_type: str = "LAST_PRICE",
        tp_order_type: str = "MARKET",
        sl_order_type: str = "MARKET",
        tp_order_price: Optional[str] = None,
        sl_order_price: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place TP/SL with explicit quantities using the documented endpoint:
        POST /api/v1/futures/tpsl/place_order

        Notes:
        - At least one of tpPrice or slPrice is required
        - At least one of tpQty or slQty is required
        - Default order type is MARKET; order price is optional for LIMIT
        """
        url = f"{self.base_url}/api/v1/futures/tpsl/place_order"
        body_dict: Dict[str, Any] = {
            "symbol": symbol,
            "positionId": position_id,
        }
        if tp_price is not None:
            body_dict["tpPrice"] = str(tp_price)
            body_dict["tpStopType"] = tp_stop_type
            body_dict["tpOrderType"] = tp_order_type
            if tp_order_price is not None:
                body_dict["tpOrderPrice"] = str(tp_order_price)
        if sl_price is not None:
            body_dict["slPrice"] = str(sl_price)
            body_dict["slStopType"] = sl_stop_type
            body_dict["slOrderType"] = sl_order_type
            if sl_order_price is not None:
                body_dict["slOrderPrice"] = str(sl_order_price)
        if tp_qty is not None:
            body_dict["tpQty"] = str(tp_qty)
        if sl_qty is not None:
            body_dict["slQty"] = str(sl_qty)

        # Use retry helper due to occasional transient API errors
        return self._post_json("/api/v1/futures/tpsl/place_order", body_dict)

    # Convenience wrappers (explicit TP or SL only)
    def set_take_profit_by_id(
        self,
        symbol: str,
        position_id: str,
        tp_price: str,
        tp_stop_type: str = "LAST_PRICE",
    ) -> Dict[str, Any]:
        """
        Convenience: Set ONLY Take Profit on a position by ID.
        """
        return self.place_position_tpsl_by_id(
            symbol=symbol,
            position_id=position_id,
            tp_price=str(tp_price),
            tp_stop_type=tp_stop_type,
        )

    def set_stop_loss_by_id(
        self,
        symbol: str,
        position_id: str,
        sl_price: str,
        sl_stop_type: str = "LAST_PRICE",
    ) -> Dict[str, Any]:
        """
        Convenience: Set ONLY Stop Loss on a position by ID.
        """
        return self.place_position_tpsl_by_id(
            symbol=symbol,
            position_id=position_id,
            sl_price=str(sl_price),
            sl_stop_type=sl_stop_type,
        )

    # Convenience wrappers that ensure 100% of the current position size is used
    def set_take_profit_full_by_id(
        self,
        symbol: str,
        position_id: str,
        tp_price: str,
        tp_stop_type: str = "LAST_PRICE",
        tp_order_type: str = "MARKET",
    ) -> Dict[str, Any]:
        """
        Set TP to close 100% of the position by fetching the current position qty.
        """
        # Fetch current pending positions and find this positionId
        pos_res = self.get_pending_positions()
        if pos_res.get("code") != 0:
            return pos_res
        qty: Optional[str] = None
        for p in pos_res.get("data", []) or []:
            if str(p.get("positionId")) == str(position_id) and p.get("symbol") == symbol:
                qty = p.get("qty") if isinstance(p.get("qty"), str) else str(p.get("qty"))
                break
        if not qty:
            return {"code": -1, "msg": "Position qty not found for positionId"}

        return self.place_tpsl_order_with_qty(
            symbol=symbol,
            position_id=position_id,
            tp_price=str(tp_price),
            tp_qty=qty,
            tp_stop_type=tp_stop_type,
            tp_order_type=tp_order_type,
        )

    def set_stop_loss_full_by_id(
        self,
        symbol: str,
        position_id: str,
        sl_price: str,
        sl_stop_type: str = "LAST_PRICE",
        sl_order_type: str = "MARKET",
    ) -> Dict[str, Any]:
        """
        Set SL to close 100% of the position by fetching the current position qty.
        """
        # Fetch current pending positions and find this positionId
        pos_res = self.get_pending_positions()
        if pos_res.get("code") != 0:
            return pos_res
        qty: Optional[str] = None
        for p in pos_res.get("data", []) or []:
            if str(p.get("positionId")) == str(position_id) and p.get("symbol") == symbol:
                qty = p.get("qty") if isinstance(p.get("qty"), str) else str(p.get("qty"))
                break
        if not qty:
            return {"code": -1, "msg": "Position qty not found for positionId"}

        return self.place_tpsl_order_with_qty(
            symbol=symbol,
            position_id=position_id,
            sl_price=str(sl_price),
            sl_qty=qty,
            sl_stop_type=sl_stop_type,
            sl_order_type=sl_order_type,
        )
    
    def get_pending_positions(self) -> Dict[str, Any]:
        """
        Get pending positions with test mode support.
        
        ✅ VERIFIED WORKING - Stable and reliable
        
        Returns:
            API response with pending positions data including positionId
        """
        if self.test_mode:
            # Return paper trading positions
            paper_positions = []
            for order_id, position in self.test_manager.paper_positions.items():
                if position['status'] == 'open':
                    paper_positions.append({
                        'positionId': order_id,
                        'symbol': position['symbol'],
                        'qty': str(position['quantity']),
                        'side': position['side'],
                        'avgOpenPrice': str(position['entry_price']),
                        'leverage': MAX_LEVERAGE,
                        'unrealizedPNL': '0.00',  # Would need current price to calculate
                        'marginCoin': 'USDT'
                    })
            
            return {
                'code': 0,
                'data': paper_positions,
                'msg': 'Success (Paper Trading)'
            }
        
        url = f"{self.base_url}/api/v1/futures/position/get_pending_positions"
        headers = get_auth_headers(self.api_key, self.secret_key, "", "")
        
        response = self.session.get(url, headers=headers)
        return self._handle_response(response)
    
    def close_all_positions(self, margin_coin: str = "USDT") -> Dict[str, Any]:
        """
        Close ALL positions with test mode support.
        
        ✅ VERIFIED WORKING - Most reliable close method
        """
        if self.test_mode:
            # Close all paper trading positions
            closed_count = 0
            for order_id, position in list(self.test_manager.paper_positions.items()):
                if position['status'] == 'open':
                    # Get mock exit price
                    exit_price = self.get_mock_price(position['symbol'])
                    result = self.test_manager.close_paper_position(order_id, exit_price, "close_all")
                    if result['success']:
                        closed_count += 1
            
            return {
                'code': 0,
                'data': f'Closed {closed_count} paper positions',
                'msg': 'Success (Paper Trading)'
            }
        
        url = f"{self.base_url}/api/v1/futures/trade/close_all_position"
        body_dict = {"marginCoin": margin_coin}
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary with test mode support"""
        if self.test_mode:
            balance_info = self.test_manager.get_paper_balance()
            return {
                'balance': balance_info['balance'],
                'total_exposure': balance_info['total_exposure'],
                'available_balance': balance_info['available_balance'],
                'open_positions': balance_info['open_positions'],
                'total_trades': balance_info['total_trades'],
                'realized_pnl': balance_info['realized_pnl'],
                'win_rate': balance_info['win_rate'],
                'daily_trades': balance_info['daily_trades'],
                'mode': 'paper_trading'
            }
        else:
            # Real account summary (would need account API)
            return {
                'mode': 'live_trading',
                'balance': 0.0,
                'note': 'Live account data requires stable account API'
            }
    
    # ==================== UNSTABLE ENDPOINTS (⚠️) ====================
    # These work sometimes but return errors intermittently
    
    def get_account(self, margin_coin: str = "USDT") -> Dict[str, Any]:
        """
        Get account information.
        
        ⚠️ UNSTABLE - May return 'Signature Error' (code 10007)
        
        Args:
            margin_coin: Margin currency (default: "USDT")
        
        Returns:
            API response with account balance and margin info
        """
        url = f"{self.base_url}/api/v1/futures/account"
        params = {"marginCoin": margin_coin}
        
        query_string = sort_params(params)
        headers = get_auth_headers(self.api_key, self.secret_key, query_string)
        
        response = self.session.get(url, params=params, headers=headers)
        return self._handle_response(response)
    
    def get_all_positions(self) -> Dict[str, Any]:
        """
        Get all current positions.
        
        ⚠️ UNSTABLE - May return 'System error' (code 2)
        
        Returns:
            API response with positions data
        """
        url = f"{self.base_url}/api/v1/futures/position/get_positions"
        headers = get_auth_headers(self.api_key, self.secret_key, "", "")
        
        response = self.session.get(url, headers=headers)
        return self._handle_response(response)
    
    def get_symbol_position(self, symbol: str, margin_coin: str = "USDT") -> Dict[str, Any]:
        """
        Get position for a specific symbol.
        
        ⚠️ UNSTABLE - May return 'System error' (code 2)
        
        Args:
            symbol: Trading symbol (e.g., "XRPUSDT")
            margin_coin: Margin currency (default: "USDT")
        
        Returns:
            API response with position data
        """
        url = f"{self.base_url}/api/v1/futures/position/get_positions"
        params = {
            "symbol": symbol,
            "marginCoin": margin_coin
        }
        
        query_string = sort_params(params)
        headers = get_auth_headers(self.api_key, self.secret_key, query_string, "")
        
        response = self.session.get(url, params=params, headers=headers)
        return self._handle_response(response)
    
    def set_leverage(self, symbol: str, margin_coin: str, leverage: int, 
                     margin_mode: str = "ISOLATION") -> Dict[str, Any]:
        """
        Set leverage for a given symbol.
        
        ⚠️ UNSTABLE - May return 'System error' (code 2)
        
        Workaround: Set leverage manually in Bitunix web UI
        
        Args:
            symbol: Trading symbol (e.g., "XRPUSDT")
            margin_coin: Margin currency (e.g., "USDT")
            leverage: Desired leverage (e.g., 1, 2, 5, 15)
            margin_mode: Margin mode (default: "ISOLATION")
        
        Returns:
            API response
        """
        url = f"{self.base_url}/api/v1/futures/account/leverage"
        body_dict = {
            "symbol": symbol,
            "marginCoin": margin_coin,
            "leverage": str(leverage),
            "marginMode": margin_mode
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    def query_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Query order details.
        
        ⚠️ UNSTABLE - May return 'System error' (code 2)
        
        Args:
            order_id: Order ID to query
            symbol: Trading symbol
        
        Returns:
            API response with order details
        """
        url = f"{self.base_url}/api/v1/futures/trade/query_order"
        body_dict = {
            "orderId": order_id,
            "symbol": symbol
        }
        
        body = json.dumps(body_dict, separators=(',', ':'), sort_keys=True)
        headers = get_auth_headers(self.api_key, self.secret_key, "", body)
        
        response = self.session.post(url, data=body, headers=headers)
        return self._handle_response(response)
    
    # ==================== PUBLIC MARKET DATA ====================
    
    def get_klines(self, symbol: str, interval: str = "15m", limit: int = 100) -> Dict[str, Any]:
        """
        Get candlestick/kline data for price analysis.
        
        PUBLIC ENDPOINT - No authentication required
        
        Args:
            symbol: Trading pair (e.g., "XRPUSDT", "SOLUSDT")
            interval: Kline interval - "1m", "5m", "15m", "30m", "1h", "4h", "1d"
            limit: Number of candles to return (max 1000, default 100)
        
        Returns:
            Candlestick data with OHLCV information
        """
        if self.test_mode:
            # Generate mock kline data for testing
            import random
            current_time = int(time.time() * 1000)
            interval_ms = {
                "1m": 60000, "5m": 300000, "15m": 900000,
                "30m": 1800000, "1h": 3600000, "4h": 14400000, "1d": 86400000
            }.get(interval, 900000)
            
            base_price = self.get_mock_price(symbol)
            klines = []
            
            for i in range(limit):
                candle_time = current_time - (interval_ms * (limit - i))
                volatility = base_price * 0.02
                
                open_price = base_price + random.uniform(-volatility, volatility)
                close_price = open_price + random.uniform(-volatility, volatility)
                high_price = max(open_price, close_price) + random.uniform(0, volatility/2)
                low_price = min(open_price, close_price) - random.uniform(0, volatility/2)
                volume = random.uniform(100000, 1000000)
                
                klines.append({
                    "time": candle_time,
                    "open": f"{open_price:.4f}",
                    "high": f"{high_price:.4f}",
                    "low": f"{low_price:.4f}",
                    "close": f"{close_price:.4f}",
                    "volume": f"{volume:.2f}",
                    "closeTime": candle_time + interval_ms - 1
                })
            
            return {"code": 0, "data": klines, "msg": "success"}
        
        # Real API call (public endpoint)
        url = f"{self.base_url}/api/v1/futures/market/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            return self._handle_response(response)
        except Exception as e:
            return {"code": -1, "msg": f"Error fetching klines: {str(e)}"}

    def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol using multiple fallback methods.
        
        This method tries multiple approaches to get the most reliable price:
        1. get_ticker_price API call
        2. get_all_tickers API call
        3. Returns 0.0 if all methods fail
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Current price as float, or 0.0 if unable to fetch
        """
        # Method 1: Try get_ticker_price
        price_info = self.get_ticker_price(symbol)
        if price_info.get('code') == 0 and price_info.get('data'):
            price = float(price_info['data']['price'])
            if price > 0:
                return price
        
        # Method 2: Try get_all_tickers
        all_tickers = self.get_all_tickers()
        if all_tickers.get('code') == 0 and all_tickers.get('data'):
            for ticker in all_tickers['data']:
                if ticker.get('symbol') == symbol:
                    price = float(ticker.get('price', 0))
                    if price > 0:
                        return price
        
        # Method 3: Return 0.0 if all methods fail
        print(f"Warning: Unable to fetch current price for {symbol}")
        return 0.0


# ==================== USAGE EXAMPLES ====================

if __name__ == "__main__":
    print("=" * 70)
    print("BITUNIX API CLIENT - Working Methods")
    print("=" * 70)
    
    client = BitunixClient()
    
    print("\n✅ WORKING METHODS:")
    print("  1. place_market_order(symbol, side, quantity)")
    print("  2. close_all_positions(margin_coin)")
    print("  3. get_pending_positions()")
    
    print("\n⚠️  UNSTABLE METHODS (use with retry logic):")
    print("  4. get_account(margin_coin)")
    print("  5. get_all_positions()")
    print("  6. get_symbol_position(symbol, margin_coin)")
    print("  7. set_leverage(symbol, margin_coin, leverage)")
    print("  8. query_order(order_id, symbol)")
    
    print("\n" + "=" * 70)
    print("Example Usage:")
    print("=" * 70)
    print("""
# Open a position
order = client.place_market_order("XRPUSDT", "BUY", "2")
print(f"Order ID: {order.get('data', {}).get('orderId')}")

# Wait for position to fill
time.sleep(5)

# Check positions
positions = client.get_pending_positions()
print(f"Positions: {positions}")

# Close all positions
result = client.close_all_positions("USDT")
print(f"Close result: {result}")
""")
    print("=" * 70)
