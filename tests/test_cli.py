import json

import pytest

from syspulse.cli import (
    _export_json,
    _format_bytes,
    _generate_hardware_table,
    _generate_health_panel,
    _generate_layout,
    _generate_network_table,
    main,
)
from syspulse.hardware import HardwareMonitor
from syspulse.network import NetworkMonitor


def test_format_bytes():
    assert _format_bytes(500) == "500.00 B"
    assert _format_bytes(1024) == "1.00 KB"
    assert _format_bytes(1024 * 1024) == "1.00 MB"
    assert _format_bytes(1024 * 1024 * 1024 * 1024 * 1024) == "1.00 PB"

def _mock_monitors(mocker):
    mocker.patch(
        "syspulse.hardware.HardwareMonitor.get_cpu_info",
        return_value=mocker.Mock(per_core_percent=[10.0, 20.0], total_percent=15.0, frequency=3000.0, load_avg=(1.0, 1.5, 2.0))
    )
    mocker.patch(
        "syspulse.hardware.HardwareMonitor.get_memory_info",
        return_value=mocker.Mock(total=1000, available=800, used=200, percent=20.0)
    )
    mocker.patch(
        "syspulse.hardware.HardwareMonitor.get_swap_info",
        return_value=mocker.Mock(total=1000, used=0, free=1000, percent=0.0)
    )
    mocker.patch(
        "syspulse.hardware.HardwareMonitor.get_disk_io",
        return_value=mocker.Mock(read_bytes=0, write_bytes=0, read_speed=0.0, write_speed=0.0)
    )

    mock_part = mocker.Mock(device="/dev/sda1", mountpoint="/", fstype="ext4", total=1000, used=100, free=900, percent=10.0)
    mocker.patch("syspulse.hardware.HardwareMonitor.get_disk_partitions", return_value=[mock_part])

    mock_iface = mocker.Mock(is_up=True, bytes_sent=100, bytes_recv=100, upload_speed=10.0, download_speed=10.0)
    mocker.patch("syspulse.network.NetworkMonitor.get_interfaces_info", return_value={"eth0": mock_iface})

    mock_ping_good = mocker.Mock(target="8.8.8.8", avg_latency=10.0, jitter=1.0, packet_loss=0.0)
    mock_ping_bad = mocker.Mock(target="1.1.1.1", avg_latency=300.0, jitter=10.0, packet_loss=10.0)
    mocker.patch("syspulse.network.NetworkMonitor.check_latency", return_value=[mock_ping_good, mock_ping_bad])

    mock_dns = mocker.Mock(provider="Google", target_domain="example.com", resolve_time=20.0)
    mock_dns_err = mocker.Mock(provider="Cloudflare", target_domain="example.com", resolve_time=-1.0)
    mocker.patch("syspulse.network.NetworkMonitor.benchmark_dns", return_value=[mock_dns, mock_dns_err])

def test_cli_generators(mocker):
    _mock_monitors(mocker)
    hw = HardwareMonitor()
    net = NetworkMonitor()

    hw_table = _generate_hardware_table(hw)
    assert hw_table.title == "Hardware Telemetry"

    net_table = _generate_network_table(net)
    assert net_table.title == "Network Diagnostics"

    health_panel = _generate_health_panel(hw, net)
    assert health_panel.title == "Health & Alerts"

    layout = _generate_layout(hw, net)
    assert layout.name is None

def test_export_json(mocker):
    _mock_monitors(mocker)
    hw = HardwareMonitor()
    net = NetworkMonitor()

    out = _export_json(hw, net)
    data = json.loads(out)
    assert data["health"]["score"] < 100

def test_main_snapshot(mocker):
    _mock_monitors(mocker)
    mocker.patch("syspulse.cli.argparse.ArgumentParser.parse_args", return_value=mocker.Mock(snapshot=True, json=False))
    mocker.patch("syspulse.cli.sys.exit", side_effect=SystemExit)

    mock_print = mocker.patch("syspulse.cli.Console.print")
    with pytest.raises(SystemExit):
        main()
    assert mock_print.call_count == 3

def test_main_json(mocker):
    _mock_monitors(mocker)
    mocker.patch("syspulse.cli.argparse.ArgumentParser.parse_args", return_value=mocker.Mock(snapshot=False, json=True))
    mocker.patch("syspulse.cli.sys.exit", side_effect=SystemExit)

    mock_print = mocker.patch("builtins.print")
    with pytest.raises(SystemExit):
        main()
    mock_print.assert_called_once()

def test_main_live_keyboard_interrupt(mocker):
    _mock_monitors(mocker)
    mocker.patch("syspulse.cli.argparse.ArgumentParser.parse_args", return_value=mocker.Mock(snapshot=False, json=False))

    class MockLive:
        def __enter__(self):
            return mocker.Mock()
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    mocker.patch("syspulse.cli.Live", return_value=MockLive())
    mocker.patch("time.sleep", side_effect=EOFError)

    with pytest.raises(EOFError):
        main()
