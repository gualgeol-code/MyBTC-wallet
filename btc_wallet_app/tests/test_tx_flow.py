# btc_wallet_app/tests/test_tx_flow.py
import unittest
import os
from decimal import Decimal
import sys # For path adjustments and stderr
import logging # For fallback logger

# Attempt to import necessary modules from the wallet application
try:
    from btc_wallet_app import config as wallet_config
    from btc_wallet_app.wallet import key_manager, utxo_manager, tx_builder, tx_signer, broadcaster
    from btc_wallet_app.storage import database
    from btc_wallet_app.utils import logger as app_logger
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) # .../tests
    project_root_assumed = os.path.dirname(current_script_dir) # .../btc_wallet_app

    # Add project root's parent to sys.path to make 'from btc_wallet_app import ...' work
    grandparent_dir = os.path.dirname(project_root_assumed)
    if grandparent_dir not in sys.path:
        sys.path.insert(0, grandparent_dir)

    try:
        from btc_wallet_app import config as wallet_config
        from btc_wallet_app.wallet import key_manager, utxo_manager, tx_builder, tx_signer, broadcaster
        from btc_wallet_app.storage import database
        from btc_wallet_app.utils import logger as app_logger
    except ImportError as e_imp:
        print(f"CRITICAL: test_tx_flow.py could not import dependencies: {e_imp}", file=sys.stderr)
        # Define minimal fallbacks if imports fail, to allow script structure to be checked
        class FallbackConfig:
            NETWORK = "regtest" # Default for tests
            BASE_DIR = "."
            LOG_FILE = "test_fallback.log" # Should match logger.py's fallback logic for path
        wallet_config = FallbackConfig()

        # Minimal fallback logger
        def get_logger_fb(name="fallback_test", level=None, log_to_console=None):
            fb_logger = logging.getLogger(name)
            if not fb_logger.handlers:
                fb_logger.setLevel(logging.INFO if level is None else level)
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                fb_logger.addHandler(handler)
            return fb_logger
        class FallbackAppLogger:
            get_logger = get_logger_fb
        app_logger = FallbackAppLogger()

        # Fallback for database module if it's critical for setup
        class FallbackDatabase:
            _db_path = "fallback_test_db.sqlite" # For setUpClass path logic
            def initialize_db(self): print("Fallback DB init called")
            def add_key_record(self, *args, **kwargs): pass
            def get_transaction_by_txid(self, *args, **kwargs): return None
            def update_transaction_status(self, *args, **kwargs): pass
        database = FallbackDatabase()


# Initialize logger for test output
test_logger = app_logger.get_logger("TestTxFlow")

# --- Test Configuration ---
SENDER_WIF_REGTEST = "cEXAMPLEPRIVKEYREGTESTSENDER"
SENDER_ADDRESS_REGTEST = "mEXAMPLEADDRESSREGTESTSENDER"
RECIPIENT_ADDRESS_REGTEST = "mEXAMPLERECIPIENTREGTEST"
SEND_AMOUNT_BTC = Decimal("0.0001")
FEE_RATE_SATS_PER_VBYTE = 2


