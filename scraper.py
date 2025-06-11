#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import sys
import os

WEB_APP_URL = os.environ["WEB_APP_URL"]

def scrape_and_store(url):
    start_ts = time.time()
    # 1) fetch page
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 ..."},
            timeout=30
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Fetch failed: {e}", file=sys.stderr)
        return

    try:
        soup = BeautifulSoup(resp.text, 'lxml')
        # — existing fields —
        set_div   = soup.find('div', class_="value text-white mb-0 me-2 lh-1 stock-info")
        set_value = set_div.get_text(strip=True) if set_div else ""

        val_span   = soup.select_one('div.d-block.quote-market-cost.ps-2.ps-xl-3 span')
        value_cost = val_span.get_text(strip=True) if val_span else ""

        last_span = soup.select_one('div.d-block.quote-market-lastInfo span')
        if last_span and ' ' in (ts := last_span.get_text(strip=True)):
            update_date, update_time = ts.rsplit(' ',1)
        else:
            update_date = last_span.get_text(strip=True) if last_span else ""
            update_time = ""

        # reformat “29 May 2025” → “29-05-2025”
        try:
            dt = datetime.strptime(update_date, "%d %B %Y")
            update_date = dt.strftime("%d-%m-%Y")
        except ValueError:
            pass

        twod = ""
        if set_value and value_cost and '.' in value_cost:
            d = value_cost.index('.')
            twod = set_value[-1] + value_cost[d-1]

        # — market-status span —
        st = soup.select_one('div.quote-market-status span')
        status_text = st.get_text(strip=True).lower() if st else ""
        market_open = (status_text != "closed")

        # 2) POST main data to Sheet1 (append)
        main_payload = {
            "set":   set_value,
            "value": value_cost,
            "twod":  twod,
            "date":  update_date,
            "time":  update_time
        }
        r1 = requests.post(WEB_APP_URL, json=main_payload, timeout=10)
        r1.raise_for_status()

        # 3) POST status data to Sheet2 (overwrite row 1)
        status_payload = {
            "sheetName":   "Sheet2",
            "market_open": market_open,
            "date":        update_date,
            "time":        update_time
        }
        r2 = requests.post(WEB_APP_URL, json=status_payload, timeout=10)
        r2.raise_for_status()

        resp1 = r1.json()
        resp2 = r2.json()
        if resp1.get("result")=="success" and resp2.get("result")=="success":
            print("✅ Sheet1 appended; Sheet2 updated.")
        else:
            print(f"[ERROR] Sheet1: {resp1}  Sheet2: {resp2}", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Processing failed: {e}", file=sys.stderr)
    finally:
        print(f"⏱ Total run time: {time.time()-start_ts:.2f}s")

if __name__=="__main__":
    scrape_and_store("https://www.set.or.th/en/market/index/set/overview")
