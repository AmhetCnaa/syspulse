"""
CLI module for syspulse.
"""

import argparse
import json
import sys
import time
from typing import Any, Dict

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .hardware import HardwareMonitor
from .health import calculate_health_score
from .network import NetworkMonitor


def _format_bytes(size: float) -> str:
    """Format bytes into a human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def _generate_hardware_table(hw: HardwareMonitor) -> Table:
    """Generate the rich table for hardware telemetry."""
    cpu = hw.get_cpu_info()
    mem = hw.get_memory_info()
    swap = hw.get_swap_info()
    io = hw.get_disk_io()

    table = Table(title="Hardware Telemetry", expand=True)
    table.add_column("Resource", style="cyan", no_wrap=True)
    table.add_column("Usage/Stats", style="magenta")

    # CPU
    cpu_cores_str = ", ".join(f"{c:.1f}%" for c in cpu.per_core_percent)
    if len(cpu_cores_str) > 50:
        cpu_cores_str = cpu_cores_str[:47] + "..."
    table.add_row(
        "CPU",
        f"Total: {cpu.total_percent:.1f}% @ {cpu.frequency:.0f}MHz\n"
        f"Load: {cpu.load_avg[0]:.2f}, {cpu.load_avg[1]:.2f}, {cpu.load_avg[2]:.2f}\n"
        f"Cores: {cpu_cores_str}"
    )

    # Memory
    table.add_row(
        "Memory",
        f"RAM: {_format_bytes(mem.used)} / {_format_bytes(mem.total)} ({mem.percent}%)\n"
        f"Swap: {_format_bytes(swap.used)} / {_format_bytes(swap.total)} ({swap.percent}%)"
    )

    # Disk I/O
    table.add_row(
        "Disk I/O",
        f"Read: {_format_bytes(io.read_speed)}/s | Write: {_format_bytes(io.write_speed)}/s"
    )

    # Disk Partitions
    partitions = hw.get_disk_partitions()
    for p in partitions:
        table.add_row(
            f"Disk [{p.mountpoint}]",
            f"{_format_bytes(p.used)} / {_format_bytes(p.total)} ({p.percent}%)"
        )

    return table


def _generate_network_table(net: NetworkMonitor) -> Table:
    """Generate the rich table for network telemetry."""
    interfaces = net.get_interfaces_info()
    pings = net.check_latency()

    table = Table(title="Network Diagnostics", expand=True)
    table.add_column("Component", style="cyan")
    table.add_column("Metrics", style="green")

    # Interfaces
    for name, info in interfaces.items():
        if info.is_up:
            table.add_row(
                f"Interface: {name}",
                f"Up: {_format_bytes(info.upload_speed)}/s | Down: {_format_bytes(info.download_speed)}/s"
            )

    # Pings
    for p in pings:
        color = "red" if p.packet_loss > 5.0 else "green"
        table.add_row(
            f"Ping -> {p.target}",
            f"[{color}]Loss: {p.packet_loss:.1f}%[/] | Latency: {p.avg_latency:.1f}ms | Jitter: {p.jitter:.1f}ms"
        )

    # DNS
    dns_bench = net.benchmark_dns()
    dns_str = " | ".join(f"{b.provider}: {b.resolve_time:.1f}ms" if b.resolve_time >= 0 else f"{b.provider}: ERR" for b in dns_bench)
    table.add_row("DNS Resolvers", dns_str)

    return table


def _generate_health_panel(hw: HardwareMonitor, net: NetworkMonitor) -> Panel:
    """Generate the health score panel."""
    cpu = hw.get_cpu_info()
    mem = hw.get_memory_info()
    parts = hw.get_disk_partitions()
    pings = net.check_latency()

    health = calculate_health_score(cpu, mem, parts, pings)

    color = "green"
    if health.score < 50:
        color = "red"
    elif health.score < 80:
        color = "yellow"

    score_text = Text(f"System Health Score: {health.score}/100\n", style=f"bold {color}")

    if health.warnings:
        score_text.append("\nWarnings:\n", style="bold yellow")
        for w in health.warnings:
            score_text.append(f"- {w}\n", style="red")
    else:
        score_text.append("\nAll systems operating nominally.", style="green")

    return Panel(score_text, title="Health & Alerts", expand=True)


def _generate_layout(hw: HardwareMonitor, net: NetworkMonitor) -> Layout:
    """Create the rich layout for live mode."""
    layout = Layout()
    layout.split_column(
        Layout(name="upper", ratio=2),
        Layout(name="lower", ratio=1)
    )
    layout["upper"].split_row(
        Layout(name="hw"),
        Layout(name="net")
    )

    layout["hw"].update(_generate_hardware_table(hw))
    layout["net"].update(_generate_network_table(net))
    layout["lower"].update(_generate_health_panel(hw, net))

    return layout


def _export_json(hw: HardwareMonitor, net: NetworkMonitor) -> str:
    """Export all telemetry as JSON."""
    cpu = hw.get_cpu_info()
    mem = hw.get_memory_info()
    swap = hw.get_swap_info()
    io = hw.get_disk_io()
    parts = hw.get_disk_partitions()

    interfaces = net.get_interfaces_info()
    pings = net.check_latency()
    dns = net.benchmark_dns()

    health = calculate_health_score(cpu, mem, parts, pings)

    data: Dict[str, Any] = {
        "hardware": {
            "cpu": {
                "per_core_percent": cpu.per_core_percent,
                "total_percent": cpu.total_percent,
                "frequency": cpu.frequency,
                "load_avg": cpu.load_avg,
            },
            "memory": {
                "total": mem.total,
                "available": mem.available,
                "used": mem.used,
                "percent": mem.percent,
            },
            "swap": {
                "total": swap.total,
                "used": swap.used,
                "free": swap.free,
                "percent": swap.percent,
            },
            "disk_io": {
                "read_bytes": io.read_bytes,
                "write_bytes": io.write_bytes,
                "read_speed": io.read_speed,
                "write_speed": io.write_speed,
            },
            "disk_partitions": [
                {
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total": p.total,
                    "used": p.used,
                    "free": p.free,
                    "percent": p.percent,
                } for p in parts
            ]
        },
        "network": {
            "interfaces": {
                k: {
                    "is_up": v.is_up,
                    "bytes_sent": v.bytes_sent,
                    "bytes_recv": v.bytes_recv,
                    "upload_speed": v.upload_speed,
                    "download_speed": v.download_speed,
                } for k, v in interfaces.items()
            },
            "pings": [
                {
                    "target": p.target,
                    "avg_latency": p.avg_latency,
                    "jitter": p.jitter,
                    "packet_loss": p.packet_loss,
                } for p in pings
            ],
            "dns": [
                {
                    "provider": d.provider,
                    "target_domain": d.target_domain,
                    "resolve_time": d.resolve_time,
                } for d in dns
            ]
        },
        "health": {
            "score": health.score,
            "warnings": health.warnings,
        }
    }

    return json.dumps(data, indent=2)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="syspulse - Modern system health diagnostic tool")
    parser.add_argument("--snapshot", action="store_true", help="Print a one-shot snapshot and exit")
    parser.add_argument("--json", action="store_true", help="Output diagnostics in JSON format")

    args = parser.parse_args()

    hw = HardwareMonitor()
    net = NetworkMonitor()

    # Warm up monitors for differential metrics
    hw.get_disk_io()
    net.get_interfaces_info()
    time.sleep(0.1)

    console = Console()

    if args.json:
        print(_export_json(hw, net))
        sys.exit(0)

    if args.snapshot:
        console.print(_generate_hardware_table(hw))
        console.print(_generate_network_table(net))
        console.print(_generate_health_panel(hw, net))
        sys.exit(0)

    # Interactive Live Monitor
    try:
        with Live(_generate_layout(hw, net), console=console, screen=True, refresh_per_second=1) as live:
            while True:
                time.sleep(1)
                live.update(_generate_layout(hw, net))
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
