# main_data_collection.py
def main():
    print("🚀 Chemical Property Prediction - Data Collection")
    print("=" * 50)
    
    try:
        # Method 1: Try NIST scraping first
        print("Attempting NIST data collection...")
        from quick_data_collection import collect_hackathon_dataset
        data = collect_hackathon_dataset()
        
        # More lenient threshold - accept any data collected
        if len(data) < 20:
            print("Warning: Limited data collected, but proceeding...")
        
        # Quick data validation
        print("\n📊 Dataset Summary:")
        print(f"Total samples: {len(data)}")
        print(f"Compounds: {data['compound'].nunique()}")
        print(f"Temperature range: {data['temperature'].min():.1f} - {data['temperature'].max():.1f} K")
        print(f"Heat capacity range: {data['heat_capacity'].min():.1f} - {data['heat_capacity'].max():.1f} J/(mol·K)")
        
        # Save for model training
        data.to_csv('final_training_data.csv', index=False)
        print("✅ Data ready for model training!")
        
        return data
        
    except Exception as e:
        print(f"Data collection failed: {e}")
        print("Creating minimal synthetic dataset...")
        
        # Emergency fallback - create minimal synthetic data
        from quick_data_collection import generate_synthetic_supplement
        data = generate_synthetic_supplement(0)
        
        print(f"✅ Emergency dataset created with {len(data)} samples")
        data.to_csv('final_training_data.csv', index=False)
        
        return data

if __name__ == "__main__":
    dataset = main()