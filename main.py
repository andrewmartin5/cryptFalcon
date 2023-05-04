from itertools import product
import os
import datetime
from queue import Queue
import pandas
from binance.client import Client
from binance.enums import *
import schedule
from time import sleep
import multiprocessing
import statistics
from emailSelf import emailSelf
import tqdm
import tkinter as tk
from tkinter import ttk
from tkinter import font
from time import strftime
import threading
import os
from tkinter import messagebox as msg
import customtkinter as ctk
import tkcalendar
from datetime import datetime, timedelta
import time  # TODO Remove


ctk.set_appearance_mode("Light")

# REF: https://python.plainenglish.io/how-to-download-trading-data-from-binance-with-python-21634af30195

symbol = "ETHUSDT"  # "BTCUSDT"
shortSymbol = "ETH"
url = "https://www.binance.us/api"
api_key = os.environ.get('BINANCE_API')
api_secret = os.environ.get('BINANCE_SECRET')
STARTING_CASH = 50

data = pandas.DataFrame()
prices = []

tracked1Day = []
tracked14Day = []
tracked30Day = []
tracked180Day = []

# TODO update to do klines


def scrapeRecent(sym):
    client = Client(api_key, api_secret, tld='us')
    client.API_URL = url
    price = client.get_symbol_ticker(symbol=sym)
    del client
    return float(price["price"])


def scrapeHist(symb, startDate):
    interval = "15m"

    # Create Client
    client = Client(api_key, api_secret, tld='us')
    client.KLINE_INTERVAL_15MINUTE

    print("Scraping Hist at increment: " + interval)
    # Get Data
    hist = client.get_historical_klines(symb, interval, startDate)

    print("Processing Data...", end="\r")
    # Process Data
    dates = []
    inf = []
    for list in hist:
        dates.append(datetime.fromtimestamp(list[0] / 1000.0))
        inf.append(
            [datetime.fromtimestamp(
                list[0] / 1000.0), list[1], list[5]]
        )
    print("Data Processed       ")
    print("Creating CSV", end="\r")

    # Manage data and create CSV
    raw = pandas.DataFrame(inf, index=dates, columns=["Time", "Price", "Vol"])
    raw.to_csv(symb + ".csv", index=None, header=True)

    raw = readRawHist()
    del client
    return raw


def getBalance(sym):
    client = Client(api_key, api_secret, tld='us')
    client.API_URL = url
    price = client.get_asset_balance(asset=sym)
    del client
    return float(price["free"])


def buy(cash, symb):
    q = round((cash/scrapeRecent(symb)) * .9, 4)
    client = Client(api_key, api_secret, tld='us')
    client.API_URL = url
    client.order_market_buy(symbol=symb,
                            quantity=q)


def sell(cash, symb):
    q = round(cash/scrapeRecent(symb), 4)
    client = Client(api_key, api_secret, tld='us')
    client.order_market_sell(
        symbol=symb, quantity=getBalance(shortSymbol))


def readRawHist():
    df = pandas.read_csv(
        symbol + ".csv",
        parse_dates=True,
        date_format="%Y-%m-%d %H:%M:%S",
        index_col="Time",
        names=["Time", "Price", "Vol"],
        header=0,
    )
    index = df.index
    df = df[~index.duplicated(keep="first")]
    return df


def readAvgHist():
    df = pandas.read_csv(
        symbol + "_AVG.csv",
        parse_dates=True,
        date_format="%Y-%m-%d %H:%M:%S",
        index_col="Time",
        names=["Time", "Price", "Vol", "1DayAvg",
               "14DayAvg", "30DayAvg", "180DayAvg", "MarketTrend", "Indicator", "Signal", "Center"],
        header=0,
    )
    index = df.index
    df = df[~index.duplicated(keep="first")]
    return df


def query(data, time, value):
    return data.loc[time][value]


