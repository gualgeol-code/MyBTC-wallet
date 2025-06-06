# Python Bitcoin Wallet Application

## Overview

This project is a Python-based Bitcoin wallet application designed for secure private key management and interaction with the Bitcoin network via a Bitcoin Core node. It allows users to generate keys, check balances, create, sign, and broadcast transactions.

## Features Implemented

*   **Key Management (`btc_wallet_app/wallet/key_manager.py`)**:
    *   Generation of new WIF (Wallet Import Format) private keys.
    *   Support for P2PKH (Legacy) and P2WPKH (SegWit) addresses.
    *   Import of existing WIF private keys.
    *   AES-256 encryption of private key data, protected by a user-defined password.
    *   Secure saving and loading of encrypted key files.
*   **UTXO Management (`btc_wallet_app/wallet/utxo_manager.py`)**:
    *   Fetching Unspent Transaction Outputs (UTXOs) for specified addresses using Bitcoin Core's `listunspent` RPC.
*   **Transaction Builder (`btc_wallet_app/wallet/tx_builder.py`)**:
    *   Selection of UTXOs to fund transactions.
    *   Calculation of estimated transaction fees.
    *   Creation of raw, unsigned Bitcoin transaction hex.
*   **Transaction Signer (`btc_wallet_app/wallet/tx_signer.py`)**:
    *   Delegates transaction signing to a running Bitcoin Core node via the `signrawtransactionwithkey` RPC call. This approach was adopted for robustness after encountering difficulties with direct Python-based signing using available libraries in the execution environment.
*   **Broadcaster (`btc_wallet_app/wallet/broadcaster.py`)**:
    *   Broadcasts signed transactions to the Bitcoin network using Bitcoin Core's `sendrawtransaction` RPC call.
*   **Configuration (`btc_wallet_app/config.py`)**:
    *   Centralized configuration for RPC connection details (host, port, user, password), file paths, and wallet policies (e.g., minimum confirmations).

## Project Structure

The main application code is within the `btc_wallet_app/` directory:

btc_wallet_app/
├── main.py                  # Main application entry point (to be developed)
├── config.py                # RPC credentials, paths, fee policies
├── wallet/                  # Core wallet logic
│   ├── key_manager.py       # Import/export WIF, encryption
│   ├── utxo_manager.py      # Fetch and cache UTXOs
│   ├── tx_builder.py        # Create raw TX from UTXOs
│   ├── tx_signer.py         # Sign TX using private key (via Bitcoin Core RPC)
│   ├── broadcaster.py       # Send TX to network via Bitcoin Core
├── cli/                     # Command Line Interface
│   ├── commands.py          # CLI commands (to be developed)
├── utils/                   # Utility modules
│   ├── logger.py            # Timestamped logs (to be developed)
│   ├── fee_estimator.py     # Fee calculation (to be developed)
├── storage/                 # Data storage
│   ├── db.sqlite            # Optional: key metadata, UTXO history (to be developed)
└── tests/                   # Automated tests
    └── test_tx_flow.py      # End-to-end transaction test (to be developed)

## Basic Setup and Usage

1.  **Python Version**: Python 3.10+ recommended.
2.  **Bitcoin Core Node**: A running Bitcoin Core node (mainnet, testnet, or regtest) is required for most operations (fetching UTXOs, signing, broadcasting).
3.  **Configuration (`btc_wallet_app/config.py`)**:
    *   Edit `btc_wallet_app/config.py` to provide your Bitcoin Core node's RPC credentials (`RPC_USER`, `RPC_PASSWORD`, `RPC_HOST`, `RPC_PORT`).
    *   Set the desired `NETWORK` ('mainnet', 'testnet', 'regtest') in `btc_wallet_app/config.py`.
4.  **Dependencies**:
    *   `bitcoinlib`: For key generation and transaction building.
    *   `cryptography`: For key encryption.
    *   `python-bitcoinrpc`: For RPC communication with Bitcoin Core.
    *   Install dependencies, e.g., `pip install bitcoinlib cryptography python-bitcoinrpc`.

## Development Notes

*   **Transaction Signing Pivot**: The decision to use Bitcoin Core's `signrawtransactionwithkey` RPC for signing was made after encountering persistent deserialization issues with `bitcoinlib` and `python-bitcoinlib` in the development environment. This approach leverages the robustness of Bitcoin Core for critical signing operations.

## Future Enhancements (Planned / Possible)

*   Fully implemented CLI and/or a web interface.
*   Comprehensive logging and fee estimation utilities.
*   SQLite database integration for metadata and history.
*   Complete end-to-end automated tests.
*   Support for SegWit Bech32 address generation.
*   Multisig wallet support.
*   Hardware wallet integration.
```
