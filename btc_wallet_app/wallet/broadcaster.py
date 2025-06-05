# btc_wallet_app/wallet/broadcaster.py

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
    if os.path.exists(os.path.join(current_dir, "utxo_manager.py")):
         import utxo_manager
    elif os.path.exists(os.path.join(parent_dir, "wallet", "utxo_manager.py")):
         from wallet import utxo_manager
    else:
        pass # Let Python raise ImportError if not found after these attempts


def broadcast_transaction(signed_tx_hex: str) -> str:
    """
    Broadcasts a signed transaction to the Bitcoin network via Bitcoin Core's
    `sendrawtransaction` RPC call.

    Args:
        signed_tx_hex: The hex string of the signed transaction.

    Returns:
        The transaction ID (TXID) as a string if the broadcast is successful.

    Raises:
        ConnectionError: If connection to Bitcoin Core fails.
        ValueError: If Bitcoin Core RPC returns an error (e.g., transaction rejected).
    """
    if not signed_tx_hex:
        raise ValueError("Signed transaction hex cannot be empty.")

    try:
        rpc_conn = utxo_manager.get_rpc_connection()

        # The `maxfeerate` parameter for `sendrawtransaction` can be used to prevent broadcasting
        # if the transaction's fee rate is too high. Default is 0 (no limit enforced by this arg,
        # but node might have its own `-maxTxFee` limit).
        # For simplicity, we are not using `maxfeerate` here, letting Core use its defaults.
        # If needed, it would be: rpc_conn.sendrawtransaction(signed_tx_hex, maxfeerate_val_sat_vb)
        txid = rpc_conn.sendrawtransaction(signed_tx_hex)

        return txid

    except ConnectionError as ce:
        # This is raised by get_rpc_connection or if the call itself fails at connection level
        raise ConnectionError(f"Failed to connect to Bitcoin Core for broadcasting: {ce}")
    except Exception as e: # Catches JSONRPCException from bitcoinrpc.authproxy and other errors
        error_message = str(e)
        if hasattr(e, 'error') and isinstance(e.error, dict) and 'message' in e.error:
            error_message = e.error['message']

        # Provide more specific error messages for common sendrawtransaction issues if possible
        # These error messages/codes can vary slightly between Bitcoin Core versions.
        # Example common error string: "txn-mempool-conflict"
        # Example error code: -26 (generic error), -27 (txn-already-in-mempool)
        # For now, a general message:
        raise ValueError(f"Bitcoin Core RPC error during sendrawtransaction: {error_message}")


if __name__ == '__main__':
    print("Testing broadcaster.py with Bitcoin Core RPC (sendrawtransaction)...")
    # This test requires:
    # 1. A running Bitcoin Core node (regtest or testnet recommended).
    # 2. RPC credentials in config.py matching the node.
    # 3. A valid, signed transaction hex. (This is the tricky part for an automated test).

    # --- Example Placeholder Data (MUST BE REPLACED with a REAL signed transaction) ---
    # A signed transaction hex is needed here. Creating one that is valid AND spendable on
    # regtest/testnet for an automated __main__ test is complex as it requires:
    #   - UTXOs available on the test network.
    #   - Keys to sign for those UTXOs.
    #   - A fully constructed and signed transaction.
    #
    # The previous `tx_signer.py` (using signrawtransactionwithkey) would produce such a hex.
    # For this __main__ block, we'll use a structurally plausible but likely invalid hex
    # just to test the call structure. A real test needs a real, spendable signed tx.

    # This is an example of a very simple, signed P2PKH transaction hex (likely invalid on any live network).
    # It would typically be the output of `tx_signer.sign_transaction_with_core`.
    # Replace with an actual signed transaction hex from your testing with previous modules.
    signed_hex_example = "010000000100000000000000000000000000000000000000000000000000000000000000000049483045022100exampleSignatureDataR0220exampleSignatureDataS01ffffffff01e8030000000000001976a914000000000000000000000000000000000000000088ac00000000" # REPLACE

    print("\n--- Test Case: Broadcast Transaction (Regtest/Testnet) ---")
    if "exampleSignatureData" in signed_hex_example:
        print("WARNING: Test is using a placeholder signed transaction hex.")
        print("For a meaningful test, replace this with a real, valid, signed transaction hex.")
        print("Ensure your Bitcoin Core node (regtest/testnet) is running and config.py has correct RPC credentials.")

    try:
        print(f"Attempting to broadcast TX: {signed_hex_example[:64]}...")

        # Before running, ensure config.py points to your desired network (regtest/testnet)
        # and UtxoManager's get_rpc_connection() will connect to it.
        txid = broadcast_transaction(signed_hex_example)

        print(f"SUCCESS: Transaction broadcasted!")
        print(f"TXID: {txid}")

    except ConnectionError as e:
        print(f"CONNECTION ERROR: {e}")
        print("Ensure Bitcoin Core is running and RPC settings in config.py are correct.")
    except ValueError as e: # Covers RPC errors (like "transaction already in chain" or format errors)
        print(f"VALUE ERROR / RPC Error during broadcast: {e}")
        if "exampleSignatureData" in signed_hex_example:
             print("This error is expected if using the placeholder transaction hex.")
    except Exception as e: # Catch-all
        print(f"UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\nBroadcaster.py testing finished.")
