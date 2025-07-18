# quick_data_collection.py
import pandas as pd
import numpy as np
from nist_scraper import NISTChemicalDataScraper

def collect_hackathon_dataset():
    """Collect essential data for hackathon demo"""
    
    # Expanded list of compounds with alternative names
    target_compounds = [
        'H2O', 'water',
        'CO2', 'carbon dioxide',
        'CH4', 'methane',
        'NH3', 'ammonia',
        'C2H5OH', 'ethanol',
        'N2', 'nitrogen',
        'O2', 'oxygen',
        'C6H6', 'benzene',
        'C8H18', 'octane',
        'NaCl', 'sodium chloride',
        'H2', 'hydrogen',
        'CO', 'carbon monoxide',
        'C2H4', 'ethylene',
        'C3H8', 'propane',
        'C2H6', 'ethane'
    ]
    
    scraper = NISTChemicalDataScraper(delay=0.5)
    
    print("🔬 Starting NIST data collection...")
    print(f"Target compounds: {len(target_compounds)}")
    
    # Scrape data with progress tracking
    raw_data = {}
    successful_scrapes = 0
    
    for compound in target_compounds:
        try:
            data = scraper.scrape_compound_data(compound)
            if data and data['thermodynamic_data'] is not None:
                raw_data[compound] = data
                successful_scrapes += 1
                print(f"✅ Successfully scraped {compound}")
            else:
                print(f"❌ No data found for {compound}")
        except Exception as e:
            print(f"❌ Error scraping {compound}: {e}")
            continue
    
    print(f"Successfully scraped {successful_scrapes} compounds")
    
    # Save raw data if any was collected
    if raw_data:
        scraper.save_data(raw_data, 'hackathon_raw_data.json')
    
    # Process into training dataset
    training_data = process_for_training(raw_data)
    
    # If still not enough data, add synthetic data
    if len(training_data) < 50:
        print("Adding synthetic data to supplement NIST data...")
        synthetic_data = generate_synthetic_supplement(len(training_data))
        training_data = pd.concat([training_data, synthetic_data], ignore_index=True)
    
    # Save processed data
    training_data.to_csv('hackathon_training_data.csv', index=False)
    
    print(f"✅ Collection complete! {len(training_data)} data points collected")
    print(f"📁 Files saved: hackathon_raw_data.json, hackathon_training_data.csv")
    
    return training_data

def process_for_training(raw_data):
    """Process raw NIST data into ML-ready format"""
    training_samples = []
    
    for compound, data in raw_data.items():
        if data['thermodynamic_data'] is not None:
            df = data['thermodynamic_data']
            
            # Clean and filter data
            df = df.dropna(subset=['temperature', 'heat_capacity'])
            df = df[(df['temperature'] >= 200) & (df['temperature'] <= 2000)]
            
            # Create training samples
            for _, row in df.iterrows():
                sample = {
                    'compound': compound,
                    'compound_id': hash(compound) % 1000,  # Simple encoding
                    'temperature': row['temperature'],
                    'heat_capacity': row['heat_capacity'],
                    'entropy': row.get('entropy', np.nan),
                    'enthalpy_minus_h298': row.get('enthalpy_minus_h298', np.nan),
                }
                
                # Add molecular properties
                sample.update(get_molecular_properties(compound))
                
                training_samples.append(sample)
    
    return pd.DataFrame(training_samples)

def get_molecular_properties(compound):
    """Get basic molecular properties for compounds"""
    properties = {
        'H2O': {'molecular_weight': 18.015, 'n_atoms': 3, 'is_polar': 1},
        'CO2': {'molecular_weight': 44.01, 'n_atoms': 3, 'is_polar': 0},
        'CH4': {'molecular_weight': 16.04, 'n_atoms': 5, 'is_polar': 0},
        'NH3': {'molecular_weight': 17.03, 'n_atoms': 4, 'is_polar': 1},
        'C2H5OH': {'molecular_weight': 46.07, 'n_atoms': 9, 'is_polar': 1},
        'N2': {'molecular_weight': 28.01, 'n_atoms': 2, 'is_polar': 0},
        'O2': {'molecular_weight': 32.00, 'n_atoms': 2, 'is_polar': 0},
        'C6H6': {'molecular_weight': 78.11, 'n_atoms': 12, 'is_polar': 0},
        'C8H18': {'molecular_weight': 114.23, 'n_atoms': 26, 'is_polar': 0},
        'NaCl': {'molecular_weight': 58.44, 'n_atoms': 2, 'is_polar': 1}
    }
    
    return properties.get(compound, {'molecular_weight': 50, 'n_atoms': 5, 'is_polar': 0})

def generate_synthetic_supplement(existing_count):
    """Generate synthetic data to supplement NIST data"""
    print(f"Generating synthetic data (current count: {existing_count})...")
    
    compounds = ['H2O', 'CO2', 'CH4', 'NH3', 'C2H5OH', 'N2', 'O2', 'C6H6', 'C8H18', 'NaCl']
    synthetic_samples = []
    
    target_samples = max(100 - existing_count, 0)
    samples_per_compound = max(target_samples // len(compounds), 5)
    
    for compound in compounds:
        mol_props = get_molecular_properties(compound)
        
        # Generate realistic temperature range
        temps = np.linspace(200, 2000, samples_per_compound)
        
        for temp in temps:
            # Generate realistic heat capacity using simplified correlations
            base_cp = 20 + mol_props['n_atoms'] * 5  # Base heat capacity
            temp_effect = 0.01 * temp + 0.000001 * temp**2  # Temperature dependence
            cp = base_cp + temp_effect + np.random.normal(0, 2)
            
            # Generate correlated entropy
            entropy = 150 + np.log(temp) * 20 + mol_props['n_atoms'] * 10 + np.random.normal(0, 5)
            
            sample = {
                'compound': compound,
                'compound_id': hash(compound) % 1000,
                'temperature': temp,
                'heat_capacity': max(cp, 10),  # Ensure positive
                'entropy': max(entropy, 0),
                'enthalpy_minus_h298': np.random.normal(0, 1000),
                **mol_props
            }
            
            synthetic_samples.append(sample)
    
    return pd.DataFrame(synthetic_samples)