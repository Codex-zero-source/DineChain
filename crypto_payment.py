import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
FUJI_RPC_URL = os.getenv("FUJI_RPC_URL", "https://api.avax-test.network/ext/bc/C/rpc")
raw_usdt_address = os.getenv("USDT_TOKEN_ADDRESS")
if not raw_usdt_address:
    raise ValueError("USDT_TOKEN_ADDRESS environment variable not set.")
USDT_TOKEN_ADDRESS = Web3.to_checksum_address(raw_usdt_address)

# Web3 Provider Setup
w3 = Web3(Web3.HTTPProvider(FUJI_RPC_URL))

# Minimal ERC20 ABI
ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

usdt = w3.eth.contract(address=USDT_TOKEN_ADDRESS, abi=ERC20_ABI)

def generate_wallet():
    acct = Account.create()
    return {"address": acct.address, "private_key": acct.key.hex()}

def get_usdt_balance(address):
    return usdt.functions.balanceOf(Web3.to_checksum_address(address)).call() / 1_000_000 