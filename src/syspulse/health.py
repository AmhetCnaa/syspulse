"""
Health scoring module for overall system wellness.
"""

from dataclasses import dataclass
from typing import List

from .hardware import CPUInfo, DiskPartitionInfo, MemoryInfo
from .network import PingStats


@dataclass
class HealthScore:
    """System health score and warnings."""
    score: int  # 0 to 100
    warnings: List[str]


def calculate_health_score(
    cpu: CPUInfo,
    memory: MemoryInfo,
    disk_partitions: List[DiskPartitionInfo],
    ping_stats: List[PingStats]
) -> HealthScore:
    """
    Calculate an overall system health score based on telemetry.
    Returns the score and a list of warnings.
    """
    score = 100.0
    warnings = []

    # 1. CPU Checks (weight: 30)
    if cpu.total_percent > 90.0:
        score -= 30.0
        warnings.append(f"CRITICAL: CPU usage is at {cpu.total_percent:.1f}%")
    elif cpu.total_percent > 70.0:
        score -= 10.0
        warnings.append(f"WARNING: CPU usage is at {cpu.total_percent:.1f}%")

    # 2. Memory Checks (weight: 30)
    if memory.percent > 90.0:
        score -= 30.0
        warnings.append(f"CRITICAL: Memory usage is at {memory.percent:.1f}%")
    elif memory.percent > 80.0:
        score -= 15.0
        warnings.append(f"WARNING: Memory usage is at {memory.percent:.1f}%")

    # 3. Disk Checks (weight: 20)
    for part in disk_partitions:
        if part.percent > 95.0:
            score -= 20.0
            warnings.append(f"CRITICAL: Disk {part.mountpoint} is {part.percent:.1f}% full")
        elif part.percent > 85.0:
            score -= 5.0
            warnings.append(f"WARNING: Disk {part.mountpoint} is {part.percent:.1f}% full")

    # 4. Network Checks (weight: 20)
    if ping_stats:
        avg_loss = sum(p.packet_loss for p in ping_stats) / len(ping_stats)
        if avg_loss > 5.0:
            score -= 20.0
            warnings.append(f"CRITICAL: High average packet loss ({avg_loss:.1f}%)")
        elif avg_loss > 1.0:
            score -= 10.0
            warnings.append(f"WARNING: Minor packet loss detected ({avg_loss:.1f}%)")

        avg_latency = sum(p.avg_latency for p in ping_stats) / len(ping_stats)
        if avg_latency > 200.0:
            score -= 10.0
            warnings.append(f"WARNING: High average latency ({avg_latency:.1f}ms)")

    final_score = max(0, min(100, int(score)))
    return HealthScore(score=final_score, warnings=warnings)