def writeAvgPrice(data):
    # Get Indeces from data
    timelist = list(data.index.values)

    print("Capturing data and reformatting dates")
    # Convert all times from numpy to datetimes
    for n in range(len(timelist)):
        timelist[n] = pandas.to_datetime(timelist[n])

    print("Calculating Avgs")

    newData = data
    newData["1DayAvg"] = pandas.Series(
        data['Price']).ewm(span=96, min_periods=96).mean()
    newData["14DayAvg"] = pandas.Series(
        data['Price']).ewm(span=1344, min_periods=1344).mean()
    newData["30DayAvg"] = pandas.Series(
        data['Price']).ewm(span=2880, min_periods=2880).mean()
    newData["180DayAvg"] = pandas.Series(
        data['Price']).ewm(span=17280, min_periods=17280).mean()

    # The price is in an upward trend (increasing) if the marketTrend is positive - will not buy if there's no upwards trend
    newData["MarketTrend"] = data["Price"] - data["180DayAvg"]

    # Indicates to buy if positive
    newData["Indicator"] = data["14DayAvg"] - data["30DayAvg"]

    data['Signal'] = pandas.Series(data['Indicator']).ewm(
        span=96, min_periods=96).mean()

    # Center line
    data['Center'] = data['Indicator'] - data['Signal']

    print("Data Averaged")

    newData.to_csv(symbol + "_AVG.csv", index=timelist, header=True)
    return readAvgHist()


# def mainloop():
#     # TODO change to hour.at(:"01   ")
#     schedule.every().minute.at(":00").do(update)
#     print("Started at " + str(datetime.now()))
#     while True:
#         schedule.run_pending()

def simulateTrades(data, stop, cash):
    data = data.tail(-17298)
    timelist = list(data.index.values)
    timelist = [pandas.to_datetime(n) for n in timelist]
    timelist = [n for n in timelist if n <= stop]
    # Set starting values
    balanceUSD = int(cash)
    cryptBalance = 0

    avgEarnings = (STARTING_CASH / query(data, timelist[0], "Price")) * query(
        data, timelist[len(timelist) - 1], "Price")
    print(f"Final price to beat: {avgEarnings}")

    df = pandas.DataFrame(index=timelist, columns=[
        "Earnings", "Price"])

    stopLoss = 0

    for time in tqdm.tqdm(timelist):
        price = query(data, time, "Price")

        # The price is in an upward trend (increasing) if the marketTrend is positive - will not buy if there's no upwards trend
        marketTrend = query(data, time, "MarketTrend")
        # Indicates to buy if positive
        indicator = query(data, time, "Indicator")
        # Center of indicator
        center = query(data, time, "Center")

        if stopLoss != 0 and (price < stopLoss or indicator < 0):
            # sell
            diff = cryptBalance
            cryptBalance -= diff
            balanceUSD += (diff * price) * .999  # To account for 0.1% Fee
            stopLoss = 0

        if stopLoss == 0 and marketTrend > 0 and indicator > 0:
            # If the indicator is positive and greater than the center, buy
            diff = balanceUSD
            balanceUSD -= diff
            cryptBalance += diff / price
            if stopLoss == 0:
                stopLoss = query(data, time, "180DayAvg") * .9

        df["Price"][time] = price
        df["Earnings"][time] = balanceUSD + (price * cryptBalance)
    df.to_csv(symbol + "_EarningsTime.csv", index=timelist, header=True)
    print(f"Earnings: {balanceUSD + (price * cryptBalance)}")
    return balanceUSD + (price * cryptBalance)


