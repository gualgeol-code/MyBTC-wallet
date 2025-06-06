# btc_wallet_app/utils/fee_estimator.py
from decimal import Decimal
import sys # For path manipulation
import os

try:
    # Assuming 'btc_wallet_app' is in PYTHONPATH
    from btc_wallet_app import config as wallet_config
except ImportError:
    # Fallback for direct execution
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root_assumed should be 'btc_wallet_app' directory
    project_root_assumed = os.path.dirname(current_script_dir) # up to 'utils' parent -> 'btc_wallet_app'
    if project_root_assumed not in sys.path:
        sys.path.insert(0, project_root_assumed)
    try:
        import config as wallet_config # type: ignore
    except ImportError:
        print("CRITICAL: fee_estimator.py could not import wallet_config.", file=sys.stderr)
        class FallbackConfig:
            DEFAULT_FEE_SATS_PER_BYTE = 10 # Minimal fallback
        wallet_config = FallbackConfig()


# This function is moved from tx_builder.py
def estimate_transaction_size_bytes(num_inputs: int, num_outputs: int,
                               input_type: str = 'p2wpkh', output_type: str = 'p2pkh') -> int:
    """
    Estimates transaction size in virtual bytes (vBytes) for SegWit or raw bytes for legacy.
    P2WPKH input (SegWit): ~68 vBytes. (Witness data has 1/4 weight)
        Base size: Previous txid (32 bytes) + vout index (4 bytes) + scriptSig length (1 byte, for 0) + nSequence (4 bytes) = 41 bytes.
        Witness: Count (1 byte) + Signature (avg 72 bytes) + Pubkey (33 bytes) = ~106 bytes.
        Total raw bytes = 41 + 106 = 147 bytes.
        vBytes = ceil( (Base * 3 + TotalRaw) / 4 ) = ceil( ( (41*4) + 106 ) / 4 ) if scriptSig is empty for witness.
                 More accurately: base_weight = 41 * 4 = 164. witness_weight = 106. total_weight = 164 + 106 = 270. vBytes = ceil(270/4) = 67.5 => 68 vB.
    P2PKH input (Legacy): ~148 bytes.
        Previous txid (32) + vout index (4) + scriptSig length (1, for ~107) + scriptSig (~107) + nSequence (4) = ~148 bytes.

    P2PKH output: ~34 bytes. (Value (8) + scriptPubKey length (1, for 25) + scriptPubKey (25))
    P2WPKH output: ~31 bytes. (Value (8) + scriptPubKey length (1, for 22) + scriptPubKey (22))
    P2SH output: ~32 bytes. (Value (8) + scriptPubKey length (1, for 23) + scriptPubKey (23))

    Base transaction overhead (version, locktime, nInputs varint, nOutputs varint): ~10-12 bytes.
    Using a common estimate for overhead.
    """
    input_vbytes = 0
    if input_type == 'p2wpkh':
        input_vbytes = 68
    elif input_type == 'p2pkh':
        input_vbytes = 148
    else: # Fallback, very rough estimate
        print(f"Warning: Unknown input_type '{input_type}' for size estimation, using 100 vB fallback.")
        input_vbytes = 100

    output_vbytes = 0
    if output_type == 'p2pkh':
        output_vbytes = 34
    elif output_type == 'p2wpkh':
        output_vbytes = 31
    elif output_type == 'p2sh': # For P2SH-P2WPKH outputs etc.
        output_vbytes = 32
    else: # Fallback
        print(f"Warning: Unknown output_type '{output_type}' for size estimation, using 34 vB fallback.")
        output_vbytes = 34

    # Overhead: version (4 bytes), input count varint (1-9), output count varint (1-9), locktime (4 bytes)
    # Simplified fixed overhead, can be more precise by calculating varint sizes for input/output counts.
    # For 1 input, 1 output, varints are 1 byte each.
    overhead_vbytes = 10
    if num_inputs > 252: overhead_vbytes += 2 # Varint for num_inputs becomes 3 bytes
    if num_outputs > 252: overhead_vbytes += 2 # Varint for num_outputs becomes 3 bytes
    # This is still simplified.

    estimated_vbytes = (num_inputs * input_vbytes) + (num_outputs * output_vbytes) + overhead_vbytes
    return estimated_vbytes

