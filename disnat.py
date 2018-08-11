import sys
import os
os.environ["path"] = os.path.dirname(sys.executable) + ";" + os.environ["path"]
import glob
import operator
import re
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
BASE_URL = "https://financials.morningstar.com/ajax/ReportProcess4CSV.html?&t={ticker}&region=can&culture=en-US&ops=clear&cur=&reportType=is&period=12&dataType=A&order=asc&columnYear=5&curYearPart=1st5year&rounding=3&view=raw&r=801461&denominatorView=raw&number=3"
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
		#myprint("resp = " + str(resp))
		data = resp.read()
		#myprint("data = " + str(data))
		text = data.decode('utf-8') # a `str`; this step can't be used if data is binary
		#myprint("text = " + text)
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
	
def get_latest_price(symbol):
	priceglob = os.path.join(DATA_FOLDER, "prices", symbol, "*.json")
	pricefiles = glob.glob(priceglob)
	pricefiles = sorted(pricefiles, reverse=True)
	pricefile = pricefiles[0]
	with open(pricefile, 'r') as jsonfile:
		data = json.load(jsonfile)
		
	return data, pricefile
	
def get_latest_financial(symbol):
	symbol = symbol.replace(".to", "")
	symbol = symbol.replace("-", ".")
	priceglob = os.path.join(DATA_FOLDER, "financials", symbol, "*.json")
	pricefiles = glob.glob(priceglob)
	if pricefiles is None or len(pricefiles) <= 0:
		return None, None
	pricefiles = sorted(pricefiles, reverse=True)
	pricefile = pricefiles[0]
	with open(pricefile, 'r') as jsonfile:
		data = json.load(jsonfile)
		
	return data, pricefile
	
	
###############################################################################
# MORNINGSTAR
###############################################################################

