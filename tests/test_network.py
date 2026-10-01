import subprocess

import pytest

from syspulse.network import NetworkMonitor


def test_get_interfaces_info(mocker):
    mock_io1 = {"eth0": mocker.Mock(bytes_sent=1000, bytes_recv=1000)}
    mock_io2 = {"eth0": mocker.Mock(bytes_sent=2000, bytes_recv=3000)}

    mock_stats = {"eth0": mocker.Mock(isup=True)}

    mocker.patch("psutil.net_io_counters", side_effect=[mock_io1, mock_io2])
    mocker.patch("psutil.net_if_stats", return_value=mock_stats)
    mocker.patch("time.time", side_effect=[1.0, 2.0])

    net = NetworkMonitor()
    info = net.get_interfaces_info()

    assert "eth0" in info
    assert info["eth0"].is_up is True
    assert info["eth0"].upload_speed == 1000.0
    assert info["eth0"].download_speed == 2000.0


def test_get_interfaces_info_down(mocker):
    mock_io1 = {"eth0": mocker.Mock(bytes_sent=1000, bytes_recv=1000)}
    mock_io2 = {"eth0": mocker.Mock(bytes_sent=2000, bytes_recv=3000)}

    mock_stats = {"eth0": mocker.Mock(isup=False)}

    mocker.patch("psutil.net_io_counters", side_effect=[mock_io1, mock_io2])
    mocker.patch("psutil.net_if_stats", return_value=mock_stats)
    mocker.patch("time.time", side_effect=[1.0, 2.0])

    net = NetworkMonitor()
    info = net.get_interfaces_info()

    assert "eth0" in info
    assert info["eth0"].is_up is False
    assert info["eth0"].upload_speed == 0.0


def test_get_default_gateway_win(mocker):
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("subprocess.check_output", return_value=b"0.0.0.0          0.0.0.0      192.168.1.1")
    net = NetworkMonitor()
    gw = net._get_default_gateway()
    assert gw == "192.168.1.1"


def test_get_default_gateway_linux(mocker):
    mocker.patch("platform.system", return_value="Linux")
    mocker.patch("subprocess.check_output", return_value=b"default via 10.0.0.1 dev eth0")
    net = NetworkMonitor()
    gw = net._get_default_gateway()
    assert gw == "10.0.0.1"


def test_ping_target_success(mocker):
    mocker.patch("platform.system", return_value="Linux")
    output = b"64 bytes from 8.8.8.8: icmp_seq=1 ttl=116 time=15.2 ms\n0% packet loss"
    mocker.patch("subprocess.check_output", return_value=output)

    net = NetworkMonitor()
    stats = net._ping_target("8.8.8.8")

    assert stats.target == "8.8.8.8"
    assert stats.avg_latency == 15.2
    assert stats.packet_loss == 0.0


def test_ping_target_fail(mocker):
    mocker.patch("subprocess.check_output", side_effect=subprocess.TimeoutExpired("ping", 5))
    net = NetworkMonitor()
    stats = net._ping_target("8.8.8.8")
    assert stats.packet_loss == 100.0


def test_check_latency(mocker):
    mocker.patch("syspulse.network.NetworkMonitor._get_default_gateway", return_value="192.168.1.1")
    mocker.patch("syspulse.network.NetworkMonitor._ping_target", return_value=mocker.Mock())

    net = NetworkMonitor()
    res = net.check_latency()

    # 2 defaults + 1 gateway
    assert len(res) == 3


def test_resolve_dns_success(mocker):
    mocker.patch("socket.gethostbyname", return_value="1.2.3.4")
    mocker.patch("time.time", side_effect=[1.0, 1.1, 1.2])
    net = NetworkMonitor()
    t = net._resolve_dns("example.com", None)
    assert pytest.approx(t) == 100.0


def test_resolve_dns_fail(mocker):
    mocker.patch("socket.gethostbyname", side_effect=Exception("No route"))
    net = NetworkMonitor()
    t = net._resolve_dns("example.com", None)
    assert t == -1.0


def test_benchmark_dns(mocker):
    mocker.patch("syspulse.network.NetworkMonitor._resolve_dns", return_value=50.0)
    net = NetworkMonitor()
    res = net.benchmark_dns()
    assert len(res) == 4
    for r in res:
        assert r.resolve_time == 50.0
