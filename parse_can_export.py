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
DOC_FOLDER = "documentation"
EXPORT_FILE = os.path.join(DOC_FOLDER, "en_visualize_explore_tree_map_hs92_export_can_all_show_2016.csv")
NAME_FILE = os.path.join(DOC_FOLDER, "products_hs_92.tsv")
PRINT_LEVEL=0


###############################################################################
# UTILITIES
###############################################################################

def myprint(str, level=0):
	if (level >= PRINT_LEVEL):
		print(str)

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
	
###############################################################################
# PROCESSES
###############################################################################

def read_file_as_csv(filename, separator):
	csv_array = []
	with open(filename, 'r') as names:
		for line in names:
			line = line.replace("\"", "")
			line = [n for n in line.split(separator)]
			csv_array.append(line)
	
	return csv_array

	
def map_id_to_name(results):
	data = read_file_as_csv(NAME_FILE, '	')
	data_as_dict = {}
	for row in data[1:]: # skip header
		if row[1] in data_as_dict:
			myprint("Warning, ID " + str(row[1]) + " already exists with mapping : " + str(data_as_dict[row[1]]) + ", will be replaced by : " + str(row[2]),5)
		data_as_dict[row[1]] = row[2]
		
	results["name_map"] = data_as_dict
	
	
		
	
def read_export(results):
	data2 = read_file_as_csv(EXPORT_FILE, ',')
		
	results["exports"] = data2
	
def combine_results(results):
	final_export = []
	export_data = results["exports"]
	name_data = results["name_map"]

	for row in export_data[1:]: # skip header
		id = row[3]
		val = row[4]
		if id not in name_data:
			myprint("ERROR: Could not find id " + id + " in name_data",5)
		name = name_data[id]
		final_export.append({"name":name, "val":val})
		
	results["combined"] = final_export
	myprint(str(results["combined"]))
		
###############################################################################
# MAIN
###############################################################################
		
def do_actions(actions, params):
	results = {}
	if "parse_names" in actions:
		map_id_to_name(results)
	if "parse_export" in actions:
		read_export(results)
	if "combine" in actions:
		combine_results(results)
		
		
		
if __name__ == '__main__':
	actions = [
		"parse_names",
		"parse_export",
		"combine",
		"nothing" # just so I don't need to play with the last ,
	]
	params = {
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
	