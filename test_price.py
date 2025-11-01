#!/usr/bin/env python3
"""
Test script for price fetching methods
"""

from bitunix_model import BitunixClient

def test_price_fetching():
    print("Testing price fetching methods...")

    client = BitunixClient()

    symbols = ['BTCUSDT', 'SOLUSDT']

    for symbol in symbols:
        print(f"\n=== Testing {symbol} ===")

        # Method 1: get_ticker_price
        print("Method 1: get_ticker_price")
        price_info = client.get_ticker_price(symbol)
        print(f"Response: {price_info}")
        if price_info.get('code') == 0 and price_info.get('data'):
            price = float(price_info['data']['price'])
            print(f"Price: {price}")
        else:
            print("Failed")

        # Method 2: get_all_tickers
        print("Method 2: get_all_tickers")
        all_tickers = client.get_all_tickers()
        print(f"Response code: {all_tickers.get('code')}")
        if all_tickers.get('code') == 0 and all_tickers.get('data'):
            tickers = all_tickers['data']
            print(f"Total tickers: {len(tickers)}")
            found = False
            for ticker in tickers:
                if ticker.get('symbol') == symbol:
                    price = float(ticker.get('price', 0))
                    print(f"Found {symbol}: {price}")
                    found = True
                    break
            if not found:
                print(f"{symbol} not found in all {len(tickers)} tickers")
                # Show first few tickers for debugging
                print("First 3 tickers:")
                for i, ticker in enumerate(tickers[:3]):
                    print(f"  {i+1}: {ticker.get('symbol')} - {ticker.get('price')}")
        else:
            print("Failed")

    print("\n=== Done ===")

if __name__ == "__main__":
    test_price_fetching()