
import asyncio
import pandas as pd
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import AmazingDataExtended
from deepsearch.infrastructure.providers.implementations.amazingdata.config import AmazingDataConfig

# Mock config - assumes environment variables or default settings are sufficient for local connection test
# or that the user has a valid config file. 
# Since we are in an agentic environment, I'll try to rely on the existing config logic.

async def probe_industry_interfaces():
    print("Initializing AmazingData Extended...")
    # Assuming local default config is valid or handled by the class machinery
    provider = AmazingDataExtended({}) 
    await provider.initialize()
    
    try:
        print("\n--- Testing get_industry_base_info ---")
        # Try to get all industries
        industries = await provider.get_industry_base_info()
        print(f"Result type: {type(industries)}")
        if isinstance(industries, pd.DataFrame):
            print(f"Shape: {industries.shape}")
            print("Columns:", industries.columns.tolist())
            print("Head:\n", industries.head())
            
            # Pick a sample industry code
            if not industries.empty:
                sample_code = industries.iloc[0]['industry_code'] # Guessing column name
                if 'industry_code' not in industries.columns:
                     sample_code = industries.iloc[0, 0] # Fallback
                
                print(f"\n--- Testing get_industry_constituent for {sample_code} ---")
                constituents = await provider.get_industry_constituent(sample_code)
                print(f"Result type: {type(constituents)}")
                if isinstance(constituents, pd.DataFrame):
                    print(f"Shape: {constituents.shape}")
                    print("Head:\n", constituents.head())
        
        print("\n--- Testing get_industry_daily (Sector Market Data) ---")
        # Try to get data for a few sectors
        # This will verify if we can get volume/turnover for sectors directly
        if isinstance(industries, pd.DataFrame) and not industries.empty:
             codes = industries.iloc[:5, 0].tolist()
             daily_data = await provider.get_industry_daily(codes)
             print(f"Daily Data Shape: {daily_data.shape if isinstance(daily_data, pd.DataFrame) else 'Not DF'}")
             if isinstance(daily_data, pd.DataFrame):
                 print(daily_data.head())

    except Exception as e:
        print(f"Error during probe: {e}")
    finally:
        await provider.stop_async()

if __name__ == "__main__":
    try:
        asyncio.run(probe_industry_interfaces())
    except KeyboardInterrupt:
        pass
