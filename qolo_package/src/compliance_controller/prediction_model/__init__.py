"""Bumper Prediction Module.

This module implements prediction model for bumper damping.
"""

__all__ = ['SVR', 'BumperModel']
__version__ = '0.1'
__author__ = 'Vaibhav Gupta'

from .svr import SVR
from .bumper_model import BumperModel
