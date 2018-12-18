from pkg_resources import get_distribution
from .client import AioSerf, serf_client
from .environment_config import EnvironmentConfig
from .exceptions import SerfError, SerfConnectionError
from . import codec
from ._version import __version__

__all__ = ['AioSerf', 'serf_client', 'EnvironmentConfig', 'SerfError', 'SerfConnectionError']
__all__ += codec.__all__

for k in codec.__all__:
	globals()[k] = getattr(codec,k)
