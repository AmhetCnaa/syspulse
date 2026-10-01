import subprocess

import pytest

from syspulse.network import NetworkMonitor


def test_get_interfaces_info_time_zero(mocker):
    mock_io = {"eth0": mocker.Mock(bytes_sent=100, bytes_recv=100)}
    mocker.patch("psutil.net_io_counters", return_value=mock_io)
    mocker.patch("psutil.net_if_stats", return_value={"eth0": mocker.Mock(isup=True)})
    mocker.patch("time.time", return_value=1.0)
    net = NetworkMonitor()
    net._last_time = 1.0  # Force time_diff = 0
    info = net.get_interfaces_info()
    assert info["eth0"].upload_speed == 0.0

def test_get_default_gateway_exception(mocker):
    mocker.patch("subprocess.check_output", side_effect=Exception("Failed"))
    net = NetworkMonitor()
    assert net._get_default_gateway() is None

def test_ping_target_windows_format(mocker):
    mocker.patch("platform.system", return_value="Windows")
    output = b"Reply from 8.8.8.8: bytes=32 time=15ms TTL=116\n(0% loss)"
    mocker.patch("subprocess.check_output", return_value=output)
    net = NetworkMonitor()
    stats = net._ping_target("8.8.8.8")
    assert stats.avg_latency == 15.0
    assert stats.packet_loss == 0.0

def test_ping_target_one_latency(mocker):
    mocker.patch("platform.system", return_value="Linux")
    output = b"time=15.2 ms\n0% packet loss"
    mocker.patch("subprocess.check_output", return_value=output)
    net = NetworkMonitor()
    stats = net._ping_target("8.8.8.8")
    assert stats.jitter == 0.0

def test_ping_target_no_latency(mocker):
    mocker.patch("platform.system", return_value="Linux")
    output = b"100% packet loss"
    mocker.patch("subprocess.check_output", return_value=output)
    net = NetworkMonitor()
    stats = net._ping_target("8.8.8.8")
    assert stats.avg_latency == 0.0

def test_ping_target_exceptions(mocker):
    mocker.patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "ping"))
    net = NetworkMonitor()
    stats = net._ping_target("8.8.8.8")
    assert stats.packet_loss == 100.0

    mocker.patch("subprocess.check_output", side_effect=Exception("Generic"))
    stats2 = net._ping_target("8.8.8.8")
    assert stats2.packet_loss == 100.0

def test_resolve_dns_custom_server(mocker):
    mocker.patch("subprocess.check_output")
    mocker.patch("time.time", side_effect=[1.0, 1.1, 1.2])
    net = NetworkMonitor()
    t = net._resolve_dns("example.com", "8.8.8.8")
    assert pytest.approx(t) == 100.0

def test_benchmark_dns_exception(mocker):
    mocker.patch("syspulse.network.NetworkMonitor._resolve_dns", side_effect=Exception("fail"))
    net = NetworkMonitor()
    res = net.benchmark_dns()
    assert all(r.resolve_time == -1.0 for r in res)
