# btc_wallet_app/utils/logger.py
import logging
import os
import sys # Added for stderr printing

try:
    # Assuming 'btc_wallet_app' is in PYTHONPATH
    from btc_wallet_app import config as wallet_config
except ImportError:
    # Fallback for direct execution or if 'btc_wallet_app' is not directly discoverable
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root_assumed should be the 'btc_wallet_app' directory itself if we want to import 'config.py' from it.
    project_root_assumed = os.path.dirname(current_script_dir) # Goes up to 'utils' parent, which is 'btc_wallet_app'
    if project_root_assumed not in sys.path:
        sys.path.insert(0, project_root_assumed)
    try:
        import config as wallet_config # type: ignore
    except ImportError:
        # If 'config.py' is not in 'btc_wallet_app' but in its parent (e.g. project_root/config.py)
        # This case is less likely given the established structure.
        # For now, assume config.py is at btc_wallet_app/config.py
        # If this fails, wallet_config will not be defined, leading to errors below.
        # A default config could be defined here as a fallback.
        print("CRITICAL: logger.py could not import wallet_config. Logging will be impaired.", file=sys.stderr)
        # Define a minimal fallback config object if import fails, to prevent crashes
        class FallbackConfig:
            LOG_FILE = "wallet_fallback.log"
            BASE_DIR = "."
        wallet_config = FallbackConfig()


# Determine log file path from config
_log_file_path = wallet_config.LOG_FILE
if not os.path.isabs(_log_file_path) and hasattr(wallet_config, 'BASE_DIR') and wallet_config.BASE_DIR:
    # Make path absolute if BASE_DIR is provided and log_file_path is relative
    # If BASE_DIR is '.', it becomes current working directory.
    # For consistency, if BASE_DIR is '.', make it relative to project root (btc_wallet_app directory)
    if wallet_config.BASE_DIR == ".":
        # Assuming this script is in btc_wallet_app/utils/logger.py
        # project_root becomes btc_wallet_app/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _log_file_path = os.path.join(project_root, _log_file_path)
    else:
        _log_file_path = os.path.join(wallet_config.BASE_DIR, _log_file_path)
else:
    # If _log_file_path is already absolute, or no BASE_DIR, use it as is (or CWD if relative & no BASE_DIR)
    if not os.path.isabs(_log_file_path):
        _log_file_path = os.path.abspath(_log_file_path)


# Ensure log directory exists
_log_dir = os.path.dirname(_log_file_path)
if _log_dir and not os.path.exists(_log_dir):
    try:
        os.makedirs(_log_dir, exist_ok=True) # exist_ok=True is helpful
    except OSError as e:
        print(f"Warning: Could not create log directory {_log_dir}: {e}", file=sys.stderr)
        # Fallback to logging in current directory or disable file logging if dir creation fails
        _log_file_path = os.path.basename(_log_file_path) if _log_file_path else "wallet_fallback.log"
        _log_file_path = os.path.abspath(_log_file_path)


_logger_initialized = False
_app_logger = None

def get_logger(name="btc_wallet_app", level=logging.INFO, log_to_console=True):
    """
    Configures and returns a logger instance.
    Logger is configured only once.
    """
    global _logger_initialized, _app_logger

    if _logger_initialized and _app_logger:
        # Ensure the existing logger's level is appropriate if called with a different level
        # This might not be ideal; usually, first call sets the level.
        # For simplicity, we return the existing logger as is.
        return _app_logger

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers (if any from previous runs in same Python session, e.g. testing)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler
    try:
        fh = logging.FileHandler(_log_file_path)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Warning: Could not set up file logger for {_log_file_path}: {e}", file=sys.stderr)


    # Console Handler
    if log_to_console:
        ch = logging.StreamHandler(sys.stdout) # Explicitly use sys.stdout
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    logger.propagate = False # Prevent messages from propagating to the root logger

    _app_logger = logger
    _logger_initialized = True
    return logger

if __name__ == '__main__':
    # Example usage:
    logger = get_logger(log_to_console=True, level=logging.DEBUG)
    logger.debug("This is a debug message.")
    logger.info("Logger initialized. This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")

    print(f"Log file should be at: {os.path.abspath(_log_file_path)}")

    # Test that calling get_logger again returns the same instance without reconfiguring handlers
    logger2 = get_logger()
    assert logger is logger2, "get_logger() should return the same instance"
    # If this assert fails, it means handlers might be added multiple times.
    # Check number of handlers
    # print(f"Number of handlers for logger: {len(logger.handlers)}") # Should ideally be 1 or 2

    logger2.info("Testing logger again from the same instance. This should not duplicate handlers.")
    # Example of how another module might use it:
    # other_module_logger = get_logger(name="module_x")
    # other_module_logger.info("Message from module_x")
    # This will use the same handlers but a different logger name.
    # If a separate logger instance for 'module_x' is desired, the get_logger logic would need adjustment,
    # but typically one configured root/app logger is fine, or getLogger(name) is used directly after one setup.
    # The current setup makes one central 'btc_wallet_app' logger.
