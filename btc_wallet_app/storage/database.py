# btc_wallet_app/storage/database.py
import sqlite3
import os
from decimal import Decimal
from datetime import datetime
import sys # For path and error printing
import logging # Added for fallback logger

try:
    # Assuming 'btc_wallet_app' is in PYTHONPATH
    from btc_wallet_app import config as wallet_config
    from btc_wallet_app.utils.logger import get_logger
except ImportError:
    # Fallback for direct execution or if 'btc_wallet_app' is not directly discoverable
    current_script_dir = os.path.dirname(os.path.abspath(__file__)) # .../storage
    project_root_assumed = os.path.dirname(current_script_dir) # .../btc_wallet_app

    if project_root_assumed not in sys.path:
        sys.path.insert(0, project_root_assumed)

    try:
        import config as wallet_config # type: ignore
        from utils.logger import get_logger # type: ignore
    except ImportError:
        # If utils.logger still not found, try adding parent of project_root_assumed for btc_wallet_app.utils
        grandparent_dir = os.path.dirname(project_root_assumed)
        if grandparent_dir not in sys.path:
            sys.path.insert(0, grandparent_dir)
        try:
            from btc_wallet_app import config as wallet_config
            from btc_wallet_app.utils.logger import get_logger
        except ImportError as e_imp:
            print(f"CRITICAL: database.py could not import dependencies: {e_imp}", file=sys.stderr)
            # Define a minimal fallback config and logger if import fails
            class FallbackConfig:
                BASE_DIR = "."
            wallet_config = FallbackConfig()

            # Minimal fallback logger
            def get_logger(name="fallback_db", level=None, log_to_console=None):
                fb_logger = logging.getLogger(name)
                if not fb_logger.handlers: # Setup only if no handlers to avoid duplication
                    fb_logger.setLevel(logging.INFO if level is None else level)
                    handler = logging.StreamHandler(sys.stdout if log_to_console is None else sys.stdout if log_to_console else sys.devnull)
                    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                    fb_logger.addHandler(handler)
                return fb_logger


DB_NAME = "db.sqlite"
_db_path = getattr(wallet_config, 'DB_PATH', None) # Check if a specific DB_PATH is in config

if not _db_path:
    # Default path construction if DB_PATH is not in config
    base_dir_to_use = getattr(wallet_config, 'BASE_DIR', ".")
    if base_dir_to_use == ".":
        # If BASE_DIR is '.', place db in btc_wallet_app/storage/
        # Assumes this script is in btc_wallet_app/storage/database.py
        # Project root is parent of parent of current_script_dir if current_script_dir = .../storage/database.py
        _project_root_for_db = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _db_path = os.path.join(_project_root_for_db, "storage", DB_NAME)
    else:
        # If BASE_DIR is specific, put db in BASE_DIR/storage/ (or just BASE_DIR if that's preferred)
        # The original prompt implied db.sqlite was directly in storage/, not BASE_DIR/storage
        # Let's assume it's meant to be in the 'storage' subdirectory of where BASE_DIR points.
        _db_path = os.path.join(base_dir_to_use, "storage", DB_NAME)


# Ensure _db_path is absolute
_db_path = os.path.abspath(_db_path)

