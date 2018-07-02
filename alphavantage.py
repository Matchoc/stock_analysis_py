import sys
import os
os.environ["path"] = os.path.dirname(sys.executable) + ";" + os.environ["path"]
import glob
import operator
import datetime
import dateutil.relativedelta
import win32gui
import win32ui
import win32con
import win32api
import numpy
import json
import csv
import urllib.request
import urllib.error
import scipy.ndimage
import multiprocessing
import matplotlib.pyplot as plt
from PIL import Image
from time import strftime
from time import sleep


###############################################################################
# GLOBAL CONSTANTS
###############################################################################


DATA_FOLDER = "data"
STOCK_LIST = os.path.join(DATA_FOLDER, "news_link.json")
ALPHA_KEY = "JTQ5969IQZV04J91"
BASE_URL = "https://www.alphavantage.co/query?"
JSON_PRICE_ROOT = "Time Series (Daily)"
JSON_CLOSE = "4. close"
JSON_REGRESSION_SLOPE = "cust. regression slope"
JSON_REGRESSION_ORIGIN = "cust. regression origin"
PRINT_LEVEL=0


###############################################################################
# UTILITIES
###############################################################################

def myprint(str, level=0):
	if (level >= PRINT_LEVEL):
		print(str)

def downloadURL(url):
	try:
		myprint("request : " + url)
		req = urllib.request.Request(url)
		req.add_header('Referer', 'http://us.rd.yahoo.com/')
		req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.1 \
				  (KHTML, like Gecko) Chrome/21.0.1180.89 Safari/537.1')
		resp = urllib.request.urlopen(req)
		myprint("resp = " + str(resp))
		data = resp.read()
		myprint("data = " + str(data))
		text = data.decode('utf-8') # a `str`; this step can't be used if data is binary
		myprint("text = " + text)
	except http.client.IncompleteRead as e:
		data = e.partial
		text = data.decode('utf-8') # a `str`; this step can't be used if data is binary
	except urllib.error.HTTPError as e:
		myprint("URL failed : " + str(e.code) + " " + e.reason, 5)
		return ""
	except UnicodeDecodeError as e:
		myprint("URL failed : Response not unicode", 5)
		return ""
	except Exception as e:
		myprint("Unknown exception : " + str(e))
		return ""
	return text

def as_float(obj):
	for k in obj:
		try:
			obj[k] = float(obj[k])
		except (ValueError, TypeError):
			pass
	return obj
	
	
def circular_iter(data, index):
	size = len(data)
	cur_index = index
	for i in range(size):
		yield data[cur_index]
		cur_index -= 1
		if cur_index < 0:
			cur_index = size-1
	
def get_latest_json(symbol):
	priceglob = os.path.join(DATA_FOLDER, "prices", symbol, "*.json")
	pricefiles = glob.glob(priceglob)
	pricefiles = sorted(pricefiles, reverse=True)
	pricefile = pricefiles[0]
	with open(pricefile, 'r') as jsonfile:
		data = json.load(jsonfile)
		
	return data
	
###############################################################################
# PLOTTING
###############################################################################

def plot_points(params):
	start_key = params["plot_start_date"]
	length = params["plot_period"]
	
	x = list(range(length))
	y = []
	data = get_latest_json(params["single_symbol"])
	price_data = data[JSON_PRICE_ROOT]
	sorted_dates = sorted(price_data.keys())
	
	index = sorted_dates.index(start_key)
	for i in range(length):
		y.append(price_data[sorted_dates[index]][JSON_CLOSE])
		index -= 1
	
	plot_points_do(x, y)
	plot_points_do(x, y, 'b')

def plot_points_do(x, y, type='ro'):
	plt.plot(x, y, type)#, label="predicted", linewidth=2)
	
def plot_line(params):
	start_key = params["plot_start_date"]
	length = params["plot_period"]
	
	x = list(range(length))
	y = []
	data = get_latest_json(params["single_symbol"])
	price_data = data[JSON_PRICE_ROOT]
	sorted_dates = sorted(price_data.keys())
	index = sorted_dates.index(start_key)
	slope = price_data[sorted_dates[index]][JSON_REGRESSION_SLOPE]
	origin = price_data[sorted_dates[index]][JSON_REGRESSION_ORIGIN]
	for i in range(length):
		y.append(slope * i + origin)
	
	plot_points_do(x, y, 'b-')

def plot_line_do(slope, origin, type='r-'):
	plt.plot([1,2,3], [1,2,3], type)
	
	
###############################################################################
# STOCK MARKET
###############################################################################
	
