from syspulse.hardware import CPUInfo, DiskPartitionInfo, MemoryInfo
from syspulse.health import calculate_health_score
from syspulse.network import PingStats


def test_calculate_health_score_perfect():
    cpu = CPUInfo([10.0], 10.0, 3000.0, (1.0, 1.0, 1.0))
    mem = MemoryInfo(1000, 800, 200, 20.0)
    disk = DiskPartitionInfo("/dev/sda1", "/", "ext4", 1000, 100, 900, 10.0)
    ping = PingStats("8.8.8.8", 15.0, 2.0, 0.0)

    health = calculate_health_score(cpu, mem, [disk], [ping])

    assert health.score == 100
    assert len(health.warnings) == 0


def test_calculate_health_score_critical():
    cpu = CPUInfo([95.0], 95.0, 3000.0, (1.0, 1.0, 1.0))
    mem = MemoryInfo(1000, 50, 950, 95.0)
    disk = DiskPartitionInfo("/dev/sda1", "/", "ext4", 1000, 960, 40, 96.0)
    ping = PingStats("8.8.8.8", 300.0, 2.0, 10.0)

    health = calculate_health_score(cpu, mem, [disk], [ping])

    # -30 (cpu) -30 (mem) -20 (disk) -20 (packet loss) -10 (latency) = -10 => 0
    assert health.score == 0
    assert len(health.warnings) == 5

def test_calculate_health_score_warnings():
    cpu = CPUInfo([75.0], 75.0, 3000.0, (1.0, 1.0, 1.0))
    mem = MemoryInfo(1000, 150, 850, 85.0)
    disk = DiskPartitionInfo("/dev/sda1", "/", "ext4", 1000, 880, 120, 88.0)
    ping = PingStats("8.8.8.8", 50.0, 2.0, 2.0)

    health = calculate_health_score(cpu, mem, [disk], [ping])

    # -10 (cpu) -15 (mem) -5 (disk) -10 (loss) = 60
    assert health.score == 60
    assert len(health.warnings) == 4
