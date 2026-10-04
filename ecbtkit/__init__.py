"""
eCBTKit — Production CBT & Online Examination Framework

Build the CBT API, not the CBT engine.

Author: Emmanuel Emmanuel Etim
License: MIT
"""

from ecbtkit.core.app import CBT
from ecbtkit.core.config import Settings

__version__ = "0.1.1"
__author__ = "Emmanuel Emmanuel Etim"

__all__ = ["CBT", "Settings", "__version__", "__author__"]
