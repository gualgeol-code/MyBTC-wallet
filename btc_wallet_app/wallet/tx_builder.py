# btc_wallet_app/wallet/tx_builder.py
from decimal import Decimal, ROUND_DOWN

# bitcoinlib imports
from bitcoinlib.transactions import Transaction, Output, Input
from bitcoinlib.keys import Address # For validating addresses
from bitcoinlib.networks import NetworkError # Removed get_network
from bitcoinlib.scripts import Script, ScriptError # Changed from bitcoinlib.script

# App-specific imports
try:
    from .. import config # For package-like execution
    from . import utxo_manager # To potentially fetch UTXOs if not provided
except ImportError:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import config
    import utxo_manager # Fallback for direct execution

SATOSHIS_PER_BTC = Decimal('100000000')

def btc_to_satoshi(btc_amount: Decimal) -> int:
    """Converts BTC Decimal to satoshis (integer)."""
    return int(btc_amount * SATOSHIS_PER_BTC)

def satoshi_to_btc(satoshi_amount: int) -> Decimal:
    """Converts satoshis (integer) to BTC (Decimal)."""
    return Decimal(satoshi_amount) / SATOSHIS_PER_BTC

def estimate_transaction_size(num_inputs: int, num_outputs: int, input_type: str = 'p2wpkh', output_type: str = 'p2pkh') -> int:
    """
    Estimates transaction size in bytes.
    P2WPKH input: approx 68 vbytes (base size ~10.5 bytes, witness ~108 bytes, total vbytes ~68)
                Non-segwit: P2PKH input approx 148 bytes.
    P2PKH output: approx 34 bytes.
    P2WPKH output: approx 31 bytes.
    P2SH output: approx 32 bytes.
    Base transaction overhead (version, locktime, nInputs, nOutputs): approx 10 bytes.
    """
    # Simplified estimates, can be refined
    input_size = 0
    if input_type == 'p2wpkh': # Segwit P2WPKH
        input_size = 68 # vbytes
    elif input_type == 'p2pkh': # Legacy P2PKH
        input_size = 148 # bytes
    else: # Fallback, rough estimate
        input_size = 100

    # For outputs, P2PKH is common, P2WPKH is smaller
    # Assuming P2PKH for recipient and change for simplicity now
    output_size = 34 # P2PKH output

    # Overhead: version (4 bytes), input count (1-9 bytes), output count (1-9 bytes), locktime (4 bytes)
    # Using a common estimate, can vary.
    overhead = 10

    estimated_size = (num_inputs * input_size) + (num_outputs * output_size) + overhead
    return estimated_size


def select_utxos_for_amount(utxos: list, target_amount_sats: int, fee_rate_sats_per_byte: int, input_address_type: str = 'p2wpkh', output_address_type: str = 'p2pkh'):
    """
    Selects UTXOs to cover the target amount plus estimated fee.
    Args:
        utxos: List of UTXO dicts from utxo_manager (amount should be Decimal in BTC).
               Each UTXO dict MUST contain 'txid', 'vout', 'amount' (Decimal BTC), 'scriptPubKey'.
        target_amount_sats: The amount to send, in satoshis.
        fee_rate_sats_per_byte: Fee rate in satoshis per byte.
        input_address_type: Type of inputs ('p2pkh', 'p2wpkh') to estimate size.
        output_address_type: Type of outputs ('p2pkh', 'p2wpkh') to estimate size.

    Returns:
        A tuple: (selected_utxos_list, total_selected_sats, estimated_fee_sats)
        The selected_utxos_list will have an added 'satoshi_amount' field.
    Raises:
        ValueError if funds are insufficient or UTXOs are missing required fields.
    """
    if not utxos:
        raise ValueError("No UTXOs provided to select from.")

    # Validate UTXO structure and convert amount to satoshis
    utxos_with_sats = []
    for i, u in enumerate(utxos):
        if not all(k in u for k in ['txid', 'vout', 'amount', 'scriptPubKey']):
            raise ValueError(f"UTXO at index {i} is missing one of required keys: 'txid', 'vout', 'amount', 'scriptPubKey'. Found: {u.keys()}")
        u_copy = u.copy()
        u_copy['satoshi_amount'] = btc_to_satoshi(u['amount'])
        utxos_with_sats.append(u_copy)

    # Sort by amount descending (largest first) to minimize inputs
    utxos_with_sats.sort(key=lambda u: u['satoshi_amount'], reverse=True)

    selected_utxos_list = []
    total_selected_sats = 0
    estimated_fee_sats = 0

    # Iteratively select UTXOs and re-calculate fee
    for utxo in utxos_with_sats:
        selected_utxos_list.append(utxo)
        total_selected_sats += utxo['satoshi_amount']

        num_inputs = len(selected_utxos_list)
        # Assume 2 outputs (recipient + change) for fee estimation during selection
        num_outputs = 2

        current_tx_size = estimate_transaction_size(num_inputs, num_outputs, input_address_type, output_address_type)
        estimated_fee_sats = current_tx_size * fee_rate_sats_per_byte

        if total_selected_sats >= target_amount_sats + estimated_fee_sats:
            break # Found enough UTXOs for now

    # Final check if enough funds were selected
    # Determine actual number of outputs based on whether change is needed
    if total_selected_sats > target_amount_sats + estimated_fee_sats: # Change will be produced
        num_outputs_final = 2
    elif total_selected_sats == target_amount_sats + estimated_fee_sats: # Exact amount, no change
        num_outputs_final = 1
    else: # Not enough funds even before precise change output consideration
        num_outputs_final = 1 # Doesn't matter, will fail below

    final_tx_size = estimate_transaction_size(len(selected_utxos_list), num_outputs_final, input_address_type, output_address_type)
    final_estimated_fee_sats = final_tx_size * fee_rate_sats_per_byte

    if total_selected_sats < target_amount_sats + final_estimated_fee_sats:
            raise ValueError(
            f"Insufficient funds. Need {target_amount_sats + final_estimated_fee_sats} satoshis (amount + fee), "
            f"but only {total_selected_sats} satoshis available from selected UTXOs ({len(selected_utxos_list)} UTXOs). "
            f"Final estimated fee: {final_estimated_fee_sats} satoshis."
        )

    return selected_utxos_list, total_selected_sats, final_estimated_fee_sats


