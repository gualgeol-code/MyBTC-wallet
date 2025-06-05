import bitcoin
import bitcoin.core
import bitcoin.core.script as script
import bitcoin.core.serialize as serialize

def minimal_deserialize_test():
    network_to_use = 'regtest'
    print(f"Setting network to: {network_to_use}")
    bitcoin.SelectParams(network_to_use)

    # Version 1, 1 input, 1 output. PKH is 20 zero bytes. Amount 1000 satoshis.
    ultra_simple_tx_hex = "0100000001000000000000000000000000000000000000000000000000000000000000000000ffffffff01e8030000000000001976a914000000000000000000000000000000000000000088ac00000000"
    raw_tx_bytes = bytes.fromhex(ultra_simple_tx_hex)

    print(f"Attempting to deserialize: {ultra_simple_tx_hex}")
    try:
        tx = bitcoin.core.CTransaction.deserialize(raw_tx_bytes)
        print("Success: Deserialization appears to have worked.")
        print("Transaction structure (as dict):")
        # print(tx.to_dict()) # to_dict() might not exist, try string representation
        print(str(tx))
        print(f"Version: {tx.nVersion}")
        print(f"Input count: {len(tx.vin)}")
        print(f"Output count: {len(tx.vout)}")
        if tx.vin:
            print(f"First input prevout hash: {tx.vin[0].prevout.hash.hex()[::-1]}") # Reverse for big-endian
            print(f"First input prevout n: {tx.vin[0].prevout.n}")
        if tx.vout:
            print(f"First output value (satoshi): {tx.vout[0].nValue}")
            print(f"First output scriptPubKey (hex): {tx.vout[0].scriptPubKey.hex()}")

    except Exception as e:
        print("Failed: Deserialization error.")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    minimal_deserialize_test()
