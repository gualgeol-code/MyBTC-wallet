# btc_wallet_app/wallet/tx_signer.py

from decimal import Decimal
# Assuming config.py and utxo_manager.py are structured to be importable
try:
    from .. import config
    from . import utxo_manager # For get_rpc_connection
except ImportError:
    # Fallback for direct execution or different project structures
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import config
    # Need to ensure utxo_manager can also be found if structure is flat for testing
    if os.path.exists(os.path.join(current_dir, "utxo_manager.py")):
         import utxo_manager
    elif os.path.exists(os.path.join(parent_dir, "wallet", "utxo_manager.py")): # If running from btc_wallet_app
         from wallet import utxo_manager
    else:
        # This path might be needed if running a script from within the 'wallet' directory directly for tests
        # and 'btc_wallet_app' is the main project root added to PYTHONPATH by an IDE, for example.
        # However, the above two relative import attempts should cover most package and direct script run cases.
        # If 'utxo_manager' is still not found, an ImportError will naturally occur.
        pass


def sign_transaction_with_core(unsigned_tx_hex: str,
                               private_keys_wif: list[str],
                               utxos_spent_details: list[dict],
                               network_name: str = None # For consistency, though RPC connection dictates network
                               ) -> tuple[str, bool]:
    """
    Signs a raw Bitcoin transaction using Bitcoin Core's `signrawtransactionwithkey` RPC call.

    Args:
        unsigned_tx_hex: The raw unsigned transaction hex.
        private_keys_wif: A list of WIF private keys for signing.
        utxos_spent_details: A list of dictionaries, one for each UTXO an input spends.
                             Required fields: 'txid', 'vout', 'scriptPubKey', 'amount' (Decimal BTC).
        network_name: Optional network name ('mainnet', 'testnet', 'regtest').
                      Mainly for logging or future use; RPC connection is network-specific.

    Returns:
        A tuple: (signed_tx_hex: str, complete: bool)
        'complete' is True if Bitcoin Core reports the transaction as fully signed.

    Raises:
        ConnectionError: If connection to Bitcoin Core fails.
        ValueError: If Bitcoin Core RPC returns an error or unexpected response.
    """

    if not unsigned_tx_hex:
        raise ValueError("Unsigned transaction hex cannot be empty.")
    if not private_keys_wif:
        # signrawtransactionwithkey can be called with empty keys to just fill in prevtx details
        # but for actual signing, keys are needed. We'll let Core decide if that's an error.
        print("Warning: private_keys_wif list is empty. Bitcoin Core might only add prevtx details.")
    if not utxos_spent_details:
        # Prevtx details are generally required by signrawtransactionwithkey for inputs being signed.
        raise ValueError("UTXOs spent details (prevtxs) cannot be empty.")

    prevtxs = []
    for utxo in utxos_spent_details:
        if not all(k in utxo for k in ['txid', 'vout', 'scriptPubKey', 'amount']):
            raise ValueError("Each UTXO in utxos_spent_details must contain 'txid', 'vout', 'scriptPubKey', and 'amount'.")

        # Ensure amount is float for JSON-RPC, from Decimal
        # Bitcoin Core expects the 'amount' field for prevtxs in some contexts (like PSBT processing for amounts)
        # For signrawtransactionwithkey, 'value' (satoshi) or 'amount' (BTC) might be supported.
        # The 'amount' field (BTC decimal) is more common in examples for `prevtxs` for `signrawtransactionwithkey`
        # and `fundrawtransaction`. Let's stick to 'amount'.
        prevtxs.append({
            "txid": utxo['txid'],
            "vout": int(utxo['vout']),
            "scriptPubKey": utxo['scriptPubKey'],
            "amount": float(utxo['amount']) # Convert Decimal to float for JSON RPC
        })

    try:
        rpc_conn = utxo_manager.get_rpc_connection()
        # print(f"DEBUG: Calling signrawtransactionwithkey with unsigned_tx_hex: {unsigned_tx_hex}")
        # print(f"DEBUG: private_keys_wif: {private_keys_wif}")
        # print(f"DEBUG: prevtxs: {prevtxs}")

        result = rpc_conn.signrawtransactionwithkey(unsigned_tx_hex, private_keys_wif, prevtxs)

        # print(f"DEBUG: Result from signrawtransactionwithkey: {result}")

    except ConnectionError as ce:
        raise ConnectionError(f"Failed to connect to Bitcoin Core for signing: {ce}")
    except Exception as e: # Catches JSONRPCException and other potential errors from the call
        # Specific error parsing could be added here if desired
        # e.g. if hasattr(e, 'error') and e.error and 'message' in e.error
        error_message = str(e)
        if hasattr(e, 'error') and isinstance(e.error, dict) and 'message' in e.error:
            error_message = e.error['message']
        raise ValueError(f"Bitcoin Core RPC error during signrawtransactionwithkey: {error_message}")

    if not isinstance(result, dict) or 'hex' not in result or 'complete' not in result:
        raise ValueError("Unexpected response from signrawtransactionwithkey. Missing 'hex' or 'complete'.")

    signed_tx_hex = result['hex']
    complete = result['complete']

    if not complete:
        print("Warning: Bitcoin Core reported the transaction as not fully signed ('complete': false).")
        # This might be expected if some inputs are signed by other means (e.g. hardware wallet)
        # or if some keys were not provided.
        # Check for errors in the result if any
        if 'errors' in result and result['errors']:
            print(f"Bitcoin Core reported signing errors: {result['errors']}")
            # Potentially raise an error here if any error means failure for the current use case
            # For now, just log and return the (partially) signed tx.

    return signed_tx_hex, complete


