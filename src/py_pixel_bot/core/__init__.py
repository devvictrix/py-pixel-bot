# PyPixelBot Core Sub-package
# This file makes 'core' a Python sub-package.

# This sub-package contains essential, non-engine-specific functionalities
# like configuration management and logging setup.

import logging

logger = logging.getLogger(__name__)
logger.debug("Core sub-package initialized.")

# You could expose classes from this sub-package here if desired, e.g.:
# from .config_manager import ConfigManager
# from .logging_setup import setup_logging
# This would allow imports like `from py_pixel_bot.core import ConfigManager`
# instead of `from py_pixel_bot.core.config_manager import ConfigManager`.
# For now, direct submodule imports are used.