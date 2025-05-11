// File: src/py_pixel_bot/ui/cli/__init__.py
# PyPixelBot CLI Sub-package
# This file makes 'cli' (under 'ui') a Python sub-package.

# This sub-package contains modules specifically for the
# Command-Line Interface.

import logging

logger = logging.getLogger(__name__)
logger.debug("UI.CLI sub-package initialized.")

# from .cli import create_parser # create_parser is typically used by __main__