if __name__ == '__main__':
    print("Testing tx_signer.py with Bitcoin Core RPC (signrawtransactionwithkey)...")
    # This test requires:
    # 1. A running Bitcoin Core node (regtest or testnet recommended).
    # 2. RPC credentials in config.py matching the node.
    # 3. An unsigned raw transaction hex.
    # 4. WIF private key(s) for the inputs.
    # 5. UTXO details (txid, vout, scriptPubKey, amount in BTC Decimal) for those inputs.

    # --- Example Placeholder Data (MUST BE REPLACED) ---
    # Use output from tx_builder.py (even if it uses the problematic bitcoinlib for generation, Core should parse it)
    # and key_manager.py for WIFs.

    # Ensure config.NETWORK is set appropriately ('testnet', 'regtest')
    current_network_config = config.NETWORK
    print(f"Using network from config: {current_network_config}")
    # Note: utxo_manager.get_rpc_connection() will use RPC settings from config.py,
    # which implicitly define the network.

    # Example: Unsigned P2PKH transaction hex (replace with actual from tx_builder)
    # This is the same ultra-simple regtest tx hex used in the previous minimal deserialization test.
    # Bitcoin Core should be able to parse this.
    unsigned_hex_example = "0100000001000000000000000000000000000000000000000000000000000000000000000000ffffffff01e8030000000000001976a914000000000000000000000000000000000000000088ac00000000"

    # WIF private key for the input (replace with actual WIF for a regtest address that can spend the dummy input)
    # For the dummy input 0000...0000:0, there's no real key unless it's a coinbase on regtest.
    # For a real test, generate a key, get its address, send funds to it (e.g. on regtest),
    # then use that UTXO's details.
    #
    # Let's assume we have a regtest WIF:
    # (e.g., from `bitcoin-cli -regtest dumpprivkey <address>`)
    # Or generate one with key_manager.py for 'bitcoin_regtest' network.
    # Example: (REPLACE with a real regtest WIF you control and that can spend the UTXO below)
    wif_keys_example = ["cEXAMPLE Regtest WIF private key"]

    # UTXO details for the input being spent by unsigned_hex_example
    # This must correspond to the input in unsigned_hex_example (0000...0000:0)
    # scriptPubKey should be the one that the WIF key can unlock.
    # Amount is the value of that UTXO in BTC (Decimal).
    utxos_details_example = [
        {
            "txid": "0000000000000000000000000000000000000000000000000000000000000000", # Matches input in unsigned_hex
            "vout": 0,
            "scriptPubKey": "76a914000000000000000000000000000000000000000088ac", # P2PKH, zeroed PKH (matches output in unsigned_hex)
            "amount": Decimal("0.01") # Example amount for this UTXO (e.g., if it was funded with 0.01 BTC)
                                      # This amount is critical for sighash in some cases, Core needs it.
        }
    ]

    print("\n--- Test Case: Sign with signrawtransactionwithkey (Regtest/Testnet) ---")
    # Basic check if placeholders are still there
    if "cEXAMPLE" in wif_keys_example[0] or utxos_details_example[0]['amount'] == Decimal("0.01"):
         print("WARNING: Test is using placeholder WIF key or UTXO amount.")
         print("For a meaningful test, replace placeholders with actual data from your regtest/testnet environment:")
         print("1. Generate an unsigned transaction hex using tx_builder.py or bitcoin-cli.")
         print("2. Provide valid WIF private key(s) for the inputs in that transaction.")
         print("3. Provide correct UTXO details (txid, vout, scriptPubKey, amount_BTC) for each input.")
         print("Ensure your Bitcoin Core node (regtest/testnet) is running and config.py has correct RPC credentials.")

    # Attempt to run only if not using obvious placeholders, or if user intends to test RPC connection part
    # This test will likely fail due to invalid WIF/UTXO if placeholders are not changed,
    # but it can still test the RPC call structure.
    try:
        print(f"Attempting to sign TX: {unsigned_hex_example[:64]}...")
        print(f"Using WIFs (first 10 chars): {[k[:10] + '...' for k in wif_keys_example]}")
        print(f"UTXO details (first UTXO): txid={utxos_details_example[0]['txid'][:10]}..., vout={utxos_details_example[0]['vout']}, amount={utxos_details_example[0]['amount']}")

        signed_hex, complete = sign_transaction_with_core(
            unsigned_hex_example,
            wif_keys_example,
            utxos_details_example
            # network_name can be passed if needed, but RPC connection defines it
        )

        print(f"SUCCESS: signrawtransactionwithkey call completed.")
        print(f"Signed TX hex: {signed_hex}")
        print(f"Transaction complete (fully signed): {complete}")

        if not complete and utxos_details_example[0]['amount'] == Decimal("0.01"): # Placeholder amount likely means incomplete data
            print("INFO: Transaction reported as incomplete. This is expected if using placeholder WIF/UTXO data.")
            print("      Bitcoin Core might have only added prevtx details or failed to find suitable keys.")


    except ConnectionError as e:
        print(f"CONNECTION ERROR: {e}")
        print("Ensure Bitcoin Core is running and RPC settings in config.py are correct.")
    except ValueError as e: # Covers RPC errors and other value issues
        print(f"VALUE ERROR / RPC Error: {e}")
    except Exception as e: # Catch-all for other unexpected errors
        print(f"UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\nTx_signer.py (Bitcoin Core RPC) testing finished.")
