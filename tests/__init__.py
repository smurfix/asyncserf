import logging

logging.basicConfig(level=logging.INFO)

import trio._core._run as tcr
import os

if "PYTHONHASHSEED" in os.environ:
    tcr._ALLOW_DETERMINISTIC_SCHEDULING = True
    tcr._r.seed(os.environ["PYTHONHASHSEED"])
