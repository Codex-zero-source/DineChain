import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
FUJI_RPC_URL = os.getenv("FUJI_RPC_URL", "https://api.avax-test.network/ext/bc/C/rpc")
raw_usdc_address = os.getenv("USDC_TOKEN_ADDRESS")
if not raw_usdc_address:
    raise ValueError("USDC_TOKEN_ADDRESS environment variable not set.")
USDC_TOKEN_ADDRESS = Web3.to_checksum_address(raw_usdc_address)

# Web3 Provider Setup
w3 = Web3(Web3.HTTPProvider(FUJI_RPC_URL))

# Minimal ERC20 ABI
ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

usdc = w3.eth.contract(address=USDC_TOKEN_ADDRESS, abi=ERC20_ABI)

def generate_wallet():
    acct = Account.create()
    return {"address": acct.address, "private_key": acct.key.hex()}

def get_usdc_balance(address):
    return usdc.functions.balanceOf(Web3.to_checksum_address(address)).call() / 1_000_000 