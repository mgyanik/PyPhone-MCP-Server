"""确保裸跑 pytest 时项目根目录在 sys.path 中，可 import src.*。"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)