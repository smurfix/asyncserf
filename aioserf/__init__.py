from pkg_resources import get_distribution
from aioserf.client import AioSerf
from aioserf.environment_config import EnvironmentConfig

__version__ = get_distribution('aioserf').version

__all__ = ['AioSerf', 'EnvironmentConfig']
