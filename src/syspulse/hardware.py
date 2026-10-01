"""
Hardware monitoring module for system telemetry.
"""

import time
from dataclasses import dataclass
from typing import List, Tuple

import psutil


@dataclass
class CPUInfo:
    """CPU telemetry data."""
    per_core_percent: List[float]
    total_percent: float
    frequency: float
    load_avg: Tuple[float, float, float]


@dataclass
class MemoryInfo:
    """Memory telemetry data."""
    total: int
    available: int
    used: int
    percent: float


@dataclass
class SwapInfo:
    """Swap telemetry data."""
    total: int
    used: int
    free: int
    percent: float


@dataclass
class DiskPartitionInfo:
    """Disk partition telemetry data."""
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class DiskIOInfo:
    """Disk I/O telemetry data."""
    read_bytes: int
    write_bytes: int
    read_speed: float  # bytes per second
    write_speed: float # bytes per second


class HardwareMonitor:
    """Monitors hardware telemetry."""

    def __init__(self) -> None:
        """Initialize the hardware monitor."""
        self._last_disk_io = psutil.disk_io_counters()
        self._last_time = time.time()

    def get_cpu_info(self) -> CPUInfo:
        """Get current CPU info."""
        try:
            freq = psutil.cpu_freq()
            freq_current = freq.current if freq else 0.0
        except Exception:
            freq_current = 0.0

        try:
            # os.getloadavg() is not available on all platforms (e.g., Windows in some cases)
            if hasattr(psutil, "getloadavg"):
                load_avg = psutil.getloadavg()
            else:
                # Mock load avg for Windows if not available natively
                load_avg = (0.0, 0.0, 0.0)
        except Exception:
            load_avg = (0.0, 0.0, 0.0)

        return CPUInfo(
            per_core_percent=psutil.cpu_percent(interval=None, percpu=True),
            total_percent=psutil.cpu_percent(interval=None),
            frequency=freq_current,
            load_avg=load_avg,
        )

    def get_memory_info(self) -> MemoryInfo:
        """Get current virtual memory info."""
        vm = psutil.virtual_memory()
        return MemoryInfo(
            total=vm.total,
            available=vm.available,
            used=vm.used,
            percent=vm.percent,
        )

    def get_swap_info(self) -> SwapInfo:
        """Get current swap memory info."""
        sm = psutil.swap_memory()
        return SwapInfo(
            total=sm.total,
            used=sm.used,
            free=sm.free,
            percent=sm.percent,
        )

    def get_disk_partitions(self) -> List[DiskPartitionInfo]:
        """Get disk partition usage info."""
        partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append(DiskPartitionInfo(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total=usage.total,
                    used=usage.used,
                    free=usage.free,
                    percent=usage.percent,
                ))
            except PermissionError:
                # Ignore partitions we don't have access to
                pass
            except Exception:
                pass
        return partitions

    def get_disk_io(self) -> DiskIOInfo:
        """Get disk I/O throughput since last call."""
        current_time = time.time()
        current_io = psutil.disk_io_counters()

        if not current_io or not self._last_disk_io:
            return DiskIOInfo(0, 0, 0.0, 0.0)

        time_diff = current_time - self._last_time
        if time_diff <= 0:
            time_diff = 1.0

        read_speed = (current_io.read_bytes - self._last_disk_io.read_bytes) / time_diff
        write_speed = (current_io.write_bytes - self._last_disk_io.write_bytes) / time_diff

        self._last_disk_io = current_io
        self._last_time = current_time

        return DiskIOInfo(
            read_bytes=current_io.read_bytes,
            write_bytes=current_io.write_bytes,
            read_speed=read_speed,
            write_speed=write_speed,
        )