class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        ctk.CTk.__init__(self, *args, **kwargs)
        self.title("CryptFalcon")
        self.minsize(1280, 720)
        self.defaultFont = tk.font.nametofont("TkDefaultFont")
        self.defaultFont.configure(family="Segoe", size=12)

        for x in range(2):
            self.columnconfigure(x, weight=1, uniform="")
        for y in range(6):
            self.rowconfigure(y, weight=1, uniform="")

        self.titleFrame = ctk.CTkFrame(self)
        self.titleFrame.columnconfigure(0, weight=1, uniform="")
        self.titleFrame.rowconfigure(0, weight=0, uniform="")
        self.titleFrame.rowconfigure(1, weight=0, uniform="")
        ctk.CTkLabel(self.titleFrame, text="CryptFalcon", font=(
            "Segoe", 22), justify=tk.CENTER).pack(expand=True)
        self.clockLabel = ctk.CTkLabel(
            self.titleFrame, text="00:00:00", font=("Segoe", 18))
        self.clockLabel.pack(expand=True)
        self.titleFrame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.isTrading = False

        self.initQueryFrame()

        self.initTransactFrame()

        self.initSimulateFrame()

        self.initRunFrame()

        # self.transactFrame = ttk.LabelFrame(self, text="Make a Transaction")
        # self.transactFrame.grid(row=2, column=0, sticky=tk.NSEW)

    def initQueryFrame(self):
        self.queryFrame = ctk.CTkFrame(self)
        for x in range(2):
            self.queryFrame.columnconfigure(x, weight=1, uniform="")
        for y in range(7):
            self.queryFrame.rowconfigure(y, weight=1, uniform="")
        ctk.CTkLabel(self.queryFrame, text="Check Prices", font=("Segoe", 16), justify=tk.CENTER).grid(
            row=0, column=0, columnspan=2, sticky=tk.EW)
        ctk.CTkLabel(self.queryFrame, text="Symbol").grid(
            row=1, column=0, sticky=tk.W)
        self.queryFrame.symbolEntry = ctk.CTkEntry(
            self.queryFrame, justify=tk.CENTER)
        self.queryFrame.symbolEntry.grid(row=1, column=1, sticky=tk.EW)
        self.queryFrame.symbolEntry.insert(0, "ETH")
        self.queryFrame.queryButton = ctk.CTkButton(
            self.queryFrame, text="Search!", command=self.search)
        self.queryFrame.queryButton.grid(row=2, column=0,
                                         columnspan=2, sticky=tk.EW)
        ctk.CTkLabel(self.queryFrame, text="Price:").grid(
            row=3, column=0, sticky=tk.W)

        ctk.CTkLabel(self.queryFrame, text="Crypto Balance:").grid(
            row=4, column=0, sticky=tk.W)

        ctk.CTkLabel(self.queryFrame, text="Current Balance (USDT):").grid(
            row=5, column=0, sticky=tk.W)

        ctk.CTkLabel(self.queryFrame, text="Can Afford:").grid(
            row=6, column=0, sticky=tk.W)

        self.queryFrame.priceAnswer = ctk.CTkEntry(
            self.queryFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.queryFrame.priceAnswer.grid(row=3, column=1, sticky=tk.EW)

        self.queryFrame.cryptoAnswer = ctk.CTkEntry(
            self.queryFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.queryFrame.cryptoAnswer.grid(row=4, column=1, sticky=tk.EW)

        self.queryFrame.balanceAnswer = ctk.CTkEntry(
            self.queryFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.queryFrame.balanceAnswer.grid(row=5, column=1, sticky=tk.EW)

        self.queryFrame.affordsAnswer = ctk.CTkEntry(
            self.queryFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.queryFrame.affordsAnswer.grid(row=6, column=1, sticky=tk.EW)

        self.queryFrame.grid(row=1, column=0, rowspan=3,
                             sticky=tk.NSEW, padx=5, pady=5)

        for child in self.queryFrame.winfo_children():
            child.grid_configure(pady=5, padx=5)

    def initTransactFrame(self):
        self.transactFrame = ctk.CTkFrame(self)
        for x in range(4):
            self.transactFrame.columnconfigure(x, weight=1, uniform="")
        for y in range(4):
            self.transactFrame.rowconfigure(y, weight=1, uniform="")
        ctk.CTkLabel(self.transactFrame, text="Make a Transaction", font=("Segoe", 16), justify=tk.CENTER).grid(
            row=0, column=0, columnspan=4, sticky=tk.EW)

        ctk.CTkLabel(self.transactFrame, text="Buy Amount (USD):").grid(
            row=1, column=0, sticky=tk.W)
        self.transactFrame.buyEntry = ctk.CTkEntry(
            self.transactFrame, justify=tk.CENTER)
        self.transactFrame.buyEntry.grid(row=1, column=1, sticky=tk.EW)

        ctk.CTkLabel(self.transactFrame, text="Sell Amount (USD):").grid(
            row=1, column=2, sticky=tk.W)
        self.transactFrame.sellEntry = ctk.CTkEntry(
            self.transactFrame, justify=tk.CENTER)
        self.transactFrame.sellEntry.grid(row=1, column=3, sticky=tk.EW)

        self.transactFrame.buyMax = ctk.CTkButton(
            self.transactFrame, text="Find Maximum Buy", command=self.findMaxBuy)
        self.transactFrame.buyMax.grid(
            row=2, column=0, columnspan=2, sticky=tk.EW)

        self.transactFrame.sellMax = ctk.CTkButton(
            self.transactFrame, text="Find Maximum Sell", command=self.findMaxSell)
        self.transactFrame.sellMax.grid(
            row=2, column=2, columnspan=2, sticky=tk.EW)

        self.transactFrame.buyButton = ctk.CTkButton(
            self.transactFrame, text="Buy", command=self.buy)
        self.transactFrame.buyButton.grid(
            row=3, column=0, columnspan=2, sticky=tk.EW)

        self.transactFrame.sellButton = ctk.CTkButton(
            self.transactFrame, text="Sell", command=self.sell)
        self.transactFrame.sellButton.grid(
            row=3, column=2, columnspan=2, sticky=tk.EW)

        self.transactFrame.grid(
            row=4, column=0, rowspan=2, sticky=tk.NSEW, padx=5, pady=5)

        for child in self.transactFrame.winfo_children():
            child.grid_configure(pady=5, padx=5)

    def initSimulateFrame(self):
        self.simulateFrame = ctk.CTkFrame(self)
        for x in range(2):
            self.simulateFrame.columnconfigure(x, weight=1, uniform="")
        for y in range(4):
            self.simulateFrame.rowconfigure(y, weight=1, uniform="")
        ctk.CTkLabel(self.simulateFrame, text="Simulate a Run", font=("Segoe", 16), justify=tk.CENTER).grid(
            row=0, column=0, columnspan=4, sticky=tk.EW)

        ctk.CTkLabel(self.simulateFrame, text="Starting Cash:").grid(
            row=1, column=0, sticky=tk.W)
        self.simulateFrame.startCashEntry = ctk.CTkEntry(
            self.simulateFrame, justify=tk.CENTER)
        self.simulateFrame.startCashEntry.insert(0, "50")
        self.simulateFrame.startCashEntry.grid(row=1, column=1, sticky=tk.EW)

        ctk.CTkLabel(self.simulateFrame, text="Start Date:").grid(
            row=2, column=0, sticky=tk.W)
        self.simulateFrame.startDateEntry = tkcalendar.DateEntry(
            self.simulateFrame, justify=tk.CENTER)
        self.simulateFrame.startDateEntry.grid(row=2, column=1, sticky=tk.EW)

        ctk.CTkLabel(self.simulateFrame, text="Stop Date:").grid(
            row=3, column=0, sticky=tk.W)
        self.simulateFrame.stopDateEntry = tkcalendar.DateEntry(
            self.simulateFrame, justify=tk.CENTER)
        self.simulateFrame.stopDateEntry.grid(row=3, column=1, sticky=tk.EW)

        self.simulateFrame.simulateButton = ctk.CTkButton(
            self.simulateFrame, text="Start Simulation", command=self.simulate)
        self.simulateFrame.simulateButton.grid(
            row=4, column=0, columnspan=2, sticky=tk.EW)

        self.simulateFrame.grid(
            row=0, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)

        for child in self.simulateFrame.winfo_children():
            child.grid_configure(pady=5, padx=5)

    def initRunFrame(self):
        self.runFrame = ctk.CTkFrame(self)
        for x in range(2):
            self.runFrame.columnconfigure(x, weight=1, uniform="")
        for y in range(5):
            self.runFrame.rowconfigure(y, weight=1, uniform="")
        ctk.CTkLabel(self.runFrame, text="Live Trading", font=("Segoe", 16), justify=tk.CENTER).grid(
            row=0, column=0, columnspan=4, sticky=tk.EW)

        self.runFrame.toggleButton = ctk.CTkButton(
            self.runFrame, text="Start Trading", command=self.toggleTrades)
        self.runFrame.toggleButton.grid(
            row=1, column=0, columnspan=2, sticky=tk.EW)

        ctk.CTkLabel(self.runFrame, text="Current Balance:").grid(
            row=2, column=0, sticky=tk.W)
        self.runFrame.balanceEntry = ctk.CTkEntry(
            self.runFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.runFrame.balanceEntry.grid(row=2, column=1, sticky=tk.EW)

        ctk.CTkLabel(self.runFrame, text="Current Price:").grid(
            row=3, column=0, sticky=tk.W)
        self.runFrame.priceEntry = ctk.CTkEntry(
            self.runFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.runFrame.priceEntry.grid(row=3, column=1, sticky=tk.EW)

        ctk.CTkLabel(self.runFrame, text="Profit:").grid(
            row=4, column=0, sticky=tk.W)
        self.runFrame.profitEntry = ctk.CTkEntry(
            self.runFrame, justify=tk.CENTER, state=tk.DISABLED)
        self.runFrame.profitEntry.grid(row=4, column=1, sticky=tk.EW)

        self.runFrame.grid(row=3, column=1, rowspan=3,
                           sticky=tk.NSEW, padx=5, pady=5)

        for child in self.runFrame.winfo_children():
            child.grid_configure(pady=5, padx=5)

    def search(self):
        symb = self.queryFrame.symbolEntry.get()
        try:
            price = scrapeRecent(symb + "USDT")
            balance = getBalance("USDT")
            cryptoBalance = getBalance(symb)
            afford = balance / price
            self.queryFrame.priceAnswer.configure(state=tk.NORMAL)
            self.queryFrame.priceAnswer.delete(0, tk.END)
            self.queryFrame.priceAnswer.insert(0, price)
            self.queryFrame.priceAnswer.configure(state=tk.DISABLED)

            self.queryFrame.cryptoAnswer.configure(state=tk.NORMAL)
            self.queryFrame.cryptoAnswer.delete(0, tk.END)
            self.queryFrame.cryptoAnswer.insert(0, cryptoBalance)
            self.queryFrame.cryptoAnswer.configure(state=tk.DISABLED)

            self.queryFrame.balanceAnswer.configure(state=tk.NORMAL)
            self.queryFrame.balanceAnswer.delete(0, tk.END)
            self.queryFrame.balanceAnswer.insert(0, balance)
            self.queryFrame.balanceAnswer.configure(state=tk.DISABLED)

            self.queryFrame.affordsAnswer.configure(state=tk.NORMAL)
            self.queryFrame.affordsAnswer.delete(0, tk.END)
            self.queryFrame.affordsAnswer.insert(0, afford)
            self.queryFrame.affordsAnswer.configure(state=tk.DISABLED)

            self.findMaxBuy()
            self.findMaxSell()
        except:
            msg.showerror(
                title="Error", message=f"\"{symb}\" is not a valid symbol")

    def findMaxBuy(self):
        symb = self.queryFrame.symbolEntry.get()
        try:
            balance = getBalance("USDT")
            self.transactFrame.buyEntry.delete(0, tk.END)
            self.transactFrame.buyEntry.insert(0, balance)
        except:
            msg.showerror(
                title="Error", message=f"\"{symb}\" is not a valid symbol")

    def findMaxSell(self):
        symb = self.queryFrame.symbolEntry.get()
        try:
            price = scrapeRecent(symb + "USDT")
            balance = getBalance(symb)
            amount = price * balance
            self.transactFrame.sellEntry.delete(0, tk.END)
            self.transactFrame.sellEntry.insert(0, amount)
        except:
            msg.showerror(
                title="Error", message=f"\"{symb}\" is not a valid symbol")

    def buy(self):
        symb = self.queryFrame.symbolEntry.get() + "USDT"
        cash = float(self.transactFrame.buyEntry.get())
        buy(cash, symb)
        self.search()
        self.findMaxBuy()
        self.findMaxSell()

    def sell(self):
        symb = self.queryFrame.symbolEntry.get() + "USDT"
        cash = float(self.transactFrame.buyEntry.get())
        sell(cash, symb)
        self.search()
        self.findMaxBuy()
        self.findMaxSell()

    def simulate(self):
        self.top = ctk.CTkToplevel(self)
        ctk.CTkLabel(self.top, text="Simulating").grid(
            row=0, column=0, sticky=tk.EW)
        self.top.loading = ctk.CTkProgressBar(self.top, mode='indeterminate')
        self.top.loading.grid(row=1, column=0, sticky=tk.EW)
        self.top.loading.start()
        self.top.update()
        self.top.lift()
        self.top.focus_force()
        self.top.grab_set()
        self.q = Queue()

        symb = self.queryFrame.symbolEntry.get() + "USDT"
        start = datetime.strptime(
            self.simulateFrame.startDateEntry.get(), "%m/%d/%y")
        start -= timedelta(days=180)
        stop = datetime.strptime(
            self.simulateFrame.stopDateEntry.get(), "%m/%d/%y")
        cash = self.simulateFrame.startCashEntry.get()

        tempThread = threading.Thread(
            target=self.simhelper, args=[symb, start, stop, cash])
        tempThread.start()

        self.monitor(tempThread)
        # symb = self.simulateFrame.startCashEntry.get()
        # start = datetime.strptime(
        #     self.simulateFrame.startDateEntry.get(), "%m/%d/%y")
        # start -= timedelta(days=180)
        # stop = datetime.strptime(
        #     self.simulateFrame.stopDateEntry.get(), "%m/%d/%y")
        # raw = scrapeHist(datetime.strftime(start, "%#d %b, %Y"))
        # data = writeAvgPrice(raw)
        # simulateTrades(data, stop)

    def toggleTrades(self):
        if self.isTrading:
            self.isTrading = False
            self.runFrame.toggleButton.configure(text="Start Trading")
            self.runFrame.balanceEntry.configure(state=tk.NORMAL)
            self.runFrame.balanceEntry.delete(0, tk.END)
            self.runFrame.balanceEntry.insert(0, "0.00")
            self.runFrame.balanceEntry.configure(state=tk.DISABLED)
            self.runFrame.priceEntry.configure(state=tk.NORMAL)
            self.runFrame.priceEntry.delete(0, tk.END)
            self.runFrame.priceEntry.insert(0, "0.00")
            self.runFrame.priceEntry.configure(state=tk.DISABLED)
            self.runFrame.profitEntry.configure(state=tk.NORMAL)
            self.runFrame.profitEntry.delete(0, tk.END)
            self.runFrame.profitEntry.insert(0, "0.00")
            self.runFrame.profitEntry.configure(state=tk.DISABLED)
        else:
            self.isTrading = True
            self.runFrame.toggleButton.configure(text="Stop Trading")
            time.sleep(1.2)
            symb = self.queryFrame.symbolEntry.get()
            price = scrapeRecent(symb + "USDT")
            balance = getBalance("USDT") + (price * getBalance(symb))
            self.runFrame.balanceEntry.configure(state=tk.NORMAL)
            self.runFrame.balanceEntry.delete(0, tk.END)
            self.runFrame.balanceEntry.insert(0, f"{balance:.2f}")
            self.runFrame.balanceEntry.configure(state=tk.DISABLED)
            self.runFrame.priceEntry.configure(state=tk.NORMAL)
            self.runFrame.priceEntry.delete(0, tk.END)
            self.runFrame.priceEntry.insert(0, f"{price:.2f}")
            self.runFrame.priceEntry.configure(state=tk.DISABLED)
            self.runFrame.profitEntry.configure(state=tk.NORMAL)
            self.runFrame.profitEntry.delete(0, tk.END)
            self.runFrame.profitEntry.insert(0, "0.00")
            self.runFrame.profitEntry.configure(state=tk.DISABLED)

    def monitor(self, thread):
        if thread.is_alive():
            self.after(100, lambda: self.monitor(thread))
        else:
            self.top.destroy()
            msg.showinfo(title="Earnings",
                         message=f"After simulation, you have {self.q.get():.2f}")

    def simhelper(self, symb, start, stop, cash):

        raw = scrapeHist(symb, datetime.strftime(start, "%#d %b, %Y"))
        data = writeAvgPrice(raw)
        ans = simulateTrades(data, stop, cash)
        self.q.put(ans)

    def time(self):
        self.clockLabel.after(1000, self.time)
        self.clockLabel.configure(text=strftime("%H:%M:%S"))

    def on_delete(self):
        if msg.askyesno("Quit", "Would you like to Exit?"):
            self.destroy()


def main():

    # print(scrapeRec/ent())
    # raw = scrapeHist()
    # raw = readRawHist()
    # writeAvgPrice(raw)
    # data = readAvgHist()
    # for i in range(50):
    #     simulateTrades(data, i-25)
    # mainloop
    # update()
    # sell()
    # emailSelf()

    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_delete)
    threading.Thread(target=app.time).start()
    app.bind_all("<Button-1>", lambda event: event.widget.focus_set())

    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    finally:
        app.mainloop()
        os._exit(0)


if __name__ == "__main__":
    main()
