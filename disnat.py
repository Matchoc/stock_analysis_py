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
import statistics
from bs4 import BeautifulSoup
from PIL import Image
from time import strftime
from time import sleep
from operator import itemgetter


###############################################################################
# GLOBAL CONSTANTS
###############################################################################


DATA_FOLDER = "data"
STOCK_LIST = os.path.join(DATA_FOLDER, "news_link.json")
TSX_CIE_INFO_OUTPUT = os.path.join(DATA_FOLDER, "tsx_cie_info.json")
# taken from https://www.tmxmoney.com/en/research/listed_company_directory.html with the ajax request : https://www.tsx.com/json/company-directory/search/tsx/%5E?callback=jQuery17105222798890806253_1534841471620&_=1534841501595
TSX_STOCK_LIST = os.path.join(DATA_FOLDER, "all_tsx_listing.json")
ALPHA_KEY = "JTQ5969IQZV04J91"
BASE_URL = "https://financials.morningstar.com/ajax/ReportProcess4CSV.html?&t={ticker}&region=can&culture=en-US&ops=clear&cur=&reportType=is&period=12&dataType=A&order=asc&columnYear=5&curYearPart=1st5year&rounding=3&view=raw&r=801461&denominatorView=raw&number=3"
KEY_STAT_URL = "http://financials.morningstar.com/ajax/exportKR2CSV.html?t={ticker}&culture=en-CA&region=CAN&order=asc&r=115497"
TSX_URL = "https://money.tmx.com/company.php?qm_symbol={symbol}&locale=EN"
JSON_PRICE_ROOT = "Time Series (Daily)"
JSON_CLOSE = "4. close"
JSON_DIVIDEND = "7. dividend amount"
JSON_REGRESSION_SLOPE = "cust. regression slope"
JSON_REGRESSION_ORIGIN = "cust. regression origin"
#FINANCIAL_SHARE_OUTSTANDING = "Weighted average shares outstanding Diluted"
FINANCIAL_SHARE_OUTSTANDING = "Shares Mil"
FINANCIAL_MARKET_CAP = "Market Capitalization"
SMALL_WAIT = 4.0
LONG_WAIT = 20.0
PRINT_LEVEL=1


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
		# Referer is now important. Must come from morningstar or they will not answer our prayers
		req.add_header('Referer', 'http://financials.morningstar.com/ratios/r.html?t=AQN&region=can&culture=en-US')
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
	
def as_float_list(obj):
	for i in range(len(obj)):
		try:
			obj[i] = float(obj[i])
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
	symbol = symbol.replace(".v", "")
	symbol = symbol.replace("-", ".")
	priceglob = os.path.join(DATA_FOLDER, "financials", symbol, "*-key.json")
	pricefiles = glob.glob(priceglob)
	if pricefiles is None or len(pricefiles) <= 0:
		return None, None
	pricefiles = sorted(pricefiles, reverse=True)
	pricefile = pricefiles[0]
	with open(pricefile, 'r') as jsonfile:
		data = json.load(jsonfile)
		
	return data, pricefile
	
	
def get_tsx_symbols(symbol_file, withexchange=True, separator='-'):
	loadpath = os.path.join(DATA_FOLDER, symbol_file)
	with open(loadpath, 'r') as jsonfile:
		symbols = json.load(jsonfile)
		
	if withexchange:
		return [a.replace(".", separator) + "." + symbols[a]["exchange"] for a in symbols]
	else:
		return [a.replace(".", separator) for a in symbols]
	
def get_custom_symbols(withexchange=True):
	with open(STOCK_LIST, 'r') as jsonfile:
		symbols = json.load(jsonfile)
		
	if withexchange:
		return [symbol + "." + symbols[symbol]["exchange"] for symbol in symbols]
	else:
		return [symbol for symbol in symbols]
	
###############################################################################
# MORNINGSTAR
###############################################################################