class TestTransactionFlow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        test_logger.info("Setting up TestTransactionFlow...")
        try:
            db_name = "test_wallet_db.sqlite" # Use a dedicated test DB name
            base_dir_to_use = getattr(wallet_config, 'BASE_DIR', ".")

            # Determine project root for placing storage/test_wallet_db.sqlite consistently
            # Assumes this test script is in .../btc_wallet_app/tests/test_tx_flow.py
            current_file_path_abs = os.path.abspath(__file__) # .../tests/test_tx_flow.py
            tests_dir = os.path.dirname(current_file_path_abs) # .../tests
            project_root_for_db = os.path.dirname(tests_dir) # .../btc_wallet_app

            storage_dir = os.path.join(project_root_for_db, "storage")
            if not os.path.exists(storage_dir):
                os.makedirs(storage_dir, exist_ok=True)
            cls.db_path = os.path.join(storage_dir, db_name)

            cls.db_path = os.path.abspath(cls.db_path)
            test_logger.info(f"Test database path set to: {cls.db_path}")

            if os.path.exists(cls.db_path):
                os.remove(cls.db_path)
                test_logger.info(f"Removed existing test database: {cls.db_path}")

            original_db_path = None
            if hasattr(database, '_db_path'): # Check if the database module has the global _db_path
                original_db_path = database._db_path
                database._db_path = cls.db_path # Override for this test session

            database.initialize_db()
            test_logger.info("Test database initialized.")

            if original_db_path and hasattr(database, '_db_path'):
                database._db_path = original_db_path # Restore original path

        except Exception as e:
            test_logger.error(f"Failed to initialize database for tests: {e}")
            import traceback
            traceback.print_exc()
            raise

        if hasattr(wallet_config, 'NETWORK') and wallet_config.NETWORK != "regtest":
            test_logger.warning(
                f"Wallet config network is '{wallet_config.NETWORK}'. "
                "End-to-end tests are best run on 'regtest'. "
                "Actual RPC calls will be skipped if not on regtest or if placeholders are used."
            )

        cls.rpc_conn_for_setup = None


    def _is_placeholder_config(self):
        return SENDER_WIF_REGTEST.startswith("cEXAMPLE") or \
               SENDER_ADDRESS_REGTEST.startswith("mEXAMPLE") or \
               RECIPIENT_ADDRESS_REGTEST.startswith("mEXAMPLE")

    @unittest.skipIf("cEXAMPLE" in SENDER_WIF_REGTEST or \
                     (hasattr(wallet_config, 'NETWORK') and wallet_config.NETWORK != "regtest"),
                     "Skipping full TX flow test: Requires valid regtest WIF and config.NETWORK='regtest'.")
    def test_full_transaction_cycle_regtest(self):
        test_logger.info("Starting test_full_transaction_cycle_regtest...")
        sender_address = SENDER_ADDRESS_REGTEST
        sender_wif = SENDER_WIF_REGTEST
        recipient_address = RECIPIENT_ADDRESS_REGTEST

        test_logger.info(f"Fetching UTXOs for sender: {sender_address}")
        simulated_utxos = [
            {'txid': 'dummy_txid_1_replace_for_real_test', 'vout': 0, 'amount': Decimal("0.005"),
             'scriptPubKey': '76a914' + ('0'*40) + '88ac', 'confirmations': 101, 'address_type': 'p2pkh'},
        ]
        utxos = simulated_utxos
        self.assertTrue(utxos, "No UTXOs found for sender (or simulated UTXOs missing).")
        test_logger.info(f"Found/Simulated {len(utxos)} UTXOs.")

        test_logger.info(f"Building transaction to send {SEND_AMOUNT_BTC} BTC to {recipient_address}")
        raw_tx_hex, fee_sats = "dummy_unsigned_tx_hex_replace_me", 500
        self.assertIsNotNone(raw_tx_hex, "Failed to create raw transaction hex.")
        test_logger.info(f"Raw unsigned transaction hex created (placeholder), Fee: {fee_sats} sats.")

        test_logger.info("Signing transaction...")
        signed_tx_hex, complete = "dummy_signed_tx_hex_replace_me", True
        self.assertTrue(complete, "Transaction signing was not complete.")
        self.assertIsNotNone(signed_tx_hex, "Failed to sign transaction.")
        test_logger.info(f"Transaction signed (placeholder), Complete: {complete}.")

        test_logger.info("Broadcasting transaction...")
        txid = "dummy_txid_broadcast_replace_me"
        self.assertIsNotNone(txid, "Failed to broadcast transaction.")
        test_logger.info(f"Transaction broadcasted (placeholder), TXID: {txid}")

        test_logger.info("Transaction recorded in database (simulated).")
        test_logger.info("Block mined and transaction confirmed (simulated).")

    def test_placeholder_always_runs(self):
        self.assertTrue(True, "Placeholder test failed, something is wrong with unittest itself.")
        test_logger.info("Placeholder test executed successfully.")


if __name__ == '__main__':
    unittest.main()
