from bitcoinlib.transactions import Transaction
# from bitcoinlib.networks import set_network # This import caused an error

def test_deserialization():
    # A simple, valid unsigned transaction hex for regtest.
    # Version 2, 1 input, 1 output.
    # Input: spends output 0 of txid 0000...0000 (common placeholder for coinbase in simple setups or first tx)
    # Output: 1 BTC (0x05f5e100 satoshis) to a P2PKH script (76a914...88ac)
    # scriptPubKey: 76a9140000000000000000000000000000000000000000088ac (OP_DUP OP_HASH160 <20_zero_bytes> OP_EQUALVERIFY OP_CHECKSIG)
    # Locktime: 0
    # Sequence: ffffffff
    unsigned_regtest_tx_hex = "0200000001000000000000000000000000000000000000000000000000000000000000000000ffffffff0100e1f505000000001976a914000000000000000000000000000000000000000088ac00000000"
    raw_tx_bytes = bytes.fromhex(unsigned_regtest_tx_hex)
    network_to_use = 'regtest' # bitcoinlib usually expects 'bitcoin', 'testnet', or 'regtest'

    print(f"Attempting deserialization of: {unsigned_regtest_tx_hex} on network {network_to_use}")

    # Make sure the network context is set if bitcoinlib relies on a global default
    # set_network(network_to_use) # Commented out due to import error

    methods_to_try = {
        "Transaction.from_hex(hex, network=net)": lambda: Transaction.from_hex(unsigned_regtest_tx_hex, network=network_to_use),
        "Transaction.deserialize(bytes, network=net) (static)": lambda: Transaction.deserialize(raw_tx_bytes, network=network_to_use),
        "tx_obj = Transaction(network=net); tx_obj.deserialize(bytes)": lambda: Transaction(network=network_to_use).deserialize(raw_tx_bytes),
        "Transaction(raw_hex, network=net) (constructor)": lambda: Transaction(unsigned_regtest_tx_hex, network=network_to_use),
        "Transaction(raw_bytes, network=net) (constructor)": lambda: Transaction(raw_tx_bytes, network=network_to_use),
    }

    results = {}
    for name, method_func in methods_to_try.items():
        print(f"\nTrying: {name}")
        try:
            tx_obj = method_func()
            results[name] = {"status": "Success", "output": tx_obj.as_dict() if hasattr(tx_obj, 'as_dict') else str(tx_obj)}
            print(f"SUCCESS: {name}")
            # If one method works, we can potentially stop or report it as the winner.
            # For this test, we'll try all to see if multiple work or have different behaviors.
        except Exception as e:
            results[name] = {"status": "Failed", "error": str(e)}
            print(f"FAILED: {name} with error: {e}")
            import traceback
            traceback.print_exc()

    print("\n--- Deserialization Test Summary ---")
    found_working_method = False
    for name, result in results.items():
        print(f"Method: {name} -> Status: {result['status']}")
        if result['status'] == 'Failed':
            print(f"  Error: {result['error']}")
        else:
            found_working_method = True
            print(f"  Output Preview: {str(result['output'])[:200]}...") # Print a preview

    if found_working_method:
        print("\nFound at least one working deserialization method.")
    else:
        print("\nNo working deserialization method found among those tested.")

if __name__ == '__main__':
    test_deserialization()