def create_raw_transaction(recipient_address: str, amount_btc: Decimal,
                           fee_rate_sats_per_byte: int, utxos_to_spend: list,
                           change_address: str, network_name: str = None, input_address_type: str = 'p2wpkh'):
    """
    Creates a raw Bitcoin transaction.
    Args:
        recipient_address: The Bitcoin address of the recipient.
        amount_btc: The amount to send, in BTC (Decimal).
        fee_rate_sats_per_byte: Fee rate in satoshis per byte.
        utxos_to_spend: A list of UTXO dictionaries (typically from select_utxos_for_amount).
                        Each UTXO must have 'txid', 'vout', 'satoshi_amount', 'scriptPubKey'.
        change_address: The Bitcoin address to send any change to.
        network_name: 'bitcoin' (mainnet) or 'bitcoin_testnet' or 'bitcoin_regtest'. Uses config.NETWORK if None.
        input_address_type: The type of addresses the UTXOs belong to ('p2pkh', 'p2wpkh'), for size estimation and witness type.

    Returns:
        A tuple: (raw_tx_hex, calculated_fee_sats)
    Raises:
        ValueError for invalid inputs or issues during transaction creation.
    """
    if network_name is None:
        network_name_cfg = config.NETWORK
        if network_name_cfg == "testnet": network_name = "testnet" # Corrected
        elif network_name_cfg == "mainnet": network_name = "bitcoin"
        elif network_name_cfg == "regtest": network_name = "regtest" # Corrected
        else: network_name = "testnet" # Default fallback, corrected

    # Ensure network_name is in the format bitcoinlib expects for Address/Transaction
    if network_name not in ["bitcoin", "testnet", "regtest"]: # Corrected list
        raise ValueError(f"Network name '{network_name}' is not recognized by bitcoinlib. Use 'bitcoin', 'testnet', or 'regtest'.")

    # network object is not explicitly needed if Address and Transaction constructors take the network_name string
    # try:
    #     network = get_network(network_name) # bitcoinlib should handle network name internally for Key/Transaction
    # except NetworkError:
    #     raise ValueError(f"Invalid network name for bitcoinlib: {network_name}")

    if not utxos_to_spend:
        raise ValueError("No UTXOs provided to spend.")
    if not all(k in u for u in utxos_to_spend for k in ['txid', 'vout', 'satoshi_amount', 'scriptPubKey']):
        raise ValueError("One or more UTXOs in utxos_to_spend is missing required keys: 'txid', 'vout', 'satoshi_amount', 'scriptPubKey'.")


    # Validate addresses
    try:
        Address(recipient_address, network=network_name) # Use network_name string directly
        Address(change_address, network=network_name)   # Use network_name string directly
    except Exception as e:
        raise ValueError(f"Invalid recipient or change address for network {network_name}. Error: {e}")

    # Determine witness type for transaction based on input type
    witness_type_param = None
    if input_address_type == 'p2wpkh':
        witness_type_param = 'segwit' # bitcoinlib uses 'segwit' for p2wpkh
    elif input_address_type == 'p2sh-p2wpkh': # Example if you had P2SH-wrapped SegWit
        witness_type_param = 'segwit_p2sh'

    tx = Transaction(network=network_name, witness_type=witness_type_param) # Pass network_name string

    total_input_sats = 0
    for utxo_data in utxos_to_spend:
        # script_pubkey from listunspent is what bitcoinlib's Input expects for signing.
        # value is the amount of the UTXO in satoshis.
        # script_pubkey is usually not passed here for P2WPKH, it's used in signing.
        # For P2PKH, a script_sig would be built, but this function creates an unsigned tx.
        tx.add_input(prev_txid=utxo_data['txid'], output_n=utxo_data['vout'],
                     value=utxo_data['satoshi_amount'])
        total_input_sats += utxo_data['satoshi_amount']

    target_sats = btc_to_satoshi(amount_btc)

    # Determine number of outputs for fee calculation
    num_outputs = 1 # Recipient output
    potential_change_sats = total_input_sats - target_sats
    # Tentative fee based on this (will be refined)
    _temp_est_size = estimate_transaction_size(len(utxos_to_spend), 2 if potential_change_sats > 0 else 1, input_address_type) # Assume 2 outputs if change > 0
    calculated_fee_sats = _temp_est_size * fee_rate_sats_per_byte

    if total_input_sats < target_sats + calculated_fee_sats:
        raise ValueError(
            f"Insufficient funds after preliminary fee calculation. "
            f"Total input: {total_input_sats} sats. Target: {target_sats} sats. Estimated fee: {calculated_fee_sats} sats. "
            f"Required: {target_sats + calculated_fee_sats} sats."
        )

    # Add recipient output
    tx.add_output(value=target_sats, address=recipient_address)

    # Add change output if necessary
    change_sats = total_input_sats - target_sats - calculated_fee_sats
    if change_sats > 0:
        # bitcoinlib's Output class has a DUST_LIMIT attribute (e.g., 546 for bitcoin network)
        # It will raise ScriptError if value is too low.
        # We can check against a typical dust limit, e.g. network.DUST_LIMIT or a fixed value
        # For bitcoinlib, network object can be obtained via get_network(network_name)
        # dust_limit = get_network(network_name).DUST_LIMIT
        # However, DUST_LIMIT might not be directly exposed on older bitcoinlib versions or always accurate for all output types.
        # A common P2PKH/P2WPKH dust value is 546 satoshis.
        MIN_CHANGE_SATS = 546
        if change_sats >= MIN_CHANGE_SATS:
            try:
                tx.add_output(value=change_sats, address=change_address)
            except ScriptError as e: # Should be caught by MIN_CHANGE_SATS, but as safeguard
                # This means change is dust. Fee effectively increases.
                # For simplicity, we don't add dust to fee here but raise error.
                # A more complex strategy would be to forgo change and add to fee.
                print(f"Warning: Change amount {change_sats} resulted in ScriptError (likely dust): {e}. Fee will be higher.")
                # No change output added, so the 'change_sats' effectively becomes part of the fee.
                calculated_fee_sats += change_sats
        else:
            # Change is below dust, so it goes to miners (becomes part of the fee)
            print(f"Change amount {change_sats} is below dust limit ({MIN_CHANGE_SATS}). Adding to fee.")
            calculated_fee_sats += change_sats
            # No change output is added.
    elif change_sats < 0:
        raise ValueError(f"Negative change ({change_sats} sats). Inputs less than outputs + fee. Error in fee calculation logic.")

    # Final check on total spent vs sum of outputs and fee
    total_out_sats = sum(o.value for o in tx.outputs)
    if total_input_sats != total_out_sats + calculated_fee_sats:
        # This can happen if dust was handled by adding to fee and tx.outputs changed
        # Re-verify:
        if total_input_sats < total_out_sats + calculated_fee_sats :
             raise ValueError(f"Mismatch: Total input {total_input_sats} != sum of outputs {total_out_sats} + fee {calculated_fee_sats}. Deficit.")
        # If total_input_sats > total_out_sats + calculated_fee_sats, it means some change was not allocated (e.g. dust handling)
        # and should have been added to calculated_fee_sats. This indicates a logic flaw if not handled above.
        # For now, assume the calculated_fee_sats has absorbed any unspent dust.

    return tx.hex(), calculated_fee_sats


