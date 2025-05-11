# PyPixelBot Package
# This file makes 'py_pixel_bot' a Python package.

# Optionally, you can expose key classes or functions at the package level
# for easier importing by users of the package, if it were to be distributed
# and imported elsewhere. For now, direct imports from submodules are fine.

# Example (if desired later):
# from .main_controller import MainController
# from .core.config_manager import ConfigManager

# Define __version__ for the package
__version__ = "3.0.0-dev-gui-phase1.8.1" # Reflecting current development phase towards v3.0.0

# It's also a good place for package-level logging setup,
# though we are doing it in __main__.py based on APP_ENV.
# If this package were to be used as a library, some minimal default logging
# configuration (e.g., adding a NullHandler to the package's root logger)
# might be considered here to prevent "No handler found" warnings if the
# consuming application doesn't configure logging for this package.

import logging
logger = logging.getLogger(__name__)
# logger.addHandler(logging.NullHandler()) # Uncomment if used as a library and want to be library-friendly

logger.info(f"PyPixelBot package initialized (version {__version__})")