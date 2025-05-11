# PyPixelBot Engines Sub-package
# This file makes 'engines' a Python sub-package.

# This sub-package contains the core processing engines of the bot:
# - CaptureEngine: For capturing screen regions.
# - AnalysisEngine: For analyzing captured image data.
# - RulesEngine: For evaluating rules based on analysis.
# - ActionExecutor: For performing actions based on rule outcomes.

import logging

logger = logging.getLogger(__name__)
logger.debug("Engines sub-package initialized.")

# Example of exposing classes (optional):
# from .capture_engine import CaptureEngine
# from .analysis_engine import AnalysisEngine
# from .rules_engine import RulesEngine
# from .action_executor import ActionExecutor