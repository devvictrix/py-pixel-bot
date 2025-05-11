# PyPixelBot UI Sub-package
# This file makes 'ui' a Python sub-package.

# This sub-package contains modules related to the user interface,
# both Command-Line Interface (CLI) and Graphical User Interface (GUI).

import logging

logger = logging.getLogger(__name__)
logger.debug("UI sub-package initialized.")

# Example of exposing main UI entry points (optional):
# from .cli import create_parser
# from .gui.main_app_window import MainAppWindow