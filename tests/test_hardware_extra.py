from syspulse.hardware import HardwareMonitor


def test_get_cpu_info_no_loadavg(mocker):
    mocker.patch("psutil.cpu_percent", return_value=0.0)
    mocker.patch("psutil.cpu_freq", return_value=mocker.Mock(current=0.0))
    mocker.patch("psutil.getloadavg", side_effect=Exception("No loadavg"))
    hw = HardwareMonitor()
    cpu = hw.get_cpu_info()
    assert cpu.load_avg == (0.0, 0.0, 0.0)

def test_get_disk_partitions_exception(mocker):
    mock_part = mocker.Mock(device="/dev/sda1", mountpoint="/", fstype="ext4")
    mocker.patch("psutil.disk_partitions", return_value=[mock_part])
    mocker.patch("psutil.disk_usage", side_effect=Exception("Generic error"))
    hw = HardwareMonitor()
    parts = hw.get_disk_partitions()
    assert len(parts) == 0

def test_get_disk_io_time_diff_zero(mocker):
    mock_io1 = mocker.Mock(read_bytes=100, write_bytes=100)
    mock_io2 = mocker.Mock(read_bytes=200, write_bytes=200)
    mocker.patch("psutil.disk_io_counters", side_effect=[mock_io1, mock_io2])
    mocker.patch("time.time", side_effect=[1.0, 1.0])
    hw = HardwareMonitor()
    io = hw.get_disk_io()
    assert io.read_speed == 100.0  # 100 bytes / 1.0 sec fallback
