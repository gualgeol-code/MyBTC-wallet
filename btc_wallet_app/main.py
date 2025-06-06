# btc_wallet_app/main.py
import click
# Assuming commands.py is in ./cli/commands.py
# Adjust sys.path to allow finding the 'btc_wallet_app' package
# when main.py is run directly from within the 'btc_wallet_app' directory.
import sys
import os

# Get the directory containing the 'btc_wallet_app' directory (i.e., the project root)
# main.py is in .../btc_wallet_app/main.py
# current_file_dir is .../btc_wallet_app
# project_root (parent of current_file_dir) is .../
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from btc_wallet_app.cli import commands

if __name__ == '__main__':
    commands.cli()
