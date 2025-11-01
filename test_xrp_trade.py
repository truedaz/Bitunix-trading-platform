#!/usr/bin/env python3
"""
XRP Minimum Quantity Trade Test Script

This script demonstrates getting the real minimum quantity for XRP from the API
and shows trade calculations before allowing the user to place a test trade.
"""

from bitunix_model import BitunixClient

def get_xrp_trade_details():
    """Get all trade details for XRP minimum quantity trade"""
    client = BitunixClient()

    # Get token info (this will fetch real min quantity from API)
    token_info = client.get_token_info('XRP')
    trading_symbol = token_info['trading_symbol']
    min_quantity = token_info['min_quantity']
    current_price = token_info['current_price']

    # Get leverage dynamically (try to get from existing positions, fallback to 5x)
    leverage = 5  # Default based on existing positions
    try:
        positions = client.get_pending_positions()
        if positions.get('code') == 0:
            data = positions.get('data', [])
            if data:
                # Use leverage from first position
                leverage = int(data[0].get('leverage', 5))
    except:
        pass

    # Calculate trade details
    quantity = min_quantity
    position_value = quantity * current_price
    margin_required = position_value / leverage
    potential_pnl = position_value * 0.02  # 2% potential gain
    liquidation_price = current_price * (1 - (1/leverage) + 0.005)  # Simplified calc

    return {
        'symbol': 'XRP',
        'trading_symbol': trading_symbol,
        'min_quantity': min_quantity,
        'current_price': current_price,
        'leverage': leverage,
        'quantity': quantity,
        'position_value': position_value,
        'margin_required': margin_required,
        'potential_pnl_2pct': potential_pnl,
        'liquidation_price': liquidation_price,
        'risk_percentage': (margin_required / 25.0) * 100  # Assuming $25 account
    }

def display_trade_details(details):
    """Display trade details in a formatted way"""
    print("=" * 60)
    print("🪙 XRP MINIMUM QUANTITY TRADE DETAILS")
    print("=" * 60)
    print(f"Symbol: {details['symbol']}")
    print(f"Trading Pair: {details['trading_symbol']}")
    print(f"Current Price: ${details['current_price']:.4f}")
    print(f"Leverage: {details['leverage']}x")
    print()
    print("📊 TRADE CALCULATIONS:")
    print(f"Min Quantity: {details['min_quantity']} XRP")
    print(f"Position Size: {details['quantity']} XRP")
    print(f"Position Value: ${details['position_value']:.4f}")
    print(f"Margin Required: ${details['margin_required']:.4f}")
    print(f"Risk: {details['risk_percentage']:.2f}% of account")
    print()
    print("🎯 POTENTIAL OUTCOMES:")
    print(f"2% Gain: +${details['potential_pnl_2pct']:.4f}")
    print(f"Liquidation Price: ${details['liquidation_price']:.4f}")
    print("=" * 60)

def place_test_trade(details):
    """Place the actual test trade"""
    client = BitunixClient()

    print(f"\n🔄 Placing test trade for {details['quantity']} XRP at ${details['current_price']:.4f}...")

    result = client.place_market_order(
        details['trading_symbol'],
        'BUY',
        str(details['quantity'])
    )

    if result.get('code') == 0:
        order_id = result.get('data', {}).get('orderId', 'Unknown')
        print(f"✅ TRADE SUCCESSFUL!")
        print(f"Order ID: {order_id}")
        return True
    else:
        error_msg = result.get('msg', 'Unknown error')
        print(f"❌ TRADE FAILED: {error_msg}")
        return False

def main():
    print("🚀 XRP Minimum Quantity Trade Test")
    print("This script will show trade details and allow placing a test trade.\n")

    try:
        # Get trade details
        details = get_xrp_trade_details()

        # Display details
        display_trade_details(details)

        # Ask user if they want to proceed
        while True:
            response = input("\n❓ Place this test trade? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                success = place_test_trade(details)
                if success:
                    print("\n📈 Trade placed successfully! Check your positions.")
                break
            elif response in ['n', 'no']:
                print("Trade cancelled.")
                break
            else:
                print("Please enter 'y' or 'n'")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()