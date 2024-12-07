import logging
from typing import Optional, Dict, List
from decimal import Decimal
import requests
from web3 import Web3
from eth_account import Account

from ..utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenSeaMonitor:
    def __init__(self):
        self.api_key = Config.OPENSEA_API_KEY
        self.eth_private_key = Config.ETH_PRIVATE_KEY
        self.ethereum_rpc_url = Config.ETHEREUM_RPC_URL
        self.collection_slug = Config.COLLECTION_SLUG
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.ethereum_rpc_url))
        self.account = Account.from_key(self.eth_private_key)
        
        # API Configuration
        self.base_url = 'https://api.opensea.io/api/v2'
        self.headers = {
            'Accept': 'application/json',
            'X-API-KEY': self.api_key
        }
    
    async def get_floor_price(self) -> Optional[Decimal]:
        """Get current floor price for the collection"""
        try:
            url = f"{self.base_url}/collections/{self.collection_slug}/stats"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return Decimal(str(response.json()['stats']['floor_price']))
        except Exception as e:
            logger.error(f"Error getting floor price: {e}")
            return None
    
    async def has_accessories(self, token_id: str) -> bool:
        """Check if NFT has accessories trait"""
        try:
            url = f"{self.base_url}/assets/{self.collection_slug}/{token_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            traits = response.json()['traits']
            return any(
                trait['trait_type'].lower() == 'accessories' 
                for trait in traits
            )
        except Exception as e:
            logger.error(f"Error checking accessories for token {token_id}: {e}")
            return False
    
    async def get_listings(self, limit: int = 50) -> List[Dict]:
        """Get current listings ordered by price"""
        try:
            url = f"{self.base_url}/collections/{self.collection_slug}/listings"
            params = {
                'limit': limit,
                'order_by': 'price',
                'order_direction': 'asc'
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()['listings']
        except Exception as e:
            logger.error(f"Error getting listings: {e}")
            return []
    
    async def buy_nft(self, listing: Dict) -> Optional[Dict]:
        """Execute NFT purchase"""
        try:
            # Prepare transaction
            transaction = {
                'from': self.account.address,
                'to': listing['protocol_address'],
                'value': Web3.to_wei(listing['price']['amount'], 'ether'),
                'data': listing['protocol_data'],
                'gas': 300000,  # Adjust as needed
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            }
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction, 
                self.eth_private_key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                logger.info(f"Successfully purchased NFT! TX: {receipt['transactionHash'].hex()}")
                return receipt
            else:
                logger.error("Transaction failed!")
                return None
                
        except Exception as e:
            logger.error(f"Error during purchase: {e}")
            return None