def dl_financial(single_symbol):
	
	single_symbol = single_symbol.replace(".to", "") # couldn't find a way to tell morningstar which exchange to use. But I think setting the local to CAN does the trick
	single_symbol = single_symbol.replace("-", ".") # morningstar uses AX.UN instead of AX-UN
	url = BASE_URL.format(ticker=single_symbol)
	myprint("Download URL : " + url, 1)
	text = downloadURL(url)
	
	if len(text) <= 1:
		return 1 # invalid url (unknown symbol)
	
	csv_array = text.splitlines()
	for i in range(len(csv_array)):
		line = csv_array[i]
		line = [n for n in line.split(',')]
		line = as_float(line)
		csv_array[i] = line
	
	timestr = strftime("%Y%m%d-%H%M%S")
	savepath = os.path.join(DATA_FOLDER, "financials", single_symbol, timestr + "-income.json")
	savepath = savepath.replace(":", "-")

	if not os.path.exists(os.path.dirname(savepath)):
		os.makedirs(os.path.dirname(savepath))
	with open(savepath, 'w') as fo:
		json.dump(csv_array, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
			
	return 0
	
def dl_all_financial():
	with open(STOCK_LIST, 'r') as jsonfile:
		symbols = json.load(jsonfile)
	
	count = 0
	total = len(symbols)
	for symbol in symbols:
		count += 1
		myprint("Downloading " + str(count) + "/" + str(total) + " : " + symbol, 2)
		ret = dl_financial(symbol)
		if ret == 1:
			myprint("Download Failed. Too many requests. Wainting 10 seconds.", 5)
			sleep(10.0) # api call frenquency exceeded
			ret = dl_financial(symbol)
		elif ret == 2:
			myprint("Download Failed. Symbol not found or URL malformed.", 5)
		sleep(3.0)
		
		
###############################################################################
# REPORTING
###############################################################################	

def gather_combine_data(data):
	companies = sorted(list(data.keys()))
	header = [["ticker"] + [x for x in companies]]
	results = []
	processed = []
	for cie in companies:
		cur_year = sorted(list(data[cie].keys()))[-1]
		for measure in data[cie][cur_year]:
			if measure not in processed:
				processed.append(measure)
				results.append([measure])
				for cie2 in companies:
					cie2_year = sorted(list(data[cie2].keys()))[-1]
					if measure in data[cie2][cie2_year]:
						results[-1].append(data[cie2][cie2_year][measure])
					else:
						results[-1].append("N/A")

	return header + results
	
def gather_individual_data(symbol, financials, prices):
	years = []
	data = {}
	datepattern = r"[0-9]{4}-[0-9]{2}" # "2018-10"
	for key in financials[1]:
		if re.match(datepattern, key) is not None or key == "TTM":
			years.append(key[0:4])
			
	name = ""
	special = ""
	for row in financials[2:]:
		count = 0
		need_special = False
		if len(row) >= len(years):
			for col in row:
				if years[count] not in data:
					data[years[count]] = {}
				try:
					col = float(col)
					full_name = name
					if need_special == True:
						full_name = special + " " + name
					data[years[count]][full_name] = col
					count += 1
				except (ValueError, TypeError):
					name += col
					if name in data[years[count]]:
						need_special = True
					else:
						need_special = False
			name = ""
		else:
			special = ", ".join(row)
				
	return data
				
				
def individual_to_csv(data):
	years = sorted(list(data.keys()))
	header = [["year"] + [x for x in years]]
	year0 = years[0]
	results = []
	
	for measure in data[year0]:
		results.append([measure])
		
	for year in years:
		for i in range(len(results)):
			measure = results[i][0]
			if measure in data[year]:
				results[i].append(data[year][measure])
			else:
				results[i].append("N/A")
			
	return header + results
	
	
def generate_report(symbols):
	timestr = strftime("%Y%m%d-%H%M%S")
	base_path = os.path.join(DATA_FOLDER, "reports", timestr)
	if not os.path.exists(base_path):
		os.makedirs(base_path)
	
	combine_report_data = {}
	individual_report_data = {}
	for symbol in symbols:
		financials, ffile = get_latest_financial(symbol)
		if financials is None:
			myprint("No data for " + symbol + ", skipping")
			continue
		prices, pfile = get_latest_price(symbol)
		individual_report_data[symbol] = gather_individual_data(symbol, financials, prices)
		individual_csv = individual_to_csv(individual_report_data[symbol])
		with open(os.path.join(base_path, symbol + ".csv"), 'w') as fo:
			for row in individual_csv:
				fo.write(",".join(str(x) for x in row) + "\n")

	combine_report_data = gather_combine_data(individual_report_data)
	
	with open(os.path.join(base_path, "combined.csv"), 'w') as fo:
		for row in combine_report_data:
			fo.write(",".join(str(x) for x in row) + "\n")
###############################################################################
# MAIN
###############################################################################
		
def do_actions(actions, params):
	if "dl_financial" in actions:
		dl_financial(params["single_symbol"])
	if "dl_all_financial" in actions:
		dl_all_financial()
	if "generate_report" in actions:
		generate_report(params["report_symbols"])
		
		
if __name__ == '__main__':
	actions = [
		#"dl_financial", # Use morning star URLs to download a CSV of financial data for the single_symbol
		#"dl_all_financial", # Use dl_financial on all tickers in news_link.json
		"generate_report", # Use financial and price data to generate csv report of each symbols in "report_symbols" (combined and individual)
		"nothing" # just so I don't need to play with the last ,
	]
	params = {
		"single_symbol" : "BNS.to", # used in dl_single_symbol, tech_lin_reg, plot_line, plot_points...
		"report_symbols" : ["DRG-UN.to", "REI-UN.to", "HR-UN.to", "D-UN.to", "CAR-UN.to", "CUF-UN.to", "AX-UN.to", "DIR-UN.to"],
		#"report_symbols" : ["AX-UN.to", "DRG-UN.to"],
		"nothing" : None # don't have to deal with last ,
	}
	do_actions(actions, params)
	