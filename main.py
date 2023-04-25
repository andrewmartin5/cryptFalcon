from itertools import product
import os
import datetime
import pandas
from binance.client import Client
from binance.enums import *
import schedule
from time import sleep
import multiprocessing
import statistics
from emailSelf import emailSelf
import tqdm

# REF: https://python.plainenglish.io/how-to-download-trading-data-from-binance-with-python-21634af30195

symbol = "ETHUSDT"  # "BTCUSDT"
url = "https://www.binance.us/api"
api_key = os.environ.get('BINANCE_API')
api_secret = os.environ.get('BINANCE_SECRET')
STARTING_CASH = 100

data = pandas.DataFrame()
prices = []

tracked1Day = []
tracked14Day = []
tracked30Day = []
tracked180Day = []

# TODO update to do klines


def scrapeRecent():
    client = Client(api_key, api_secret)
    client.API_URL = url
    price = client.get_symbol_ticker(symbol=symbol)
    del client
    return float(price["price"])


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
            [datetime.datetime.fromtimestamp(
                list[0] / 1000.0), list[1], list[5]]
        )
    print("Data Processed       ")
    print("Creating CSV", end="\r")

    # Manage data and create CSV
    raw = pandas.DataFrame(inf, index=dates, columns=["Time", "Price", "Vol"])
    raw.to_csv(symbol + ".csv", index=None, header=True)

    raw = getRawHist()
    del client
    return raw


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
        names=["Time", "Price", "Vol", "1DayAvg",
               "14DayAvg", "30DayAvg", "180DayAvg"],
        header=0,
    )
    index = df.index
    df = df[~index.duplicated(keep="first")]
    return df


def query(data, time, value):
    return data.loc[time][value]


def avgPrice(data, startTime, days):
    time = startTime
    total = 0
    totalDatas = 0
    for n in range(days * 24):
        try:
            total += query(data, time, "Price")
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
    global tracked1Day
    global tracked14Day
    global tracked30Day
    global tracked180Day
    tracked1Day = []
    avg1Day = []
    tracked14Day = []
    avg14Day = []
    tracked30Day = []
    avg30Day = []
    tracked180Day = []
    avg180Day = []
    for time in tqdm.tqdm(timelist):
        if len(tracked1Day) > 24:
            tracked1Day.pop(0)
        if len(tracked14Day) > 336:
            tracked14Day.pop(0)
        if len(tracked30Day) > 720:
            tracked30Day.pop(0)
        if len(tracked180Day) > 4320:
            tracked180Day.pop(0)
        tracked1Day.append(query(data, time, "Price"))
        avg1Day.append(sum(tracked1Day) / len(tracked1Day))
        tracked14Day.append(query(data, time, "Price"))
        avg14Day.append(sum(tracked14Day) / len(tracked14Day))
        tracked30Day.append(query(data, time, "Price"))
        avg30Day.append(sum(tracked30Day) / len(tracked30Day))
        tracked180Day.append(query(data, time, "Price"))
        avg180Day.append(sum(tracked180Day) / len(tracked180Day))

    newData = data
    newData["1DayAvg"] = avg1Day
    newData["14DayAvg"] = avg14Day
    newData["30DayAvg"] = avg30Day
    newData["180DayAvg"] = avg180Day

    print("Data Averaged      ")

    newData.to_csv(symbol + "_AVG.csv", index=timelist, header=True)
    return newData


def update():
    print(str(pandas.Timestamp.now().round('60min').to_pydatetime()))
    price = scrapeRecent()
    cryptBalance = getBalance("ETH")
    balanceUSD = getBalance("USD")
    global tracked1Day
    global tracked14Day
    global tracked30Day
    global tracked180Day
    if len(tracked1Day) > 24:
        tracked1Day.pop(0)
    if len(tracked14Day) > 336:
        tracked14Day.pop(0)
    if len(tracked30Day) > 720:
        tracked30Day.pop(0)
    if len(tracked180Day) > 4320:
        tracked180Day.pop(0)
    tracked1Day.append(price)
    tracked14Day.append(price)
    tracked30Day.append(price)
    tracked180Day.append(price)
    avg1Day = sum(tracked1Day) / len(tracked1Day)
    avg14Day = sum(tracked14Day) / len(tracked14Day)
    avg30Day = sum(tracked30Day) / len(tracked30Day)
    avg180Day = sum(tracked180Day) / len(tracked180Day)
    # The price is increasing if the current price is higher than the average
    priceIncreasing = avg30Day < avg14Day and avg1Day > avg30Day
    if priceIncreasing:
        # If the average price is greater than the current price, buy
        diff = balanceUSD
        balanceUSD -= diff
        cryptBalance += diff / price
    elif cryptBalance * scrapeRecent() > balanceUSD:
        # If price is decreasing, sell
        diff = cryptBalance
        cryptBalance -= diff
        balanceUSD += (diff * price) * .999  # To account for 0.1% Fee
    print(f"Balance: {balanceUSD + (price * cryptBalance)}")


def mainloop():
    # TODO change to hour.at(:"01   ")
    schedule.every().minute.at(":00").do(update)
    print("Started at " + str(datetime.datetime.now()))
    while True:
        schedule.run_pending()


def findIntersections(data):
    timelist = list(data.index.values)
    timelist = [pandas.to_datetime(n) for n in timelist]
    # Set starting values
    balanceUSD = query(data, timelist[0], "Price")
    cryptBalance = 0

    avgEarnings = (STARTING_CASH / query(data, timelist[0], "Price")) * query(
        data, timelist[len(timelist) - 1], "Price")
    print(f"Final price to beat: {avgEarnings}")

    df = pandas.DataFrame(index=timelist, columns=[
                          "Price", "Earnings", "Cash"])

    for time in tqdm.tqdm(timelist):
        price = query(data, time, "Price")
        # The price is increasing if the current price is higher than the average
        # priceIncreasing = query(data, time, "30DayAvg") < query(data, time, "1DayAvg")
        priceIncreasing = query(data, time, "30DayAvg") < query(
            data, time, "14DayAvg")
        prediction = query(data, time, "1DayAvg") > query(
            data, time, "30DayAvg")
        if priceIncreasing and prediction:
            # If the average price is greater than the current price, buy
            diff = balanceUSD
            balanceUSD -= diff
            cryptBalance += diff / price
        elif not priceIncreasing:
            # If price is decreasing
            diff = cryptBalance
            cryptBalance -= diff
            balanceUSD += (diff * price) * .999  # To account for 0.1% Fee
        df["Price"][time] = price
        df["Earnings"][time] = balanceUSD + (price * cryptBalance)
        df["Cash"][time] = balanceUSD
    df.to_csv(symbol + "_EarningsTime.csv", index=timelist, header=True)
    print(balanceUSD + (price * cryptBalance))


def getBalance(sym):
    client = Client(api_key, api_secret)
    client.API_URL = url
    price = client.get_asset_balance(asset=sym)
    del client
    return float(price["free"])


def buy():
    q = round((getBalance("USD")/scrapeRecent()) * .9, 5)
    client = Client(api_key, api_secret)
    client.API_URL = url
    client.create_order(symbol="ETHUSDT",
                        side=SIDE_BUY,
                        type=ORDER_TYPE_MARKET,
                        quantity=q)


def main():
    # data = scrapeHist()
    # raw = getRawHist()
    # avg = writeAvgPrice(raw)
    # mainloop
    # update()
    buy()
    # data = getAvgHist()
    # writeAvgPrice(data)
    # runLinear(data)
    # emailSelf()


if __name__ == "__main__":
    main()