def del_old_financial(key):
	priceglob = os.path.join(DATA_FOLDER, "financials", "**", "*" + key + ".json")
	pricefiles = glob.glob(priceglob)
	
	total = str(len(pricefiles))
	count = 0
	for file in pricefiles:
		count += 1
		myprint("(" + str(count) + "/" + total + ") processing file " + file, 3)
		localglob = glob.glob(os.path.join(os.path.dirname(file), "*" + key + ".json"))
		localglob = sorted(localglob)
		myprint("list of files found : " + str(localglob))
		myprint("comparing " + file + " to " + localglob[-1])
		if file != localglob[-1]:
			os.remove(file)

def dl_financial_key_stat(single_symbol):
	single_symbol = single_symbol.replace(".to", "") # couldn't find a way to tell morningstar which exchange to use. But I think setting the local to CAN does the trick
	single_symbol = single_symbol.replace(".v", "")
	single_symbol = single_symbol.replace("-", ".") # morningstar uses AX.UN instead of AX-UN
	url2 = KEY_STAT_URL.format(ticker=single_symbol)
	myprint("Download URL : " + url2, 1)
	text = downloadURL(url2)
	
	if len(text) <= 1:
		return 1
		
	csv_array = text.splitlines()
	for i in range(len(csv_array)):
		line = csv_array[i]
		line = [n for n in line.split(',')]
		#line = as_float(line)
		csv_array[i] = line
		
	new_csv_array = []
	in_quote = False
	for i in range(len(csv_array)):
		new_csv_array.append([])
		for y in range(len(csv_array[i])):
			if "\"" in csv_array[i][y] and in_quote == False:
				new_csv_array[i].append(csv_array[i][y].replace("\"", ""))
				in_quote = True
			elif "\"" in csv_array[i][y] and in_quote == True:
				new_csv_array[i][-1] += "," + csv_array[i][y].replace("\"", "")
				in_quote = False
			elif in_quote == True:
				new_csv_array[i][-1] += "," + csv_array[i][y].replace("\"", "")
			else:
				new_csv_array[i].append(csv_array[i][y])
		#new_csv_array[i] = as_float_list(new_csv_array[i])
	
	csv_array = new_csv_array
		
	timestr = strftime("%Y%m%d-%H%M%S")
	fsymbol = single_symbol
	if "prn" in single_symbol or "PRN" in single_symbol:
		fsymbol = "PRRN"
	savepath = os.path.join(DATA_FOLDER, "financials", fsymbol, timestr + "-key.json")
	savepath = savepath.replace(":", "-")
		
	if not os.path.exists(os.path.dirname(savepath)):
		os.makedirs(os.path.dirname(savepath))
	with open(savepath, 'w') as fo:
		json.dump(csv_array, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
			
	return 0
			
def dl_financial(single_symbol):
	single_symbol = single_symbol.replace(".to", "") # couldn't find a way to tell morningstar which exchange to use. But I think setting the local to CAN does the trick
	single_symbol = single_symbol.replace(".v", "")
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
		#line = as_float(line)
		csv_array[i] = line
		
	new_csv_array = []
	in_quote = False
	for i in range(len(csv_array)):
		new_csv_array.append([])
		for y in range(len(csv_array[i])):
			if "\"" in csv_array[i][y] and in_quote == False:
				new_csv_array[i].append(csv_array[i][y].replace("\"", ""))
				in_quote = True
			elif "\"" in csv_array[i][y] and in_quote == True:
				new_csv_array[i][-1] += "," + csv_array[i][y].replace("\"", "")
				in_quote = False
			elif in_quote == True:
				new_csv_array[i][-1] += "," + csv_array[i][y].replace("\"", "")
			else:
				new_csv_array[i].append(csv_array[i][y])
		#new_csv_array[i] = as_float_list(new_csv_array[i])
	
	csv_array = new_csv_array
	
	timestr = strftime("%Y%m%d-%H%M%S")
	fsymbol = single_symbol
	if "prn" in single_symbol or "PRN" in single_symbol:
		fsymbol = "PRRN"
	savepath = os.path.join(DATA_FOLDER, "financials", fsymbol, timestr + "-income.json")
	savepath = savepath.replace(":", "-")

	if not os.path.exists(os.path.dirname(savepath)):
		os.makedirs(os.path.dirname(savepath))
	with open(savepath, 'w') as fo:
		json.dump(csv_array, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
			
	return 0
	
def dl_all_financial(symbol_file):
	symbols = get_tsx_symbols(symbol_file, False)
	
	count = 0
	total = len(symbols)
	for symbol in symbols:
		count += 1
		myprint("Downloading " + str(count) + "/" + str(total) + " : " + symbol, 2)
		ret = dl_financial(symbol)
		if ret == 1:
			myprint("Download Failed. Too many requests. Wainting " + str(LONG_WAIT) + " seconds.", 5)
			sleep(LONG_WAIT) # api call frenquency exceeded
			ret = dl_financial(symbol)
		elif ret == 2:
			myprint("Download Failed. Symbol not found or URL malformed.", 5)
		sleep(SMALL_WAIT)

def dl_all_key_stat(missingonly, symbol_file):
	symbols = get_tsx_symbols(symbol_file, False)
	
	count = 0
	total = len(symbols)
	for symbol in symbols:
		count += 1
		
		# Don't execute this most of the time !
		if missingonly:
			single_symbol = symbol.replace(".to", "") # couldn't find a way to tell morningstar which exchange to use. But I think setting the local to CAN does the trick
			single_symbol = single_symbol.replace(".v", "")
			single_symbol = single_symbol.replace("-", ".") # morningstar uses AX.UN instead of AX-UN
			savepath = os.path.join(DATA_FOLDER, "financials", single_symbol)
			if os.path.exists(savepath):
				continue
		###########
		
		myprint("Downloading " + str(count) + "/" + str(total) + " : " + symbol, 2)
		ret = dl_financial_key_stat(symbol)
		if ret == 1:
			myprint("Download Failed. Too many requests. Wainting " + str(LONG_WAIT) + " seconds.", 5)
			sleep(LONG_WAIT) # api call frenquency exceeded
			ret = dl_financial_key_stat(symbol)
		elif ret == 2:
			myprint("Download Failed. Symbol not found or URL malformed.", 5)
		sleep(SMALL_WAIT)
		
		

def dl_cie_info(symbol_file):
	symbols = get_tsx_symbols(symbol_file, False, '.')
	#<tr>
	#	<td class="label">Business Description:</td>
	#	<td class="data" colspan="4">WPT Industrial Real Estate Investment Trust (the REIT) is an open-ended real estate investment trust. The REIT is engaged in the business of acquiring and owning industrial investment properties located in the United States. Its objective is to provide Unitholders with an opportunity to invest in a portfolio of institutional-quality industrial properties in the United States markets, with a particular focus on distribution of the industrial real estate.</td>
	#</tr>
	#soup.select("td[class='label'] ~ td[class='data']")
	#soup.find_all(name="td", class_="label", text="Business Description").find_next_siblings("td").text
	#css_soup.select("td.label")

	results = {}
	
	index = 1
	
	for symbol in symbols:
		myprint("[" + str(index) + " / " + str(len(symbols)) + "] DL cie info for " + symbol, 1)
		symb_res = {}
		url = TSX_URL.format(symbol=symbol)
		text = downloadURL(url)
		soup = BeautifulSoup(text, "html.parser")
		titles = soup.find_all(name="td", class_="label")
		if len(titles) <= 0:
			myprint("DOWNLOAD FAILED", 5)
		for title in titles:
			data = title.find_next_sibling("td").text
			symb_res[title.text] = data
			
		results[symbol] = symb_res
		index += 1
	
	with open(TSX_CIE_INFO_OUTPUT, 'w') as fo:
		json.dump(results, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
	
		
		
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
	for key in financials[2]:
		if re.match(datepattern, key) is not None or key == "TTM":
			years.append(key[0:4])
			
	name = ""
	special = ""
	for row in financials[3:]:
		count = 0
		#myprint("(" + symbol + ") row : " + str(row))
		need_special = False
		if len(row) >= len(years):
			for col in row:
				if years[count] not in data:
					data[years[count]] = {}
				try:
					#myprint("try to cast float " + str(col))
					if col == "":
						col = 0.0
					else:
						col = float(col.replace(",", ""))
					full_name = name
					if need_special == True:
						full_name = special + " " + name
					data[years[count]][full_name] = col
					count += 1
				except (ValueError, TypeError):
					name += col
					#myprint("failed to cast float " + str(name))
					if name in data[years[count]]:
						need_special = True
					else:
						need_special = False
			name = ""
		else:
			special = ", ".join(row)
			
	#myprint("symbol " + symbol)
	price_data = prices[JSON_PRICE_ROOT]
	sorted_dates = sorted(price_data.keys())
	latest_price = price_data[sorted_dates[-1]][JSON_CLOSE]
	data[years[-1]][JSON_CLOSE] = latest_price
	#myprint("Symbol : " + symbol + " whole data : " + str(data))
	#myprint("Symbol : " + symbol + " data : " + str(data[years[-1]]))
	data[years[-1]][FINANCIAL_MARKET_CAP] = latest_price * data[years[-1]][FINANCIAL_SHARE_OUTSTANDING]
	
	for year in years[0:-1]:
		last_year = year + sorted_dates[-1][4:]
		if last_year in price_data:
			data[year][JSON_CLOSE] = price_data[last_year][JSON_CLOSE]
			data[year][FINANCIAL_MARKET_CAP] = data[year][JSON_CLOSE] * data[year][FINANCIAL_SHARE_OUTSTANDING]
			#myprint(symbol + " : price for " + last_year + " is " + str(data[year][JSON_CLOSE]))
		else:
			#myprint(symbol + " : price for " + last_year + " is N/A")
			data[year][JSON_CLOSE] = "N/A"
			data[year][FINANCIAL_MARKET_CAP] =  "N/A"
	
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
		myprint("Processing " + symbol)
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
			
def generate_filtered_all(max_cols, symbol_file):
	symbols = get_tsx_symbols(symbol_file)
	good_symbols = []
	# first remove any symbol that have invalid data (no key financials from morningstar or no price history)
	skip_financial = 0
	skip_price = 0
	for symbol in symbols:
		key_data, file = get_latest_financial(symbol)
		if key_data is None or len(key_data) <= 2:
			myprint("skipped " + symbol + " because couldn't find key financials", 1)
			skip_financial += 1
			continue
		price_data, file = get_latest_price(symbol)
		if price_data is None or "Information" in price_data or "Error Message" in price_data:
			myprint("skipped " + symbol + " because couldn't find price history", 1)
			skip_price += 1
			continue
		good_symbols.append({"symbol" : symbol, "price_data" : price_data, "key_data" : key_data})
		
	myprint("Skipped {} symbols because of financial and {} symbols because of price for a total of {} / {}".format(skip_financial, skip_price, skip_financial + skip_price, len(symbols)), 3)
		
	# second, gather usefull info
	count = 1
	for symbol_info in good_symbols:
		myprint("({} / {})Gathering info for {}".format(count, len(good_symbols), symbol_info["symbol"]),1)
		count += 1
		key_data = symbol_info["key_data"]
		price_data = symbol_info["price_data"]
		
		# first gathering. Latest price
		price_data_root = price_data[JSON_PRICE_ROOT]
		sorted_dates = sorted(price_data_root.keys())
		latest_price = price_data_root[sorted_dates[-1]][JSON_CLOSE]
		symbol_info["latest_price"] = latest_price
		
		# second interesting key financials
		big_data = gather_individual_data(symbol_info["symbol"], key_data, price_data)
		cur_year = sorted(list(big_data.keys()))[-1]
		most_recent_data = big_data[cur_year]
		myprint(most_recent_data)
		revenuepattern = r"Revenue [A-Z]{3} Mil" # "2018-10"
		cur = "CAD"
		for elem in most_recent_data:
			if re.match(revenuepattern, elem) is not None:
				cur = elem[8:11]
		symbol_info[FINANCIAL_MARKET_CAP] = most_recent_data[FINANCIAL_MARKET_CAP]
		symbol_info["Share Outstanding"] = most_recent_data[FINANCIAL_SHARE_OUTSTANDING]
		symbol_info["Long-Term Debt"] = most_recent_data['Long-Term Debt']
		symbol_info["Short-Term Debt"] = most_recent_data['Short-Term Debt']
		symbol_info["Debt/Equity"] = most_recent_data['Debt/Equity']
		symbol_info["Total Debt"] = symbol_info["Long-Term Debt"] + symbol_info["Short-Term Debt"]
		symbol_info["Revenue Mil"] = most_recent_data["Revenue " + cur + " Mil"]
		symbol_info["Net Income Mil"] = most_recent_data['Net Income ' + cur + ' Mil']
		symbol_info["Dividends $"] = most_recent_data['Dividends ' + cur]
		symbol_info["Dividends %"] = symbol_info["Dividends $"] / symbol_info["latest_price"]
		symbol_info["EPS"] = most_recent_data['Earnings Per Share ' + cur]
		symbol_info["R&D"] = most_recent_data['R&D']
		symbol_info["ROE %"] = most_recent_data['Return on Equity %']
		symbol_info["Operating Income Mil"] = most_recent_data['Operating Income ' + cur + ' Mil']
		symbol_info["Total Liabilities"] = most_recent_data['Total Liabilities']
		symbol_info["Shares Mil"] = most_recent_data['Shares Mil']
		symbol_info["currency"] = cur
		
		symbol_info[JSON_REGRESSION_SLOPE] = price_data_root[sorted_dates[-1]][JSON_REGRESSION_SLOPE]
		symbol_info[JSON_REGRESSION_ORIGIN] = price_data_root[sorted_dates[-1]][JSON_REGRESSION_ORIGIN]
		
		symbol_info["key_data"] = None
		symbol_info["price_data"] = None
	
	#third, compute a csv for output
	good_symbols = sorted(good_symbols, key=operator.itemgetter("symbol"))
	
	header = sorted(list(good_symbols[0].keys()))
	header.remove("symbol")
	csv_array = []
	for symbol_info in good_symbols:
		row_str = symbol_info["symbol"]
		for key in header:
			if key != "symbol":
				row_str += ", " + str(symbol_info[key])
		csv_array.append(row_str)
		
	timestr = strftime("%Y%m%d-%H%M%S")
	base_path = os.path.join(DATA_FOLDER, "reports", timestr)
	if not os.path.exists(base_path):
		os.makedirs(base_path)
	with open(os.path.join(base_path, "custom_filtered.csv"), 'w') as fo:
		fo.write("symbol, " + ",".join(str(x) for x in header) + "\n")
		for row in csv_array:
			fo.write(row + "\n")
			
def print_cie_match_regex(params):
	with open(TSX_CIE_INFO_OUTPUT, 'r') as jsonfile:
		data = json.load(jsonfile)
	
	result = []
	regex = re.compile(params["regex"])
	for symbol in data:
		if "Business Description:" in data[symbol]:
			res = regex.search(data[symbol]["Business Description:"])
			if res is not None:
				result.append(symbol)
				myprint(symbol,1)
				desc = data[symbol]["Business Description:"]
				num_char = len(desc)
				for i in range(0, num_char, 200):
					myprint(desc[i:i+200],1)
	myprint(result, 5)
	
	
def update_news_link():
	timestr = strftime("%Y%m%d-%H%M%S")
	savepath = os.path.join(DATA_FOLDER, "news_link-" + timestr + ".json")
	base_urls = [
		{"url":"https://www.tsx.com/json/company-directory/search/tsx/", "exchange":"to"}, 
		{"url":"https://www.tsx.com/json/company-directory/search/tsxv/", "exchange":"v"}]
	letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "0-9"]
	data = {}
	for letter in letters:
		for base_url in base_urls:
			url = base_url["url"] + letter
			result = downloadURL(url)
			j_data = json.loads(result)
			if "results" not in j_data or len(j_data["results"]) == 0:
				continue
			for cie in j_data["results"]:
				for instrument in cie["instruments"]:
					if instrument["symbol"] in data:
						myprint(instrument["symbol"] + " Already in news_link", 2)
					if instrument["symbol"] not in data or base_url["exchange"] == "to":
						data[instrument["symbol"]] = {"exchange":base_url["exchange"], "name":instrument["name"]}
			
			sleep(SMALL_WAIT)
	
	with open(savepath, 'w') as fo:
		json.dump(data, fo, sort_keys=True,
			indent=4, separators=(',', ': '))
			
def generate_price_report(start_date, num_days):
	dirlist = [x[0] for x in os.walk(os.path.join(DATA_FOLDER, "prices"))]
	
	count = 0
	count_valid = 0
	count_invalid = 0
	total = len(dirlist)
	csv_result = ["symbol, latest price, january price, std deviation, 16-day avg std, dividend, jan diff, dev %, avg dev %"]
	for dir in dirlist:
		if "." not in dir:
			continue
		myprint("({}/{}) processing file {}".format(str(count), str(total), dir),1)
		count += 1
		symbol = os.path.basename(dir)
		data, f = get_latest_price(symbol)
		if data is None or "Meta Data" not in data:
			myprint("Invalid Entry: " + dir + ", skipped")
			count_invalid += 1
			continue
		
		time_series = data[JSON_PRICE_ROOT]
		sorted_dates = sorted(time_series.keys())
		latest_price = time_series[sorted_dates[-1]][JSON_CLOSE]
		if latest_price < 8.0:
			myprint("Price too low (" + str(latest_price) + "), skipped")
			count_invalid += 1
			continue
		if latest_price > 100.0:
			myprint("Price too high (" + str(latest_price) + "), skipped")
			count_invalid += 1
			continue
		
		count_valid += 1
		
		# calculated since nov 2019?
		# symbol, std dev, latest close price, jan close price, total dividend
		myprint("symbol, latest, jan, dividend")
		#avg_std_dev = calculate_std_dev(time_series)
		# date format 2005-01-04
		start_time = datetime.datetime(2020, 1, 1)
		text_time = start_time.strftime("%Y-%m-%d")
		num_try = 0
		while text_time not in time_series and num_try < 60:
			start_time -= datetime.timedelta(days=1)
			text_time = start_time.strftime("%Y-%m-%d")
			num_try += 1
		if num_try > 50:
			myprint("Could not find a valid price for January, skipped")
			count_invalid += 1
			continue
		jan_price = time_series[text_time][JSON_CLOSE]
		text_time = start_date.strftime("%Y-%m-%d")
		dividend = 0
		std_data = []
		for i in range(num_days):
			cur_date = start_date - datetime.timedelta(days=i)
			text_time = cur_date.strftime("%Y-%m-%d")
			if text_time in time_series:
				dividend += time_series[text_time][JSON_DIVIDEND]
				std_data.append(time_series[text_time][JSON_CLOSE])
		
		std_dev = statistics.stdev(std_data)
		
		n = int(len(std_data)/16.0)
		chunks = [std_data[i:i+n] for i in range(0, len(std_data), n)]
		avgs = []
		for chunk in chunks:
			if len(chunk) <= 1:
				avgs.append(chunk[0])
			else:
				avgs.append(statistics.stdev(chunk))
		avg_std_dev = statistics.mean(avgs)
		jan_diff = latest_price-jan_price
		std_dev_per = std_dev / latest_price
		avg_std_dev_per = avg_std_dev / latest_price
		
		csv_result.append("{},{},{},{},{},{},{},{},{}".format(
			symbol, latest_price, jan_price, 
			std_dev, avg_std_dev, dividend, 
			jan_diff, std_dev_per, avg_std_dev_per))
			
	myprint("Processed {}, discarded {}, output {} ".format(count, count_invalid, count_valid),3)
	myprint("RESULT:",5)
	for l in csv_result:
		myprint(l, 5)
		
###############################################################################
# MAIN
###############################################################################
		
def do_actions(actions, params):
	if "update_news_link" in actions:
		update_news_link()
	if "dl_financial" in actions:
		dl_financial(params["single_symbol"])
	if "dl_financial_key_stat" in actions:
		dl_financial_key_stat(params["single_symbol"])
	if "dl_all_financial" in actions:
		dl_all_financial(params["stock_file"])
	if "dl_all_key_stat" in actions:
		dl_all_key_stat(params["dl_missing_only"], params["stock_file"])
	if "generate_price_report" in actions:
		generate_price_report(params["start_date"], params["how_many_days"])
	if "generate_report" in actions:
		generate_report(params["report_symbols"])
	if "generate_filtered_all" in actions:
		generate_filtered_all(params["max_report"], params["stock_file"])
	if "del_old_financial" in actions:
		del_old_financial("income")
		del_old_financial("key")
	if "dl_cie_info" in actions:
		dl_cie_info(params["stock_file"])
	if "print_cie_match_regex" in actions:
		print_cie_match_regex(params)
		
		
		
if __name__ == '__main__':
	actions = [
		#"update_news_link", # use https://www.tsx.com/json/company-directory/search/tsx/A to fetch a json of all tsx listed companies
		#"dl_cie_info", # Use https://money.tmx.com/company.php?qm_symbol=BB&locale=EN to save simple info about each company on the tsx (website, description, etc.)
		#"print_cie_match_regex", # Print the list of companies in tsx_cie_info.json who's description matches a given regex in params
		#"dl_financial", # Use MorningStar URLs to download a CSV of financial data for the single_symbol (mostly revenues and expenses and outstanding shares)
		#"dl_financial_key_stat", # Use MorningStar URL to download a CSV of financial key data for the single_symbol (mostly dividend and various ratios)
		#"dl_all_financial", # Use dl_financial on all tickers in news_link.json
		#"dl_all_key_stat", # Use dl_financial_key_stat on all tickers in news_link.json (should probably be used in colaboration with dl_all_financial)
		"generate_price_report", # generate csv report of price data for last 1 1/2 year for all interesting symbol (above 9$/share)
		#"generate_report", # Use financial and price data to generate csv report of each symbols in "report_symbols" (combined and individual)
		#"del_old_financial", # Cleanup old financial data and keep only the latest in folder data/financials/<symbol>/*-income.json
		#"generate_filtered_all", # generate a combine report of top "max_report" number of tickers that fit a certain list of filters
		"nothing" # just so I don't need to play with the last ,
	]
	params = {
		"single_symbol" : "AAAA.v", # used in dl_single_symbol, tech_lin_reg, plot_line, plot_points...
		"report_symbols" : ["ETX.to", "AQN.to", "AAAA.v", "BB.to"],
		"stock_file": "news_link-20210205-161445.json",
		"max_report" : 20,
		"dl_missing_only" : False, # when doing a dl_all_key_stat. Will only download missing prices (if the folder doesn't exist)
		"regex":'(?=.*warehouse)(?=.*data)', # Find those two words in any order inside the description of the company
		#"regex":'analy', # Find those two words in any order inside the description of the company
		"start_date":datetime.datetime(2021,2,5), # date to start report calculation
		"how_many_days":462, # from nov 1 2019 to feb 6 2020
		"nothing" : None # don't have to deal with last ,
	}
	do_actions(actions, params)
	
	
	
	'''
	globpat = os.path.join(DATA_FOLDER, "financials", "**", "*.json")
	financials = glob.glob(globpat)
	financials = [os.path.basename(os.path.dirname(n)) for n in financials]
	myprint(financials)
	with open(STOCK_LIST, 'r') as jsonfile:
		symbols = json.load(jsonfile)
		
	symbols = list(symbols.keys())
	symbols = [symbol.replace("-", ".") for symbol in symbols]

	myprint(str(set(symbols) - set(financials)))
	
	
	sys.exit(0)
	'''
	