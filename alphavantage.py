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
import scipy.stats
import multiprocessing
import matplotlib.pyplot as plt
from PIL import Image
from time import strftime
from time import sleep
from operator import itemgetter


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
PRINT_LEVEL=2


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
		
	return data, pricefile
	
###############################################################################
# PLOTTING
###############################################################################

def plot_points(params):
	start_key = params["plot_start_date"]
	length = params["plot_period"]
	
	x = list(reversed(range(length)))
	y = []
	data, pricefile = get_latest_json(params["single_symbol"])
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
	tech_period = params["tech_period"]
	
	num_line = int(length / tech_period)
	data, pricefile = get_latest_json(params["single_symbol"])
	price_data = data[JSON_PRICE_ROOT]
	sorted_dates = sorted(price_data.keys())
	index = sorted_dates.index(start_key)
	for l in range(num_line):
		x = list(range((num_line*tech_period) - (l * tech_period), (num_line*tech_period) - ((l+1) * tech_period), -1))
		#x = list(range(tech_period * l, tech_period * (l+1)))
		y = []
		slope = price_data[sorted_dates[index]][JSON_REGRESSION_SLOPE]
		origin = price_data[sorted_dates[index]][JSON_REGRESSION_ORIGIN]
		for i in range(tech_period):
			y.append(slope * i + origin)
		
		index -= tech_period
		plot_points_do(x, y, 'g-')

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
	data, pricefile = get_latest_json(symbol)
	if data is None or JSON_PRICE_ROOT not in data:
		myprint("Invalid data for " + pricefile, 4)
		return
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
	
	#myprint(datay)
	
def tech_linear_regression_all(period):
	symbols = os.walk(os.path.join(DATA_FOLDER, "prices"))
	symbols = next(symbols)[1]
	total = len(symbols)
	count = 1
	for symbol in symbols:
		myprint("[" + str(count) + "/" + str(total) + "] linear regression for " + symbol)
		tech_linear_regression(symbol, period)
		count += 1
	
def cmp_pearson_corelation_all(compare_to_symbol):
	cmp_data, cmp_pricefile = get_latest_json(compare_to_symbol)
	cmp_price_data = cmp_data[JSON_PRICE_ROOT]
	cmp_sorted_dates = sorted(cmp_price_data.keys(), reverse=True) # earliest first
	
	symbols = os.walk(os.path.join(DATA_FOLDER, "prices"))
	symbols = next(symbols)[1]
	
	result = []
	
	for symbol in symbols:
		other_data, other_pricefile = get_latest_json(symbol)
		if other_data is None or JSON_PRICE_ROOT not in other_data:
			myprint("Invalid data for " + other_pricefile, 4)
			continue
		other_price_data = other_data[JSON_PRICE_ROOT]
		other_sorted_dates = sorted(other_price_data.keys(), reverse=True)
		closing_x = []
		closing_y = []
		matching_period_count = 0
		
		for cur_date in cmp_sorted_dates:
			if cur_date not in other_price_data:
				myprint("Could not find " + cur_date + " in " + other_pricefile, 4)
				break
			#myprint("cur_date " + str(cur_date) + " between " + my_pricefile + " and " + other_pricefile)
			matching_period_count += 1
			
			closing_x.append(cmp_price_data[cur_date][JSON_CLOSE])
			closing_y.append(other_price_data[cur_date][JSON_CLOSE])
		
		if len(closing_x) <= 0:
			myprint("Empty")
			continue
		
		cmp_start_price = closing_x[-1]
		cmp_other_price = closing_y[-1]
		
		cmp_prev_price = None
		other_prev_price = None
		result_x = []
		result_y = []
		for i in range(matching_period_count-1, 0, -1):
			cur_price_x = closing_x[i]
			cur_price_y = closing_y[i]
			
			if cmp_prev_price is not None:
				x = 100.0 if cmp_prev_price == 0 else (cmp_prev_price - cur_price_x) / cmp_prev_price
				y = 100.0 if other_prev_price == 0 else (other_prev_price - cur_price_y) / other_prev_price
				result_x.append(x)
				result_y.append(y)
			
			cmp_prev_price = cur_price_x
			other_prev_price = cur_price_y
		
		coef, prob = scipy.stats.pearsonr(result_x, result_y)
		result.append((other_pricefile, coef, prob, matching_period_count))
	
	result = sorted(result, key=itemgetter(1))
	myprint(result, 4)
	return result
	
	
