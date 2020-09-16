import mock

from asyncserf import EnvironmentConfig


@mock.patch("os.getenv")
def test_defaults(os_getenv):
    os_getenv.return_value = None

    env = EnvironmentConfig()

    assert env.host == "localhost"
    assert env.port == 7373
    assert env.auth_key is None


@mock.patch("os.getenv")
def test_serf_rpc_addr(os_getenv):
    def fake_os_getenv(key, default=None):  # pylint:disable=unused-argument
        if key == "SERF_RPC_ADDR":
            return "serf.company.com:6464"
        return None

    os_getenv.side_effect = fake_os_getenv

    env = EnvironmentConfig()

    assert env.host == "serf.company.com"
    assert env.port == 6464
    assert env.auth_key is None


@mock.patch("os.getenv")
def test_serf_rpc_auth(os_getenv):
    def fake_os_getenv(key, default=None):  # pylint:disable=unused-argument
        if key == "SERF_RPC_AUTH":
            return "secret"
        return None

    os_getenv.side_effect = fake_os_getenv

    env = EnvironmentConfig()

    assert env.host == "localhost"
    assert env.port == 7373
    assert env.auth_key == "secret"
