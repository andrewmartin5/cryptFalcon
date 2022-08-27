import time, os, json
from binance.client import Client

symbol = "ETHUSDT"
url = "https://testnet.binance.vision/api"
api_key = os.environ.get('binance_api')
api_secret = os.environ.get('binance_secret')

def scrapeRecent():
    client = Client(api_key, api_secret)
    client.API_URL = url
    price = client.get_symbol_ticker(symbol = symbol)
    print(float(price["price"]))
    del client

def scrapeHist():
    client = Client(api_key, api_secret)
    client.API_URL = url
    timestamp = client._get_earliest_valid_timestamp(symbol, '1h')
    print(timestamp)
    # bars = client.get_historical_klines(symbol, '1h', timestamp)
    # with open(symbol + '_bars.json', 'w') as e:
    #     json.dump(bars, e)
    del client

def main():
    scrapeHist()
    pass

if __name__ == "__main__":
    main()