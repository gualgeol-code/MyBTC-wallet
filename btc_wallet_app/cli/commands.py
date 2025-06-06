# btc_wallet_app/cli/commands.py
import click
import os
from getpass import getpass # For securely getting passwords

# Adjust imports based on actual project structure and how config is accessed
try:
    # This assumes 'btc_wallet_app' is the top-level package in PYTHONPATH
    from btc_wallet_app.wallet import key_manager, utxo_manager, tx_builder, tx_signer, broadcaster
    from btc_wallet_app import config as wallet_config
except ImportError:
    # Fallback for scenarios where 'btc_wallet_app' is not directly in PYTHONPATH
    # This might happen if running commands.py directly or if Python path is not set up for the package.
    # For robust execution, ensure btc_wallet_app's parent directory is in sys.path
    # or install btc_wallet_app as a package.
    import sys
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_assumed = os.path.dirname(os.path.dirname(current_script_dir)) # up two levels from cli/commands.py to btc_wallet_app_root

    # Attempt to add project root to sys.path if not already there
    # This is a common pattern but might need adjustment based on actual execution context
    # This should point to the directory CONTAINING 'btc_wallet_app' if 'btc_wallet_app' is the package name.
    # Or, if 'btc_wallet_app' is the root and we do 'from wallet import ...', then project_root_assumed is correct.
    # The provided import `from btc_wallet_app.wallet import ...` suggests `project_root_assumed`'s PARENT should be in path,
    # or `project_root_assumed` itself IS the `btc_wallet_app` directory. Let's try adding `project_root_assumed`
    # which would make sense if we are doing `from wallet import ...`

    # If the top-level package is btc_wallet_app, then project_root_assumed (parent of btc_wallet_app) needs to be in path.
    # For imports like `from btc_wallet_app.wallet import ...`
    # Let's adjust path for this case:
    parent_of_project_root_assumed = os.path.dirname(project_root_assumed)
    if parent_of_project_root_assumed not in sys.path:
        sys.path.insert(0, parent_of_project_root_assumed)

    # If the structure is such that 'btc_wallet_app' is the root of the modules being imported
    # (e.g. `import config`, `from wallet import key_manager`), then add `project_root_assumed` to path.
    # The original code had `from btc_wallet_app.wallet import ...`, so the above (parent_of_project_root_assumed) is more likely.
    # Let's stick to the original logic for now and see if it works.
    # The prompt's original fallback was:
    # module_src_path = os.path.join(project_root_assumed)
    # if module_src_path not in sys.path:
    #      sys.path.insert(0, module_src_path)
    # from wallet import key_manager, utxo_manager, tx_builder, tx_signer, broadcaster
    # import config as wallet_config
    # This implies project_root_assumed IS the btc_wallet_app directory.

    # Sticking to the prompt's original fallback structure for imports:
    if project_root_assumed not in sys.path: # project_root_assumed is .../btc_wallet_app
         sys.path.insert(0, project_root_assumed)

    from wallet import key_manager, utxo_manager, tx_builder, tx_signer, broadcaster
    import config as wallet_config


# Default wallet file path from config
DEFAULT_WALLET_FILENAME = wallet_config.WALLET_FILE
default_wallet_path = os.path.join(wallet_config.BASE_DIR, DEFAULT_WALLET_FILENAME)

if wallet_config.BASE_DIR == ".":
    # If BASE_DIR is relative '.', make it relative to the assumed project root (btc_wallet_app/)
    # This is where main.py would be executed from.
    _project_root_for_wallet = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_wallet_path = os.path.join(_project_root_for_wallet, DEFAULT_WALLET_FILENAME)
    # However, if BASE_DIR is '.', it's usually current working directory.
    # Let's refine: if BASE_DIR is '.', default_wallet_path will be ./wallet.dat (in CWD)
    # This is generally fine. The user can override with --walletfile.
    # The config.py sets BASE_DIR = "."
    # If running `python btc_wallet_app/main.py` from outside `btc_wallet_app`, CWD is outside.
    # If running `python main.py` from inside `btc_wallet_app`, CWD is `btc_wallet_app`.
    # A common expectation for BASE_DIR="." is that paths are relative to where the main script is invoked.
    # For Click, it's often better to use `click.get_app_dir()` for user-specific config/data.
    # For now, let's keep it simple: if BASE_DIR is '.', it's relative to CWD.
    # The definition in the prompt for default_wallet_path using _project_root_for_wallet is specific.
    # Let's adhere to the prompt's logic for default_wallet_path.
    pass # The prompt's logic for default_wallet_path is kept for now.


