import time
import os
import json
import datetime
import pandas
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

    # Create Client
    client = Client(api_key, api_secret)
    client.KLINE_INTERVAL_1HOUR

    # Get Data
    hist = client.get_historical_klines(symbol, interval, "1 Jan, 2015")

    # Process Data
    dates = []
    inf = []
    for list in hist:
        dates.append(datetime.datetime.fromtimestamp(list[0]/1000.0))
        inf.append([datetime.datetime.fromtimestamp(
            list[0]/1000.0), list[1], list[5]])

    # Manage data and create CSV
    data = pandas.DataFrame(inf, index=dates, columns=["Time", "Price", "Vol"])
    data.to_csv(symbol + ".csv", index=None, header=True)
    del client


def dateparse(datelist):
    return [datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S") for x in datelist]


def getHistData():
    df = pandas.read_csv(symbol + ".csv", parse_dates=True, date_parser=dateparse,
                         index_col="Time", names=["Time", "Price", "Vol"], header=0)
    index = df.index
    df = df[~index.duplicated(keep="first")]
    return df


def queryPrice(data, time):
    return data.loc[time]["Price"]


def queryVol(data, time):
    return data.loc[time]["Vol"]


def avgPrice(data, startTime, days):
    time = startTime
    total = 0
    totalDatas = 0
    for n in range(days * 24):
        try:
            total += queryPrice(data, time)
            totalDatas += 1
        except:
            pass
        time = time - datetime.timedelta(hours=1)
    return (total / totalDatas)

def writeAvgPrice(data):
    # Get Indeces from data
    timelist = list(data.index.values)

    # Convert all times from numpy to datetimes
    for n in range(len(timelist)):
        timelist[n] = pandas.to_datetime(timelist[n])
    
    

def main():
    data = getHistData()
    writeAvgPrice(data)
    # print(queryPrice(data, datetime.datetime(2021, 11, 7, 1)))
    # f = open("test.txt", "a+")
    # for index, row in data.iterrows():
    #     test = (str(index) + ":\n\t")
    #     test = ("Price: " + str(row["Price"]) + "\n\t")
    #     test = ("Price Avg (1 Day): " + str(avgPrice(data, index, 1)) + "\n\t")
    #     test = ("Price Avg (14 Day): " + str(avgPrice(data, index, 14)) + "\n\t")
    #     test = ("Price Avg (30 Day): " + str(avgPrice(data, index, 30)) + "\n\t")
    #     test = ("Price Avg(180 Day): " + str(avgPrice(data, index, 180)) + "\n\t")
    #     test = ("Volume: " + str(row["Vol"]) + "\n")
    #     # print("Progress: " + str(index), end='\r')
    pass


if __name__ == "__main__":
    main()
