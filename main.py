import time, os, json, datetime, pandas
from binance.client import Client

# REF: https://python.plainenglish.io/how-to-download-trading-data-from-binance-with-python-21634af30195

symbol = "ETHUSDT"
url = "https://testnet.binance.vision/api"
api_key = os.environ.get("binance_api")
api_secret = os.environ.get("binance_secret")


def scrapeRecent():
    client = Client(api_key, api_secret)
    client.API_URL = url
    price = client.get_symbol_ticker(symbol=symbol)
    print(float(price["price"]))
    del client


def scrapeHist():
    interval = "1h"
    client = Client(api_key, api_secret)
    client.KLINE_INTERVAL_1HOUR
    hist = client.get_historical_klines(symbol, interval, "1 Jan, 2017")
    data = pandas.DataFrame(hist)
    # create colums name
    data.columns = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "qav",
        "num_trades",
        "taker_base_vol",
        "taker_quote_vol",
        "ignore",
    ]

    # change the timestamp
    data.index = [datetime.datetime.fromtimestamp(x / 1000.0) for x in data.close_time]
    data.to_csv(symbol + ".csv", index=None, header=True)
    # convert data to float and plot
    df = df.astype(float)
    df["close"].plot(title="DOTUSDT", legend="close")
    del client


def main():
    scrapeHist()
    pass


if __name__ == "__main__":
    main()
