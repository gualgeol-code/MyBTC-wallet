# btc_wallet_app/config.py

# Bitcoin Core RPC settings
RPC_USER = "your_rpc_user"
RPC_PASSWORD = "your_rpc_password"
RPC_HOST = "127.0.0.1"  # Or your Bitcoin Core host
RPC_PORT = 8332  # Mainnet RPC port (18332 for Testnet)
RPC_URL = f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}"

# Wallet settings
WALLET_FILE = "wallet.dat"  # Encrypted wallet file
LOG_FILE = "wallet.log"
MIN_CONFIRMATIONS = 1  # Minimum confirmations for UTXOs

# Fee policy
DEFAULT_FEE_SATS_PER_BYTE = 10  # Default fee rate in satoshis per byte

# Network (mainnet or testnet)
NETWORK = "mainnet"  # Options: "mainnet", "testnet"

# Paths
BASE_DIR = "." # Or specify an absolute path

# Add __init__.py to make sure the files are importable
# already done in previous step.

# You can add more configuration options as needed
