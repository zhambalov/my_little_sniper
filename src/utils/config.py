import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # OpenSea Configuration
    OPENSEA_API_KEY = os.getenv('OPENSEA_API_KEY')
    ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
    ETHEREUM_RPC_URL = os.getenv('ETHEREUM_RPC_URL')
    
    # Telegram Configuration
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ALLOWED_USERS = set(map(int, os.getenv('ALLOWED_USERS', '').split(',')))
    
    # Bot Settings
    MAX_PRICE_MULTIPLIER = float(os.getenv('MAX_PRICE_MULTIPLIER', '1.1'))
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))
    
    # Collection Settings
    COLLECTION_SLUG = 'chonks'  # Default collection
    
    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required_vars = [
            'OPENSEA_API_KEY',
            'ETH_PRIVATE_KEY',
            'ETHEREUM_RPC_URL',
            'TELEGRAM_TOKEN',
            'ALLOWED_USERS'
        ]
        
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )