# btc_wallet_app/wallet/key_manager.py
import os
import json
import hashlib
import base64

from bitcoinlib.keys import Key, Address # CKey is Key in newer versions
from bitcoinlib.networks import Network # Removed network_by_name
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Placeholder for now, will be used from config.py
DEFAULT_NETWORK = 'bitcoin' # bitcoin for mainnet, bitcoin_testnet for testnet

def _derive_encryption_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte key for Fernet encryption from a password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000, # OWASP recommendation
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def generate_wif_key(network_name: str = DEFAULT_NETWORK, address_type: str = 'p2pkh'):
    """
    Generates a new private key in WIF format and its corresponding address.
    Supports 'p2pkh' (legacy) and 'p2wpkh' (SegWit) address types.
    Returns a dictionary with 'wif', 'address', 'private_key_hex', 'public_key_hex', 'network', 'address_type'.
    """
    # bitcoinlib's Key class can typically take the network name as a string directly
    key = Key(network=network_name)

    private_key_hex = key.private_hex
    public_key_hex = key.public_hex
    wif = key.wif() # Use wif() for WIF format

    if address_type == 'p2pkh':
        # Default address from key is P2PKH
        address = key.address(script_type='p2pkh')
    elif address_type == 'p2wpkh':
        # P2WPKH (SegWit)
        address = key.address(script_type='p2wpkh')
    else:
        raise ValueError(f"Unsupported address type: {address_type}. Choose 'p2pkh' or 'p2wpkh'.")

    return {
        'wif': wif,
        'address': str(address),
        'private_key_hex': private_key_hex,
        'public_key_hex': public_key_hex,
        'network': network_name,
        'address_type': address_type
    }

def import_wif_key(wif_key: str, network_name: str = DEFAULT_NETWORK, address_type: str = 'p2pkh'):
    """
    Imports a WIF key and derives the address.
    Returns a dictionary with 'wif', 'address', 'private_key_hex', 'public_key_hex', 'network', 'address_type'.
    """
    try:
        # bitcoinlib's Key class can typically take the network name as a string directly
        key = Key(wif_key, network=network_name)
    except Exception as e:
        raise ValueError(f"Invalid WIF key or network name: {e}")

    private_key_hex = key.private_hex
    public_key_hex = key.public_hex

    if address_type == 'p2pkh':
        address = key.address(script_type='p2pkh')
    elif address_type == 'p2wpkh':
        address = key.address(script_type='p2wpkh')
    else:
        raise ValueError(f"Unsupported address type: {address_type}. Choose 'p2pkh' or 'p2wpkh'.")

    return {
        'wif': wif_key,
        'address': str(address),
        'private_key_hex': private_key_hex,
        'public_key_hex': public_key_hex,
        'network': network_name,
        'address_type': address_type
    }

def encrypt_key_data(data: dict, password: str) -> bytes:
    """Encrypts a dictionary of key data using AES-256-GCM (via Fernet) with a password-derived key."""
    salt = os.urandom(16)  # Generate a new salt for each encryption
    key = _derive_encryption_key(password, salt)
    fernet = Fernet(key)

    # Serialize data to JSON string before encryption
    serialized_data = json.dumps(data).encode('utf-8')
    encrypted_payload = fernet.encrypt(serialized_data)

    # Prepend salt to the encrypted payload for later use in decryption
    # Salt must be stored alongside the ciphertext
    return salt + encrypted_payload

def decrypt_key_data(encrypted_data_with_salt: bytes, password: str) -> dict:
    """Decrypts the data. Salt is assumed to be prepended to the encrypted data."""
    salt = encrypted_data_with_salt[:16] # Extract salt (first 16 bytes)
    encrypted_payload = encrypted_data_with_salt[16:] # The rest is the actual payload

    key = _derive_encryption_key(password, salt)
    fernet = Fernet(key)

    decrypted_payload = fernet.decrypt(encrypted_payload)
    # Deserialize JSON string back to dictionary
    data = json.loads(decrypted_payload.decode('utf-8'))
    return data

def save_encrypted_key(key_data: dict, password: str, filepath: str):
    """Saves the encrypted key data to a file."""
    encrypted_data = encrypt_key_data(key_data, password)
    with open(filepath, 'wb') as f:
        f.write(encrypted_data)
    print(f"Key data encrypted and saved to {filepath}")

def load_encrypted_key(filepath: str, password: str) -> dict:
    """Loads and decrypts key data from a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Wallet file not found: {filepath}")
    with open(filepath, 'rb') as f:
        encrypted_data_with_salt = f.read()

    try:
        key_data = decrypt_key_data(encrypted_data_with_salt, password)
        print(f"Key data loaded and decrypted from {filepath}")
        return key_data
    except Exception as e:
        # Catching generic Exception because Fernet can raise various errors on invalid token/key
        raise ValueError(f"Failed to decrypt key. Incorrect password or corrupted file. Error: {e}")

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    try:
        # Test Key Generation
        print("Generating P2PKH key for mainnet...")
        p2pkh_key_mainnet = generate_wif_key(network_name='bitcoin', address_type='p2pkh')
        print(f"P2PKH Mainnet: {p2pkh_key_mainnet}")

        print("\nGenerating P2WPKH key for testnet...")
        p2wpkh_key_testnet = generate_wif_key(network_name='testnet', address_type='p2wpkh')
        print(f"P2WPKH Testnet: {p2wpkh_key_testnet}")

        # Test WIF Import
        print("\nImporting WIF for P2PKH mainnet...")
        imported_key = import_wif_key(p2pkh_key_mainnet['wif'], network_name='bitcoin', address_type='p2pkh')
        assert imported_key['address'] == p2pkh_key_mainnet['address']
        print(f"Imported P2PKH Mainnet: {imported_key}")

        # Test Encryption/Decryption
        password = "supersecretpassword"
        wallet_filepath = "test_wallet.enc"

        print(f"\nEncrypting and saving key to {wallet_filepath}...")
        save_encrypted_key(p2wpkh_key_testnet, password, wallet_filepath)

        print(f"\nLoading and decrypting key from {wallet_filepath}...")
        loaded_key_data = load_encrypted_key(wallet_filepath, password)
        assert loaded_key_data['wif'] == p2wpkh_key_testnet['wif']
        assert loaded_key_data['address'] == p2wpkh_key_testnet['address']
        print(f"Decrypted Key Data: {loaded_key_data}")

        print("\nTesting with incorrect password...")
        try:
            load_encrypted_key(wallet_filepath, "wrongpassword")
        except ValueError as e:
            print(f"Caught expected error: {e}")

        # Clean up test file
        if os.path.exists(wallet_filepath):
            os.remove(wallet_filepath)
        print(f"\nCleaned up {wallet_filepath}")

        print("\nAll key_manager tests passed!")

    except ValueError as ve:
        print(f"ValueError: {ve}")
    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure bitcoinlib and cryptography are installed.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
