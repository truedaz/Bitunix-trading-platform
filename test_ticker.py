#!/usr/bin/env python3
"""
Test script to check ticker price functionality
"""

from bitunix_model import BitunixClient

def main():
    print("Testing ticker price functionality...")

    client = BitunixClient()

    # Test with BTCUSDT
    print("\n=== Testing get_ticker_price for BTCUSDT ===")
    try:
        price_info = client.get_ticker_price("BTCUSDT")
        print(f"Response: {price_info}")

        if price_info.get('code') == 0:
            price = price_info.get('data', {}).get('price')
            print(f"Current BTC price: {price}")
        else:
            print(f"Failed to get price: {price_info.get('msg')}")
    except Exception as e:
        print(f"Error: {e}")

    # Test with SOLUSDT
    print("\n=== Testing get_ticker_price for SOLUSDT ===")
    try:
        price_info = client.get_ticker_price("SOLUSDT")
        print(f"Response: {price_info}")

        if price_info.get('code') == 0:
            price = price_info.get('data', {}).get('price')
            print(f"Current SOL price: {price}")
        else:
            print(f"Failed to get price: {price_info.get('msg')}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    main()