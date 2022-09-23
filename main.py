from sqlite3 import Time
import os
import datetime
import pandas
from binance.client import Client
import schedule

# REF: https://python.plainenglish.io/how-to-download-trading-data-from-binance-with-python-21634af30195

symbol = "ETHUSDT"
url = "https://testnet.binance.vision/api"
api_key = os.environ.get("binance_api")
api_secret = os.environ.get("binance_secret")

# TODO update to do klines
def scrapeRecent():
    client = Client(api_key, api_secret)
    client.API_URL = url
    price = client.get_symbol_ticker(symbol=symbol)
    del client
    return price["price"]


def scrapeHist():
    interval = "1h"

    # Create Client
    client = Client(api_key, api_secret)
    client.KLINE_INTERVAL_1HOUR

    print("Scraping Hist at increment: " + interval)
    # Get Data
    hist = client.get_historical_klines(symbol, interval, "1 Jan, 2015")

    print("Processing Data...", end="\r")
    # Process Data
    dates = []
    inf = []
    for list in hist:
        dates.append(datetime.datetime.fromtimestamp(list[0] / 1000.0))
        inf.append(
            [datetime.datetime.fromtimestamp(list[0] / 1000.0), list[1], list[5]]
        )
    print("Data Processed       ")
    print("Creating CSV", end="\r")

    # Manage data and create CSV
    raw = pandas.DataFrame(inf, index=dates, columns=["Time", "Price", "Vol"])
    raw.to_csv(symbol + ".csv", index=None, header=True)

    raw = getRawHist()

    avg = writeAvgPrice(raw)
    del client
    return avg


def dateparse(datelist):
    return [datetime.datetime.strptime(x, "%Y-%m-%d %H:%M:%S") for x in datelist]


def getRawHist():
    df = pandas.read_csv(
        symbol + ".csv",
        parse_dates=True,
        date_parser=dateparse,
        index_col="Time",
        names=["Time", "Price", "Vol"],
        header=0,
    )
    index = df.index
    df = df[~index.duplicated(keep="first")]
    return df


def getAvgHist():
    df = pandas.read_csv(
        symbol + "_AVG.csv",
        parse_dates=True,
        date_parser=dateparse,
        index_col="Time",
        names=["Time", "Price", "Vol", "1DayAvg", "14DayAvg", "30DayAvg", "180DayAvg"],
        header=0,
    )
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
    return total / totalDatas


def writeAvgPrice(data):
    # Get Indeces from data
    timelist = list(data.index.values)

    print("Capturing data and reformatting dates")
    # Convert all times from numpy to datetimes
    for n in range(len(timelist)):
        timelist[n] = pandas.to_datetime(timelist[n])

    print("Calculating Avgs")
    tracked1Day = []
    avg1Day = []
    tracked14Day = []
    avg14Day = []
    tracked30Day = []
    avg30Day = []
    tracked180Day = []
    avg180Day = []
    for time in timelist:
        print(str(time), end="\r")
        if len(tracked1Day) > 24:
            tracked1Day.pop(0)
        if len(tracked14Day) > 336:
            tracked14Day.pop(0)
        if len(tracked30Day) > 720:
            tracked30Day.pop(0)
        if len(tracked180Day) > 4320:
            tracked180Day.pop(0)
        tracked1Day.append(queryPrice(data, time))
        avg1Day.append(sum(tracked1Day) / len(tracked1Day))
        tracked14Day.append(queryPrice(data, time))
        avg14Day.append(sum(tracked14Day) / len(tracked14Day))
        tracked30Day.append(queryPrice(data, time))
        avg30Day.append(sum(tracked30Day) / len(tracked30Day))
        tracked180Day.append(queryPrice(data, time))
        avg180Day.append(sum(tracked180Day) / len(tracked180Day))

    newData = data
    newData["1DayAvg"] = avg1Day
    newData["14DayAvg"] = avg14Day
    newData["30DayAvg"] = avg30Day
    newData["180DayAvg"] = avg180Day

    print("Data Averaged      ")

    newData.to_csv(symbol + "_AVG.csv", index=Time, header=True)
    return newData


def update():
    print(str(pandas.Timestamp.now().round('60min').to_pydatetime()) + " " + scrapeRecent())

def main():
    data = getAvgHist()
    # TODO change to hour.at(:"01   ")
    schedule.every().minute.at(":00").do(update)
    print("Started at " + str(datetime.datetime.now()))
    while True:
        schedule.run_pending()


if __name__ == "__main__":

    main()
