#!/usr/bin/env python3
"""
Test script for price fetching methods
"""

from bitunix_model import BitunixClient

def test_price_fetching():
    print("Testing price fetching methods...")

    client = BitunixClient()

    symbols = ['BTCUSDT']

    # for symbol in symbols:
    #     print(f"\n=== Testing {symbol} ===")

    # Method 1: get_ticker_price
    print("Method 1: get_ticker_price")
    price_info = client.get_ticker_price(symbols)
    print(f"Response: {price_info}")
    if price_info.get('code') == 0 and price_info.get('data'):
        # Handle the case where data is a list of tickers
        if isinstance(price_info['data'], list):
            for ticker in price_info['data']:
                symbol_name = ticker.get('symbol')
                price = float(ticker.get('lastPrice', 0))
                print(f"Price for {symbol_name}: {price}")
        else:
            # Handle single ticker response
            price = float(price_info['data'].get('lastPrice', 0))
            print(f"Price: {price}")
    else:
        print("Failed")

    # Method 2: get_all_tickers
    print("Method 2: get_all_tickers")
    all_tickers = client.get_all_tickers()
    print(all_tickers)
    print(f"Response code: {all_tickers.get('code')}")
    print("\n=== Done ===")

if __name__ == "__main__":
    test_price_fetching()