def estimate_fee_details(num_inputs: int, num_outputs: int,
                         input_type: str = 'p2wpkh', output_type: str = 'p2pkh',
                         custom_fee_rate_sats_per_vbyte: int = None) -> dict:
    """
    Estimates transaction fee details based on size and fee rate.
    Returns a dictionary with 'estimated_size_vbytes', 'fee_rate_sats_per_vbyte', 'total_fee_sats'.
    """
    estimated_size_vbytes = estimate_transaction_size_bytes(num_inputs, num_outputs, input_type, output_type)

    fee_rate_to_use = custom_fee_rate_sats_per_vbyte if custom_fee_rate_sats_per_vbyte is not None \
                      else wallet_config.DEFAULT_FEE_SATS_PER_BYTE

    total_fee_sats = estimated_size_vbytes * fee_rate_to_use

    return {
        'estimated_size_vbytes': estimated_size_vbytes,
        'fee_rate_sats_per_vbyte': fee_rate_to_use,
        'total_fee_sats': total_fee_sats
    }

# Future:
# def get_dynamic_fee_rate_from_core(rpc_conn, confirmation_target_blocks=6):
#    try:
#        fee_btc_per_kvb = rpc_conn.estimatesmartfee(confirmation_target_blocks, "CONSERVATIVE")['feerate']
#        if fee_btc_per_kvb and fee_btc_per_kvb > 0:
#            fee_sats_per_vbyte = int((Decimal(str(fee_btc_per_kvb)) * Decimal('100000000')) / Decimal('1000'))
#            return max(fee_sats_per_vbyte, 1)
#    except Exception as e:
#        # print(f"Could not fetch dynamic fee from Bitcoin Core: {e}. Falling back to default.")
#        pass
#    return wallet_config.DEFAULT_FEE_SATS_PER_BYTE


if __name__ == '__main__':
    # Example of using the logger from this module if it were structured differently
    # try:
    #     from .logger import get_logger
    # except ImportError: # Fallback if run directly and logger is in same dir for testing
    #     from logger import get_logger
    # test_logger = get_logger(name="fee_estimator_test", log_to_console=True)
    # test_logger.info("Testing logger from fee_estimator.py __main__ (if logger.py is accessible)")

    print("Testing fee_estimator.py...")

    details_p2wpkh = estimate_fee_details(num_inputs=1, num_outputs=2, input_type='p2wpkh')
    print(f"P2WPKH (1 in, 2 out): Size={details_p2wpkh['estimated_size_vbytes']} vB, "
          f"Rate={details_p2wpkh['fee_rate_sats_per_vbyte']} sat/vB, Fee={details_p2wpkh['total_fee_sats']} sats")

    details_p2pkh = estimate_fee_details(num_inputs=1, num_outputs=2, input_type='p2pkh')
    print(f"P2PKH (1 in, 2 out): Size={details_p2pkh['estimated_size_vbytes']} vB, "
          f"Rate={details_p2pkh['fee_rate_sats_per_vbyte']} sat/vB, Fee={details_p2pkh['total_fee_sats']} sats")

    details_custom_rate = estimate_fee_details(num_inputs=2, num_outputs=3, input_type='p2wpkh', custom_fee_rate_sats_per_vbyte=50)
    print(f"P2WPKH (2 in, 3 out, custom rate): Size={details_custom_rate['estimated_size_vbytes']} vB, "
          f"Rate={details_custom_rate['fee_rate_sats_per_vbyte']} sat/vB, Fee={details_custom_rate['total_fee_sats']} sats")

    print(f"Default fee rate from config: {wallet_config.DEFAULT_FEE_SATS_PER_BYTE} sat/vB")
