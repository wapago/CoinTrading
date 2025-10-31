import os
import sys

from .models import *
from .interface import Interface, AsyncSession

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

db = Interface()