def cmp_lin_reg(symbol, compare_to, period):
	my_data, my_pricefile = get_latest_json(params["single_symbol"])
	
	my_price_data = my_data[JSON_PRICE_ROOT]
	# most recent first because it's more interesting
	my_sorted_dates = sorted(my_price_data.keys(), reverse=True)
	diffs = []
	myprint("comparet to " + str(compare_to))
	for other_s in compare_to:
		other_data, other_pricefile = get_latest_json(other_s)
		if other_data is None or JSON_PRICE_ROOT not in other_data:
			myprint("Invalid data for " + other_pricefile, 4)
			continue
		other_price_data = other_data[JSON_PRICE_ROOT]
		other_sorted_dates = sorted(other_price_data.keys(), reverse=True)
		count = 0
		total_diff = 0
		matching_period_count = 0
		for i in range(int(len(my_sorted_dates) / period)):
			cur_date = my_sorted_dates[count]
			if cur_date not in other_price_data:
				myprint("Could not find " + cur_date + " in " + other_pricefile, 4)
				break
			#myprint("cur_date " + str(cur_date) + " between " + my_pricefile + " and " + other_pricefile)
			count += period
			
			my_slope = my_price_data[cur_date][JSON_REGRESSION_SLOPE]
			other_slope = other_price_data[cur_date][JSON_REGRESSION_SLOPE]
			
			ideal_slope = -my_slope
			diff = (other_slope - ideal_slope) * (other_slope - ideal_slope) # squared diff
			total_diff += diff
			matching_period_count += 1
		diffs.append((other_pricefile, 0 if matching_period_count == 0 else total_diff / matching_period_count, matching_period_count))
	diffs = sorted(diffs, key=itemgetter(1))
	myprint(diffs, 4)
	return diffs
		
		
def do_actions(actions, params):
	if "dl_everything" in actions:
		dl_full_time_series_daily_adjusted()
	if "dl_single_symbol" in actions:
		dl_time_series_daily_adjusted(params["single_symbol"], False)
	if "tech_lin_reg_all" in actions:
		tech_linear_regression_all(params["tech_period"])
	if "tech_lin_reg" in actions:
		tech_linear_regression(params["single_symbol"], params["tech_period"])
	if "cmp_pearson_corelation_all" in actions:
		cmp_pearson_corelation_all(params["single_symbol"])
	if "cmp_lin_reg" in actions:
		symbols = os.walk(os.path.join(DATA_FOLDER, "prices"))
		symbols = next(symbols)[1]
		cmp_lin_reg(params["single_symbol"], symbols, params["tech_period"])
	if "plot_line" in actions:
		plot_line(params)
	if "plot_points" in actions:
		plot_points(params)
	if "plot_line" in actions or "plot_points" in actions:
		plt.show()
		
		
if __name__ == '__main__':
	actions = [
		#"cmp_lin_reg",
		#"cmp_pearson_corelation_all", # calculate the pearson correlation factor single_symbol in params to all other symbols in prices folder
		#"tech_lin_reg_all", # calculate linear regression for all symbols in the "prices" folder
		#"tech_lin_reg", # calculate the slope and origin of a linear regression of closing prices
		#"plot_line", # plot data from JSON_REGRESSION_SLOPE & JSON_REGRESSION_ORIGIN at "plot_start_date"
		#"plot_points", # plot closing price of a range of data from plot_start_date back a number of "plot_period"
		"dl_everything", # Download the full 20 years history of daily open/close/adjusted stock info for everything in news_link.json
		#"dl_single_symbol", # Download the full 20 years history of daily for the specified symbol in single_symbol
		"nothing" # just so I don't need to play with the last ,
	]
	params = {
		"single_symbol" : "BNS.to", # used in dl_single_symbol, tech_lin_reg, plot_line, plot_points...
		#"single_symbol" : "TV.to", # used in dl_single_symbol, tech_lin_reg, plot_line, plot_points...
		"tech_period" : 100, # days to calculate the moving technical (moving average, moving regression, etc.)
		"plot_start_date" : "2018-06-08", # date from which to start plotting
		"plot_period" : 140, # length of time to go back in time from plot_start_date
		"nothing" : None # don't have to deal with last ,
	}
	do_actions(actions, params)
	
	#dl_full_time_series_daily_adjusted()
	#dl_time_series_daily_adjusted("tsx:aif", False)
	#dl_time_series_daily_adjusted("aif.to", False)
	#print(str(test["Meta Data"]))
	#print(test)