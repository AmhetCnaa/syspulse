from syspulse.hardware import HardwareMonitor


def test_get_cpu_info(mocker):
    mocker.patch("psutil.cpu_percent", side_effect=[[10.0, 20.0], 15.0])

    mock_freq = mocker.Mock()
    mock_freq.current = 3000.0
    mocker.patch("psutil.cpu_freq", return_value=mock_freq)

    # Mock psutil.getloadavg if it exists, or just ensure it returns cleanly
    if hasattr("psutil", "getloadavg"):
        mocker.patch("psutil.getloadavg", return_value=(1.0, 1.5, 2.0))

    hw = HardwareMonitor()
    cpu = hw.get_cpu_info()

    assert cpu.per_core_percent == [10.0, 20.0]
    assert cpu.total_percent == 15.0
    assert cpu.frequency == 3000.0


def test_get_cpu_info_exceptions(mocker):
    mocker.patch("psutil.cpu_percent", return_value=0.0)
    mocker.patch("psutil.cpu_freq", side_effect=Exception("No freq"))

    hw = HardwareMonitor()
    cpu = hw.get_cpu_info()
    assert cpu.frequency == 0.0


def test_get_memory_info(mocker):
    mock_mem = mocker.Mock()
    mock_mem.total = 1000
    mock_mem.available = 400
    mock_mem.used = 600
    mock_mem.percent = 60.0
    mocker.patch("psutil.virtual_memory", return_value=mock_mem)

    hw = HardwareMonitor()
    mem = hw.get_memory_info()

    assert mem.total == 1000
    assert mem.used == 600
    assert mem.percent == 60.0


def test_get_swap_info(mocker):
    mock_swap = mocker.Mock()
    mock_swap.total = 1000
    mock_swap.used = 200
    mock_swap.free = 800
    mock_swap.percent = 20.0
    mocker.patch("psutil.swap_memory", return_value=mock_swap)

    hw = HardwareMonitor()
    swap = hw.get_swap_info()

    assert swap.total == 1000
    assert swap.used == 200


def test_get_disk_partitions(mocker):
    mock_part = mocker.Mock()
    mock_part.device = "/dev/sda1"
    mock_part.mountpoint = "/"
    mock_part.fstype = "ext4"
    mocker.patch("psutil.disk_partitions", return_value=[mock_part])

    mock_usage = mocker.Mock()
    mock_usage.total = 1000
    mock_usage.used = 500
    mock_usage.free = 500
    mock_usage.percent = 50.0
    mocker.patch("psutil.disk_usage", return_value=mock_usage)

    hw = HardwareMonitor()
    parts = hw.get_disk_partitions()

    assert len(parts) == 1
    assert parts[0].mountpoint == "/"
    assert parts[0].percent == 50.0


def test_get_disk_partitions_exceptions(mocker):
    mock_part = mocker.Mock()
    mock_part.mountpoint = "/"
    mocker.patch("psutil.disk_partitions", return_value=[mock_part])
    mocker.patch("psutil.disk_usage", side_effect=PermissionError)

    hw = HardwareMonitor()
    parts = hw.get_disk_partitions()
    assert len(parts) == 0


def test_get_disk_io(mocker):
    mock_io1 = mocker.Mock()
    mock_io1.read_bytes = 1000
    mock_io1.write_bytes = 1000

    mock_io2 = mocker.Mock()
    mock_io2.read_bytes = 2000
    mock_io2.write_bytes = 3000

    mocker.patch("psutil.disk_io_counters", side_effect=[mock_io1, mock_io2])

    # Mock time so time_diff is 1.0
    mocker.patch("time.time", side_effect=[1.0, 2.0])

    hw = HardwareMonitor()
    # First call in init uses mock_io1
    io = hw.get_disk_io()

    assert io.read_bytes == 2000
    assert io.write_bytes == 3000
    assert io.read_speed == 1000.0  # (2000 - 1000) / 1.0
    assert io.write_speed == 2000.0 # (3000 - 1000) / 1.0

def test_get_disk_io_none(mocker):
    mocker.patch("psutil.disk_io_counters", return_value=None)
    hw = HardwareMonitor()
    io = hw.get_disk_io()
    assert io.read_bytes == 0