logger = get_logger(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    db_dir = os.path.dirname(_db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        except OSError as e:
            logger.error(f"Error creating database directory {db_dir}: {e}")
            raise

    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                wif_filename TEXT,
                label TEXT,
                network TEXT NOT NULL,
                address_type TEXT NOT NULL,
                creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            logger.info("Keys table initialized or already exists.")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                txid TEXT UNIQUE NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                amount_btc TEXT,
                fee_sats INTEGER,
                recipient_address TEXT,
                status TEXT,
                notes TEXT
            )
            """)
            logger.info("Transactions table initialized or already exists.")

            conn.commit()
        logger.info(f"Database initialized successfully at {_db_path}")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during DB initialization: {e}")
        raise


# --- Key Management Functions ---
def add_key_record(address: str, network: str, address_type: str,
                   wif_filename: str = None, label: str = None):
    sql = "INSERT INTO keys (address, wif_filename, label, network, address_type) VALUES (?, ?, ?, ?, ?)"
    try:
        with get_db_connection() as conn:
            conn.execute(sql, (address, wif_filename, label, network, address_type))
            conn.commit()
        logger.info(f"Added key record for address: {address}")
    except sqlite3.IntegrityError:
        logger.warning(f"Key record for address {address} already exists.")
    except sqlite3.Error as e:
        logger.error(f"Error adding key record for {address}: {e}")
        raise

def get_key_by_address(address: str) -> dict | None:
    sql = "SELECT * FROM keys WHERE address = ?"
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql, (address,)).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching key by address {address}: {e}")
        return None

def get_all_keys() -> list[dict]:
    sql = "SELECT * FROM keys ORDER BY creation_date DESC"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error fetching all keys: {e}")
        return []

def update_key_label(address: str, new_label: str):
    sql = "UPDATE keys SET label = ? WHERE address = ?"
    try:
        with get_db_connection() as conn:
            result = conn.execute(sql, (new_label, address))
            conn.commit()
            if result.rowcount == 0:
                logger.warning(f"No key found for address {address} to update label.")
                return False
        logger.info(f"Updated label for address {address} to '{new_label}'.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating label for {address}: {e}")
        raise


# --- Transaction Management Functions ---
def add_transaction_record(txid: str, amount_btc: Decimal | str, fee_sats: int,
                           recipient_address: str, status: str, notes: str = None):
    amount_btc_str = str(amount_btc) if isinstance(amount_btc, Decimal) else amount_btc
    sql = "INSERT INTO transactions (txid, amount_btc, fee_sats, recipient_address, status, notes) VALUES (?, ?, ?, ?, ?, ?)"
    try:
        with get_db_connection() as conn:
            conn.execute(sql, (txid, amount_btc_str, fee_sats, recipient_address, status, notes))
            conn.commit()
        logger.info(f"Added transaction record: {txid}")
    except sqlite3.IntegrityError:
        logger.warning(f"Transaction record for TXID {txid} already exists.")
    except sqlite3.Error as e:
        logger.error(f"Error adding transaction record for {txid}: {e}")
        raise

def get_transaction_by_txid(txid: str) -> dict | None:
    sql = "SELECT * FROM transactions WHERE txid = ?"
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql, (txid,)).fetchone()
        if row:
            record = dict(row)
            record['amount_btc'] = Decimal(record['amount_btc'])
            return record
        return None
    except sqlite3.Error as e:
        logger.error(f"Error fetching transaction by TXID {txid}: {e}")
        return None

def get_all_transactions(limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM transactions ORDER BY date DESC LIMIT ?"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        processed_rows = []
        for row in rows:
            record = dict(row)
            record['amount_btc'] = Decimal(record['amount_btc'])
            processed_rows.append(record)
        return processed_rows
    except sqlite3.Error as e:
        logger.error(f"Error fetching all transactions: {e}")
        return []

def update_transaction_status(txid: str, new_status: str):
    sql = "UPDATE transactions SET status = ? WHERE txid = ?"
    try:
        with get_db_connection() as conn:
            result = conn.execute(sql, (new_status, txid))
            conn.commit()
            if result.rowcount == 0:
                logger.warning(f"No transaction found for TXID {txid} to update status.")
                return False
        logger.info(f"Updated status for TXID {txid} to '{new_status}'.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating status for TXID {txid}: {e}")
        raise

if __name__ == '__main__':
    # Ensure logger is available for __main__ block, especially if imports failed earlier
    try:
        logger.info(f"Database path configured to: {os.path.abspath(_db_path)}")
    except NameError: # If logger itself failed to initialize due to config import issue
        print(f"Database path (attempted): {os.path.abspath(_db_path)}")


    initialize_db()

    logger.info("--- Testing database operations ---")

    add_key_record("testaddr1", "testnet", "p2wpkh", "mywallet.dat", "Test Key 1")
    add_key_record("testaddr2", "mainnet", "p2pkh", "mywallet.dat", "Savings")
    add_key_record("testaddr1", "testnet", "p2wpkh", "mywallet.dat", "Test Key 1 Duplicate")

    key1 = get_key_by_address("testaddr1")
    logger.info(f"Fetched key testaddr1: {key1}")
    assert key1 and key1['label'] == "Test Key 1"

    update_key_label("testaddr1", "My Primary Test Key")
    key1_updated = get_key_by_address("testaddr1")
    logger.info(f"Fetched updated key testaddr1: {key1_updated}")
    assert key1_updated and key1_updated['label'] == "My Primary Test Key"

    all_keys = get_all_keys()
    logger.info(f"All keys ({len(all_keys)}): {all_keys}")
    assert len(all_keys) >= 2

    txid1 = "txid_example_123"
    add_transaction_record(txid1, Decimal("0.5"), 5000, "recipient_addr_1", "broadcasted", "Sent to friend")
    add_transaction_record("txid_example_456", "1.234", 12000, "recipient_addr_2", "confirmed", "Payment for goods")
    add_transaction_record(txid1, Decimal("0.5"), 5000, "recipient_addr_1", "broadcasted", "Duplicate TX")

    tx1 = get_transaction_by_txid(txid1)
    logger.info(f"Fetched transaction {txid1}: {tx1}")
    assert tx1 and tx1['amount_btc'] == Decimal("0.5")

    update_transaction_status(txid1, "confirmed (6+)")
    tx1_updated = get_transaction_by_txid(txid1)
    logger.info(f"Fetched updated transaction {txid1}: {tx1_updated}")
    assert tx1_updated and tx1_updated['status'] == "confirmed (6+)"

    all_txs = get_all_transactions()
    logger.info(f"All transactions ({len(all_txs)}): {all_txs}")
    assert len(all_txs) >= 2
    if all_txs:
        assert isinstance(all_txs[0]['amount_btc'], Decimal)

    logger.info("--- Database operations testing finished ---")

    # Clean up the test database file
    # if os.path.exists(_db_path):
    #     logger.info(f"Attempting to remove test database: {_db_path}")
    #     try:
    #         os.remove(_db_path)
    #         logger.info(f"Cleaned up test database: {_db_path}")
    #     except OSError as e:
    #         logger.error(f"Error removing test database {_db_path}: {e}")