@click.group()
@click.pass_context
def cli(ctx):
    """A simple Bitcoin wallet CLI. Manage keys and transactions."""
    ctx.ensure_object(dict)
    # Example: ctx.obj['NETWORK'] = wallet_config.NETWORK
    # This makes wallet_config accessible in subcommands via ctx.obj['WALLET_CONFIG']
    ctx.obj['WALLET_CONFIG'] = wallet_config
    ctx.obj['DEFAULT_WALLET_PATH'] = default_wallet_path # Pass calculated default


@cli.command()
@click.option('--network', type=click.Choice(['mainnet', 'testnet', 'regtest'], case_sensitive=False),
              default=None, help="Network: mainnet, testnet, or regtest. Overrides config if set.")
@click.option('--addrtype', type=click.Choice(['p2pkh', 'p2wpkh'], case_sensitive=False),
              default='p2wpkh', show_default=True, help="Address type for the new key.")
@click.option('--walletfile', default=None, type=click.Path(), # Default handled by ctx
              help="Path to save/load the encrypted wallet file. Overrides default.")
@click.option('--save', is_flag=True, help="If set, save the generated key to the wallet file (encrypted).")
@click.pass_context # To access ctx.obj
def generatekey(ctx, network, addrtype, walletfile, save):
    """Generates a new Bitcoin private key (WIF) and address."""

    cfg = ctx.obj['WALLET_CONFIG']
    actual_wallet_path = walletfile if walletfile else ctx.obj['DEFAULT_WALLET_PATH']

    effective_network = network if network else cfg.NETWORK

    # Convert common network names to the format key_manager expects
    if effective_network == "mainnet": km_network_name = "bitcoin"
    elif effective_network == "testnet": km_network_name = "bitcoin_testnet"
    elif effective_network == "regtest": km_network_name = "bitcoin_regtest" # Assuming key_manager supports this
    else:
        click.secho(f"Error: Invalid network '{effective_network}'. Choose mainnet, testnet, or regtest.", fg="red")
        return

    try:
        key_data = key_manager.generate_wif_key(network_name=km_network_name, address_type=addrtype)

        click.secho("Successfully generated new key:", fg="green")
        click.echo(f"  Network:         {effective_network} (using internal name: {km_network_name})")
        click.echo(f"  Address Type:    {addrtype}")
        click.echo(f"  WIF Private Key: {key_data['wif']}")
        click.echo(f"  Address:         {key_data['address']}")

        if save:
            wallet_dir = os.path.dirname(actual_wallet_path)
            if wallet_dir and not os.path.exists(wallet_dir):
                try:
                    os.makedirs(wallet_dir, exist_ok=True) # exist_ok=True is helpful
                    click.echo(f"Created directory for wallet file: {wallet_dir}")
                except OSError as e:
                    click.secho(f"Error creating directory {wallet_dir}: {e}", fg="red")
                    return

            if os.path.exists(actual_wallet_path):
                click.secho(f"Warning: Wallet file '{actual_wallet_path}' already exists.", fg="yellow")
                if not click.confirm("Overwrite existing wallet file with this new key? (This is destructive if it contains other keys)"):
                    click.echo("Aborted saving key.")
                    return

            password = getpass("Enter password to encrypt key file: ")
            password_confirm = getpass("Confirm password: ")
            if password != password_confirm:
                click.secho("Passwords do not match. Key not saved.", fg="red")
                return

            try:
                key_manager.save_encrypted_key(key_data, password, actual_wallet_path)
                click.secho(f"Key securely saved to {actual_wallet_path}", fg="green")
            except Exception as e:
                click.secho(f"Error saving key: {e}", fg="red")

    except ValueError as e:
        click.secho(f"Error generating key: {e}", fg="red")
    except Exception as e:
        click.secho(f"An unexpected error occurred: {e}", fg="red")
        # import traceback; traceback.print_exc() # For debugging

# Placeholder for more commands
# @cli.command() ... def importkey(): ...
# @cli.command() ... def showkey(): ...
# @cli.command() ... def getbalance(): ...
# @cli.command() ... def send(): ...

if __name__ == '__main__':
    # This allows invocation like `python btc_wallet_app/cli/commands.py generatekey`
    # For this to work robustly with imports, the parent of btc_wallet_app
    # should ideally be in PYTHONPATH, or btc_wallet_app installed.
    # The try-except for imports at the top helps, but has limitations.
    cli()
