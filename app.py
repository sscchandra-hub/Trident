#!/usr/bin/env python3
"""
AUTOMATED ALERT SCANNER FOR ZERODHA TRIGGER BREAKOUTS WITH SECTOR ALIGNMENT
===========================================================================
Runs the enhanced Zerodha scanner continuously and sends top alerts
via Discord webhook and Telegram with full breakout, dormancy, options details,
and SECTOR ALIGNMENT confirmation.
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
import shutil
import numpy as np
import pytz
from datetime import datetime, time as dt_time, timedelta
from typing import List, Dict, Optional, Tuple
import traceback
from pathlib import Path
from collections import defaultdict

# Import the Zerodha scanner - UPDATE THIS PATH AS NEEDED
try:
    # Assuming the Zerodha scanner is saved as Zerodha_Scanner.py
    from Vamsi_Original_India import TriggerScanner, Config
except ImportError:
    print("Error: Zerodha_Scanner.py must be in the same directory")
    print("Please save the enhanced Zerodha scanner code as Zerodha_Scanner.py")
    sys.exit(1)

# ==================== SSL FIX FOR CORPORATE NETWORKS ====================
# This section fixes SSL certificate verification issues
import ssl
import certifi
import urllib3

# Fix SSL certificates
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Create unverified context for corporate networks
ssl._create_default_https_context = ssl._create_unverified_context

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey patch requests to handle SSL issues
_original_request = requests.Session.request

def patched_request(self, *args, **kwargs):
    """Patched request method that disables SSL verification"""
    kwargs['verify'] = False
    return _original_request(self, *args, **kwargs)

# Apply the patch
requests.Session.request = patched_request

print("✅ SSL fix applied - certificate verification disabled for corporate network")
# ==================== END SSL FIX ====================

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== SECTOR MAPPER ====================
class SectorMapper:
    """Maps stocks to their respective sectors and tracks sector indices"""
    
    def __init__(self):
        # Comprehensive mapping of ALL tickers from NSE_FO.txt to their sectors
        # Updated: December 2025 - 208 tickers mapped accurately
        self.stock_to_sector = {
            # ==================== IT SECTOR (13 stocks) ====================
            # Maps to NIFTY IT index
            'NSE:TCS': 'IT',
            'NSE:INFY': 'IT',
            'NSE:WIPRO': 'IT',
            'NSE:HCLTECH': 'IT',
            'NSE:TECHM': 'IT',
            'NSE:LTIM': 'IT',              # LTIMindtree
            'NSE:PERSISTENT': 'IT',
            'NSE:COFORGE': 'IT',
            'NSE:CYIENT': 'IT',
            'NSE:KPITTECH': 'IT',
            'NSE:OFSS': 'IT',              # Oracle Financial Services
            'NSE:MPHASIS': 'IT',
            'NSE:TATAELXSI': 'IT',
            
            # ==================== PRIVATE BANKS (11 stocks) ====================
            # Maps to NIFTY BANK index
            'NSE:HDFCBANK': 'BANK',
            'NSE:ICICIBANK': 'BANK',
            'NSE:AXISBANK': 'BANK',
            'NSE:KOTAKBANK': 'BANK',
            'NSE:INDUSINDBK': 'BANK',
            'NSE:AUBANK': 'BANK',
            'NSE:RBLBANK': 'BANK',
            'NSE:FEDERALBNK': 'BANK',
            'NSE:IDFCFIRSTB': 'BANK',
            'NSE:YESBANK': 'BANK',
            'NSE:BANDHANBNK': 'BANK',
            
            # ==================== PSU BANKS (7 stocks) ====================
            # Maps to NIFTY PSU BANK index
            'NSE:SBIN': 'PSUBANK',
            'NSE:BANKBARODA': 'PSUBANK',
            'NSE:CANBK': 'PSUBANK',
            'NSE:PNB': 'PSUBANK',
            'NSE:BANKINDIA': 'PSUBANK',
            'NSE:INDIANB': 'PSUBANK',
            'NSE:UNIONBANK': 'PSUBANK',
            
            # ==================== FINANCIAL SERVICES (36 stocks) ====================
            # Maps to NIFTY FIN SERVICE index
            # NBFCs
            'NSE:BAJFINANCE': 'FINSERVICE',
            'NSE:BAJAJFINSV': 'FINSERVICE',
            'NSE:CHOLAFIN': 'FINSERVICE',
            'NSE:SHRIRAMFIN': 'FINSERVICE',
            'NSE:MUTHOOTFIN': 'FINSERVICE',
            'NSE:LICHSGFIN': 'FINSERVICE',
            'NSE:MANAPPURAM': 'FINSERVICE',
            'NSE:ABCAPITAL': 'FINSERVICE',
            'NSE:PNBHOUSING': 'FINSERVICE',
            'NSE:SAMMAANCAP': 'FINSERVICE',
            'NSE:LTF': 'FINSERVICE',           # L&T Finance
            'NSE:IIFL': 'FINSERVICE',
            
            # Insurance
            'NSE:HDFCLIFE': 'FINSERVICE',
            'NSE:SBILIFE': 'FINSERVICE',
            'NSE:ICICIPRULI': 'FINSERVICE',
            'NSE:ICICIGI': 'FINSERVICE',
            'NSE:LICI': 'FINSERVICE',
            'NSE:POLICYBZR': 'FINSERVICE',
            
            # AMC & Wealth Management
            'NSE:HDFCAMC': 'FINSERVICE',
            'NSE:NUVAMA': 'FINSERVICE',
            'NSE:360ONE': 'FINSERVICE',
            'NSE:MFSL': 'FINSERVICE',
            
            # Exchanges & Depositories
            'NSE:BSE': 'FINSERVICE',
            'NSE:MCX': 'FINSERVICE',
            'NSE:CDSL': 'FINSERVICE',
            'NSE:IEX': 'FINSERVICE',
            'NSE:CAMS': 'FINSERVICE',
            'NSE:KFINTECH': 'FINSERVICE',
            
            # Other Financial Services
            'NSE:SBICARD': 'FINSERVICE',
            'NSE:ANGELONE': 'FINSERVICE',
            'NSE:JIOFIN': 'FINSERVICE',
            
            # Power/Infra Finance (technically FINSERVICE)
            'NSE:PFC': 'FINSERVICE',
            'NSE:RECLTD': 'FINSERVICE',
            'NSE:IRFC': 'FINSERVICE',
            'NSE:IREDA': 'FINSERVICE',
            'NSE:HUDCO': 'FINSERVICE',
            
            # ==================== AUTO & AUTO ANCILLARIES (14 stocks) ====================
            # Maps to NIFTY AUTO index
            'NSE:MARUTI': 'AUTO',
            'NSE:M&M': 'AUTO',
            'NSE:TATAMOTORS': 'AUTO',         # If present
            'NSE:EICHERMOT': 'AUTO',
            'NSE:HEROMOTOCO': 'AUTO',
            'NSE:TVSMOTOR': 'AUTO',
            'NSE:BAJAJ-AUTO': 'AUTO',         # If present
            'NSE:ASHOKLEY': 'AUTO',
            'NSE:BOSCHLTD': 'AUTO',
            'NSE:MOTHERSON': 'AUTO',
            'NSE:EXIDEIND': 'AUTO',
            'NSE:SONACOMS': 'AUTO',
            'NSE:TIINDIA': 'AUTO',            # Tube Investments
            'NSE:BHARATFORG': 'AUTO',
            'NSE:UNOMINDA': 'AUTO',
            'NSE:TMPV': 'AUTO',               # Tata Motors Passenger Vehicles
            
            # ==================== PHARMA (15 stocks) ====================
            # Maps to NIFTY PHARMA index
            'NSE:SUNPHARMA': 'PHARMA',
            'NSE:DRREDDY': 'PHARMA',
            'NSE:CIPLA': 'PHARMA',
            'NSE:LUPIN': 'PHARMA',
            'NSE:TORNTPHARM': 'PHARMA',
            'NSE:ZYDUSLIFE': 'PHARMA',
            'NSE:DIVISLAB': 'PHARMA',
            'NSE:AUROPHARMA': 'PHARMA',
            'NSE:ALKEM': 'PHARMA',
            'NSE:BIOCON': 'PHARMA',
            'NSE:GLENMARK': 'PHARMA',
            'NSE:MANKIND': 'PHARMA',
            'NSE:PPLPHARMA': 'PHARMA',
            'NSE:LAURUSLABS': 'PHARMA',
            'NSE:SYNGENE': 'PHARMA',
            
            # ==================== HEALTHCARE (3 stocks) ====================
            # Maps to NIFTY HEALTHCARE INDEX
            'NSE:APOLLOHOSP': 'HEALTHCARE',
            'NSE:FORTIS': 'HEALTHCARE',
            'NSE:MAXHEALTH': 'HEALTHCARE',
            
            # ==================== FMCG (13 stocks) ====================
            # Maps to NIFTY FMCG index
            'NSE:ITC': 'FMCG',
            'NSE:HINDUNILVR': 'FMCG',
            'NSE:NESTLEIND': 'FMCG',
            'NSE:BRITANNIA': 'FMCG',
            'NSE:DABUR': 'FMCG',
            'NSE:MARICO': 'FMCG',
            'NSE:TATACONSUM': 'FMCG',
            'NSE:COLPAL': 'FMCG',
            'NSE:GODREJCP': 'FMCG',
            'NSE:JUBLFOOD': 'FMCG',
            'NSE:VBL': 'FMCG',                 # Varun Beverages
            'NSE:UNITDSPR': 'FMCG',            # United Spirits
            'NSE:PATANJALI': 'FMCG',
            
            # ==================== ENERGY / OIL & GAS (18 stocks) ====================
            # Maps to NIFTY ENERGY index
            'NSE:RELIANCE': 'ENERGY',
            'NSE:ONGC': 'ENERGY',
            'NSE:NTPC': 'ENERGY',
            'NSE:POWERGRID': 'ENERGY',
            'NSE:BPCL': 'ENERGY',
            'NSE:IOC': 'ENERGY',
            'NSE:GAIL': 'ENERGY',
            'NSE:TATAPOWER': 'ENERGY',
            'NSE:HINDPETRO': 'ENERGY',
            'NSE:OIL': 'ENERGY',
            'NSE:PETRONET': 'ENERGY',
            'NSE:ADANIGREEN': 'ENERGY',
            'NSE:ADANIENSOL': 'ENERGY',
            'NSE:JSWENERGY': 'ENERGY',
            'NSE:NHPC': 'ENERGY',
            'NSE:TORNTPOWER': 'ENERGY',
            'NSE:SUZLON': 'ENERGY',
            'NSE:INOXWIND': 'ENERGY',
            
            # ==================== METALS & MINING (11 stocks) ====================
            # Maps to NIFTY METAL index
            'NSE:TATASTEEL': 'METAL',
            'NSE:JSWSTEEL': 'METAL',
            'NSE:HINDALCO': 'METAL',
            'NSE:VEDL': 'METAL',
            'NSE:JINDALSTEL': 'METAL',
            'NSE:SAIL': 'METAL',
            'NSE:HINDZINC': 'METAL',
            'NSE:NMDC': 'METAL',
            'NSE:NATIONALUM': 'METAL',
            'NSE:COALINDIA': 'METAL',
            'NSE:APLAPOLLO': 'METAL',          # APL Apollo Tubes - Steel
            
            # ==================== REALTY (6 stocks) ====================
            # Maps to NIFTY REALTY index
            'NSE:DLF': 'REALTY',
            'NSE:GODREJPROP': 'REALTY',
            'NSE:OBEROIRLTY': 'REALTY',
            'NSE:LODHA': 'REALTY',
            'NSE:PRESTIGE': 'REALTY',
            'NSE:PHOENIXLTD': 'REALTY',
            
            # ==================== INFRASTRUCTURE & CONSTRUCTION (30 stocks) ====================
            # Maps to NIFTY INFRA index
            'NSE:LT': 'INFRA',
            'NSE:ADANIPORTS': 'INFRA',
            'NSE:ADANIENT': 'INFRA',
            
            # Cement
            'NSE:ULTRACEMCO': 'INFRA',
            'NSE:SHREECEM': 'INFRA',
            'NSE:AMBUJACEM': 'INFRA',
            'NSE:DALBHARAT': 'INFRA',
            'NSE:GRASIM': 'INFRA',             # Also has cement business
            
            # Capital Goods / Engineering
            'NSE:ABB': 'INFRA',
            'NSE:SIEMENS': 'INFRA',
            'NSE:CGPOWER': 'INFRA',
            'NSE:BHEL': 'INFRA',
            'NSE:CUMMINSIND': 'INFRA',
            'NSE:POWERINDIA': 'INFRA',
            
            # Defense
            'NSE:HAL': 'INFRA',
            'NSE:BEL': 'INFRA',
            'NSE:BDL': 'INFRA',
            'NSE:MAZDOCK': 'INFRA',
            
            # Railways
            'NSE:RVNL': 'INFRA',
            'NSE:IRCTC': 'INFRA',
            'NSE:TITAGARH': 'INFRA',
            'NSE:CONCOR': 'INFRA',
            
            # Construction
            'NSE:NCC': 'INFRA',
            'NSE:NBCC': 'INFRA',
            
            # Cables & Wires
            'NSE:POLYCAB': 'INFRA',
            'NSE:KEI': 'INFRA',
            'NSE:HFCL': 'INFRA',
            
            # Pipes
            'NSE:ASTRAL': 'INFRA',
            
            # Telecom Towers
            'NSE:INDUSTOWER': 'INFRA',
            
            # Airports
            'NSE:GMRAIRPORT': 'INFRA',
            
            # ==================== CONSUMER DURABLES (14 stocks) ====================
            # Maps to NIFTY CONSUMER DURABLES index
            'NSE:TITAN': 'CONSDUR',
            'NSE:HAVELLS': 'CONSDUR',
            'NSE:VOLTAS': 'CONSDUR',
            'NSE:BLUESTARCO': 'CONSDUR',
            'NSE:CROMPTON': 'CONSDUR',
            'NSE:DIXON': 'CONSDUR',
            'NSE:AMBER': 'CONSDUR',
            'NSE:TRENT': 'CONSDUR',            # Retail
            'NSE:DMART': 'CONSDUR',            # Retail
            'NSE:KALYANKJIL': 'CONSDUR',       # Jewelry
            'NSE:SUPREMEIND': 'CONSDUR',       # Plastics
            'NSE:KAYNES': 'CONSDUR',           # Electronics Manufacturing
            'NSE:ASIANPAINT': 'CONSDUR',       # Paints
            'NSE:PIDILITIND': 'CONSDUR',       # Adhesives
            
            # ==================== TELECOM (2 stocks) ====================
            # No specific telecom index, using NIFTY50
            'NSE:BHARTIARTL': 'TELECOM',
            'NSE:IDEA': 'TELECOM',
            
            # ==================== MEDIA & TECH PLATFORMS (4 stocks) ====================
            # Maps to NIFTY MEDIA index
            'NSE:NAUKRI': 'MEDIA',             # Info Edge
            'NSE:NYKAA': 'MEDIA',
            'NSE:PAYTM': 'MEDIA',
            'NSE:ETERNAL': 'MEDIA',            # Zomato
            
            # ==================== COMMODITIES / CHEMICALS (5 stocks) ====================
            # Maps to NIFTY COMMODITIES index
            'NSE:UPL': 'COMMODITIES',
            'NSE:PIIND': 'COMMODITIES',
            'NSE:SRF': 'COMMODITIES',
            'NSE:SOLARINDS': 'COMMODITIES',
            'NSE:PAGEIND': 'COMMODITIES',      # Textiles but in commodities index
            
            # ==================== SERVICES (4 stocks) ====================
            # Maps to NIFTY SERVICES SECTOR index
            'NSE:INDIGO': 'SERVICES',          # Aviation
            'NSE:INDHOTEL': 'SERVICES',        # Hotels
            'NSE:DELHIVERY': 'SERVICES',       # Logistics
            'NSE:TATATECH': 'SERVICES',        # Engineering Services
            
            # ==================== EMS / ELECTRONICS MANUFACTURING ====================
            # PG Electroplast - EMS company (makes ACs, TVs, washing machines)
            # Grouped with Consumer Durables as that's where EMS stocks are categorized
            'NSE:PGEL': 'CONSDUR',
            
            # ==================== INDEX ====================
            'NSE:NIFTY 50': 'INDEX',
            'NSE:NIFTY': 'INDEX',
        }
        
        # CORRECT Zerodha API sector index symbols
        # These are the actual tradeable index symbols on NSE
        self.sector_indices = {
            'IT': 'NSE:NIFTY IT',
            'BANK': 'NSE:NIFTY BANK',
            'PSUBANK': 'NSE:NIFTY PSU BANK',
            'FINSERVICE': 'NSE:NIFTY FIN SERVICE',
            'AUTO': 'NSE:NIFTY AUTO',
            'PHARMA': 'NSE:NIFTY PHARMA',
            'HEALTHCARE': 'NSE:NIFTY HEALTHCARE INDEX',
            'FMCG': 'NSE:NIFTY FMCG',
            'ENERGY': 'NSE:NIFTY ENERGY',
            'METAL': 'NSE:NIFTY METAL',
            'REALTY': 'NSE:NIFTY REALTY',
            'INFRA': 'NSE:NIFTY INFRA',
            'CONSDUR': 'NSE:NIFTY CONSUMER DURABLES',
            'MEDIA': 'NSE:NIFTY MEDIA',
            'COMMODITIES': 'NSE:NIFTY COMMODITIES',
            'SERVICES': 'NSE:NIFTY SERVICES SECTOR',
            'TELECOM': 'NSE:NIFTY50',          # No specific telecom index, use NIFTY50
            'INDEX': 'NSE:NIFTY 50',
        }
        
        # Store sector data
        self.sector_data = {}
        
    def get_stock_sector(self, symbol: str) -> str:
        """Get the sector for a given stock symbol"""
        return self.stock_to_sector.get(symbol)
    
    def get_all_stocks_by_sector(self, sector: str) -> list:
        """Get all stocks belonging to a specific sector"""
        return [stock for stock, sec in self.stock_to_sector.items() if sec == sector]
    
    def get_sector_summary(self) -> dict:
        """Get a summary of all sectors and their stock counts"""
        sector_counts = {}
        for stock, sector in self.stock_to_sector.items():
            if sector not in sector_counts:
                sector_counts[sector] = []
            sector_counts[sector].append(stock)
        
        return {sector: len(stocks) for sector, stocks in sector_counts.items()}
    
    def validate_mapping(self, fo_file_stocks: list) -> dict:
        """Validate that all stocks from FO file are mapped"""
        mapped_stocks = set(self.stock_to_sector.keys())
        fo_stocks = set(fo_file_stocks)
        
        missing_in_mapping = fo_stocks - mapped_stocks
        extra_in_mapping = mapped_stocks - fo_stocks
        
        return {
            'total_fo_stocks': len(fo_stocks),
            'total_mapped_stocks': len(mapped_stocks),
            'missing_in_mapping': list(missing_in_mapping),
            'extra_in_mapping': list(extra_in_mapping),
            'mapping_complete': len(missing_in_mapping) == 0
        }
    
    def fetch_sector_data(self, client) -> dict:
        """Fetch real-time sector index data"""
        try:
            if not hasattr(client, 'kite'):
                print("⚠️ Client not properly initialized, skipping sector data fetch")
                return {}
            
            # Get quotes for all sector indices
            sector_symbols = list(self.sector_indices.values())
            
            # Remove duplicates (NIFTY50 used for multiple sectors)
            sector_symbols = list(set(sector_symbols))
            
            sector_data = {}
            
            # Fetch all at once
            try:
                quotes = client.kite.quote(sector_symbols)
            except Exception as e:
                print(f"❌ Failed to fetch sector quotes: {e}")
                return {}
            
            # Process the data
            for sector_name, sector_symbol in self.sector_indices.items():
                if sector_symbol in quotes:
                    quote = quotes[sector_symbol]
                    change_pct = quote.get('change_percent', 0)
                    last_price = quote.get('last_price', 0)
                    
                    # Zerodha returns N/A for change_percent on indices
                    # Calculate it manually from open price
                    if change_pct == 0 or change_pct == 'N/A':
                        ohlc = quote.get('ohlc', {})
                        open_price = ohlc.get('open', 0)
                        
                        if open_price > 0 and last_price > 0:
                            # Calculate change manually
                            change_pct = ((last_price - open_price) / open_price) * 100
                    
                    # Determine direction
                    if change_pct > 0.05:
                        direction = 'bullish'
                    elif change_pct < -0.05:
                        direction = 'bearish'
                    else:
                        direction = 'neutral'
                    
                    sector_data[sector_name] = {
                        'symbol': sector_symbol,
                        'last_price': last_price,
                        'change_pct': change_pct,
                        'direction': direction,
                        'open': quote.get('ohlc', {}).get('open', 0),
                        'high': quote.get('ohlc', {}).get('high', 0),
                        'low': quote.get('ohlc', {}).get('low', 0),
                        'volume': quote.get('volume', 0)
                    }
            
            # Print summary
            if sector_data:
                bullish_sectors = [(s, d['change_pct']) for s, d in sector_data.items() if d['direction'] == 'bullish']
                bearish_sectors = [(s, d['change_pct']) for s, d in sector_data.items() if d['direction'] == 'bearish']
                
                print(f"✅ Loaded data for {len(sector_data)} sectors")
                
                if bullish_sectors:
                    print(f"   🟢 Bullish sectors ({len(bullish_sectors)}):")
                    for sector, change in sorted(bullish_sectors, key=lambda x: x[1], reverse=True)[:5]:
                        print(f"      • {sector}: {change:+.2f}%")
                
                if bearish_sectors:
                    print(f"   🔴 Bearish sectors ({len(bearish_sectors)}):")
                    for sector, change in sorted(bearish_sectors, key=lambda x: x[1])[:5]:
                        print(f"      • {sector}: {change:+.2f}%")
            
            self.sector_data = sector_data
            return sector_data
            
        except Exception as e:
            print(f"❌ Error fetching sector data: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def is_sector_aligned(self, stock_symbol: str, stock_direction: str) -> tuple:
        """
        Check if stock's sector is aligned with the stock's direction.
        
        RULES:
        1. If stock is bullish and sector is bullish/neutral (>=0%) → PASS ✅
        2. If stock is bearish and sector is bearish/neutral (<=0%) → PASS ✅
        3. If stock is bullish but sector is bearish (<0%) → FAIL ❌
        4. If stock is bearish but sector is bullish (>0%) → FAIL ❌
        
        Returns:
            tuple: (is_aligned: bool, info_dict: dict)
        """
        sector = self.get_stock_sector(stock_symbol)
        
        if not sector:
            # If no sector mapping found, allow the trade (don't filter)
            return True, {'aligned': True, 'reason': 'No sector mapping', 'sector': None}
        
        if not self.sector_data or sector not in self.sector_data:
            # If sector data not available, allow the trade
            return True, {'aligned': True, 'reason': 'Sector data unavailable', 'sector': sector}
        
        sector_info = self.sector_data[sector]
        sector_change = sector_info['change_pct']
        sector_direction = sector_info['direction']
        
        # Alignment logic
        aligned = False
        
        if stock_direction == 'bullish':
            # Bullish stock needs sector to be >= 0% (bullish or neutral)
            aligned = (sector_change >= 0)
        elif stock_direction == 'bearish':
            # Bearish stock needs sector to be <= 0% (bearish or neutral)
            aligned = (sector_change <= 0)
        
        return aligned, {
            'aligned': aligned,
            'sector': sector,
            'sector_symbol': sector_info['symbol'],
            'sector_change': sector_change,
            'sector_direction': sector_direction,
            'stock_direction': stock_direction,
            'reason': f"Sector {sector} at {sector_change:+.2f}% ({sector_direction}), Stock is {stock_direction}"
        }
    
    def print_mapping_summary(self):
        """Print a summary of all sector mappings"""
        summary = self.get_sector_summary()
        print("\n" + "=" * 60)
        print("SECTOR MAPPING SUMMARY")
        print("=" * 60)
        
        total = 0
        for sector, count in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            index_symbol = self.sector_indices.get(sector, 'N/A')
            print(f"  {sector:15} : {count:3} stocks → {index_symbol}")
            total += count
        
        print("-" * 60)
        print(f"  {'TOTAL':15} : {total:3} stocks")
        print("=" * 60)


# ==================== TEST FUNCTION ====================
def test_sector_mapper():
    """Test the sector mapper with the new ticker list"""
    
    # Load tickers from file
    tickers = []
    ticker_str = """NSE:BLUESTARCO,NSE:VOLTAS,NSE:HDFCAMC,NSE:CHOLAFIN,NSE:NUVAMA,NSE:HCLTECH,NSE:SAIL,NSE:VBL,NSE:CANBK,NSE:HFCL,NSE:LTIM,NSE:HINDZINC,NSE:HINDALCO,NSE:COFORGE,NSE:SYNGENE,NSE:DALBHARAT,NSE:360ONE,NSE:NMDC,NSE:NATIONALUM,NSE:AUBANK,NSE:JSWSTEEL,NSE:KOTAKBANK,NSE:DIXON,NSE:ICICIBANK,NSE:SHREECEM,NSE:MARICO,NSE:DRREDDY,NSE:UNIONBANK,NSE:SUNPHARMA,NSE:GODREJCP,NSE:CROMPTON,NSE:TCS,NSE:ADANIPORTS,NSE:AXISBANK,NSE:BSE,NSE:COALINDIA,NSE:MPHASIS,NSE:PAGEIND,NSE:LTF,NSE:ITC,NSE:GRASIM,NSE:MFSL,NSE:WIPRO,NSE:ICICIGI,NSE:BHEL,NSE:BHARTIARTL,NSE:DABUR,NSE:SBIN,NSE:TITAN,NSE:ULTRACEMCO,NSE:LUPIN,NSE:TATASTEEL,NSE:ONGC,NSE:VEDL,NSE:TECHM,NSE:NTPC,NSE:ADANIENT,NSE:ETERNAL,NSE:INDIANB,NSE:PIDILITIND,NSE:M&M,NSE:RBLBANK,NSE:MARUTI,NSE:IOC,NSE:NAUKRI,NSE:LICI,NSE:CUMMINSIND,NSE:HEROMOTOCO,NSE:HDFCBANK,NSE:CONCOR,NSE:ALKEM,NSE:BOSCHLTD,NSE:PERSISTENT,NSE:BANKINDIA,NSE:HINDUNILVR,NSE:RECLTD,NSE:ZYDUSLIFE,NSE:JINDALSTEL,NSE:CDSL,NSE:SBILIFE,NSE:BPCL,NSE:AMBUJACEM,NSE:IIFL,NSE:INFY,NSE:ICICIPRULI,NSE:INDIGO,NSE:PNB,NSE:CAMS,NSE:BAJFINANCE,NSE:TRENT,NSE:SUPREMEIND,NSE:LICHSGFIN,NSE:MUTHOOTFIN,NSE:KFINTECH,NSE:BAJAJFINSV,NSE:NESTLEIND,NSE:DELHIVERY,NSE:JUBLFOOD,NSE:FEDERALBNK,NSE:GMRAIRPORT,NSE:UPL,NSE:ADANIGREEN,NSE:COLPAL,NSE:OBEROIRLTY,NSE:BRITANNIA,NSE:LT,NSE:IDFCFIRSTB,NSE:TATACONSUM,NSE:HAL,NSE:SAMMAANCAP,NSE:PFC,NSE:TORNTPHARM,NSE:UNITDSPR,NSE:PIIND,NSE:HAVELLS,NSE:ASTRAL,NSE:ASHOKLEY,NSE:IEX,NSE:EXIDEIND,NSE:INDUSINDBK,NSE:SOLARINDS,NSE:YESBANK,NSE:CIPLA,NSE:ADANIENSOL,NSE:SIEMENS,NSE:HINDPETRO,NSE:HDFCLIFE,NSE:INDHOTEL,NSE:ABCAPITAL,NSE:OIL,NSE:INDUSTOWER,NSE:SRF,NSE:AUROPHARMA,NSE:GAIL,NSE:JSWENERGY,NSE:MCX,NSE:RELIANCE,NSE:IREDA,NSE:APLAPOLLO,NSE:APOLLOHOSP,NSE:BANKBARODA,NSE:MANKIND,NSE:CYIENT,NSE:AMBER,NSE:ASIANPAINT,NSE:CGPOWER,NSE:TATAPOWER,NSE:PRESTIGE,NSE:IRCTC,NSE:DIVISLAB,NSE:EICHERMOT,NSE:SUZLON,NSE:ABB,NSE:ANGELONE,NSE:JIOFIN,NSE:BIOCON,NSE:TITAGARH,NSE:PATANJALI,NSE:DMART,NSE:TATATECH,NSE:DLF,NSE:GLENMARK,NSE:NCC,NSE:PHOENIXLTD,NSE:PETRONET,NSE:MANAPPURAM,NSE:LODHA,NSE:TMPV,NSE:NYKAA,NSE:TVSMOTOR,NSE:NHPC,NSE:OFSS,NSE:HUDCO,NSE:TORNTPOWER,NSE:POWERGRID,NSE:SONACOMS,NSE:MAZDOCK,NSE:TIINDIA,NSE:INOXWIND,NSE:POWERINDIA,NSE:GODREJPROP,NSE:BDL,NSE:BHARATFORG,NSE:BEL,NSE:MAXHEALTH,NSE:SBICARD,NSE:PGEL,NSE:FORTIS,NSE:IRFC,NSE:PPLPHARMA,NSE:LAURUSLABS,NSE:KALYANKJIL,NSE:POLICYBZR,NSE:MOTHERSON,NSE:BANDHANBNK,NSE:UNOMINDA,NSE:KAYNES,NSE:PNBHOUSING,NSE:SHRIRAMFIN,NSE:PAYTM,NSE:RVNL,NSE:POLYCAB,NSE:KEI,NSE:NBCC,NSE:KPITTECH,NSE:IDEA,NSE:TATAELXSI,NSE:NIFTY"""
    
    tickers = [t.strip() for t in ticker_str.split(',')]
    
    # Create mapper
    mapper = SectorMapper()
    
    # Print summary
    mapper.print_mapping_summary()
    
    # Validate mapping
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    
    validation = mapper.validate_mapping(tickers)
    
    print(f"Total tickers in file: {validation['total_fo_stocks']}")
    print(f"Total mapped stocks: {validation['total_mapped_stocks']}")
    print(f"Mapping complete: {'✅ YES' if validation['mapping_complete'] else '❌ NO'}")
    
    if validation['missing_in_mapping']:
        print(f"\n⚠️ MISSING from mapping ({len(validation['missing_in_mapping'])}):")
        for symbol in sorted(validation['missing_in_mapping']):
            print(f"   - {symbol}")
    
    print("\n" + "=" * 60)
    
    return mapper, validation


if __name__ == "__main__":
    mapper, validation = test_sector_mapper()


# ==================== OPTIONS DATA LOADER ====================
class OptionsDataLoader:
    """Load and compare night vs realtime API options data for OI changes"""
    
    def __init__(self, scanner=None):
        self.data_dir = Path("zerodha_options_data")
        self.night_data_file = self.data_dir / "night_options_data.json"
        self.live_data_file_1 = self.data_dir / "live_options_data_1.json"
        self.live_data_file_2 = self.data_dir / "live_options_data_2.json"
        self.night_data = {}
        self.live_data = {}
        self.oi_changes = {}
        self.scanner = scanner  # Store scanner reference for API access
        self.realtime_oi_cache = {}  # Cache for realtime OI data per scan
        self.current_option_data = {}  # Initialize current option data cache
        
        # NEW: Add OI accumulation tracker
        self.oi_accumulation_tracker = OIAccumulationTracker()
        
    def load_data(self):
        """Load night data only (live data not used for comparison)"""
        # Load night data
        if self.night_data_file.exists():
            try:
                with open(self.night_data_file, 'r') as f:
                    self.night_data = json.load(f)
                logger.info(f"Loaded night options data")
            except Exception as e:
                logger.error(f"Error loading night data: {e}")
        
        # Note: We're not loading live data since we'll use realtime API data
    
    def clear_realtime_cache(self):
        """Clear the realtime OI cache - call this at the start of each scan"""
        # IMPORTANT: We now only clear the current cache, NOT the accumulation history
        self.realtime_oi_cache.clear()
        self.current_option_data = {}  # Initialize properly
        # Do NOT clear oi_accumulation_tracker here - we need to maintain history
        
    def get_option_oi_change(self, symbol: str, strike: float, option_type: str, expiry: str) -> Dict:
        """Get OI change comparing NIGHT data vs REALTIME API data"""
        try:
            # Ensure strike is float for consistent comparison
            strike = float(strike)
            
            # Clean symbol (remove exchange prefix if needed)
            clean_symbol = symbol.replace('NSE:', '')
            
            # Format expiry consistently
            expiry_str = expiry[:10] if expiry else ''
            
            # Get NIGHT OI data
            night_oi = None
            night_options = self.night_data.get('options_data', {})
            night_symbol_data = night_options.get(symbol) or night_options.get(f'NSE:{clean_symbol}')
            
            if night_symbol_data and expiry_str:
                # Look for matching expiry in night data
                for night_exp_key, night_expiry_data in night_symbol_data.get('expiries', {}).items():
                    # Match by date portion only (first 10 chars: YYYY-MM-DD)
                    if night_exp_key[:10] == expiry_str:
                        night_options_list = night_expiry_data.get(f'{option_type.lower()}_options', [])
                        
                        for opt in night_options_list:
                            if float(opt['strike']) == strike:
                                night_oi = opt.get('oi', 0)
                                break
                        break
            
            # Get current OI from the realtime option data cache
            # CRITICAL: Use same cache key format as written in has_significant_oi_increase
            cache_key = f"{symbol}_{strike}_{option_type}_{expiry_str}"
            
            if hasattr(self, 'current_option_data') and cache_key in self.current_option_data:
                current_oi = self.current_option_data[cache_key]
                
                # NEW: Update accumulation tracker
                self.oi_accumulation_tracker.update_oi(symbol, strike, option_type, expiry_str, current_oi)
                
                if night_oi is not None:
                    oi_change = current_oi - night_oi
                    oi_change_pct = ((current_oi - night_oi) / night_oi * 100) if night_oi > 0 else (100 if current_oi > 0 else 0)
                    
                    return {
                        'night_oi': night_oi,
                        'live_oi': current_oi,
                        'oi_change': oi_change,
                        'oi_change_pct': oi_change_pct,
                        'has_data': True,
                        'status': 'increased' if oi_change_pct > 0 else 'decreased'
                    }
                else:
                    # No night data for this strike/expiry combo
                    return {
                        'night_oi': 0,
                        'live_oi': current_oi,
                        'oi_change': current_oi,
                        'oi_change_pct': 100.0 if current_oi > 0 else 0,
                        'has_data': True,
                        'is_new': True,
                        'no_night_data': True,
                        'status': 'new',
                        'current_oi': current_oi
                    }
            
            # No data in cache
            return {}
                
        except Exception as e:
            logger.error(f"Error getting OI change for {symbol} {strike} {option_type}: {e}")
            return {}
    
    def has_significant_oi_increase(self, symbol: str, options: List[Dict], min_oi_change_pct: float = 1.0, 
                                   direction: str = None, check_accumulation: bool = True) -> Tuple[bool, Dict]:
        """Check if symbol has OI increase AND accumulation if enabled"""
        # Initialize current option data cache if not exists
        if not hasattr(self, 'current_option_data'):
            self.current_option_data = {}
        
        # Store current OI data for later use in alerts
        for opt in options:
            # Include expiry in cache key to avoid collisions
            expiry_str = opt.get('expiry', '')[:10] if opt.get('expiry') else ''
            cache_key = f"{symbol}_{opt['strike']}_{opt['type']}_{expiry_str}"
            current_oi = opt.get('open_interest', 0) or opt.get('oi', 0)
            self.current_option_data[cache_key] = current_oi
            
            # Update accumulation tracker
            self.oi_accumulation_tracker.update_oi(symbol, opt['strike'], opt['type'], expiry_str, current_oi)
        
        # Check for significant increases from night
        has_night_increase = False
        for opt in options:
            oi_change_data = self.get_option_oi_change(
                symbol,
                opt['strike'],
                opt['type'],
                opt.get('expiry', '')  # Pass expiry for proper matching
            )
            
            if oi_change_data.get('has_data'):
                oi_change_pct = oi_change_data.get('oi_change_pct', 0)
                # Only check for positive changes (increases)
                if oi_change_pct >= min_oi_change_pct:
                    has_night_increase = True
                    break
        
        # NEW: Check for accumulation if direction is provided
        accumulation_info = {'accumulating': False, 'reason': 'No accumulation check'}
        
        if check_accumulation and direction:
            is_accumulating, accumulation_details = self.oi_accumulation_tracker.has_accumulating_oi(
                symbol, direction, min_scans=3, min_accumulating_strikes=2
            )
            
            accumulation_info = accumulation_details
            
            if has_night_increase and not is_accumulating:
                logger.info(f"⚠️ {symbol} has OI increase from night but NO accumulation - could be stale")
                return False, {
                    'night_increase': True,
                    'accumulation': False,
                    'reason': f"No sustained accumulation (only {accumulation_details['num_accumulating']} strikes accumulating)",
                    'details': accumulation_details
                }
            
            if is_accumulating:
                if accumulation_details['is_accelerating']:
                    logger.info(f"🚀 {symbol} has ACCELERATING OI accumulation! Velocity: {accumulation_details['velocity']:.1f}%/scan")
                else:
                    logger.info(f"✅ {symbol} has steady OI accumulation across {accumulation_details['num_accumulating']} strikes")
        
        # Return combined result
        if has_night_increase:
            if check_accumulation and direction:
                # Both night increase AND accumulation required
                return accumulation_info['accumulating'], {
                    'night_increase': True,
                    'accumulation': accumulation_info['accumulating'],
                    'details': accumulation_info
                }
            else:
                # Just night increase (backward compatibility)
                return True, {'night_increase': True, 'accumulation': 'not_checked'}
        else:
            logger.info(f"❌ {symbol} filtered out - no OI increases >= {min_oi_change_pct}%")
            return False, {'night_increase': False}

# ==================== STOP LOSS CALCULATOR ====================
class StopLossCalculator:
    """Calculate stop loss based on ATR27 and golden ratio"""
    
    def __init__(self, client):
        self.client = client
        self.indian_tz = pytz.timezone('Asia/Kolkata')
        self.golden_ratio = 1.618
        
    def calculate_5min_9ema_sl(self, symbol: str, direction: str, current_price: float, atr27: float = None) -> Dict:
        """Calculate stop loss based on ATR27 * 0.272 / golden_ratio"""
        try:
            # If ATR27 not provided or zero, fallback
            if atr27 is None or atr27 == 0:
                return self._get_percentage_based_sl(current_price, direction)
            
            # Calculate stop loss using ATR27 * 0.272 / golden_ratio
            sl_buffer = (atr27 * 0.272) / self.golden_ratio
            
            if direction == 'bullish':
                # For long positions: SL = Current Price - buffer
                sl_price = current_price - sl_buffer
            else:
                # For short positions: SL = Current Price + buffer
                sl_price = current_price + sl_buffer
            
            sl_distance = abs(current_price - sl_price)
            sl_percentage = (sl_distance / current_price) * 100
            
            return {
                'sl_price': round(sl_price, 2),
                'sl_text': f"₹{sl_price:.2f}",
                'sl_distance': round(sl_distance, 2),
                'sl_percentage': round(sl_percentage, 2),
                'ema_value': 0,
                'method': 'atr_golden_ratio'
            }
            
        except Exception as e:
            logger.error(f"Error calculating ATR-based SL for {symbol}: {e}")
            return self._get_percentage_based_sl(current_price, direction)
    
    def _get_percentage_based_sl(self, current_price: float, direction: str) -> Dict:
        """Fallback percentage-based stop loss"""
        sl_percentage = 0.75  # 0.75% stop loss
        
        if direction == 'bullish':
            sl_price = current_price * (1 - sl_percentage / 100)
        else:
            sl_price = current_price * (1 + sl_percentage / 100)
        
        return {
            'sl_price': round(sl_price, 2),
            'sl_text': f"₹{sl_price:.2f}",
            'sl_distance': round(abs(current_price - sl_price), 2),
            'sl_percentage': sl_percentage,
            'ema_value': 0,
            'method': 'percentage'
        }

# ==================== MONEY FLOW CALCULATOR ====================
class MoneyFlowCalculator:
    """Calculate sophisticated money flow for options with hedge detection"""
    
    def __init__(self):
        # Context-aware thresholds (not magic numbers)
        self.NEAR_MONEY_THRESHOLD = 0.03  # 3% for near-the-money classification
        self.HIGH_ACTIVITY_PERCENTILE = 75  # Top 25% volume/OI ratio
        self.RECENT_ACTIVITY_WINDOW = 30  # Minutes for recent activity
        
    def calculate_option_money_flow(self, option: Dict, spot_price: float = None) -> Dict:
        """Calculate money flow for a single option with position type analysis"""
        try:
            # Get the mid price (average of bid and ask) or last price
            bid = option.get('bid', 0)
            ask = option.get('ask', 0)
            last_price = option.get('last_price', 0)
            
            # Use mid price if available, otherwise last price
            if bid > 0 and ask > 0:
                contract_price = (bid + ask) / 2
            elif last_price > 0:
                contract_price = last_price
            else:
                contract_price = 0
            
            # Get volume and lot size
            volume = option.get('volume', 0)
            lot_size = option.get('lot_size', 1)
            oi = option.get('open_interest', 0)
            
            # CRITICAL FIX: In Zerodha API, volume is already in shares/units, NOT contracts
            # So money flow = volume * premium_per_share (NO lot_size multiplication)
            money_flow = volume * contract_price
            
            # For OI value, we need to multiply by lot_size since OI is in contracts
            oi_value = oi * contract_price * lot_size
            
            # Calculate volume/OI ratio (fresh activity indicator)
            # Since volume is in shares and OI is in contracts, we need to adjust
            volume_in_contracts = volume / lot_size if lot_size > 0 else 0
            vol_oi_ratio = volume_in_contracts / oi if oi > 0 else float('inf')
            
            # Log for debugging
            logger.debug(f"Option {option.get('symbol', 'Unknown')}: "
                        f"Volume={volume} shares, "
                        f"Volume in contracts={volume_in_contracts:.0f}, "
                        f"OI={oi} contracts, "
                        f"Premium=₹{contract_price:.2f}, "
                        f"Money Flow=₹{money_flow:,.0f} ({money_flow/10_000_000:.2f} Cr)")
            
            # Analyze position characteristics
            position_analysis = self._analyze_position_type(
                option, contract_price, vol_oi_ratio, spot_price
            )
            
            return {
                'money_flow': money_flow,
                'oi_value': oi_value,
                'contract_price': contract_price,
                'volume': volume,
                'volume_in_contracts': int(volume_in_contracts),
                'oi': oi,
                'lot_size': lot_size,
                'vol_oi_ratio': vol_oi_ratio,
                'position_type': position_analysis['type'],
                'confidence': position_analysis['confidence'],
                'characteristics': position_analysis['characteristics'],
                'strike': option.get('strike'),
                'type': option.get('type'),
                'expiry': option.get('expiry'),
                'moneyness': option.get('moneyness', 'OTM'),
                'score': option.get('score', 0)
            }
        except Exception as e:
            logger.error(f"Error calculating money flow: {e}")
            return {
                'money_flow': 0,
                'oi_value': 0,
                'contract_price': 0,
                'volume': 0,
                'volume_in_contracts': 0,
                'oi': 0,
                'lot_size': 1,
                'vol_oi_ratio': 0,
                'position_type': 'UNKNOWN',
                'confidence': 0,
                'characteristics': []
            }
    
    def _analyze_position_type(self, option: Dict, contract_price: float, 
                            vol_oi_ratio: float, spot_price: float = None) -> Dict:
        """Accurately analyze if position is likely directional or hedge"""
        characteristics = []
        directional_score = 0
        hedge_score = 0
        
        # 1. MONEYNESS ANALYSIS - FIXED
        if spot_price and option.get('strike'):
            strike = option['strike']
            moneyness_ratio = (strike - spot_price) / spot_price
            
            # For CALLS
            if option.get('type') == 'CE':
                if -0.01 <= moneyness_ratio <= 0.01:  # ATM (±1%)
                    characteristics.append('ATM - Prime directional zone')
                    directional_score += 0.5  # Strong directional
                    hedge_score += 0.1
                    
                elif 0.01 < moneyness_ratio <= 0.05:  # 1-5% OTM
                    characteristics.append('Near OTM - Common directional target')
                    directional_score += 0.4
                    hedge_score += 0.1
                    
                elif -0.03 <= moneyness_ratio < -0.01:  # 1-3% ITM
                    characteristics.append('Slight ITM - Momentum trade')
                    directional_score += 0.3
                    hedge_score += 0.2
                    
                elif moneyness_ratio < -0.05:  # Deep ITM (>5%)
                    characteristics.append('Deep ITM - Likely hedge/synthetic')
                    directional_score += 0.1
                    hedge_score += 0.5  # Usually hedges
                    
                elif 0.05 < moneyness_ratio <= 0.10:  # 5-10% OTM
                    characteristics.append('Moderate OTM - Speculative')
                    directional_score += 0.25
                    hedge_score += 0.25
                    
                else:  # >10% OTM
                    characteristics.append('Far OTM - Lottery/hedge')
                    directional_score += 0.1
                    hedge_score += 0.4
            
            # For PUTS
            else:
                if -0.01 <= moneyness_ratio <= 0.01:  # ATM
                    characteristics.append('ATM - Prime directional zone')
                    directional_score += 0.5
                    hedge_score += 0.1
                    
                elif -0.05 <= moneyness_ratio < -0.01:  # 1-5% OTM
                    characteristics.append('Near OTM - Common directional target')
                    directional_score += 0.4
                    hedge_score += 0.1
                    
                elif 0.01 < moneyness_ratio <= 0.03:  # 1-3% ITM
                    characteristics.append('Slight ITM - Momentum trade')
                    directional_score += 0.3
                    hedge_score += 0.2
                    
                elif moneyness_ratio > 0.05:  # Deep ITM (>5%)
                    characteristics.append('Deep ITM - Likely hedge/synthetic')
                    directional_score += 0.1
                    hedge_score += 0.5
                    
                elif -0.10 <= moneyness_ratio < -0.05:  # 5-10% OTM
                    characteristics.append('Moderate OTM - Protection/speculation')
                    directional_score += 0.2
                    hedge_score += 0.3  # Puts more likely protective
                    
                else:  # >10% OTM
                    characteristics.append('Far OTM - Tail hedge')
                    directional_score += 0.05
                    hedge_score += 0.5  # Far OTM puts usually hedges
        
        # 2. VOLUME/OI RATIO - ADJUSTED THRESHOLDS
        if vol_oi_ratio > 0.25:  # Lowered from 0.5
            characteristics.append(f'High activity ({vol_oi_ratio:.2f}) - Fresh directional')
            directional_score += 0.25
        elif vol_oi_ratio > 0.10:  # 10-25% is normal directional
            characteristics.append(f'Normal activity ({vol_oi_ratio:.2f})')
            directional_score += 0.15
        elif vol_oi_ratio < 0.05:  # Very low activity
            characteristics.append('Low activity - Likely old hedge')
            hedge_score += 0.25
        
        # 3. PREMIUM ANALYSIS - RELATIVE TO SPOT
        if spot_price and contract_price > 0:
            premium_pct = (contract_price / spot_price) * 100
            
            if premium_pct > 3:  # Expensive (>3% of spot)
                characteristics.append('High premium - Directional/protective')
                directional_score += 0.15
            elif premium_pct > 1:  # Normal (1-3%)
                characteristics.append('Normal premium')
                directional_score += 0.1
            elif premium_pct < 0.5:  # Very cheap (<0.5%)
                characteristics.append('Cheap premium - Lottery/tail hedge')
                hedge_score += 0.2
        
        # 4. VOLUME THRESHOLD - ABSOLUTE
        volume = option.get('volume', 0)
        if volume > 10000:
            characteristics.append('High volume - Active interest')
            directional_score += 0.1
        elif volume < 100:
            characteristics.append('Low volume - Possibly stale')
            hedge_score += 0.1
        
        # 5. SPREAD ANALYSIS
        if option.get('bid', 0) > 0 and option.get('ask', 0) > 0:
            spread_pct = (option['ask'] - option['bid']) / option['ask']
            if spread_pct < 0.03:  # Very tight
                characteristics.append('Very tight spread - Active trading')
                directional_score += 0.2
            elif spread_pct < 0.08:  # Normal
                directional_score += 0.1
            elif spread_pct > 0.15:  # Wide
                characteristics.append('Wide spread - Low interest')
                hedge_score += 0.15
        
        # FINAL CLASSIFICATION
        total_score = directional_score + hedge_score
        if total_score > 0:
            directional_probability = directional_score / total_score
        else:
            directional_probability = 0.5
        
        # Adjusted thresholds
        if directional_probability > 0.60:  # Lowered from 0.65
            position_type = 'DIRECTIONAL'
        elif directional_probability < 0.40:  # Raised from 0.35
            position_type = 'HEDGE/PROTECTIVE'
        else:
            position_type = 'MIXED/UNCLEAR'
        
        return {
            'type': position_type,
            'confidence': abs(directional_probability - 0.5) * 2,
            'directional_probability': directional_probability,
            'characteristics': characteristics
        }
    
    def analyze_money_flow(self, options: List[Dict], spot_price: float = None, 
                          breakout_time: str = None) -> Dict:
        """Analyze money flow with advanced position detection"""
        try:
            # Initialize counters
            ce_money_flow = 0
            pe_money_flow = 0
            ce_directional_flow = 0
            pe_directional_flow = 0
            ce_hedge_flow = 0
            pe_hedge_flow = 0
            ce_oi_value = 0
            pe_oi_value = 0
            
            ce_options_flow = []
            pe_options_flow = []
            
            # Get all vol/OI ratios for percentile calculation
            all_vol_oi_ratios = []
            for opt in options:
                if opt.get('oi', 0) > 0 and opt.get('lot_size', 1) > 0:
                    # Convert volume to contracts for ratio calculation
                    volume_in_contracts = opt.get('volume', 0) / opt.get('lot_size', 1)
                    all_vol_oi_ratios.append(volume_in_contracts / opt['oi'])
            
            # Calculate percentile thresholds
            if all_vol_oi_ratios:
                high_activity_threshold = np.percentile(all_vol_oi_ratios, self.HIGH_ACTIVITY_PERCENTILE)
            else:
                high_activity_threshold = 0.3
            
            # Analyze each option
            for opt in options:
                flow_data = self.calculate_option_money_flow(opt, spot_price)
                
                # Check if recent activity (if breakout_time provided)
                flow_data['is_recent'] = self._is_recent_activity(breakout_time)
                flow_data['is_high_activity'] = flow_data['vol_oi_ratio'] > high_activity_threshold
                
                # Accumulate flows
                if opt['type'] == 'CE':
                    ce_money_flow += flow_data['money_flow']
                    ce_oi_value += flow_data['oi_value']
                    ce_options_flow.append(flow_data)
                    
                    if flow_data['position_type'] == 'DIRECTIONAL':
                        ce_directional_flow += flow_data['money_flow']
                    elif flow_data['position_type'] == 'HEDGE/PROTECTIVE':
                        ce_hedge_flow += flow_data['money_flow']
                else:
                    pe_money_flow += flow_data['money_flow']
                    pe_oi_value += flow_data['oi_value']
                    pe_options_flow.append(flow_data)
                    
                    if flow_data['position_type'] == 'DIRECTIONAL':
                        pe_directional_flow += flow_data['money_flow']
                    elif flow_data['position_type'] == 'HEDGE/PROTECTIVE':
                        pe_hedge_flow += flow_data['money_flow']
            
            # Sort by money flow
            ce_options_flow.sort(key=lambda x: x['money_flow'], reverse=True)
            pe_options_flow.sort(key=lambda x: x['money_flow'], reverse=True)
            
            # Calculate directional flow ratio (more accurate than total flow)
            directional_flow_ratio = (ce_directional_flow / pe_directional_flow 
                                    if pe_directional_flow > 0 else float('inf'))
            
            # Calculate net flows
            net_flow = ce_money_flow - pe_money_flow
            net_directional_flow = ce_directional_flow - pe_directional_flow
            
            # Overall flow ratio
            flow_ratio = ce_money_flow / pe_money_flow if pe_money_flow > 0 else float('inf')
            
            # Determine sentiment based on DIRECTIONAL flow
            if directional_flow_ratio > 2.0:
                sentiment = "STRONGLY BULLISH"
                sentiment_emoji = "🟢🟢"
            elif directional_flow_ratio > 1.3:
                sentiment = "BULLISH"
                sentiment_emoji = "🟢"
            elif directional_flow_ratio < 0.5:
                sentiment = "STRONGLY BEARISH"
                sentiment_emoji = "🔴🔴"
            elif directional_flow_ratio < 0.77:
                sentiment = "BEARISH"
                sentiment_emoji = "🔴"
            else:
                sentiment = "NEUTRAL"
                sentiment_emoji = "🟡"
            
            # Add hedge warning if significant hedge flow detected
            total_hedge_flow = ce_hedge_flow + pe_hedge_flow
            total_directional_flow = ce_directional_flow + pe_directional_flow
            
            if total_hedge_flow > total_directional_flow * 0.5:
                sentiment += " (High Hedge Activity)"
                sentiment_emoji += "⚠️"
            
            # Get top directional options only
            top_ce_directional = [opt for opt in ce_options_flow 
                                if opt['position_type'] == 'DIRECTIONAL'][:3]
            top_pe_directional = [opt for opt in pe_options_flow 
                                if opt['position_type'] == 'DIRECTIONAL'][:3]
            
            # Calculate overall confidence based on directional flows
            if total_directional_flow > 0:
                # For neutral flow, reduce confidence
                if sentiment == "NEUTRAL":
                    confidence = 0.5 * abs(directional_flow_ratio - 1.0)
                else:
                    # FIXED: Symmetric confidence calculation for both bullish and bearish
                    if directional_flow_ratio > 1:
                        # Bullish: how far above 1.0
                        confidence = (directional_flow_ratio - 1.0) / directional_flow_ratio
                    else:
                        # Bearish: how far below 1.0 (inverted)
                        confidence = (1.0 - directional_flow_ratio) / 1.0
                confidence = min(confidence, 1.0)
            else:
                confidence = 0
            
            logger.info(f"Money Flow Summary: CE=₹{ce_money_flow/10_000_000:.1f}Cr, "
                       f"PE=₹{pe_money_flow/10_000_000:.1f}Cr, "
                       f"Directional Ratio={directional_flow_ratio:.2f}, "
                       f"Sentiment={sentiment}")
            
            return {
                'ce_money_flow': ce_money_flow,
                'pe_money_flow': pe_money_flow,
                'ce_directional_flow': ce_directional_flow,
                'pe_directional_flow': pe_directional_flow,
                'ce_hedge_flow': ce_hedge_flow,
                'pe_hedge_flow': pe_hedge_flow,
                'ce_oi_value': ce_oi_value,
                'pe_oi_value': pe_oi_value,
                'net_flow': net_flow,
                'net_directional_flow': net_directional_flow,
                'flow_ratio': flow_ratio,
                'directional_flow_ratio': directional_flow_ratio,
                'sentiment': sentiment,
                'sentiment_emoji': sentiment_emoji,
                'ce_options': ce_options_flow,
                'pe_options': pe_options_flow,
                'top_ce_flows': ce_options_flow[:3],
                'top_pe_flows': pe_options_flow[:3],
                'top_ce_directional': top_ce_directional,
                'top_pe_directional': top_pe_directional,
                'hedge_percentage': (total_hedge_flow / (total_hedge_flow + total_directional_flow) * 100 
                                   if (total_hedge_flow + total_directional_flow) > 0 else 0),
                'confidence': confidence,
                'flow_direction': 'bullish' if sentiment in ['STRONGLY BULLISH', 'BULLISH'] else ('bearish' if sentiment in ['STRONGLY BEARISH', 'BEARISH'] else 'neutral')
            }
        except Exception as e:
            logger.error(f"Error analyzing money flow: {e}")
            return self._empty_flow_analysis()
    
    def _is_recent_activity(self, breakout_time: str) -> bool:
        """Check if activity is recent relative to breakout"""
        if not breakout_time:
            return True  # Assume recent if no breakout time
        
        try:
            # Parse breakout time (format: HH:MM)
            now = datetime.now()
            breakout_hour, breakout_min = map(int, breakout_time.split(':'))
            breakout_datetime = now.replace(hour=breakout_hour, minute=breakout_min)
            
            # Check if within recent window
            time_since_breakout = (now - breakout_datetime).total_seconds() / 60
            return 0 <= time_since_breakout <= self.RECENT_ACTIVITY_WINDOW
        except:
            return True
    
    def _empty_flow_analysis(self) -> Dict:
        """Return empty flow analysis structure"""
        return {
            'ce_money_flow': 0,
            'pe_money_flow': 0,
            'ce_directional_flow': 0,
            'pe_directional_flow': 0,
            'ce_hedge_flow': 0,
            'pe_hedge_flow': 0,
            'ce_oi_value': 0,
            'pe_oi_value': 0,
            'net_flow': 0,
            'net_directional_flow': 0,
            'flow_ratio': 1.0,
            'directional_flow_ratio': 1.0,
            'sentiment': "UNKNOWN",
            'sentiment_emoji': "❓",
            'ce_options': [],
            'pe_options': [],
            'top_ce_flows': [],
            'top_pe_flows': [],
            'top_ce_directional': [],
            'top_pe_directional': [],
            'hedge_percentage': 0,
            'confidence': 0,
            'flow_direction': 'neutral'
        }


# ==================== OI ACCUMULATION TRACKER ====================
class OIAccumulationTracker:
    """Track OI accumulation across scans to confirm genuine interest"""
    
    def __init__(self):
        self.oi_history = {}  # {symbol_strike_type_expiry: [(timestamp, oi), ...]}
        self.last_scan_oi = {}  # Store last scan's OI for velocity calculation
        self.accumulation_scores = {}  # Track accumulation strength
        
    def update_oi(self, symbol: str, strike: float, option_type: str, expiry: str, current_oi: int):
        """Update OI history for a specific option"""
        # Create unique key including expiry
        expiry_str = expiry[:10] if expiry else ''
        key = f"{symbol}_{strike}_{option_type}_{expiry_str}"
        
        if key not in self.oi_history:
            self.oi_history[key] = []
        
        # Add current OI with timestamp
        self.oi_history[key].append({
            'timestamp': datetime.now(),
            'oi': current_oi
        })
        
        # Keep only last 10 scans (about 100 seconds of data at 10s intervals)
        if len(self.oi_history[key]) > 10:
            self.oi_history[key].pop(0)
            
    def calculate_oi_velocity(self, symbol: str, direction: str) -> float:
        """Calculate if OI accumulation is accelerating (velocity)"""
        option_type = 'CE' if direction == 'bullish' else 'PE'
        
        velocities = []
        
        for key in self.oi_history:
            if symbol in key and option_type in key:
                history = self.oi_history[key]
                
                if len(history) >= 4:  # Need at least 4 data points
                    # Calculate rate of change between consecutive scans
                    recent_changes = []
                    for i in range(1, len(history)):
                        if history[i-1]['oi'] > 0:
                            change_pct = ((history[i]['oi'] - history[i-1]['oi']) / history[i-1]['oi']) * 100
                            recent_changes.append(change_pct)
                    
                    if len(recent_changes) >= 3:
                        # Check if rate is accelerating (each change > previous)
                        accelerating = sum(1 for i in range(1, len(recent_changes)) 
                                         if recent_changes[i] > recent_changes[i-1])
                        
                        # Velocity score: how much is it accelerating
                        if accelerating >= len(recent_changes) - 1:
                            # Calculate average acceleration
                            avg_acceleration = sum(recent_changes[-3:]) / 3
                            velocities.append(avg_acceleration)
        
        # Return average velocity across all accumulating strikes
        return sum(velocities) / len(velocities) if velocities else 0
    
    def has_accumulating_oi(self, symbol: str, direction: str, min_scans: int = 3, 
                           min_accumulating_strikes: int = 2) -> Tuple[bool, Dict]:
        """Check if directional OI is accumulating consistently"""
        option_type = 'CE' if direction == 'bullish' else 'PE'
        
        accumulating_strikes = []
        total_strikes_checked = 0
        total_oi_increase = 0
        
        for key in self.oi_history:
            if symbol in key and option_type in key:
                history = self.oi_history[key]
                
                if len(history) >= min_scans:
                    # Get OI values from recent scans
                    recent_ois = [h['oi'] for h in history[-min_scans:]]
                    
                    # Count how many times OI increased
                    increases = sum(1 for i in range(1, len(recent_ois)) 
                                  if recent_ois[i] > recent_ois[i-1])
                    
                    # Check if consistently rising (at least 66% of the time)
                    if increases >= (len(recent_ois) - 1) * 0.5:
                        # Calculate total increase percentage
                        if recent_ois[0] > 0:
                            total_increase_pct = ((recent_ois[-1] - recent_ois[0]) / recent_ois[0]) * 100
                            
                            # Extract strike from key
                            strike = float(key.split('_')[1])
                            
                            accumulating_strikes.append({
                                'strike': strike,
                                'type': option_type,
                                'increase_pct': total_increase_pct,
                                'current_oi': recent_ois[-1],
                                'scans': len(recent_ois)
                            })
                            
                            total_oi_increase += total_increase_pct
                    
                    total_strikes_checked += 1
        
        # Calculate velocity
        velocity = self.calculate_oi_velocity(symbol, direction)
        
        # Check if we have enough accumulating strikes
        is_accumulating = len(accumulating_strikes) >= 2
        
        return is_accumulating, {
            'accumulating': is_accumulating,
            'accumulating_strikes': accumulating_strikes,
            'num_accumulating': len(accumulating_strikes),
            'total_strikes': total_strikes_checked,
            'avg_increase': total_oi_increase / len(accumulating_strikes) if accumulating_strikes else 0,
            'velocity': velocity,
            'is_accelerating': velocity > 1.0  # Accelerating if velocity > 1% per scan
        }

# ==================== ALERT CONFIGURATION ====================
class AlertConfig:
    """Alert system configuration"""
    
    def __init__(self):
        # Discord settings
        self.DISCORD_WEBHOOK = os.getenv('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/1389832310244773948/Z6JQCvYsRfDWwICfdaH7-uDJXzQBM9CIHzA4R4OQSS1G5nBh1OxiNXYJBPL8hzvtOZjD')
        
        # Telegram settings
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # Alert settings
        self.TOP_ALERTS = int(os.getenv('TOP_ALERTS', '10'))
        
        # Top 10 tracking
        self.current_top_10 = []  # Current top 10 list
        self.alert_count = 0  # Track number of alerts sent
        
        # ADDED: OI increase threshold
        self.MIN_OI_CHANGE_PCT = 1.0  # Minimum OI increase percentage for alerts
        
        # Score tracking and daily summary
        self.score_tracking = {}  # Track scores for each symbol
        self.daily_alert_summary = defaultdict(int)  # Track all alerts by symbol for the day
        self.score_increase_threshold = 1.0  # Minimum score increase to track
        
        # Cumulative count threshold for alerts
        self.MIN_CUMULATIVE_COUNT = 3  # Only send alerts for symbols that appear > 2 times
        
        # Track which tickers have been alerted today - SEPARATE FOR EACH PLATFORM
        self.discord_alerted_tickers = set()  # Discord alerted tickers
        self.telegram_alerted_tickers = set()  # Telegram alerted tickers
        self.daily_alerted_tickers = set()  # Combined for both (for backward compatibility)
        
        # Track filter reasons for each symbol
        self.filter_reasons = {}  # Track why symbols were filtered out
        
        # Flow confidence threshold
        self.MIN_FLOW_CONFIDENCE = 0.65  # 65% confidence threshold

# ==================== DISCORD ALERTS ====================
class DiscordAlerter:
    """Send alerts via Discord webhook"""
    
    def __init__(self, webhook_url: str, options_loader: OptionsDataLoader, sector_mapper=None):
        self.webhook_url = webhook_url
        self.options_loader = options_loader
        self.sector_mapper = sector_mapper  # Store sector mapper
        self.money_flow_calculator = MoneyFlowCalculator()
        self.stop_loss_calculator = None  # Will be set by AlertScanner
        
    def send_alert(self, breakouts: List[Dict], options: Dict, changes: Dict, alert_count: int, 
                min_oi_change_pct: float = 1.0, score_changes: Dict = None, 
                daily_summary: Dict = None, daily_alerted_tickers: set = None,
                filter_reasons: Dict = None) -> bool:
        """Send formatted alert to Discord with change summary, OI changes, score tracking, and sector alignment"""
        if not self.webhook_url:
            return False
            
        try:
            # Initialize filter_reasons if not provided
            if filter_reasons is None:
                filter_reasons = {}
            
            # ADDED: Filter breakouts by OI increase
            # ADDED: Filter breakouts by OI increase AND accumulation
            filtered_breakouts = []
            filtered_out = []

            for breakout in breakouts:
                symbol_options = options.get(breakout['symbol'], [])
                if symbol_options:
                    # NEW: Check both OI increase and accumulation
                    passes_oi, oi_info = self.options_loader.has_significant_oi_increase(
                        breakout['symbol'], 
                        symbol_options, 
                        min_oi_change_pct,
                        direction=breakout['direction'],  # Pass direction for accumulation check
                        check_accumulation=True
                    )
                    
                    if passes_oi:
                        # Store accumulation info for display
                        breakout['oi_accumulation'] = oi_info.get('details', {})
                        filtered_breakouts.append(breakout)
                    else:
                        if oi_info.get('night_increase') and not oi_info.get('accumulation'):
                            filtered_out.append(f"{breakout['symbol']} (no accum)")
                            filter_reasons[breakout['symbol']] = "no OI accum"
                        else:
                            filtered_out.append(breakout['symbol'])
                            filter_reasons[breakout['symbol']] = f"OI < {min_oi_change_pct}%"
                else:
                    filtered_out.append(breakout['symbol'])
                    filter_reasons[breakout['symbol']] = "no options"

            if filtered_out:
                logger.info(f"🔕 Filtered out (OI/Accumulation): {', '.join(filtered_out)}")
            
            
            if filtered_out:
                logger.info(f"🔕 Filtered out (OI increase < {min_oi_change_pct}%): {', '.join(filtered_out)}")
            
            # NEW: Filter by cumulative count > 2
            count_filtered_breakouts = []
            count_filtered_out = []
            
            for breakout in filtered_breakouts:
                symbol = breakout['symbol']
                cumulative_count = daily_summary.get(symbol, 0) if daily_summary else 0
                
                if cumulative_count > 2:
                    count_filtered_breakouts.append(breakout)
                else:
                    count_filtered_out.append(f"{symbol} (count={cumulative_count})")
                    filter_reasons[symbol] = f"count≤{cumulative_count}"
            
            if count_filtered_out:
                logger.info(f"🔢 Filtered out (cumulative count <= 2): {', '.join(count_filtered_out)}")
            
            # If everything is filtered at count stage, return False
            if not count_filtered_breakouts:
                logger.info(f"🔭 No alerts sent - all symbols filtered at count <= 2")
                return False  # CHANGED: Return False when nothing passes count filter
            
            # LATEST: Filter by already alerted today
            pre_alerted_breakouts = []
            already_alerted_out = []
            
            for breakout in count_filtered_breakouts:
                symbol = breakout['symbol']
                if daily_alerted_tickers is not None and symbol in daily_alerted_tickers:
                    already_alerted_out.append(symbol)
                    filter_reasons[symbol] = "alerted"
                else:
                    pre_alerted_breakouts.append(breakout)
            
            if already_alerted_out:
                logger.info(f"📅 Filtered out (already alerted today): {', '.join(already_alerted_out)}")
            
            if not pre_alerted_breakouts:
                logger.info(f"🔭 No alerts sent - all symbols already alerted today")
                return False  # CHANGED: Return False when all already alerted
            
            # NEW: Filter by direction match and flow confidence
            direction_filtered_breakouts = []
            direction_mismatch_out = []
            low_confidence_out = []
            
            for breakout in pre_alerted_breakouts:
                symbol = breakout['symbol']
                symbol_options = options.get(symbol, [])
                
                if symbol_options:
                    # Calculate money flow
                    spot_price = breakout.get('current_price', 0)
                    breakout_time = breakout.get('breakout_time')
                    flow_analysis = self.money_flow_calculator.analyze_money_flow(
                        symbol_options, spot_price, breakout_time
                    )
                    
                    # Check direction match (allow neutral flow to pass)
                    breakout_direction = breakout['direction']
                    flow_direction = flow_analysis['flow_direction']
                    
                    # Check confidence
                    flow_confidence = flow_analysis.get('confidence', 0)
                    
                    # CHANGED: Different confidence thresholds for bullish vs bearish
                    if breakout_direction == 'bullish':
                        min_confidence = 0.65  # Keep 65% for bullish
                    else:
                        min_confidence = 0.40  # Lower 40% for bearish
                    
                    # Allow neutral flow with any breakout direction if confidence is low
                    direction_matches = (
                        breakout_direction == flow_direction or 
                        flow_direction == 'neutral'  # Allow neutral flow to pass
                    )
                    
                    if direction_matches:
                        if flow_confidence >= min_confidence:
                            # Store flow analysis for later use
                            breakout['flow_analysis'] = flow_analysis
                            direction_filtered_breakouts.append(breakout)
                        else:
                            low_confidence_out.append(f"{symbol} (conf={flow_confidence:.1%})")
                            filter_reasons[symbol] = f"conf<{int(min_confidence*100)}% ({flow_confidence:.0%})"
                    else:
                        direction_mismatch_out.append(f"{symbol} (B:{breakout_direction[:4]}/F:{flow_direction[:4]})")
                        filter_reasons[symbol] = f"dir≠ (B:{breakout_direction[:4]}/F:{flow_direction[:4]})"
                else:
                    # No options data, skip
                    filter_reasons[symbol] = "no opts"
            
            if direction_mismatch_out:
                logger.info(f"🔄 Filtered out (direction mismatch): {', '.join(direction_mismatch_out)}")
            if low_confidence_out:
                logger.info(f"📉 Filtered out (flow confidence): {', '.join(low_confidence_out)}")
            
            if not direction_filtered_breakouts:
                logger.info(f"🔭 No alerts sent - all symbols failed direction/confidence check")
                return False  # CHANGED: Return False when all fail direction/confidence
            
            # FIXED FILTER: Net Directional Flow > 3Cr AND Proper Ratio Check for BOTH Bullish and Bearish
            flow_filtered_breakouts = []
            flow_filter_out = []
            
            for breakout in direction_filtered_breakouts:
                symbol = breakout['symbol']
                flow_analysis = breakout.get('flow_analysis', {})
                
                net_directional_flow = flow_analysis.get('net_directional_flow', 0)
                directional_flow_ratio = flow_analysis.get('directional_flow_ratio', 0)
                
                # FIXED: Check if meets flow criteria based on direction
                should_pass = False
                
                if breakout['direction'] == 'bullish':
                    # For bullish: need positive net flow > 3Cr AND CE/PE ratio > 3.0
                    should_pass = (net_directional_flow > 30_000_000 and 
                                directional_flow_ratio > 3.0)
                elif breakout['direction'] == 'bearish':
                    # For bearish: need negative net flow < -3Cr AND CE/PE ratio < 0.33 (1/3)
                    should_pass = (net_directional_flow < -30_000_000 and 
                                directional_flow_ratio < 0.55)
                
                if should_pass:
                    flow_filtered_breakouts.append(breakout)
                else:
                    net_cr = net_directional_flow / 10_000_000
                    if breakout['direction'] == 'bullish':
                        filter_reasons[symbol] = f"flow<3Cr/3x (N:{net_cr:.1f}Cr/R:{directional_flow_ratio:.1f})"
                    else:
                        filter_reasons[symbol] = f"flow<-3Cr/0.33x (N:{net_cr:.1f}Cr/R:{directional_flow_ratio:.1f})"
                    flow_filter_out.append(f"{symbol} (Net:{net_cr:.1f}Cr/Ratio:{directional_flow_ratio:.1f})")
            
            if flow_filter_out:
                logger.info(f"💰 Filtered out (Flow requirements not met): {', '.join(flow_filter_out)}")
            
            if not flow_filtered_breakouts:
                logger.info(f"🔭 No alerts sent - all symbols failed flow requirements")
                return False  # CHANGED: Return False when all fail flow requirements
            
            # SECTOR ALIGNMENT FILTER
            final_breakouts = []
            sector_misaligned_out = []
            
            for breakout in flow_filtered_breakouts:
                symbol = breakout['symbol']
                direction = breakout['direction']
                
                # Check sector alignment
                is_aligned, sector_info = self.sector_mapper.is_sector_aligned(symbol, direction)
                
                if is_aligned:
                    # Store sector info for display
                    breakout['sector_info'] = sector_info
                    final_breakouts.append(breakout)
                else:
                    sector_name = sector_info.get('sector', 'Unknown')
                    sector_dir = sector_info.get('sector_direction', 'unknown')
                    sector_change = sector_info.get('sector_change', 0)
                    sector_misaligned_out.append(f"{symbol} (Stock:{direction[:4]}/Sector:{sector_name}:{sector_dir[:4]}@{sector_change:+.1f}%)")
                    filter_reasons[symbol] = f"sector≠ ({sector_name}:{sector_dir[:4]})"
            
            if sector_misaligned_out:
                logger.info(f"📊 Filtered out (sector misalignment): {', '.join(sector_misaligned_out)}")
            
            # If no breakouts pass all filters, don't send alert
            if not final_breakouts:
                logger.info(f"🔭 No alerts sent - no symbols passed all filters")
                return False  # CHANGED: Return False instead of True
            
            # CRITICAL FIX: Mark ALL symbols in final_breakouts as alerted NOW
            for breakout in final_breakouts:
                if daily_alerted_tickers is not None:
                    daily_alerted_tickers.add(breakout['symbol'])
                    logger.info(f"✅ Marked {breakout['symbol']} as alerted - will NOT alert again today")
            
            # Create rich embed for Discord
            embeds = []
            
            # SECTOR STATUS EMBED FOR DEBUGGING
            if self.sector_mapper and hasattr(self.sector_mapper, 'sector_data') and self.sector_mapper.sector_data:
                sector_embed = {
                    "title": "📊 Current Sector Status (Live Data)",
                    "description": "Real-time sector directions for alignment check",
                    "color": 0x9932cc,  # Purple
                    "fields": []
                }
                
                # Sort sectors by change percentage
                sorted_sectors = sorted(self.sector_mapper.sector_data.items(), 
                                    key=lambda x: x[1]['change_pct'], reverse=True)
                
                # Split into bullish and bearish
                bullish_sectors = []
                bearish_sectors = []
                neutral_sectors = []
                
                for sector_name, sector_info in sorted_sectors:
                    emoji = "🟢" if sector_info['direction'] == 'bullish' else ("🔴" if sector_info['direction'] == 'bearish' else "⚪")
                    text = f"{emoji} **{sector_name}**: {sector_info['change_pct']:+.2f}%"
                    
                    if sector_info['direction'] == 'bullish':
                        bullish_sectors.append(text)
                    elif sector_info['direction'] == 'bearish':
                        bearish_sectors.append(text)
                    else:
                        neutral_sectors.append(text)
                
                if bullish_sectors:
                    sector_embed["fields"].append({
                        "name": "🟢 Bullish Sectors",
                        "value": "\n".join(bullish_sectors[:8]),  # Limit to 8
                        "inline": True
                    })
                
                if bearish_sectors:
                    sector_embed["fields"].append({
                        "name": "🔴 Bearish Sectors",
                        "value": "\n".join(bearish_sectors[:8]),  # Limit to 8
                        "inline": True
                    })
                
                if neutral_sectors:
                    sector_embed["fields"].append({
                        "name": "⚪ Neutral Sectors",
                        "value": "\n".join(neutral_sectors[:4]),  # Limit to 4
                        "inline": True
                    })
                
                embeds.append(sector_embed)
            
            # NEW: Score increase summary embed (only for symbols with count > 2 and not already alerted)
            if score_changes and score_changes.get('symbols_with_increases'):
                # Filter score changes to only include symbols with count > 2 and not already alerted
                filtered_score_symbols = []
                for sc in score_changes['symbols_with_increases']:
                    if daily_summary and daily_summary.get(sc['symbol'], 0) > 2:
                        # Check if symbol is in final breakouts (passed all filters)
                        if any(b['symbol'] == sc['symbol'] for b in final_breakouts):
                            filtered_score_symbols.append(sc)
                
                if filtered_score_symbols:
                    score_embed = {
                        "title": f"📈 {len(filtered_score_symbols)} Top 10 Breakouts with Score Increases!",
                        "description": f"Average increase: {score_changes['avg_increase']:.1f} points",
                        "color": 0xffd700,  # Gold
                        "fields": []
                    }
                    
                    increase_text = []
                    for sc in filtered_score_symbols[:10]:  # Limit to 10
                        symbol = sc['symbol'].replace('NSE:', '')
                        increase_text.append(f"**{symbol}**: {sc['old_score']:.0f} → {sc['new_score']:.0f} (+{sc['increase']:.1f})")
                    
                    score_embed["fields"].append({
                        "name": "Score Changes",
                        "value": "\n".join(increase_text),
                        "inline": False
                    })
                    
                    embeds.append(score_embed)
            
            # NEW: Daily cumulative ticker summary embed (with filter reasons)
            if daily_summary:
                unique_symbols = len(daily_summary)
                total_alerts = sum(daily_summary.values())
                
                summary_embed = {
                    "title": "📊 Daily Cumulative Ticker Summary",
                    "description": f"Total unique symbols with alerts: **{unique_symbols}**\n"
                                f"Total alerts generated: **{total_alerts}**\n"
                                f"Note: Alerts sent when ALL filters pass:\n"
                                f"• OI ↑ ≥ {min_oi_change_pct}%\n"
                                f"• Count > 2\n"
                                f"• Once/day per symbol\n"
                                f"• Direction match (B=F)\n"
                                f"• Flow confidence ≥ 65% (Bull) / 40% (Bear)\n"
                                f"• Net Dir Flow > |3Cr| AND Ratio\n"
                                f"• **SECTOR ALIGNMENT (Stock dir = Sector dir)**",
                    "color": 0x3498db,  # Blue
                    "fields": []
                }
                
                # Sort symbols by alert count
                sorted_symbols = sorted(daily_summary.items(), key=lambda x: x[1], reverse=True)
                
                # Show top 15 symbols
                symbol_text = []
                for symbol, count in sorted_symbols[:15]:
                    clean_symbol = symbol.replace('NSE:', '')
                    alerted_marker = "✅" if daily_alerted_tickers and symbol in daily_alerted_tickers else "⏳"
                    
                    # Add filter reason if filtered out
                    reason = ""
                    if symbol in filter_reasons:
                        reason = f" ({filter_reasons[symbol]})"
                        alerted_marker = "❌"
                    
                    symbol_text.append(f"• **{clean_symbol}**: {count} alerts {alerted_marker}{reason}")
                
                if len(sorted_symbols) > 15:
                    symbol_text.append(f"\n... and {len(sorted_symbols) - 15} more symbols")
                
                summary_embed["fields"].append({
                    "name": "Breakdown by Symbol (All Alerts)",
                    "value": "\n".join(symbol_text),
                    "inline": False
                })
                
                embeds.append(summary_embed)
            
            # Change summary embed (only after first alert) - filtered by count > 2 and not already alerted
            if alert_count > 1 and changes:
                # Filter changes to only include symbols in final_breakouts
                filtered_symbols = {b['symbol'] for b in final_breakouts}
                
                filtered_changes = {
                    'new_entries': [e for e in changes.get('new_entries', []) 
                                if e['symbol'] in filtered_symbols],
                    'grade_improvements': [g for g in changes.get('grade_improvements', []) 
                                        if g['symbol'] in filtered_symbols],
                    'position_changes': [p for p in changes.get('position_changes', []) 
                                    if p['symbol'] in filtered_symbols],
                    'exited': changes.get('exited', [])  # Keep all exits
                }
                
                if any(filtered_changes.values()):
                    change_embed = {
                        "title": f"📊 Top 10 Changes Summary (All Filters Applied)",
                        "description": f"Alert #{alert_count} - {datetime.now().strftime('%H:%M:%S IST')}",
                        "color": 0xffff00,  # Yellow
                        "fields": []
                    }
                    
                    # New entries
                    if filtered_changes['new_entries']:
                        new_text = []
                        for entry in filtered_changes['new_entries']:
                            count = daily_summary.get(entry['symbol'], 0)
                            new_text.append(f"#{entry['position']}: **{entry['symbol']}** ({entry['direction']}) [{entry['grade']}] [cnt:{count}]")
                        change_embed["fields"].append({
                            "name": f"🆕 New Entries ({len(filtered_changes['new_entries'])})",
                            "value": "\n".join(new_text),
                            "inline": False
                        })
                    
                    # Grade improvements
                    if filtered_changes['grade_improvements']:
                        grade_text = []
                        for imp in filtered_changes['grade_improvements']:
                            count = daily_summary.get(imp['symbol'], 0)
                            grade_text.append(f"**{imp['symbol']}**: {imp['old_grade']} → **{imp['new_grade']}** (#{imp['position']}) [cnt:{count}]")
                        change_embed["fields"].append({
                            "name": f"⬆️ Grade Improvements ({len(filtered_changes['grade_improvements'])})",
                            "value": "\n".join(grade_text),
                            "inline": False
                        })
                    
                    # Position changes
                    if filtered_changes['position_changes']:
                        pos_text = []
                        for pc in filtered_changes['position_changes'][:5]:  # Limit to top 5
                            arrow = "↗️" if pc['old_position'] > pc['new_position'] else "↘️"
                            count = daily_summary.get(pc['symbol'], 0)
                            pos_text.append(f"{arrow} **{pc['symbol']}**: #{pc['old_position']} → #{pc['new_position']} [cnt:{count}]")
                        change_embed["fields"].append({
                            "name": f"🔄 Position Changes",
                            "value": "\n".join(pos_text),
                            "inline": False
                        })
                    
                    # Exited top 10
                    if filtered_changes['exited']:
                        exit_text = ", ".join([f"{e['symbol']} (was #{e['old_position']})" for e in filtered_changes['exited']])
                        change_embed["fields"].append({
                            "name": f"👋 Exited Top 10",
                            "value": exit_text,
                            "inline": False
                        })
                    
                    embeds.append(change_embed)
            
            # Summary embed
            summary_embed = {
                "title": f"🚨 {len(final_breakouts)} Breakouts (ALL Filters Passed + SECTOR ALIGNED)",
                "description": f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}\n"
                            f"Alert #{alert_count}\n"
                            f"Filters: OI ↑ ≥ {min_oi_change_pct}%, Count > 2, Once/Day, **Dir Match**, **Conf ≥ 65% (Bull) / 40% (Bear)**, **Flow Thresholds**, **SECTOR ALIGNED**\n"
                            f"Options: +/-10% strikes | Directional positions only\n"
                            f"💰 Advanced flow analysis with strong directional bias required",
                "color": 0x00ff00,  # Green
                "fields": []
            }
            
            # Add quick summary
            bullish_count = sum(1 for b in final_breakouts if b['direction'] == 'bullish')
            bearish_count = len(final_breakouts) - bullish_count
            dormant_count = sum(1 for b in final_breakouts if b.get('is_dormant_breakout', False))
            
            summary_embed["fields"].append({
                "name": "Direction Breakdown",
                "value": f"🟢 Bullish: {bullish_count}\n🔴 Bearish: {bearish_count}",
                "inline": True
            })
            
            summary_embed["fields"].append({
                "name": "Special Breakouts",
                "value": f"💜 Dormant: {dormant_count}",
                "inline": True
            })
            
            embeds.append(summary_embed)
            
            # Calculate max individual breakout embeds we can add
            max_breakout_embeds = max(0, 10 - len(embeds))  # Discord limit is 10 total
            
            # Individual breakout embeds (limited to prevent exceeding Discord's 10 embed limit)
            for breakout in final_breakouts[:max_breakout_embeds]:
                color = 0x00ff00 if breakout['direction'] == 'bullish' else 0xff0000
                
                # Compact fields for main metrics
                compact_fields = []
                
                # FIX: Check if extension_pct exists before using it
                extension_pct = breakout.get('extension_pct', 0)
                
                # First row - key metrics
                compact_fields.append({
                    "name": "📈 Price Action",
                    "value": f"**₹{breakout.get('current_price', 0):.2f}**\n"
                            f"Ext: {extension_pct:.1f}%",
                    "inline": True
                })
                
                compact_fields.append({
                    "name": "📊 Volume",
                    "value": f"**{breakout.get('volume_ratio', 0):.1f}x** avg\n"
                            f"{breakout.get('volume_percentile', 0):.0f}th %ile",
                    "inline": True
                })
                
                compact_fields.append({
                    "name": "💯 Score",
                    "value": f"**{breakout.get('strength_score', 0):.0f}**\n"
                            f"Grade: **{breakout.get('quality_grade', 'N/A')}**",
                    "inline": True
                })
                
                # Get daily count
                daily_count = daily_summary.get(breakout['symbol'], 0) if daily_summary else 0
                
                # Title with special badges
                title_suffix = ""
                if breakout.get('is_dormant_breakout', False):
                    title_suffix += " 💜 DORMANT"
                if changes and breakout['symbol'] in [e['symbol'] for e in changes.get('new_entries', [])]:
                    title_suffix += " 🆕"
                if daily_count > 5:
                    title_suffix += f" 🔥x{daily_count}"
                
                # Get flow analysis
                flow_analysis = breakout.get('flow_analysis', {})
                
                # Get sector info
                sector_info = breakout.get('sector_info', {})
                sector_name = sector_info.get('sector', 'N/A')
                sector_change = sector_info.get('sector_change', 0)
                sector_direction = sector_info.get('sector_direction', 'unknown')
                sector_display = f"{sector_name} ({sector_change:+.2f}% {sector_direction.upper()})"
                
                # FIX: Get ATR27 with default value
                atr27 = breakout.get('atr27', 0)
                
                embed = {
                    "title": f"{breakout['symbol']} - {breakout['direction'].upper()}{title_suffix}",
                    "color": color,
                    "fields": compact_fields,
                    "footer": {
                        "text": f"Time: {breakout.get('breakout_time', 'Active')} | ATR: ₹{atr27:.2f} | Conf: {flow_analysis.get('confidence', 0):.0%} | Sector: {sector_display}" + 
                            (f" | OI Vel: {breakout.get('oi_accumulation', {}).get('velocity', 0):.1f}%/scan" if breakout.get('oi_accumulation', {}).get('is_accelerating') else "")
                    }
                }
                
                # Add money flow analysis (COMPACT VERSION)
                symbol_options = options.get(breakout['symbol'], [])
                if symbol_options and flow_analysis:
                    ce_cr = flow_analysis.get('ce_money_flow', 0) / 10_000_000
                    pe_cr = flow_analysis.get('pe_money_flow', 0) / 10_000_000
                    net_dir_cr = flow_analysis.get('net_directional_flow', 0) / 10_000_000
                    
                    flow_text = f"**💰 {flow_analysis.get('sentiment', 'UNKNOWN')} {flow_analysis.get('sentiment_emoji', '')}**\n"
                    flow_text += f"CE: ₹{ce_cr:.1f}Cr | PE: ₹{pe_cr:.1f}Cr\n"
                    flow_text += f"Net Dir: ₹{net_dir_cr:+.1f}Cr | Ratio: {flow_analysis.get('directional_flow_ratio', 0):.2f}"
                    
                    embed["fields"].append({
                        "name": "💸 Money Flow",
                        "value": flow_text[:500],
                        "inline": False
                    })
                    
                    # Show top option recommendation (COMPACT)
                    if breakout['direction'] == 'bullish' and flow_analysis.get('top_ce_directional'):
                        for flow_opt in flow_analysis['top_ce_directional'][:1]:  # Just top 1
                            matching_opt = None
                            for opt in symbol_options:
                                if opt['strike'] == flow_opt['strike'] and opt['type'] == 'CE':
                                    matching_opt = opt
                                    break
                            
                            if matching_opt:
                                oi_change = self.options_loader.get_option_oi_change(
                                    breakout['symbol'], matching_opt['strike'], 'CE', matching_opt.get('expiry', '')
                                )
                                
                                if oi_change.get('oi_change_pct', 0) >= min_oi_change_pct:
                                    option_text = f"**{matching_opt['strike']} CE** @ ₹{matching_opt.get('last_price', 0):.2f}\n"
                                    option_text += f"OI ↑ {oi_change.get('oi_change_pct', 0):.1f}% | Vol/OI: {flow_opt.get('vol_oi_ratio', 0):.2f}"
                                    
                                    embed["fields"].append({
                                        "name": "🎯 Best CALL",
                                        "value": option_text,
                                        "inline": False
                                    })
                                    break
                    
                    elif breakout['direction'] == 'bearish' and flow_analysis.get('top_pe_directional'):
                        for flow_opt in flow_analysis['top_pe_directional'][:1]:  # Just top 1
                            matching_opt = None
                            for opt in symbol_options:
                                if opt['strike'] == flow_opt['strike'] and opt['type'] == 'PE':
                                    matching_opt = opt
                                    break
                            
                            if matching_opt:
                                oi_change = self.options_loader.get_option_oi_change(
                                    breakout['symbol'], matching_opt['strike'], 'PE', matching_opt.get('expiry', '')
                                )
                                
                                if oi_change.get('oi_change_pct', 0) >= min_oi_change_pct:
                                    option_text = f"**{matching_opt['strike']} PE** @ ₹{matching_opt.get('last_price', 0):.2f}\n"
                                    option_text += f"OI ↑ {oi_change.get('oi_change_pct', 0):.1f}% | Vol/OI: {flow_opt.get('vol_oi_ratio', 0):.2f}"
                                    
                                    embed["fields"].append({
                                        "name": "🎯 Best PUT",
                                        "value": option_text,
                                        "inline": False
                                    })
                                    break
                
                embeds.append(embed)
            
            # CRITICAL: Ensure we don't exceed Discord's 10 embed limit
            if len(embeds) > 10:
                logger.warning(f"⚠️ Trimming embeds from {len(embeds)} to 10 (Discord limit)")
                embeds = embeds[:10]
            
            # Send to Discord
            summary_content = f"🔔 **Zerodha Scanner Alert** - Strong Directional Flow + SECTOR ALIGNED ({len(final_breakouts)} stocks)"
            
            data = {
                "content": summary_content,
                "embeds": embeds
            }
            
            response = requests.post(self.webhook_url, json=data)
            
            if response.status_code == 204:
                logger.info(f"Discord alert sent successfully for {len(final_breakouts)} symbols")
                return True
            else:
                logger.error(f"Discord webhook failed: {response.status_code}")
                if response.text:
                    logger.error(f"Discord error message: {response.text}")
                logger.error(f"Number of embeds sent: {len(embeds)}")
                logger.error(f"Webhook URL: {self.webhook_url[:50]}...")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Discord alert: {e}")
            import traceback
            traceback.print_exc()
            return False
    
# ==================== TELEGRAM ALERTS ====================
class TelegramAlerter:
    """Send simple alerts via Telegram bot"""
    
    def __init__(self, bot_token: str, chat_id: str, options_loader: OptionsDataLoader, sector_mapper=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.options_loader = options_loader
        self.sector_mapper = sector_mapper  # Store sector mapper
        self.money_flow_calculator = MoneyFlowCalculator()
        self.stop_loss_calculator = None  # Will be set by AlertScanner
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.golden_ratio = 1.618  # Add golden ratio here
      
    def send_alert(self, breakouts: List[Dict], options: Dict, changes: Dict, alert_count: int, 
                min_oi_change_pct: float = 1.0, score_changes: Dict = None, 
                daily_summary: Dict = None, daily_alerted_tickers: set = None,
                filter_reasons: Dict = None) -> bool:
        """Send simple formatted alert to Telegram with only essential info"""
        if not self.bot_token or not self.chat_id:
            return False
            
        try:
            # Initialize filter_reasons if not provided
            if filter_reasons is None:
                filter_reasons = {}
            
            # NEW: Get NIFTY 50 direction for additional filter
            nifty_direction = None
            nifty_change_pct = 0
            try:
                # Check if sector mapper has NIFTY data
                if self.sector_mapper and hasattr(self.sector_mapper, 'sector_data'):
                    nifty_data = self.sector_mapper.sector_data.get('INDEX')
                    if nifty_data:
                        nifty_change_pct = nifty_data.get('change_pct', 0)
                        if nifty_change_pct > 0:
                            nifty_direction = 'bullish'
                        elif nifty_change_pct < 0:
                            nifty_direction = 'bearish'
                        else:
                            nifty_direction = 'neutral'
                        logger.info(f"📊 NIFTY 50: {nifty_change_pct:+.2f}% ({nifty_direction}) - Additional Telegram filter active")
            except Exception as e:
                logger.warning(f"Could not get NIFTY direction: {e}")
            
            # Apply all the same filters as Discord
            filtered_breakouts = []
            
            # OI filter with accumulation check
            for breakout in breakouts:
                symbol_options = options.get(breakout['symbol'], [])
                if symbol_options:
                    # NEW: Check both OI increase and accumulation
                    passes_oi, oi_info = self.options_loader.has_significant_oi_increase(
                        breakout['symbol'], 
                        symbol_options, 
                        min_oi_change_pct,
                        direction=breakout['direction'],  # Pass direction for accumulation check
                        check_accumulation=True
                    )
                    
                    if passes_oi:
                        # Store accumulation info for display
                        breakout['oi_accumulation'] = oi_info.get('details', {})
                        filtered_breakouts.append(breakout)
                    else:
                        if oi_info.get('night_increase') and not oi_info.get('accumulation'):
                            filter_reasons[breakout['symbol']] = "no OI accum"
                        else:
                            filter_reasons[breakout['symbol']] = f"OI < {min_oi_change_pct}%"
                else:
                    filter_reasons[breakout['symbol']] = "no options"
            
            if not filtered_breakouts:
                logger.info("No Telegram alerts - all filtered at OI check")
                return False
            
            # Count filter
            count_filtered_breakouts = []
            for breakout in filtered_breakouts:
                symbol = breakout['symbol']
                cumulative_count = daily_summary.get(symbol, 0) if daily_summary else 0
                if cumulative_count > 2:
                    count_filtered_breakouts.append(breakout)
                else:
                    filter_reasons[symbol] = f"count≤{cumulative_count}"
            
            if not count_filtered_breakouts:
                logger.info("No Telegram alerts - all filtered at count <= 2")
                return False
            
            # Already alerted filter
            pre_alerted_breakouts = []
            for breakout in count_filtered_breakouts:
                symbol = breakout['symbol']
                if daily_alerted_tickers is not None and symbol in daily_alerted_tickers:
                    filter_reasons[symbol] = "alerted"
                    logger.info(f"📅 {symbol} already alerted today - skipping")
                else:
                    pre_alerted_breakouts.append(breakout)
            
            if not pre_alerted_breakouts:
                logger.info("No Telegram alerts - all already alerted today")
                return False
            
            # Direction match and confidence filter
            direction_filtered_breakouts = []
            for breakout in pre_alerted_breakouts:
                symbol = breakout['symbol']
                symbol_options = options.get(symbol, [])
                
                if symbol_options:
                    # Calculate money flow
                    spot_price = breakout.get('current_price', 0)
                    breakout_time = breakout.get('breakout_time')
                    flow_analysis = self.money_flow_calculator.analyze_money_flow(
                        symbol_options, spot_price, breakout_time
                    )
                    
                    # Check direction match and confidence
                    breakout_direction = breakout['direction']
                    flow_direction = flow_analysis['flow_direction']
                    flow_confidence = flow_analysis.get('confidence', 0)
                    
                    # CHANGED: Different confidence thresholds for bullish vs bearish
                    if breakout_direction == 'bullish':
                        min_confidence = 0.65  # Keep 65% for bullish
                    else:
                        min_confidence = 0.40  # Lower 40% for bearish
                    
                    direction_matches = (
                        breakout_direction == flow_direction or 
                        flow_direction == 'neutral'
                    )
                    
                    if direction_matches and flow_confidence >= min_confidence:
                        breakout['flow_analysis'] = flow_analysis
                        direction_filtered_breakouts.append(breakout)
                    else:
                        if not direction_matches:
                            filter_reasons[symbol] = f"dir≠ (B:{breakout_direction[:4]}/F:{flow_direction[:4]})"
                        else:
                            filter_reasons[symbol] = f"conf<{int(min_confidence*100)}% ({flow_confidence:.0%})"
                else:
                    filter_reasons[symbol] = "no opts"
            
            if not direction_filtered_breakouts:
                logger.info("No Telegram alerts - all failed direction/confidence check")
                return False
            
            # Net Directional Flow > 3Cr AND Proper Ratio Check
            flow_filtered_breakouts = []
            
            for breakout in direction_filtered_breakouts:
                symbol = breakout['symbol']
                flow_analysis = breakout.get('flow_analysis', {})
                
                net_directional_flow = flow_analysis.get('net_directional_flow', 0)
                directional_flow_ratio = flow_analysis.get('directional_flow_ratio', 0)
                
                should_pass = False
                
                if breakout['direction'] == 'bullish':
                    should_pass = (net_directional_flow > 30_000_000 and 
                                directional_flow_ratio > 3.0)
                elif breakout['direction'] == 'bearish':
                    should_pass = (net_directional_flow < -30_000_000 and 
                                directional_flow_ratio < 0.55)
                
                if should_pass:
                    flow_filtered_breakouts.append(breakout)
                else:
                    net_cr = net_directional_flow / 10_000_000
                    if breakout['direction'] == 'bullish':
                        filter_reasons[symbol] = f"flow<3Cr/3x"
                    else:
                        filter_reasons[symbol] = f"flow<-3Cr/0.33x"
            
            if not flow_filtered_breakouts:
                logger.info("No Telegram alerts - all failed flow requirements")
                return False
            
            # SECTOR ALIGNMENT FILTER
            sector_aligned_breakouts = []
            
            for breakout in flow_filtered_breakouts:
                symbol = breakout['symbol']
                direction = breakout['direction']
                
                # Check sector alignment
                is_aligned, sector_info = self.sector_mapper.is_sector_aligned(symbol, direction)
                
                if is_aligned:
                    breakout['sector_info'] = sector_info
                    sector_aligned_breakouts.append(breakout)
                else:
                    filter_reasons[symbol] = f"sector≠"
            
            if not sector_aligned_breakouts:
                logger.info("No Telegram alerts - all failed sector alignment")
                return False
            
            # ====== NEW NIFTY DIRECTION FILTER FOR TELEGRAM ONLY ======
            final_breakouts = []
            nifty_filtered_out = []
            
            for breakout in sector_aligned_breakouts:
                symbol = breakout['symbol']
                direction = breakout['direction']
                
                # Check NIFTY alignment
                nifty_aligned = True
                
                if nifty_direction:
                    if direction == 'bullish' and nifty_change_pct <= 0:
                        # Bullish breakout but NIFTY is not positive
                        nifty_aligned = False
                        nifty_filtered_out.append(f"{symbol} (Bull but NIFTY {nifty_change_pct:+.1f}%)")
                        filter_reasons[symbol] = f"NIFTY≤0 ({nifty_change_pct:+.1f}%)"
                    elif direction == 'bearish' and nifty_change_pct >= 0:
                        # Bearish breakout but NIFTY is not negative
                        nifty_aligned = False
                        nifty_filtered_out.append(f"{symbol} (Bear but NIFTY {nifty_change_pct:+.1f}%)")
                        filter_reasons[symbol] = f"NIFTY≥0 ({nifty_change_pct:+.1f}%)"
                
                if nifty_aligned:
                    final_breakouts.append(breakout)
            
            if nifty_filtered_out:
                logger.info(f"📈 Filtered out (NIFTY direction mismatch): {', '.join(nifty_filtered_out)}")
            
            # If no breakouts pass all filters, don't send alert
            if not final_breakouts:
                logger.info("No Telegram alerts - all filtered out (including NIFTY direction check)")
                return False
            # ====== END NEW NIFTY DIRECTION FILTER ======
            
            # CRITICAL FIX: Mark ALL symbols in final_breakouts as alerted NOW
            for breakout in final_breakouts:
                if daily_alerted_tickers is not None:
                    daily_alerted_tickers.add(breakout['symbol'])
                    logger.info(f"✅ Marked {breakout['symbol']} as alerted - will NOT alert again today")
            
            # Create simple messages for Telegram
            messages = []
            
            for breakout in final_breakouts[:5]:  # Limit to 5 for Telegram
                symbol = breakout['symbol'].replace('NSE:', '')
                direction = breakout['direction']
                current_price = breakout.get('current_price', 0)
                
                # Get flow analysis
                flow_analysis = breakout.get('flow_analysis', {})
                
                # Find best option recommendation with EXPIRY-AWARE LOGIC
                symbol_options = options.get(breakout['symbol'], [])
                recommended_option = None
                option_premium = None
                selected_expiry_date = None
                days_to_expiry = None
                
                if symbol_options and flow_analysis:
                    # Calculate days to expiry for current month
                    today = datetime.now().date()
                    current_expiries = set()
                    
                    # Get all unique expiries from options
                    for opt in symbol_options:
                        if opt.get('expiry'):
                            try:
                                expiry_date = datetime.strptime(opt['expiry'][:10], '%Y-%m-%d').date()
                                current_expiries.add(expiry_date)
                            except:
                                pass
                    
                    # Find nearest expiry
                    nearest_expiry = None
                    if current_expiries:
                        future_expiries = sorted([e for e in current_expiries if e >= today])
                        if future_expiries:
                            nearest_expiry = future_expiries[0]
                    
                    days_to_expiry = (nearest_expiry - today).days if nearest_expiry else 30
                    
                    # Determine strike selection parameters based on days to expiry
                    if days_to_expiry < 5:
                        # LESS THAN 5 DAYS TO EXPIRY - SPECIAL HANDLING FOR NEXT MONTH
                        logger.info(f"📅 {symbol}: Only {days_to_expiry} days to current expiry - fetching next month options")
                        
                        # Try to fetch next month options via separate API call
                        try:
                            import pandas as pd
                            
                            # Get the Zerodha client
                            if hasattr(self.options_loader, 'scanner') and hasattr(self.options_loader.scanner, 'client'):
                                client = self.options_loader.scanner.client
                                
                                # Get base symbol
                                base_symbol = breakout['symbol'].split(':')[-1] if ':' in breakout['symbol'] else breakout['symbol']
                                
                                # Get all instruments for this symbol
                                nfo_instruments = client.instruments[
                                    (client.instruments['exchange'] == 'NFO') & 
                                    (client.instruments['name'] == base_symbol)
                                ]
                                
                                # Filter for options
                                all_options = nfo_instruments[nfo_instruments['instrument_type'].isin(['CE', 'PE'])]
                                
                                # Get expiries
                                expiries = pd.to_datetime(all_options['expiry']).dt.date.unique()
                                future_expiries = sorted([e for e in expiries if e >= today])
                                
                                if len(future_expiries) > 1:
                                    next_month_expiry = future_expiries[1]
                                    selected_expiry_date = next_month_expiry
                                    
                                    # Filter for next month only
                                    next_month_opts = all_options[pd.to_datetime(all_options['expiry']).dt.date == next_month_expiry]
                                    
                                    # Get relevant strikes based on direction
                                    if direction == 'bullish':
                                        relevant_strikes = next_month_opts[
                                            (next_month_opts['instrument_type'] == 'CE') &
                                            (next_month_opts['strike'] >= current_price) &
                                            (next_month_opts['strike'] <= current_price * 1.10)
                                        ]
                                    else:
                                        relevant_strikes = next_month_opts[
                                            (next_month_opts['instrument_type'] == 'PE') &
                                            (next_month_opts['strike'] <= current_price) &
                                            (next_month_opts['strike'] >= current_price * 0.90)
                                        ]
                                    
                                    if not relevant_strikes.empty:
                                        # Get quotes for these specific options
                                        option_symbols = [f"NFO:{row['tradingsymbol']}" for _, row in relevant_strikes.iterrows()]
                                        
                                        # Fetch quotes for top 5 strikes
                                        quotes = client.kite.quote(option_symbols[:5])
                                        
                                        # Find best based on OI + Volume
                                        best_option = None
                                        best_score = 0
                                        
                                        for sym, quote in quotes.items():
                                            tradingsymbol = sym.split(':')[1]
                                            strike_rows = relevant_strikes[relevant_strikes['tradingsymbol'] == tradingsymbol]
                                            if not strike_rows.empty:
                                                strike_row = strike_rows.iloc[0]
                                                
                                                oi = quote.get('oi', 0)
                                                volume = quote.get('volume', 0)
                                                last_price = quote.get('last_price', 0)
                                                score = oi + volume
                                                
                                                if score > best_score and last_price > 0:
                                                    best_score = score
                                                    best_option = {
                                                        'strike': strike_row['strike'],
                                                        'type': strike_row['instrument_type'],
                                                        'premium': last_price
                                                    }
                                        
                                        if best_option and best_option['premium'] > 0:
                                            recommended_option = f"{best_option['strike']} {best_option['type']}"
                                            option_premium = best_option['premium']
                                            logger.info(f"Selected next month option: {recommended_option} @ ₹{option_premium:.2f} (Exp: {selected_expiry_date})")
                                else:
                                    # No next month available, fallback to current
                                    logger.warning(f"⚠️ {symbol}: No next month expiry available, using current")
                                    selected_expiry_date = nearest_expiry
                                    
                        except Exception as e:
                            logger.warning(f"Failed to fetch next month options: {e}")
                            selected_expiry_date = nearest_expiry
                        
                        # If we couldn't get next month option, fallback to current month ATM
                        if not recommended_option and current_price > 0:
                            selected_expiry_date = nearest_expiry
                            atm_strike = round(current_price / 50) * 50
                            for opt in symbol_options:
                                if opt['strike'] == atm_strike and opt['type'] == ('CE' if direction == 'bullish' else 'PE'):
                                    recommended_option = f"{opt['strike']} {opt['type']}"
                                    option_premium = opt.get('last_price', 0)
                                    break
                    
                    elif days_to_expiry <= 15:
                        # Mid-month: gradually tighten range from 5% to 3%
                        range_pct = 3 + (2 * (days_to_expiry - 5) / 10)  # Linear from 3% to 5%
                        range_pct = max(3, min(5, range_pct))  # Ensure within 3-5%
                        logger.info(f"📅 {symbol}: {days_to_expiry} days to expiry - using {range_pct:.1f}% range")
                        selected_expiry_date = nearest_expiry
                        
                        if direction == 'bullish':
                            # Find CE options within tightened range
                            ce_options = [opt for opt in symbol_options 
                                        if opt['type'] == 'CE' and 
                                        opt['strike'] >= current_price * 0.995 and  # Avoid deep ITM
                                        opt['strike'] <= current_price * (1 + range_pct/100)]
                            
                            if ce_options:
                                # Sort by distance from current price (prefer ATM/slightly OTM)
                                ce_options.sort(key=lambda x: abs(x['strike'] - current_price * 1.005))
                                best_opt = ce_options[0]
                                
                                # Verify it has good liquidity
                                if best_opt.get('oi', 0) > 0 or best_opt.get('volume', 0) > 0:
                                    recommended_option = f"{best_opt['strike']} CE"
                                    option_premium = best_opt.get('last_price', 0)
                        else:
                            # Find PE options within tightened range
                            pe_options = [opt for opt in symbol_options 
                                        if opt['type'] == 'PE' and 
                                        opt['strike'] <= current_price * 1.005 and  # Avoid deep ITM
                                        opt['strike'] >= current_price * (1 - range_pct/100)]
                            
                            if pe_options:
                                # Sort by distance from current price (prefer ATM/slightly OTM)
                                pe_options.sort(key=lambda x: abs(x['strike'] - current_price * 0.995))
                                best_opt = pe_options[0]
                                
                                if best_opt.get('oi', 0) > 0 or best_opt.get('volume', 0) > 0:
                                    recommended_option = f"{best_opt['strike']} PE"
                                    option_premium = best_opt.get('last_price', 0)
                    
                    else:
                        # Start of month (15+ days): use standard 10% range logic
                        logger.info(f"📅 {symbol}: {days_to_expiry} days to expiry - using standard 10% range")
                        selected_expiry_date = nearest_expiry
                        
                        if breakout['direction'] == 'bullish' and flow_analysis.get('top_ce_directional'):
                            # Find best CE option
                            for flow_opt in flow_analysis['top_ce_directional']:
                                for opt in symbol_options:
                                    if (opt['strike'] == flow_opt['strike'] and 
                                        opt['type'] == 'CE' and 
                                        opt.get('expiry') == flow_opt.get('expiry')):
                                        
                                        # Avoid deep ITM (more than 0.5% ITM)
                                        if opt['strike'] < current_price * 0.995:
                                            continue
                                        
                                        oi_change = self.options_loader.get_option_oi_change(
                                            breakout['symbol'], opt['strike'], 'CE', opt.get('expiry', '')
                                        )
                                        
                                        if oi_change.get('oi_change_pct', 0) >= min_oi_change_pct:
                                            recommended_option = f"{opt['strike']} CE"
                                            option_premium = opt.get('last_price', 0)
                                            break
                                if recommended_option:
                                    break
                            
                            # Fallback to ATM if no good directional option
                            if not recommended_option and current_price > 0:
                                atm_strike = round(current_price / 50) * 50
                                for opt in symbol_options:
                                    if opt['strike'] == atm_strike and opt['type'] == 'CE':
                                        recommended_option = f"{opt['strike']} CE"
                                        option_premium = opt.get('last_price', 0)
                                        break
                        
                        elif breakout['direction'] == 'bearish' and flow_analysis.get('top_pe_directional'):
                            # Find best PE option
                            for flow_opt in flow_analysis['top_pe_directional']:
                                for opt in symbol_options:
                                    if (opt['strike'] == flow_opt['strike'] and 
                                        opt['type'] == 'PE' and 
                                        opt.get('expiry') == flow_opt.get('expiry')):
                                        
                                        # Avoid deep ITM (more than 0.5% ITM)
                                        if opt['strike'] > current_price * 1.005:
                                            continue
                                        
                                        oi_change = self.options_loader.get_option_oi_change(
                                            breakout['symbol'], opt['strike'], 'PE', opt.get('expiry', '')
                                        )
                                        
                                        if oi_change.get('oi_change_pct', 0) >= min_oi_change_pct:
                                            recommended_option = f"{opt['strike']} PE"
                                            option_premium = opt.get('last_price', 0)
                                            break
                                if recommended_option:
                                    break
                            
                            # Fallback to ATM if no good directional option
                            if not recommended_option and current_price > 0:
                                atm_strike = round(current_price / 50) * 50
                                for opt in symbol_options:
                                    if opt['strike'] == atm_strike and opt['type'] == 'PE':
                                        recommended_option = f"{opt['strike']} PE"
                                        option_premium = opt.get('last_price', 0)
                                        break
                
                # ============ ITM LOGIC STARTS HERE ============
                # After 16th of month, if premium < 8 INR, switch to ITM
                today = datetime.now().date()
                if today.day > 16 and option_premium and option_premium < 8:
                    logger.info(f"🔄 {symbol}: Premium ₹{option_premium:.2f} < 8 after 16th - switching to ITM option")
                    
                    # Reset and find ITM option
                    recommended_option = None
                    option_premium = None
                    
                    if direction == 'bullish':
                        # For bullish, find ITM CE (strike < current_price)
                        itm_ce_options = [opt for opt in symbol_options 
                                        if opt['type'] == 'CE' and 
                                        opt['strike'] < current_price * 0.995 and  # At least 0.5% ITM
                                        opt['strike'] >= current_price * 0.90 and  # Max 10% ITM
                                        opt.get('last_price', 0) > 0]
                        
                        if itm_ce_options:
                            # Sort by strike descending (closest to current price first)
                            itm_ce_options.sort(key=lambda x: x['strike'], reverse=True)
                            
                            # Pick the one with best liquidity
                            for opt in itm_ce_options[:5]:  # Check top 5 ITM strikes
                                if opt.get('oi', 0) > 0 or opt.get('volume', 0) > 0:
                                    recommended_option = f"{opt['strike']} CE"
                                    option_premium = opt.get('last_price', 0)
                                    logger.info(f"Selected ITM CE: {recommended_option} @ ₹{option_premium:.2f}")
                                    break
                    else:
                        # For bearish, find ITM PE (strike > current_price)
                        itm_pe_options = [opt for opt in symbol_options 
                                        if opt['type'] == 'PE' and 
                                        opt['strike'] > current_price * 1.005 and  # At least 0.5% ITM
                                        opt['strike'] <= current_price * 1.10 and  # Max 10% ITM
                                        opt.get('last_price', 0) > 0]
                        
                        if itm_pe_options:
                            # Sort by strike ascending (closest to current price first)
                            itm_pe_options.sort(key=lambda x: x['strike'])
                            
                            # Pick the one with best liquidity
                            for opt in itm_pe_options[:5]:  # Check top 5 ITM strikes
                                if opt.get('oi', 0) > 0 or opt.get('volume', 0) > 0:
                                    recommended_option = f"{opt['strike']} PE"
                                    option_premium = opt.get('last_price', 0)
                                    logger.info(f"Selected ITM PE: {recommended_option} @ ₹{option_premium:.2f}")
                                    break
                    
                    # If still no ITM option found with good liquidity, fall back to nearest ITM
                    if not recommended_option and current_price > 0:
                        if direction == 'bullish':
                            # Find nearest ITM CE
                            nearest_itm_strike = round((current_price * 0.98) / 50) * 50  # 2% ITM
                            for opt in symbol_options:
                                if opt['strike'] == nearest_itm_strike and opt['type'] == 'CE':
                                    recommended_option = f"{opt['strike']} CE"
                                    option_premium = opt.get('last_price', 0)
                                    logger.info(f"Fallback ITM CE: {recommended_option} @ ₹{option_premium:.2f}")
                                    break
                        else:
                            # Find nearest ITM PE
                            nearest_itm_strike = round((current_price * 1.02) / 50) * 50  # 2% ITM
                            for opt in symbol_options:
                                if opt['strike'] == nearest_itm_strike and opt['type'] == 'PE':
                                    recommended_option = f"{opt['strike']} PE"
                                    option_premium = opt.get('last_price', 0)
                                    logger.info(f"Fallback ITM PE: {recommended_option} @ ₹{option_premium:.2f}")
                                    break
                # ============ ITM LOGIC ENDS HERE ============
                
                # Skip if no option found or price is invalid
                if not recommended_option or not option_premium or option_premium <= 0:
                    logger.info(f"Skipping {symbol} - no valid option found")
                    continue
                
                # Calculate option levels using your specific formulas
                premium_range_pct = 3.83
                range_low = option_premium * (1 - premium_range_pct / 100)
                range_high = option_premium * (1 + premium_range_pct / 100)
                
                # Stop Loss: premium - (premium * 0.272 / 1.618)
                option_sl = option_premium - (option_premium * 0.272 / self.golden_ratio)
                
                # Target 1: premium + (premium * 0.272)
                # NEW TP-1: 15% from current premium, rounded to nearest 0.5
                new_tp1 = round(option_premium * 1.15 * 2) / 2

                # TP-2: premium + (premium * 0.272) - old TP-1, rounded to nearest 0.5
                option_tp2 = round((option_premium + (option_premium * 0.272)) * 2) / 2

                # TP-3: premium + (premium * 0.272 * 2) - old TP-2, rounded to nearest 0.5
                option_tp3 = round((option_premium + (option_premium * 0.272 * 2)) * 2) / 2
                
                # Format message - WITH PROPER LINE BREAKS
                if direction == 'bullish':
                    alert_title = "🟢 BULLISH ALERT"
                else:
                    alert_title = "🔴 BEARISH ALERT"
                
                # Format expiry date nicely
                expiry_info = ""
                if selected_expiry_date:
                    expiry_str = selected_expiry_date.strftime("%d-%b-%Y")
                    # RECALCULATE days for the ACTUAL selected expiry
                    actual_days_to_expiry = (selected_expiry_date - today).days
                    expiry_info = f"\n    ⏰ *Expiry:* {expiry_str} ({actual_days_to_expiry} days)"
                
                # Add NIFTY status to the message
                nifty_status = f"\n    📊 *NIFTY:* {nifty_change_pct:+.2f}% ({nifty_direction})" if nifty_direction else ""
                
                message = f"""{alert_title}
        📊 *{symbol}* Current Price: *₹{current_price:.2f}*{expiry_info}{nifty_status}

        🎯 *Recommended Option:* {recommended_option}
            💰 *Premium:* ₹{option_premium:.2f}
            📈 *Entry Range:* ₹{range_low:.2f} - ₹{range_high:.2f}
            ✅ *TP-1:* ₹{new_tp1:.2f}
            ✅ *TP-2:* ₹{option_tp2:.2f}
            🎯 *TP-3:* ₹{option_tp3:.2f}"""
                
                messages.append(message)
            
            # Check if we have any messages to send
            if not messages:
                logger.info("No Telegram alerts - no valid options found for filtered breakouts")
                return False
            
            # Add disclaimer with NIFTY filter note
            nifty_note = f"\n_📊 NIFTY Filter Active: CE alerts only when NIFTY>0, PE when NIFTY<0_" if nifty_direction else ""
            disclaimer = f"\n\n_⚠️ Never chase. Honor stops. Educational only - Options trading is risky. Not financial advice._{nifty_note}"
            
            # Send all alerts as single message
            full_message = "\n\n➖➖➖➖➖\n\n".join(messages) + disclaimer
            
            # Send to Telegram
            send_url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': full_message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(send_url, json=payload)
            
            if response.status_code == 200:
                logger.info(f"Telegram alert sent for {len(messages)} symbols (NIFTY filter applied)")
                return True
            else:
                logger.error(f"Telegram send failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_connection(self) -> bool:
        """Test Telegram bot connection and get chat info"""
        try:
            # Test bot token
            test_url = f"{self.base_url}/getMe"
            response = requests.get(test_url)
            if response.status_code != 200:
                print(f"❌ Invalid bot token")
                return False
            
            bot_info = response.json()
            print(f"✅ Bot connected: @{bot_info['result']['username']}")
            
            # Send test message
            send_url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': '✅ Alert system connected successfully!'
            }
            response = requests.post(send_url, json=payload)
            
            if response.status_code == 200:
                print(f"✅ Test message sent to chat {self.chat_id}")
                return True
            else:
                print(f"❌ Failed to send to chat {self.chat_id}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
     
# ==================== ALERT SCANNER ====================
class AlertScanner:
    """Main alert scanner that wraps the Zerodha scanner"""
    
    def __init__(self):
        self.config = AlertConfig()
        self.scanner = TriggerScanner()
        self.options_loader = OptionsDataLoader(self.scanner)  # Pass scanner reference
        
        # CRITICAL: Initialize sector mapper FIRST
        self.sector_mapper = SectorMapper()
        
        # Now pass sector_mapper to all alerters
        self.discord = DiscordAlerter(
            self.config.DISCORD_WEBHOOK, 
            self.options_loader,
            self.sector_mapper  # Pass sector mapper
        )
        
        
        self.telegram = TelegramAlerter(
            self.config.TELEGRAM_BOT_TOKEN,
            self.config.TELEGRAM_CHAT_ID,
            self.options_loader,
            self.sector_mapper  # Pass sector mapper
        )
        
        # IMPORTANT: We need to add the get_option_chain_filtered method to the scanner's client
        # This is a monkey patch to add the method without modifying the original scanner
        self._add_filtered_option_chain_method()
        
        # Initialize stop loss calculator after scanner is ready
        self.stop_loss_calculator = None
    
    def _add_filtered_option_chain_method(self):
        """Add the filtered option chain method to the Zerodha client"""
        def get_option_chain_filtered(self, symbol: str, expiry_date: str = None, 
                                    current_price: float = None, percentage_range: float = 10) -> Dict[str, List[Dict]]:
            """Get option chain filtered to +/-percentage_range% of current price"""
            try:
                # Extract base symbol without exchange
                base_symbol = symbol.split(':')[-1] if ':' in symbol else symbol
                
                # For indices, use special names
                index_map = {
                    'NIFTY': 'NIFTY',
                    'BANKNIFTY': 'BANKNIFTY',
                    'FINNIFTY': 'FINNIFTY',
                    'MIDCPNIFTY': 'MIDCPNIFTY'
                }
                
                # Check if it's an index
                is_index = base_symbol in index_map
                exchange = 'NFO' if is_index else 'NFO'  # Options are on NFO
                
                # Get all NFO instruments for this symbol
                nfo_instruments = self.instruments[
                    (self.instruments['exchange'] == exchange) & 
                    (self.instruments['name'] == base_symbol)
                ]
                
                if nfo_instruments.empty:
                    logger.warning(f"No options found for {symbol}")
                    return {'CE': [], 'PE': []}
                
                # Filter for options only
                options = nfo_instruments[nfo_instruments['instrument_type'].isin(['CE', 'PE'])]
                
                if options.empty:
                    return {'CE': [], 'PE': []}
                
                # Get unique expiries and sort them
                expiries = pd.to_datetime(options['expiry']).dt.date.unique()
                expiries = sorted(expiries)
                today = datetime.now().date()
                
                # CRITICAL CHANGE: Determine which expiries to fetch
                expiries_to_fetch = []
                
                if not expiry_date:
                    # Find future expiries
                    future_expiries = [e for e in expiries if e >= today]
                    
                    if future_expiries:
                        nearest_expiry = future_expiries[0]
                        days_to_nearest = (nearest_expiry - today).days
                        
                        # If <5 days to expiry AND next month exists, fetch BOTH
                        if days_to_nearest < 5 and len(future_expiries) > 1:
                            expiries_to_fetch = future_expiries[:2]  # Current and next
                            logger.info(f"Near expiry ({days_to_nearest} days) - fetching BOTH {future_expiries[0]} and {future_expiries[1]} for {symbol}")
                        else:
                            expiries_to_fetch = [future_expiries[0]]  # Just current
                            logger.debug(f"Normal fetch - using {future_expiries[0]} for {symbol} ({days_to_nearest} days to expiry)")
                    else:
                        # No future expiries
                        return {'CE': [], 'PE': []}
                else:
                    # Specific expiry requested
                    expiries_to_fetch = [expiry_date]
                
                # Filter options for ALL selected expiries at once
                expiry_options = options[pd.to_datetime(options['expiry']).dt.date.isin(expiries_to_fetch)]
                
                # Get current price if not provided
                if current_price is None:
                    quote = self.get_quote(symbol)
                    if not quote:
                        return {'CE': [], 'PE': []}
                    current_price = quote['lastPrice']
                
                # Calculate strike range (+/-percentage_range%)
                min_strike = current_price * (1 - percentage_range / 100)
                max_strike = current_price * (1 + percentage_range / 100)
                
                # Filter options within strike range
                filtered_options = expiry_options[
                    (expiry_options['strike'] >= min_strike) & 
                    (expiry_options['strike'] <= max_strike)
                ]
                
                logger.debug(f"Filtering {symbol} options: {len(expiry_options)} → {len(filtered_options)} "
                        f"(strikes {min_strike:.0f}-{max_strike:.0f}, expiries: {expiries_to_fetch})")
                
                # Organize by type
                ce_options = []
                pe_options = []
                
                # Get quotes for filtered option instruments in batch
                option_symbols = [f"{row['exchange']}:{row['tradingsymbol']}" for _, row in filtered_options.iterrows()]
                
                # Batch fetch quotes (max 200 at a time)
                all_option_quotes = {}
                for i in range(0, len(option_symbols), 200):
                    batch = option_symbols[i:i+200]
                    try:
                        batch_quotes = self.kite.quote(batch)
                        all_option_quotes.update(batch_quotes)
                    except Exception as e:
                        if "Too many requests" in str(e):
                            logger.warning(f"Rate limited on option quotes, waiting 2s...")
                            time.sleep(2.0)
                            try:
                                batch_quotes = self.kite.quote(batch)
                                all_option_quotes.update(batch_quotes)
                            except:
                                logger.error(f"Failed to get option quotes after retry")
                        if i + 200 < len(option_symbols):
                            time.sleep(0.3)  # Delay between batches
                
                # Process each option
                for _, opt in filtered_options.iterrows():
                    option_symbol = f"{opt['exchange']}:{opt['tradingsymbol']}"
                    
                    if option_symbol in all_option_quotes:
                        quote_data = all_option_quotes[option_symbol]
                        
                        # IMPORTANT: Include the expiry in the option info
                        option_info = {
                            'symbol': opt['tradingsymbol'],
                            'strike': opt['strike'],
                            'type': opt['instrument_type'],
                            'expiry': str(opt['expiry']),  # CRITICAL: Include expiry
                            'lot_size': opt['lot_size'],
                            'instrument_token': opt['instrument_token'],
                            'last_price': quote_data.get('last_price', 0),
                            'volume': quote_data.get('volume', 0),
                            'oi': quote_data.get('oi', 0),  # Open Interest
                            'open_interest': quote_data.get('oi', 0),  # Duplicate for compatibility
                            'bid': quote_data.get('depth', {}).get('buy', [{}])[0].get('price', 0),
                            'ask': quote_data.get('depth', {}).get('sell', [{}])[0].get('price', 0),
                            'change': quote_data.get('net_change', 0),
                            'moneyness': 'ATM' if abs(opt['strike'] - current_price) / current_price < 0.01 else
                                        ('ITM' if (opt['instrument_type'] == 'CE' and opt['strike'] < current_price) or
                                                (opt['instrument_type'] == 'PE' and opt['strike'] > current_price) else 'OTM')
                        }
                        
                        # Calculate spread percentage
                        if option_info['bid'] > 0 and option_info['ask'] > 0:
                            spread_pct = (option_info['ask'] - option_info['bid']) / ((option_info['ask'] + option_info['bid']) / 2)
                        else:
                            spread_pct = 1.0
                        option_info['spread_pct'] = round(spread_pct, 3)
                        
                        # Calculate vol/OI ratio
                        if option_info['oi'] > 0:
                            option_info['vol_oi_ratio'] = round(option_info['volume'] / option_info['oi'], 2)
                        else:
                            option_info['vol_oi_ratio'] = 0
                        
                        # Calculate score (same as original)
                        oi_score = min(option_info['oi'] / 10000, 10) if option_info['oi'] > 0 else 0
                        vol_score = min(option_info['volume'] / 1000, 10) if option_info['volume'] > 0 else 0
                        combined_score = (oi_score * 0.7) + (vol_score * 0.3)
                        
                        # Add moneyness bonus
                        if option_info['moneyness'] == 'ATM':
                            combined_score *= 1.2
                        elif option_info['moneyness'] == 'ITM':
                            combined_score *= 0.9
                        
                        option_info['score'] = round(combined_score, 2)
                        
                        if opt['instrument_type'] == 'CE':
                            ce_options.append(option_info)
                        else:
                            pe_options.append(option_info)
                
                # Sort by strike price
                ce_options.sort(key=lambda x: x['strike'])
                pe_options.sort(key=lambda x: x['strike'])
                
                # Log summary
                if len(expiries_to_fetch) > 1:
                    logger.info(f"Fetched {len(ce_options)} CE and {len(pe_options)} PE options across {len(expiries_to_fetch)} expiries for {symbol}")
                
                return {
                    'CE': ce_options,
                    'PE': pe_options,
                    'spot_price': current_price,
                    'expiry_dates': [str(e) for e in expiries_to_fetch]  # Return which expiries were fetched
                }
                
            except Exception as e:
                logger.error(f"Error getting filtered option chain for {symbol}: {e}")
                return {'CE': [], 'PE': []}
        
        # Import pandas for the method
        import pandas as pd
        
        # Bind the method to the scanner's client
        self.scanner.client.get_option_chain_filtered = get_option_chain_filtered.__get__(
            self.scanner.client, self.scanner.client.__class__
        )
        
        # Update the find_best_options method to use the filtered version
        original_find_best_options = self.scanner.find_best_options
        
        def find_best_options_filtered(symbol: str, direction: str, current_price: float) -> List[Dict]:
            """Find best options using filtered option chain"""
            try:
                # Use the filtered option chain method
                chain_data = self.scanner.client.get_option_chain_filtered(symbol, percentage_range=10)
                
                if not chain_data or (not chain_data.get('CE') and not chain_data.get('PE')):
                    return []
                
                options = []
                
                # IMPORTANT: Get BOTH CE and PE options for money flow analysis
                # Process ALL options, not just one type
                
                # Process CE options
                for opt in chain_data.get('CE', []):
                    # Skip if no volume or OI
                    if opt['volume'] == 0 and opt['oi'] == 0:
                        continue
                    
                    # Skip if spread too wide (>15%)
                    if opt.get('spread_pct', 1.0) > 0.15:
                        continue
                    
                    options.append(opt)
                
                # Process PE options
                for opt in chain_data.get('PE', []):
                    # Skip if no volume or OI
                    if opt['volume'] == 0 and opt['oi'] == 0:
                        continue
                    
                    # Skip if spread too wide (>15%)
                    if opt.get('spread_pct', 1.0) > 0.15:
                        continue
                    
                    options.append(opt)
                
                # Sort by score (combination of OI and volume)
                options.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                # Return top 20 options (mix of CE and PE)
                return options[:30]
                
            except Exception as e:
                logger.error(f"Error finding best options for {symbol}: {e}")
                # Fallback to original method
                return original_find_best_options(symbol, direction, current_price)
        
        # Replace the method
        self.scanner.find_best_options = find_best_options_filtered
        
    def _compare_top_10(self, old_top_10: List[Dict], new_top_10: List[Dict]) -> Tuple[bool, Dict]:
        """Compare old and new top 10 lists to detect changes"""
        changes = {
            'new_entries': [],
            'grade_improvements': [],
            'position_changes': [],
            'exited': []
        }
        
        # Create lookup maps
        old_map = {b['symbol']: {'data': b, 'position': i+1} for i, b in enumerate(old_top_10)}
        new_map = {b['symbol']: {'data': b, 'position': i+1} for i, b in enumerate(new_top_10)}
        
        # Check for new entries and grade improvements
        for symbol, new_info in new_map.items():
            if symbol not in old_map:
                # New entry
                changes['new_entries'].append({
                    'symbol': symbol,
                    'position': new_info['position'],
                    'direction': new_info['data']['direction'],
                    'grade': new_info['data']['quality_grade']
                })
            else:
                # Check for grade improvement
                old_grade = old_map[symbol]['data']['quality_grade']
                new_grade = new_info['data']['quality_grade']
                
                grade_order = ['D', 'C', 'B', 'A', 'A+']
                if grade_order.index(new_grade) > grade_order.index(old_grade):
                    changes['grade_improvements'].append({
                        'symbol': symbol,
                        'old_grade': old_grade,
                        'new_grade': new_grade,
                        'position': new_info['position']
                    })
                
                # Check for position change
                old_pos = old_map[symbol]['position']
                new_pos = new_info['position']
                if old_pos != new_pos:
                    changes['position_changes'].append({
                        'symbol': symbol,
                        'old_position': old_pos,
                        'new_position': new_pos
                    })
        
        # Check for exited symbols
        for symbol, old_info in old_map.items():
            if symbol not in new_map:
                changes['exited'].append({
                    'symbol': symbol,
                    'old_position': old_info['position']
                })
        
        # Determine if there are significant changes
        has_changes = bool(changes['new_entries'] or changes['grade_improvements'] or changes['exited'])
        
        return has_changes, changes
    
    def _calculate_score_changes(self, old_top_10: List[Dict], new_top_10: List[Dict]) -> Dict:
        """Calculate score changes for symbols in top 10"""
        score_changes = {
            'symbols_with_increases': [],
            'avg_increase': 0
        }
        
        # Create lookup map for old scores
        old_scores = {b['symbol']: b['strength_score'] for b in old_top_10}
        
        # Check each symbol in new top 10
        total_increase = 0
        count_increases = 0
        
        for breakout in new_top_10:
            symbol = breakout['symbol']
            new_score = breakout['strength_score']
            
            # Update score tracking
            old_score = self.config.score_tracking.get(symbol, new_score)
            self.config.score_tracking[symbol] = new_score
            
            # Check if score increased
            if symbol in old_scores:
                old_score = old_scores[symbol]
                increase = new_score - old_score
                
                if increase >= self.config.score_increase_threshold:
                    score_changes['symbols_with_increases'].append({
                        'symbol': symbol,
                        'old_score': old_score,
                        'new_score': new_score,
                        'increase': increase
                    })
                    total_increase += increase
                    count_increases += 1
        
        # Calculate average increase
        if count_increases > 0:
            score_changes['avg_increase'] = total_increase / count_increases
        
        return score_changes
        
    def run_continuous(self, tickers: List[str], interval_seconds: int = 20, clear_cache: bool = True):
        """Run scanner continuously and send alerts only on top 10 changes"""
        
        # Import timezone handling
        import pytz
        indian_tz = pytz.timezone('Asia/Kolkata')
        
        print("=" * 60)
        print("AUTOMATED ALERT SCANNER - INDIAN MARKETS")
        print("WITH SECTOR ALIGNMENT CONFIRMATION")
        print("=" * 60)
        print(f"Scanning {len(tickers)} tickers every {interval_seconds} seconds")
        print(f"Tracking: TOP {self.config.TOP_ALERTS} positions")
        print(f"Alerts: Only on changes (new entries, grade improvements, exits)")
        print(f"📈 OI Filter: Only symbols with OI increases >= {self.config.MIN_OI_CHANGE_PCT}%")
        print(f"📢 Count Filter: Only symbols with cumulative count > {self.config.MIN_CUMULATIVE_COUNT}")
        print(f"📅 Once/Day Filter: Each symbol alerted only once per trading day per platform")
        print(f"💪 Score Tracking: Minimum increase {self.config.score_increase_threshold} points")
        print(f"🔄 OI Comparison: Night OI vs Realtime API OI")
        print(f"🎯 Options Range: Only fetching +/-10% strikes for speed")
        print(f"💰 RUPEE FLOW: Advanced directional flow analysis")
        print(f"🛡️ HEDGE DETECTION: Filters out hedging positions")
        print(f"📊 POSITION ANALYSIS: ATM/Near-money focus for directional trades")
        print(f"🛑 STOP LOSS: 5min close below/above 9EMA included in alerts")
        print(f"🎯 DIRECTION MATCH: Breakout direction MUST match flow direction")
        print(f"💯 FLOW CONFIDENCE: Only alerts with flow confidence >= 65%")
        print(f"📊 SECTOR ALIGNMENT: Stock direction MUST match sector direction")
        print(f"Discord: {'Enabled' if self.config.DISCORD_WEBHOOK else 'Disabled'}")
        print(f"Telegram: {'Enabled' if self.config.TELEGRAM_BOT_TOKEN else 'Disabled'}")
        print(f"Volume profiles: {'Fresh data every scan (cache cleared)' if clear_cache else 'Using cached data'}")
        print(f"OI Changes: {'Enabled - comparing NIGHT data with REALTIME API' if self.options_loader.data_dir.exists() else 'No options data found'}")
        
        # Show timezone info
        local_time = datetime.now()
        indian_time = datetime.now(indian_tz)
        print(f"\nTimezone Info:")
        print(f"Your local time: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Indian time: {indian_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print("=" * 60)
        
        # Clear volume profiles at startup for fresh start
        if clear_cache:
            volume_profiles_dir = Path("zerodha_trigger_scanner/volume_profiles")
            if volume_profiles_dir.exists():
                try:
                    shutil.rmtree(volume_profiles_dir)
                    volume_profiles_dir.mkdir(parents=True, exist_ok=True)
                    print("\n🧹 Cleared volume profiles at startup for fresh start")
                except Exception as e:
                    logger.error(f"Failed to clear volume profiles at startup: {e}")
        
        # Login to Zerodha
        if not self.scanner.login():
            print("Failed to authenticate with Zerodha API")
            return
        
        # Initialize stop loss calculator after successful login
        self.stop_loss_calculator = StopLossCalculator(self.scanner.client)
        self.discord.stop_loss_calculator = self.stop_loss_calculator
        self.telegram.stop_loss_calculator = self.stop_loss_calculator
        print("✅ Stop Loss calculator initialized (5min 9EMA)")
        
        # CRITICAL: Fetch initial sector data
        print("📊 Fetching sector index data...")
        self.sector_mapper.fetch_sector_data(self.scanner.client)
            
        scan_count = 0
        
        try:
            while True:
                scan_count += 1
                # Use Indian time for all checks
                current_time = datetime.now(indian_tz)
                print(f"\n[Scan #{scan_count}] {current_time.strftime('%H:%M:%S IST')}")
                
                # CRITICAL: Refresh sector data each scan
                self.sector_mapper.fetch_sector_data(self.scanner.client)
                
                # Load options data at the start of each scan
                self.options_loader.load_data()
                self.options_loader.clear_realtime_cache()  # Clear cache from previous scan
                if self.options_loader.night_data:
                    print(f"📊 Night OI data loaded - {len(self.options_loader.night_data.get('options_data', {}))} symbols")
                    print(f"📡 Will fetch realtime OI from API for comparison (with caching)")
                    print(f"🎯 Only fetching +/-10% strikes for faster performance")
                    print(f"💰 Advanced money flow analysis with directional vs hedge detection")
                    print(f"🛡️ Position type analysis for cleaner signals")
                    print(f"🎯 Direction match required: Breakout = Flow")
                    print(f"💯 Min flow confidence: 65%")
                    print(f"📊 Sector alignment required: Stock dir = Sector dir")
                
                # Clear top 10 and daily alerted tickers at market open (9:15 AM IST) for fresh start
                if current_time.hour == 9 and current_time.minute == 15 and len(self.config.current_top_10) > 0:
                    print("🔄 Market open - clearing previous top 10 and daily alerted tickers for fresh start")
                    self.config.current_top_10.clear()
                    self.config.alert_count = 0
                    self.config.score_tracking.clear()
                    self.config.daily_alert_summary.clear()
                    self.config.discord_alerted_tickers.clear()  # Clear Discord-specific
                    self.config.telegram_alerted_tickers.clear()  # Clear Telegram-specific
                    self.config.daily_alerted_tickers.clear()  # Clear combined
                    self.config.filter_reasons.clear()  # Clear filter reasons
                
                # Check if market is open (Indian market hours)
                market_open_time = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
                market_close_time = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
                
                # Also check if it's a weekday (Monday=0, Sunday=6)
                if current_time.weekday() in [5, 6]:  # Saturday or Sunday
                    print(f"Weekend in India. Market closed.")
                    print(f"Next market open: Monday 9:15 AM IST")
                    # Sleep for the interval and continue
                    time.sleep(interval_seconds)
                    continue
                
                if current_time.time() < market_open_time.time():
                    wait_seconds = (market_open_time - current_time).total_seconds()
                    print(f"Market not open yet. Opens at 9:15 AM IST.")
                    print(f"Current Indian time: {current_time.strftime('%H:%M:%S IST')}")
                    print(f"Waiting {int(wait_seconds/60)} minutes until market open...")
                    time.sleep(min(wait_seconds, interval_seconds))
                    continue
                elif current_time.time() > market_close_time.time():
                    print(f"\n📊 Market closed for the day at 3:30 PM IST.")
                    print(f"Current Indian time: {current_time.strftime('%H:%M:%S IST')}")
                    if self.config.alert_count > 0:
                        print(f"\nToday's summary:")
                        print(f"Total alerts sent: {self.config.alert_count}")
                        print(f"Unique symbols alerted (Discord): {len(self.config.discord_alerted_tickers)}")
                        print(f"Unique symbols alerted (Telegram): {len(self.config.telegram_alerted_tickers)}")
                        print(f"Total symbols tracked: {len(self.config.daily_alert_summary)}")
                        print(f"\nSymbols alerted today (Discord):")
                        for symbol in sorted(self.config.discord_alerted_tickers):
                            count = self.config.daily_alert_summary.get(symbol, 0)
                            print(f"  • {symbol} (count: {count})")
                        print(f"\nSymbols alerted today (Telegram):")
                        for symbol in sorted(self.config.telegram_alerted_tickers):
                            count = self.config.daily_alert_summary.get(symbol, 0)
                            print(f"  • {symbol} (count: {count})")
                        print(f"\nFinal Top 10:")
                        for i, b in enumerate(self.config.current_top_10, 1):
                            count = self.config.daily_alert_summary.get(b['symbol'], 0)
                            print(f"  {i}. {b['symbol']}: {b['direction']} [{b['quality_grade']}] Score: {b['strength_score']:.0f} (count: {count})")
                    else:
                        print("No changes in top 10 today - no alerts sent.")
                    print("\nMarket will open tomorrow at 9:15 AM IST.")
                    print("\nStopping scanner.")
                    break
                
                # Show market is open
                print(f"✅ Market is OPEN (9:15 AM - 3:30 PM IST)")
                
                try:
                    # Run scan
                    results = self.scanner.scan_tickers(tickers)
                    
                    if results and results['breakouts']:
                        # Sort ALL breakouts by strength score
                        all_breakouts = results['breakouts'].copy()
                        all_breakouts.sort(key=lambda x: x['strength_score'], reverse=True)
                        
                        # Get top N breakouts
                        new_top_10 = all_breakouts[:self.config.TOP_ALERTS]
                        
                        print(f"Found {len(all_breakouts)} total breakouts")
                        
                        if new_top_10:
                            # Calculate score changes
                            score_changes = self._calculate_score_changes(self.config.current_top_10, new_top_10)
                            
                            # Update daily alert summary for all symbols in top 10
                            for breakout in new_top_10:
                                self.config.daily_alert_summary[breakout['symbol']] += 1
                            
                            # Compare with previous top 10
                            if not self.config.current_top_10:
                                # First scan of the day
                                self.config.current_top_10 = new_top_10.copy()
                                self.config.alert_count += 1
                                
                                print(f"\n🚨 INITIAL TOP 10 ALERT!")
                                
                                # Send initial alert with all filters - Discord first
                                if self.config.DISCORD_WEBHOOK:
                                    if self.discord.send_alert(new_top_10, results['options'], {}, 
                                                            self.config.alert_count, self.config.MIN_OI_CHANGE_PCT,
                                                            score_changes, dict(self.config.daily_alert_summary),
                                                            self.config.discord_alerted_tickers,  # Use Discord-specific
                                                            self.config.filter_reasons):
                                        print("✅ Discord alert sent (Direction match + High confidence + Sector aligned)")
                                    else:
                                        print("❌ Discord alert failed")
                                
                                # Add Telegram alert with its own tracking
                                if self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID:
                                    if self.telegram.send_alert(new_top_10, results['options'], {}, 
                                                            self.config.alert_count, self.config.MIN_OI_CHANGE_PCT,
                                                            score_changes, dict(self.config.daily_alert_summary),
                                                            self.config.telegram_alerted_tickers,  # Use Telegram-specific
                                                            self.config.filter_reasons):
                                        print("✅ Telegram alert sent (Direction match + High confidence + Sector aligned)")
                                    else:
                                        print("❌ Telegram alert failed")
                                
                                # Update combined set after both platforms
                                self.config.daily_alerted_tickers = self.config.discord_alerted_tickers.union(self.config.telegram_alerted_tickers)
                                
                                # Print initial top 10
                                print("\nInitial Top 10:")
                                for i, b in enumerate(new_top_10, 1):
                                    dormant_flag = " 🎯 DORMANT" if b.get('is_dormant_breakout', False) else ""
                                    count = self.config.daily_alert_summary.get(b['symbol'], 0)
                                    discord_alerted = "D✅" if b['symbol'] in self.config.discord_alerted_tickers else ""
                                    telegram_alerted = "T✅" if b['symbol'] in self.config.telegram_alerted_tickers else ""
                                    alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "⏳"
                                    reason = f" ({self.config.filter_reasons.get(b['symbol'], '')})" if b['symbol'] in self.config.filter_reasons else ""
                                    
                                    # Get sector info
                                    is_aligned, sector_info = self.sector_mapper.is_sector_aligned(b['symbol'], b['direction'])
                                    sector_status = "✅" if is_aligned else "❌"
                                    sector_name = sector_info.get('sector', 'N/A')
                                    
                                    print(f"  {i}. {b['symbol']}: {b['direction'].upper()} "
                                        f"[{b['quality_grade']}] Score: {b['strength_score']:.1f} @ ₹{b['current_price']:.2f} "
                                        f"(count: {count}) {alerted}{reason} Sector:{sector_name}{sector_status}{dormant_flag}")
                            else:
                                # Compare with previous top 10
                                has_changes, changes = self._compare_top_10(self.config.current_top_10, new_top_10)
                                
                                if has_changes:
                                    # Update current top 10
                                    self.config.current_top_10 = new_top_10.copy()
                                    self.config.alert_count += 1
                                    
                                    print(f"\n🚨 TOP 10 CHANGES DETECTED!")
                                    
                                    # Print changes summary
                                    if changes['new_entries']:
                                        print(f"🆕 New entries: {len(changes['new_entries'])}")
                                        for entry in changes['new_entries']:
                                            count = self.config.daily_alert_summary.get(entry['symbol'], 0)
                                            discord_alerted = "D✅" if entry['symbol'] in self.config.discord_alerted_tickers else ""
                                            telegram_alerted = "T✅" if entry['symbol'] in self.config.telegram_alerted_tickers else ""
                                            alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "📅"
                                            reason = f" ({self.config.filter_reasons.get(entry['symbol'], '')})" if entry['symbol'] in self.config.filter_reasons else ""
                                            print(f"   - #{entry['position']}: {entry['symbol']} ({entry['direction']}) [{entry['grade']}] (count: {count}) {alerted}{reason}")
                                    
                                    if changes['grade_improvements']:
                                        print(f"⬆️  Grade improvements: {len(changes['grade_improvements'])}")
                                        for imp in changes['grade_improvements']:
                                            count = self.config.daily_alert_summary.get(imp['symbol'], 0)
                                            discord_alerted = "D✅" if imp['symbol'] in self.config.discord_alerted_tickers else ""
                                            telegram_alerted = "T✅" if imp['symbol'] in self.config.telegram_alerted_tickers else ""
                                            alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "📅"
                                            reason = f" ({self.config.filter_reasons.get(imp['symbol'], '')})" if imp['symbol'] in self.config.filter_reasons else ""
                                            print(f"   - {imp['symbol']}: {imp['old_grade']} → {imp['new_grade']} (count: {count}) {alerted}{reason}")
                                    
                                    if changes['exited']:
                                        print(f"👋 Exited top 10: {len(changes['exited'])}")
                                        for ex in changes['exited']:
                                            print(f"   - {ex['symbol']} (was #{ex['old_position']})")
                                    
                                    if score_changes['symbols_with_increases']:
                                        print(f"💪 Score increases: {len(score_changes['symbols_with_increases'])}")
                                        for sc in score_changes['symbols_with_increases']:
                                            count = self.config.daily_alert_summary.get(sc['symbol'], 0)
                                            discord_alerted = "D✅" if sc['symbol'] in self.config.discord_alerted_tickers else ""
                                            telegram_alerted = "T✅" if sc['symbol'] in self.config.telegram_alerted_tickers else ""
                                            alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "📅"
                                            reason = f" ({self.config.filter_reasons.get(sc['symbol'], '')})" if sc['symbol'] in self.config.filter_reasons else ""
                                            print(f"   - {sc['symbol']}: +{sc['increase']:.1f} ({sc['old_score']:.1f} → {sc['new_score']:.1f}) (count: {count}) {alerted}{reason}")
                                    
                                    # Send alert with all filters - Discord first
                                    if self.config.DISCORD_WEBHOOK:
                                        if self.discord.send_alert(new_top_10, results['options'], changes, 
                                                                self.config.alert_count, self.config.MIN_OI_CHANGE_PCT,
                                                                score_changes, dict(self.config.daily_alert_summary),
                                                                self.config.discord_alerted_tickers,  # Use Discord-specific
                                                                self.config.filter_reasons):
                                            print("✅ Discord alert sent (All filters + Direction match + High confidence + Sector aligned)")
                                        else:
                                            print("❌ Discord alert failed")
                                    
                                    # Add Telegram alert with its own tracking
                                    if self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID:
                                        if self.telegram.send_alert(new_top_10, results['options'], changes, 
                                                                self.config.alert_count, self.config.MIN_OI_CHANGE_PCT,
                                                                score_changes, dict(self.config.daily_alert_summary),
                                                                self.config.telegram_alerted_tickers,  # Use Telegram-specific
                                                                self.config.filter_reasons):
                                            print("✅ Telegram alert sent (All filters + Sector aligned)")
                                        else:
                                            print("❌ Telegram alert failed")
                                    
                                    # Update combined set after both platforms
                                    self.config.daily_alerted_tickers = self.config.discord_alerted_tickers.union(self.config.telegram_alerted_tickers)
                                    
                                else:
                                    print("No changes in top 10 - no alert sent")
                                    
                                    # Show current top 10 summary
                                    print("\nCurrent Top 10 (unchanged):")
                                    for i, b in enumerate(self.config.current_top_10[:3], 1):
                                        count = self.config.daily_alert_summary.get(b['symbol'], 0)
                                        discord_alerted = "D✅" if b['symbol'] in self.config.discord_alerted_tickers else ""
                                        telegram_alerted = "T✅" if b['symbol'] in self.config.telegram_alerted_tickers else ""
                                        alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "⏳"
                                        reason = f" ({self.config.filter_reasons.get(b['symbol'], '')})" if b['symbol'] in self.config.filter_reasons else ""
                                        
                                        # Get sector info
                                        is_aligned, sector_info = self.sector_mapper.is_sector_aligned(b['symbol'], b['direction'])
                                        sector_status = "✅" if is_aligned else "❌"
                                        sector_name = sector_info.get('sector', 'N/A')
                                        
                                        print(f"  {i}. {b['symbol']} [{b['quality_grade']}] Score: {b['strength_score']:.0f} "
                                            f"(count: {count}) {alerted}{reason} Sector:{sector_name}{sector_status}")
                                    if len(self.config.current_top_10) > 3:
                                        print(f"  ... and {len(self.config.current_top_10) - 3} more")
                                    
                                    # Show daily cumulative summary
                                    if self.config.daily_alert_summary:
                                        discord_alerted = len(self.config.discord_alerted_tickers)
                                        telegram_alerted = len(self.config.telegram_alerted_tickers)
                                        symbols_with_reasons = len(self.config.filter_reasons)
                                        print(f"\n📊 Daily Summary: {len(self.config.daily_alert_summary)} total symbols, "
                                            f"D:{discord_alerted} T:{telegram_alerted} alerted, "
                                            f"{symbols_with_reasons} filtered, "
                                            f"{sum(self.config.daily_alert_summary.values())} total alerts")
                    else:
                        print("No breakouts detected")
                    
                except Exception as e:
                    logger.error(f"Scan error: {e}")
                    traceback.print_exc()
                
                # Clear volume profiles cache for fresh data next scan
                if clear_cache:
                    volume_profiles_dir = Path("zerodha_trigger_scanner/volume_profiles")
                    if volume_profiles_dir.exists():
                        try:
                            shutil.rmtree(volume_profiles_dir)
                            # Recreate the directory immediately
                            volume_profiles_dir.mkdir(parents=True, exist_ok=True)
                            print("\n🧹 Cleared volume profiles cache for fresh data")
                        except Exception as e:
                            logger.error(f"Failed to clear volume profiles: {e}")
                
                # Wait for next scan
                print(f"\nNext scan in {interval_seconds} seconds...", end='', flush=True)
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n\n✋ Alert scanner stopped")
            print(f"Total scans: {scan_count}")
            print(f"Total alerts sent: {self.config.alert_count}")
            print(f"Unique symbols alerted (Discord): {len(self.config.discord_alerted_tickers)}")
            print(f"Unique symbols alerted (Telegram): {len(self.config.telegram_alerted_tickers)}")
            
            if self.config.discord_alerted_tickers or self.config.telegram_alerted_tickers:
                print("\nSymbols alerted today (Discord):")
                for symbol in sorted(self.config.discord_alerted_tickers):
                    count = self.config.daily_alert_summary.get(symbol, 0)
                    print(f"  • {symbol} (count: {count})")
                
                print("\nSymbols alerted today (Telegram):")
                for symbol in sorted(self.config.telegram_alerted_tickers):
                    count = self.config.daily_alert_summary.get(symbol, 0)
                    print(f"  • {symbol} (count: {count})")
            
            if self.config.current_top_10:
                print("\nFinal Top 10:")
                for i, b in enumerate(self.config.current_top_10, 1):
                    count = self.config.daily_alert_summary.get(b['symbol'], 0)
                    discord_alerted = "D✅" if b['symbol'] in self.config.discord_alerted_tickers else ""
                    telegram_alerted = "T✅" if b['symbol'] in self.config.telegram_alerted_tickers else ""
                    alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "⏳"
                    reason = f" ({self.config.filter_reasons.get(b['symbol'], '')})" if b['symbol'] in self.config.filter_reasons else ""
                    print(f"  {i}. {b['symbol']}: {b['direction']} [{b['quality_grade']}] Score: {b['strength_score']:.0f} (count: {count}) {alerted}{reason}")
            
            if self.config.daily_alert_summary:
                print(f"\n📊 Daily Summary:")
                print(f"Total unique symbols: {len(self.config.daily_alert_summary)}")
                print(f"Symbols alerted Discord: {len(self.config.discord_alerted_tickers)}")
                print(f"Symbols alerted Telegram: {len(self.config.telegram_alerted_tickers)}")
                print(f"Symbols filtered: {len(self.config.filter_reasons)}")
                print(f"Total alerts: {sum(self.config.daily_alert_summary.values())}")
                print("\nTop 10 most tracked symbols:")
                sorted_symbols = sorted(self.config.daily_alert_summary.items(), 
                                    key=lambda x: x[1], reverse=True)
                for symbol, count in sorted_symbols[:10]:
                    discord_alerted = "D✅" if symbol in self.config.discord_alerted_tickers else ""
                    telegram_alerted = "T✅" if symbol in self.config.telegram_alerted_tickers else ""
                    alerted = f"{discord_alerted}{telegram_alerted}" if (discord_alerted or telegram_alerted) else "❌"
                    reason = f" ({self.config.filter_reasons.get(symbol, '')})" if symbol in self.config.filter_reasons else ""
                    print(f"  {symbol}: {count} alerts {alerted}{reason}")
    
# ==================== MAIN ====================
def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Automated Alert Scanner for Zerodha Breakouts with Sector Alignment')
    parser.add_argument('-f', '--file', default='NSE_FO.txt', help='Ticker file')
    parser.add_argument('-t', '--tickers', nargs='+', help='Ticker symbols')
    parser.add_argument('-i', '--interval', type=int, default=10, help='Scan interval in seconds (default: 10)')
    parser.add_argument('--discord', help='Discord webhook URL (overrides env var)')
    parser.add_argument('--telegram', nargs=2, metavar=('TOKEN', 'CHAT_ID'), 
                       help='Telegram bot token and chat ID')
    parser.add_argument('--test', action='store_true', help='Send test alert and exit')
    parser.add_argument('--keep-cache', action='store_true', help='Keep volume profiles cache between scans')
    parser.add_argument('--oi-threshold', type=float, default=1.0, help='Minimum OI increase percentage for alerts (default: 1.0)')
    parser.add_argument('--score-threshold', type=float, default=2.0, help='Minimum score increase to track (default: 2.0)')
    parser.add_argument('--count-threshold', type=int, default=2, help='Minimum cumulative count for alerts (default: 2)')
    parser.add_argument('--flow-confidence', type=float, default=65.0, help='Minimum flow confidence percentage (default: 65.0)')
    
    args = parser.parse_args()
    
    # Override environment variables if provided
    if args.discord:
        os.environ['DISCORD_WEBHOOK_URL'] = args.discord
    if args.telegram:
        os.environ['TELEGRAM_BOT_TOKEN'] = args.telegram[0]
        os.environ['TELEGRAM_CHAT_ID'] = args.telegram[1]
    
    # Initialize scanner
    alert_scanner = AlertScanner()
    
    # Set thresholds if provided
    alert_scanner.config.MIN_OI_CHANGE_PCT = args.oi_threshold
    alert_scanner.config.score_increase_threshold = args.score_threshold
    alert_scanner.config.MIN_CUMULATIVE_COUNT = args.count_threshold
    alert_scanner.config.MIN_FLOW_CONFIDENCE = args.flow_confidence / 100.0  # Convert to decimal
    
    # Test mode
    if args.test:
        print("Sending test alert...")
        
        # Load options data for test
        alert_scanner.options_loader.load_data()
        
        # Initialize dummy stop loss calculator for test
        class DummyStopLossCalculator:
            def calculate_5min_9ema_sl(self, symbol, direction, price, atr27=None):
                if direction == 'bullish':
                    sl_price = price * 0.9925  # 0.75% below
                    return {
                        'sl_price': round(sl_price, 2),
                        'sl_text': f"5min close below ₹{sl_price:.2f} (9EMA)",
                        'sl_distance': round(price - sl_price, 2),
                        'sl_percentage': 0.75,
                        'ema_value': round(sl_price, 2),
                        'method': '5min_9ema'
                    }
                else:
                    sl_price = price * 1.0075  # 0.75% above
                    return {
                        'sl_price': round(sl_price, 2),
                        'sl_text': f"5min close above ₹{sl_price:.2f} (9EMA)",
                        'sl_distance': round(sl_price - price, 2),
                        'sl_percentage': 0.75,
                        'ema_value': round(sl_price, 2),
                        'method': '5min_9ema'
                    }
        
        alert_scanner.discord.stop_loss_calculator = DummyStopLossCalculator()
        alert_scanner.telegram.stop_loss_calculator = DummyStopLossCalculator()
        
        # Create dummy data
        test_breakouts = [{
            'symbol': 'NSE:RELIANCE',
            'direction': 'bullish',
            'current_price': 2850.50,
            'breakout_time': '10:30',
            'upper_trigger': 2825.75,
            'lower_trigger': 2795.25,
            'yesterday_high': 2820.50,
            'yesterday_low': 2780.80,
            'atr27': 35.15,
            'volume_ratio': 2.5,
            'volume_percentile': 85,
            'vs_expected_pct': 45.2,
            'vs_sector_pct': 23.5,
            'volume_confidence': 82.5,
            'adaptive_threshold': 1.25,
            'is_unusual_volume': True,
            'dormancy_score': 72.5,
            'is_dormant_breakout': True,
            'tightness_ratio': 1.8,
            'strength_score': 85.5,
            'quality_grade': 'A',
            'extension_pct': 1.2
        }]
        
        test_options = {
            'NSE:RELIANCE': [{
                'symbol': 'RELIANCE25JAN2900CE',
                'type': 'CE',
                'strike': 2900,
                'expiry': '2025-01-30',
                'lot_size': 250,
                'volume': 12500,
                'open_interest': 54300,
                'oi': 54300,  # Added for compatibility
                'last_price': 35.25,
                'bid': 34.50,
                'ask': 36.00,
                'spread_pct': 0.042,
                'vol_oi_ratio': 0.23,
                'moneyness': 'OTM',
                'score': 8.5
            }]
        }
        
        test_changes = {
            'new_entries': [{'symbol': 'NSE:RELIANCE', 'position': 1, 'direction': 'bullish', 'grade': 'A'}],
            'grade_improvements': [],
            'position_changes': [],
            'exited': []
        }
        
        test_score_changes = {
            'symbols_with_increases': [
                {'symbol': 'NSE:RELIANCE', 'old_score': 82.5, 'new_score': 85.5, 'increase': 3.0}
            ],
            'avg_increase': 3.0
        }
        
        test_daily_summary = {
            'NSE:RELIANCE': 5,
            'NSE:TCS': 3,
            'NSE:INFY': 2
        }
        
        test_daily_alerted = set(['NSE:TCS'])
        
        test_filter_reasons = {
            'NSE:INFY': 'count≤2',
            'NSE:TCS': 'alerted'
        }
        
        # Set dummy sector data
        alert_scanner.sector_mapper.sector_data = {
            'CNXENERGY': {
                'symbol': 'NSE:CNXENERGY',
                'last_price': 15000,
                'change_pct': 1.5,
                'direction': 'bullish'
            }
        }
        
        if alert_scanner.discord.send_alert(test_breakouts, test_options, test_changes, 1, 
                                           alert_scanner.config.MIN_OI_CHANGE_PCT,
                                           test_score_changes, test_daily_summary, test_daily_alerted,
                                           test_filter_reasons):
            print("✅ Test Discord alert sent")
        else:
            print("❌ Test Discord alert failed")
        
        # Test Telegram
        if alert_scanner.config.TELEGRAM_BOT_TOKEN and alert_scanner.config.TELEGRAM_CHAT_ID:
            if alert_scanner.telegram.send_alert(test_breakouts, test_options, test_changes, 1, 
                                               alert_scanner.config.MIN_OI_CHANGE_PCT,
                                               test_score_changes, test_daily_summary, test_daily_alerted,
                                               test_filter_reasons):
                print("✅ Test Telegram alert sent")
            else:
                print("❌ Test Telegram alert failed")
            
        return
    
    # Load tickers
    tickers = []
    
    if args.tickers:
        # Add NSE prefix if not present
        tickers = []
        for t in args.tickers:
            t = t.upper().strip()
            if ':' not in t:
                t = f"NSE:{t}"
            tickers.append(t)
    else:
        # Load from file (same logic as Zerodha scanner)
        from pathlib import Path
        ticker_file = Path(args.file)
        
        search_paths = [
            ticker_file,
            Path.cwd() / ticker_file,
            Path.home() / "Desktop" / ticker_file,
            Path("zerodha_trigger_scanner") / ticker_file,
        ]
        
        for path in search_paths:
            if path.exists():
                content = path.read_text().strip()
                if ',' in content:
                    raw_tickers = [t.strip() for t in content.split(',')]
                else:
                    raw_tickers = [t.strip() for t in content.split('\n')]
                
                for ticker in raw_tickers:
                    if not ticker:
                        continue
                    # Keep as is if already has exchange prefix
                    if ':' not in ticker:
                        ticker = f"NSE:{ticker}"
                    ticker = ticker.upper().strip()
                    if ticker and ticker not in tickers:
                        tickers.append(ticker)
                
                print(f"Loaded {len(tickers)} tickers from {path}")
                break
    
    if not tickers:
        print("No tickers loaded! Please provide tickers via -t or -f")
        return
    
    # Run continuous scanner
    alert_scanner.run_continuous(tickers, interval_seconds=args.interval, clear_cache=not args.keep_cache)

if __name__ == "__main__":
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    main()