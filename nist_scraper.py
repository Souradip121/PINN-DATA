# nist_scraper.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import time
import re
import json
from urllib.parse import urlencode, quote
import warnings
warnings.filterwarnings('ignore')

class NISTChemicalDataScraper:
    def __init__(self, delay=1.0):
        """
        NIST Chemistry WebBook scraper
        
        Args:
            delay (float): Delay between requests to be respectful
        """
        self.base_url = "https://webbook.nist.gov/cgi/cbook.cgi"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.delay = delay
        
    def search_compound(self, formula_or_name):
        """Search for a compound and get its ID"""
        # Try multiple search strategies
        search_attempts = [
            {'Formula': formula_or_name, 'NoIon': 'on', 'Units': 'SI'},
            {'Name': formula_or_name, 'NoIon': 'on', 'Units': 'SI'},
            {'Formula': formula_or_name, 'Units': 'SI'},
            {'Name': formula_or_name, 'Units': 'SI'}
        ]
        
        for params in search_attempts:
            try:
                response = self.session.get(self.base_url, params=params, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for compound links with more flexible patterns
                compound_links = soup.find_all('a', href=re.compile(r'ID=C\d+'))
                
                if compound_links:
                    href = compound_links[0]['href']
                    compound_id = re.search(r'ID=(C\d+)', href).group(1)
                    print(f"Found compound ID: {compound_id} for {formula_or_name}")
                    return compound_id
                    
                # Also check for direct compound pages
                if 'ID=C' in response.url:
                    compound_id = re.search(r'ID=(C\d+)', response.url)
                    if compound_id:
                        return compound_id.group(1)
                        
            except Exception as e:
                print(f"Search attempt failed for {formula_or_name}: {e}")
                continue
        
        print(f"No compound found for: {formula_or_name}")
        return None

    def get_thermodynamic_data(self, compound_id):
        """Get thermodynamic data for a compound"""
        params = {
            'ID': compound_id,
            'Mask': '1',  # Thermochemical data
            'Type': 'JANAFG',  # JANAF tables
            'Units': 'SI'
        }
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            return self._parse_thermodynamic_tables(soup)
            
        except Exception as e:
            print(f"Error getting thermodynamic data for {compound_id}: {e}")
            return None
    
    def get_phase_change_data(self, compound_id):
        """Get phase change data (boiling point, melting point, etc.)"""
        params = {
            'ID': compound_id,
            'Mask': '4',  # Phase change data
            'Units': 'SI'
        }
        
        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            return self._parse_phase_change_data(soup)
            
        except Exception as e:
            print(f"Error getting phase change data for {compound_id}: {e}")
            return {}
    
    def _parse_thermodynamic_tables(self, soup):
        """Parse thermodynamic data tables with improved robustness"""
        data = {
            'temperature': [],
            'heat_capacity': [],
            'entropy': [],
            'enthalpy_minus_h298': [],
            'gibbs_free_energy': []
        }
        
        # Look for thermodynamic tables
        tables = soup.find_all('table')
        
        for table in tables:
            # Check if this is a thermodynamic table
            headers = table.find_all('th')
            if not headers:
                continue
                
            header_text = ' '.join([th.get_text().strip() for th in headers])
            
            # More comprehensive keyword matching
            thermo_keywords = [
                'temperature', 'heat capacity', 'entropy', 'cp°', 'cp',
                'enthalpy', 'gibbs', 'janaf', 'thermodynamic'
            ]
            
            if any(keyword in header_text.lower() for keyword in thermo_keywords):
                rows = table.find_all('tr')[1:]  # Skip header row
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:  # At least temperature and one property
                        try:
                            # Try to parse temperature from first column
                            temp = self._parse_number(cells[0].get_text().strip())
                            if temp is None or temp < 50 or temp > 5000:  # Reasonable temperature range
                                continue
                            
                            # Try to find heat capacity in any column
                            cp = None
                            entropy = None
                            enthalpy = None
                            gibbs = None
                            
                            for i, cell in enumerate(cells[1:], 1):
                                value = self._parse_number(cell.get_text().strip())
                                if value is not None:
                                    if i == 1:  # Usually Cp
                                        cp = value
                                    elif i == 2:  # Usually entropy
                                        entropy = value
                                    elif i == 3:  # Usually Gibbs function
                                        gibbs = value
                                    elif i == 4:  # Usually enthalpy
                                        enthalpy = value
                            
                            if cp is not None and cp > 0:  # Valid heat capacity
                                data['temperature'].append(temp)
                                data['heat_capacity'].append(cp)
                                data['entropy'].append(entropy)
                                data['enthalpy_minus_h298'].append(enthalpy)
                                data['gibbs_free_energy'].append(gibbs)
                                
                        except Exception as e:
                            continue
        
        return pd.DataFrame(data) if data['temperature'] else None
    
    def _parse_phase_change_data(self, soup):
        """Parse phase change properties"""
        phase_data = {}
        
        # Look for phase change tables
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    property_name = cells[0].get_text().strip().lower()
                    value_text = cells[1].get_text().strip()
                    
                    # Extract numerical value
                    value = self._parse_number(value_text)
                    
                    if value is not None:
                        if 'boiling' in property_name or 'vaporization' in property_name:
                            if 'temperature' in property_name or 'point' in property_name:
                                phase_data['boiling_point_K'] = value
                            elif 'enthalpy' in property_name:
                                phase_data['heat_of_vaporization'] = value
                                
                        elif 'melting' in property_name or 'fusion' in property_name:
                            if 'temperature' in property_name or 'point' in property_name:
                                phase_data['melting_point_K'] = value
                            elif 'enthalpy' in property_name:
                                phase_data['heat_of_fusion'] = value
        
        return phase_data
    
    def _parse_number(self, text):
        """Extract numerical value from text with improved parsing"""
        if not text or text == '-' or text == '':
            return None
            
        # Handle scientific notation and various formats
        text = text.strip()
        
        # Remove common non-numeric characters but keep scientific notation
        cleaned = re.sub(r'[^\d.+-eE×]', '', text)
        cleaned = cleaned.replace('×', 'e')  # Handle × notation
        
        # Handle ranges (take first value)
        if '±' in text:
            cleaned = cleaned.split('±')[0]
        
        try:
            return float(cleaned)
        except ValueError:
            # Try to extract first number from string
            numbers = re.findall(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', text)
            if numbers:
                return float(numbers[0])
            return None
    
    def scrape_compound_data(self, formula_or_name):
        """Scrape all available data for a compound"""
        print(f"Scraping data for: {formula_or_name}")
        
        # Search for compound
        compound_id = self.search_compound(formula_or_name)
        if not compound_id:
            return None
        
        print(f"Found compound ID: {compound_id}")
        
        # Get thermodynamic data
        time.sleep(self.delay)
        thermo_data = self.get_thermodynamic_data(compound_id)
        
        # Get phase change data
        time.sleep(self.delay)
        phase_data = self.get_phase_change_data(compound_id)
        
        return {
            'formula': formula_or_name,
            'compound_id': compound_id,
            'thermodynamic_data': thermo_data,
            'phase_change_data': phase_data
        }
    
    def scrape_multiple_compounds(self, compound_list, save_progress=True):
        """Scrape data for multiple compounds"""
        results = {}
        
        for i, compound in enumerate(compound_list):
            print(f"\nProgress: {i+1}/{len(compound_list)}")
            
            try:
                data = self.scrape_compound_data(compound)
                if data:
                    results[compound] = data
                    
                    # Save progress periodically
                    if save_progress and (i+1) % 5 == 0:
                        self.save_data(results, f'nist_data_progress_{i+1}.json')
                        
            except Exception as e:
                print(f"Error scraping {compound}: {e}")
                continue
            
            # Be respectful to NIST servers
            time.sleep(self.delay)
        
        return results
    
    def save_data(self, data, filename):
        """Save scraped data to file"""
        # Convert DataFrames to dictionaries for JSON serialization
        serializable_data = {}
        
        for compound, compound_data in data.items():
            serializable_data[compound] = {
                'formula': compound_data['formula'],
                'compound_id': compound_data['compound_id'],
                'phase_change_data': compound_data['phase_change_data']
            }
            
            # Convert DataFrame to dict
            if compound_data['thermodynamic_data'] is not None:
                serializable_data[compound]['thermodynamic_data'] = \
                    compound_data['thermodynamic_data'].to_dict('records')
            else:
                serializable_data[compound]['thermodynamic_data'] = None
        
        with open(filename, 'w') as f:
            json.dump(serializable_data, f, indent=2)
        
        print(f"Data saved to {filename}")
    
    def load_data(self, filename):
        """Load previously scraped data"""
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # Convert thermodynamic data back to DataFrames
        for compound in data:
            if data[compound]['thermodynamic_data']:
                data[compound]['thermodynamic_data'] = pd.DataFrame(
                    data[compound]['thermodynamic_data']
                )
        
        return data