if __name__ == '__main__':
    print("Testing tx_builder.py...")

    # network_config_name = config.NETWORK # e.g. "mainnet", "testnet", "regtest"
    # Forcing testnet for this test run to execute the test block:
    network_config_name = "testnet"
    current_network_bitcoinlib = "testnet" # Corrected

    print(f"Using network for bitcoinlib: {current_network_bitcoinlib} (FORCED for test, original config.NETWORK: {config.NETWORK})")

    print("\n--- Test Case: P2WPKH on Testnet ---")
    if current_network_bitcoinlib == 'testnet': # This will now be true (corrected)
        try:
            # These are placeholder values. Replace with actual data from your testnet node.
            # 1. Generate a P2WPKH address using key_manager.py or bitcoin-cli for testnet.
            #    from wallet.key_manager import generate_wif_key
            #    my_key_info = generate_wif_key(network_name='bitcoin_testnet', address_type='p2wpkh')
            #    from_address_p2wpkh = my_key_info['address']
            #    print(f"Test P2WPKH Address (for UTXOs and change): {from_address_p2wpkh}")
            #    # Generate another for recipient or use a known one
            #    recipient_key_info = generate_wif_key(network_name='bitcoin_testnet', address_type='p2wpkh')
            #    recipient_p2wpkh = recipient_key_info['address']
            #    print(f"Test P2WPKH Recipient Address: {recipient_p2wpkh}")

            # Hardcoded example addresses (replace!)
            from_address_p2wpkh = "tb1qf9y5m3n7lgjpmj5j9z5kzgv8jcnhpv3wlam7wa" # Replace
            change_address_p2wpkh = from_address_p2wpkh
            recipient_p2wpkh = "tb1q0s3z3g0z9y0j7r8z3f0z9y0j7r8z3f0z9y0j7r" # Replace

            print(f"Test scenario: Send from {from_address_p2wpkh} to {recipient_p2wpkh}, change to {change_address_p2wpkh}")
            print("IMPORTANT: The UTXO data below is DUMMY. Replace with actual `listunspent` output from your node.")
            print(f"1. Send testnet coins to {from_address_p2wpkh}")
            print(f"2. Get UTXO details: bitcoin-cli -testnet listunspent 0 999999 '[\"{from_address_p2wpkh}\"]'")
            print("3. Update 'example_utxos_p2wpkh' with txid, vout, scriptPubKey, and amount (as Decimal).")

            example_utxos_p2wpkh = [
                {'txid': 'deadbeef00000000000000000000000000000000000000000000000000000000',
                 'vout': 0,
                 'address': from_address_p2wpkh,
                 'scriptPubKey': '00140000000000000000000000000000000000000000', # Replace with actual P2WPKH scriptPubKey
                 'amount': Decimal('0.005'), # BTC
                 # 'satoshi_amount' will be added by select_utxos_for_amount
                 'confirmations': 10
                },
                 {'txid': 'cafebabe00000000000000000000000000000000000000000000000000000000',
                 'vout': 1,
                 'address': from_address_p2wpkh,
                 'scriptPubKey': '00140000000000000000000000000000000000000001', # Replace
                 'amount': Decimal('0.003'), # BTC
                 'confirmations': 5
                }
            ]

            target_send_amount_btc = Decimal('0.002')
            fee_sats_per_byte = 2

            print(f"Target send: {target_send_amount_btc} BTC. Fee rate: {fee_sats_per_byte} sat/byte.")

            selected_utxos, total_selected_sats, est_fee = select_utxos_for_amount(
                example_utxos_p2wpkh,
                btc_to_satoshi(target_send_amount_btc),
                fee_sats_per_byte,
                input_address_type='p2wpkh'
            )
            print(f"UTXOs selected: {len(selected_utxos)}")
            for u in selected_utxos:
                print(f"  - TXID: {u['txid'][:10]}... Vout: {u['vout']}, Amount: {u['amount']} BTC, scriptPubKey: {u['scriptPubKey'][:20]}...")
            print(f"Total input amount: {satoshi_to_btc(total_selected_sats)} BTC ({total_selected_sats} sats)")
            print(f"Estimated fee for selection: {est_fee} sats")

            # Create Raw Transaction
            # Ensure utxos_to_spend (which is selected_utxos here) has 'satoshi_amount' and 'scriptPubKey'
            raw_tx_hex, actual_fee_sats = create_raw_transaction(
                recipient_address=recipient_p2wpkh,
                amount_btc=target_send_amount_btc,
                fee_rate_sats_per_byte=fee_sats_per_byte,
                utxos_to_spend=selected_utxos,
                change_address=change_address_p2wpkh,
                network_name=current_network_bitcoinlib,
                input_address_type='p2wpkh'
            )
            print(f"Raw P2WPKH transaction hex: {raw_tx_hex}")
            print(f"Actual fee calculated by create_raw_transaction: {actual_fee_sats} satoshis")
            print(f"Transaction length (chars): {len(raw_tx_hex)}, Approx. size (bytes): {len(raw_tx_hex) / 2}")

        except ValueError as e:
            print(f"ValueError in P2WPKH test: {e}")
        except NetworkError as e:
            print(f"NetworkError in P2WPKH test: {e}")
        except ScriptError as e:
            print(f"ScriptError in P2WPKH test: {e}")
        except Exception as e:
            print(f"An unexpected error in P2WPKH test: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"Skipping P2WPKH test as current bitcoinlib network is not bitcoin_testnet (it's {current_network_bitcoinlib})")

    print("\nTx_builder.py testing finished.")
