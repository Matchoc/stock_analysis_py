import sys
import os
os.environ["path"] = os.path.dirname(sys.executable) + ";" + os.environ["path"]
import re
from bs4 import BeautifulSoup
import urllib.request
import urllib.error


def downloadURL(url):
	try:
		print("request : " + url)
		req = urllib.request.Request(url)
		req.add_header('Referer', 'http://financials.morningstar.com/ratios/r.html?t=AQN&region=can&culture=en-US')
		req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.1 \
				  (KHTML, like Gecko) Chrome/21.0.1180.89 Safari/537.1')
		resp = urllib.request.urlopen(req)
		#print("resp = " + str(resp))
		data = resp.read()
		#print("data = " + str(data))
		text = data.decode('utf-8') # a `str`; this step can't be used if data is binary
		#print("text = " + text)
	except http.client.IncompleteRead as e:
		print("partial")
		data = e.partial
		text = data.decode('utf-8') # a `str`; this step can't be used if data is binary
	except urllib.error.HTTPError as e:
		print("URL failed : " + str(e.code) + " " + e.reason)
		return "failed"
	except UnicodeDecodeError as e:
		print("URL failed : Response not unicode")
		return "failed"
	except Exception as e:
		print("Unknown exception : " + str(e))
		return "failed"
	return text


if __name__ == '__main__':
	
	a = "http://financials.morningstar.com/finan/ajax/exportKR2CSV.html?&callback=?&t=XTSE:AQN&region=can&culture=en-US&cur=&order=asc"
	
	print(str(downloadURL(a)))
	
	
	sys.exit(0)
	
	
	
	text = '<table class="data-table tablemaster">\
		<tr class="tableheader">\
			<th colspan="5">Description &amp; Contact Information</th>\
		</tr>\
		<tr>\
			<td class="label">Business Description:</td>\
			<td class="data" colspan="4">WPT Industrial Real Estate Investment Trust (the REIT) is an open-ended real estate investment trust. The REIT is engaged in the business of acquiring and owning industrial investment properties located in the United States. Its objective is to provide Unitholders with an opportunity to invest in a portfolio of institutional-quality industrial properties in the United States markets, with a particular focus on distribution of the industrial real estate.</td>\
		</tr>\
		<tr>\
			<td class="label">Address:</td>\
			<td class="data" colspan="4">199 Bay Street, 	Suite 4000, 	Toronto, ON, CAN, M5L 1A9	</td>\
		</tr>\
		<tr>\
			<td class="label">Telephone:</td>\
			<td class="data">+1 612 800-8503</td>\
			<td class="spacer"><span></span></td>\
			<td class="label">Website:</td>\
				<td class="data"><a href="http://www.wptreit.com" target="_blank">http://www.wptreit.com</a></td></tr>\
		<tr>\
			<td class="label">Facsimile:</td>\
			<td class="data">+1 612 800-8535</td>\
			<td class="spacer"><span></span></td>\
			<td class="label">Email:</td>\
			<td class="data"><a title="Email" href="javascript:qmsm(\'welshpt.com:?:stf\');">stf@welshpt.com</a></td>\
		</tr>\
		'
	#soup.select("td[class='label'] ~ td[class='data']")
#soup.find_all(name="td", class_="label", text="Business Description").find_next_siblings("td").text
#css_soup.select("td.label")

	soup = BeautifulSoup(text, "html.parser", from_encoding="utf-8")
	#b = soup.select("td[class='label']")
	b = soup.find_all(name="td", class_="label", text=re.compile("Business Description"))
	for v in b:
		print(v.find_next_sibling("td").text)
	print(b)
	