def dl_time_series_daily_adjusted(symbol, compact):
	if compact:
		outputsize = "compact"
	else:
		outputsize = "full"
		
	url = BASE_URL + "function=TIME_SERIES_DAILY_ADJUSTED&symbol=" + symbol + "&outputsize=" + outputsize + "&datatype=json&apikey=" + ALPHA_KEY
	myprint("Download URL : " + url, 1)
	text = downloadURL(url)
	
	jtext = json.loads(text, object_hook=as_float)
	
	timestr = strftime("%Y%m%d-%H%M%S")
	savepath = os.path.join(DATA_FOLDER, "prices", symbol, timestr + "-adj.json")
	savepath = savepath.replace(":", "-")

	if not os.path.exists(os.path.dirname(savepath)):
		os.makedirs(os.path.dirname(savepath))
	with open(savepath, 'w') as fo:
		json.dump(jtext, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
			
	if "Information" in jtext:
		return 1
	if "Error Message" in jtext:
		return 2
	else:
		return 0

def dl_full_time_series_daily_adjusted():
	with open(STOCK_LIST, 'r') as jsonfile:
		symbols = json.load(jsonfile)
	
	count = 0
	total = len(symbols)
	for symbol in symbols:
		count += 1
		myprint("Downloading " + str(count) + "/" + str(total) + " : " + symbol, 2)
		ret = dl_time_series_daily_adjusted(symbol + "." + symbols[symbol]["exchange"], False)
		if ret == 1:
			myprint("Download Failed. Too many requests. Wainting 10 seconds.", 5)
			sleep(10.0) # api call frenquency exceeded
			ret = dl_time_series_daily_adjusted(symbol + "." + symbols[symbol]["exchange"], False)
		elif ret == 2:
			myprint("Download Failed. Symbol not found or URL malformed.", 5)
		sleep(3.0)
		
def tech_linear_regression(symbol, period):
	data = get_latest_json(symbol)
	price_data = data[JSON_PRICE_ROOT]
	sorted_dates = sorted(price_data.keys())
	
	moyx = period / 2.0
	datay = []
	datay_index = 0
	for i in range(period):
		datay.append(price_data[sorted_dates[0]][JSON_CLOSE])
	for cur_date in sorted_dates:
		cur_price = price_data[cur_date][JSON_CLOSE]
		datay[datay_index] = cur_price
		sumy = 0
		for p in circular_iter(datay, datay_index):
			sumy += p
		moyy = sumy / period
		p_index = 0
		# slope = sum((xi - moyx)(yi - moyy))/sum(xi - moyx)^2
		# origin = moyy - slope*moyx
		sum1 = 0
		sum2 = 0
		for p in circular_iter(datay, datay_index):
			sum1 += (p_index - moyx) * (p - moyy)
			sum2 += (p_index - moyx) * (p_index - moyx)
			p_index += 1
		price_data[cur_date][JSON_REGRESSION_SLOPE] = sum1 / sum2
		price_data[cur_date][JSON_REGRESSION_ORIGIN] = moyy - (sum1/sum2) * moyx
		datay_index += 1
		if datay_index >= period:
			datay_index = 0
	
	data[JSON_PRICE_ROOT] = price_data
	
	with open(pricefile, 'w') as fo:
		json.dump(data, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
	
	myprint(datay)
		
def do_actions(actions, params):
	if "dl_everything" in actions:
		dl_full_time_series_daily_adjusted()
	if "dl_single_symbol" in actions:
		dl_time_series_daily_adjusted(params["single_symbol"], False)
	if "tech_lin_reg" in actions:
		tech_linear_regression(params["single_symbol"], params["tech_period"])
	if "plot_line" in actions:
		plot_line(params)
	if "plot_points" in actions:
		plot_points(params)
	if "plot_line" in actions or "plot_points" in actions:
		plt.show()
		
		
if __name__ == '__main__':
	actions = [
		#"tech_lin_reg", # calculate the slope and origin of a linear regression of closing prices
		#"plot_line", # plot data from JSON_REGRESSION_SLOPE & JSON_REGRESSION_ORIGIN at "plot_start_date"
		"plot_points", # plot closing price of a range of data from plot_start_date back a number of "plot_period"
		#"dl_everything", # Download the full 20 years history of daily open/close/adjusted stock info for everything in news_link.json
		#"dl_single_symbol", # Download the full 20 years history of daily for the specified symbol in single_symbol
		"nothing" # just so I don't need to play with the last ,
	]
	params = {
		"single_symbol" : "bns.to", # used in dl_single_symbol
		"tech_period" : 14, # days to calculate the moving technical (moving average, moving regression, etc.)
		"plot_start_date" : "2018-06-08", # date from which to start plotting
		"plot_period" : 200, # length of time to go back in time from plot_start_date
		"nothing" : None # don't have to deal with last ,
	}
	do_actions(actions, params)
	
	#dl_full_time_series_daily_adjusted()
	#dl_time_series_daily_adjusted("tsx:aif", False)
	#dl_time_series_daily_adjusted("aif.to", False)
	#print(str(test["Meta Data"]))
	#print(test)