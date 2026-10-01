"""
Network diagnostics module for connectivity and throughput telemetry.
"""

import concurrent.futures
import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import psutil


@dataclass
class NetworkInterfaceInfo:
    """Network interface throughput telemetry."""
    name: str
    is_up: bool
    bytes_sent: int
    bytes_recv: int
    upload_speed: float  # bytes per second
    download_speed: float # bytes per second


@dataclass
class PingStats:
    """Ping statistics for a target."""
    target: str
    avg_latency: float  # ms
    jitter: float       # ms
    packet_loss: float  # percent 0-100


@dataclass
class DNSBenchmark:
    """DNS lookup benchmark result."""
    provider: str
    target_domain: str
    resolve_time: float  # ms


class NetworkMonitor:
    """Monitors network telemetry and diagnostics."""

    DEFAULT_PING_TARGETS = ["1.1.1.1", "8.8.8.8"]
    DNS_PROVIDERS = [
        ("System Default", None),
        ("Cloudflare", "1.1.1.1"),
        ("Google", "8.8.8.8"),
        ("Quad9", "9.9.9.9")
    ]

    def __init__(self) -> None:
        """Initialize the network monitor."""
        self._last_net_io = psutil.net_io_counters(pernic=True)
        self._last_time = time.time()

    def get_interfaces_info(self) -> Dict[str, NetworkInterfaceInfo]:
        """Get throughput stats for active network interfaces."""
        current_time = time.time()
        current_io = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()

        time_diff = current_time - self._last_time
        if time_diff <= 0:
            time_diff = 1.0

        interfaces = {}
        for name, io in current_io.items():
            is_up = stats[name].isup if name in stats else False

            last_io = self._last_net_io.get(name)
            if not last_io or not is_up:
                upload_speed = 0.0
                download_speed = 0.0
            else:
                upload_speed = (io.bytes_sent - last_io.bytes_sent) / time_diff
                download_speed = (io.bytes_recv - last_io.bytes_recv) / time_diff

            interfaces[name] = NetworkInterfaceInfo(
                name=name,
                is_up=is_up,
                bytes_sent=io.bytes_sent,
                bytes_recv=io.bytes_recv,
                upload_speed=max(0.0, upload_speed),
                download_speed=max(0.0, download_speed),
            )

        self._last_net_io = current_io
        self._last_time = current_time

        return interfaces

    def _get_default_gateway(self) -> Optional[str]:
        """Attempt to find the default gateway IP."""
        try:
            # We can use a simple trick with socket to find the local IP used for internet access
            # This doesn't get the gateway IP directly, but we can look it up if needed.
            # However, `psutil` doesn't provide gateway info. We can mock it or parse `netstat -rn` / `route -n`.
            # For cross-platform simplicity in this scope, we can parse `ipconfig` or `ip route`.
            if platform.system() == "Windows":
                output = subprocess.check_output("route print 0.0.0.0", shell=True).decode()
                match = re.search(r"0\.0\.0\.0\s+0\.0\.0\.0\s+([0-9\.]+)", output)
                if match:
                    return match.group(1)
            else:
                output = subprocess.check_output("ip route", shell=True).decode()
                match = re.search(r"default via ([0-9\.]+)", output)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def _ping_target(self, target: str, count: int = 4) -> PingStats:
        """Ping a target using system ping and parse results."""
        # Due to privileges required for ICMP sockets, we'll use subprocess ping.
        is_win = platform.system() == "Windows"
        cmd = ["ping", "-n" if is_win else "-c", str(count), target]

        try:
            # timeout ensures we don't hang forever
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5).decode(errors="ignore")

            # parse packet loss
            loss_match = re.search(r"(\d+)% packet loss", output, re.IGNORECASE)
            if not loss_match:
                # Windows might use different formatting
                loss_match = re.search(r"\((\d+)% loss\)", output, re.IGNORECASE)

            packet_loss = float(loss_match.group(1)) if loss_match else 100.0

            # parse latencies
            if is_win:
                latencies = [float(x) for x in re.findall(r"time[=<](\d+)ms", output, re.IGNORECASE)]
            else:
                latencies = [float(x) for x in re.findall(r"time=([\d\.]+) ms", output, re.IGNORECASE)]

            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                # Jitter is average absolute difference between consecutive latencies
                if len(latencies) > 1:
                    diffs = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]
                    jitter = sum(diffs) / len(diffs)
                else:
                    jitter = 0.0
            else:
                avg_latency = 0.0
                jitter = 0.0

            return PingStats(target, avg_latency, jitter, packet_loss)

        except subprocess.TimeoutExpired:
            return PingStats(target, 0.0, 0.0, 100.0)
        except subprocess.CalledProcessError:
            return PingStats(target, 0.0, 0.0, 100.0)
        except Exception:
            return PingStats(target, 0.0, 0.0, 100.0)

    def check_latency(self) -> List[PingStats]:
        """Check latency to default targets + local gateway concurrently."""
        targets = list(self.DEFAULT_PING_TARGETS)
        gateway = self._get_default_gateway()
        if gateway and gateway not in targets:
            targets.append(gateway)

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets)) as executor:
            future_to_target = {executor.submit(self._ping_target, t): t for t in targets}
            for future in concurrent.futures.as_completed(future_to_target):
                results.append(future.result())

        return results

    def _resolve_dns(self, target_domain: str, server: Optional[str] = None) -> float:
        """Resolve DNS and return time in ms. Note: true custom DNS needs dnspython.
           We use socket for default, and an approximation or fallback for custom."""
        start = time.time()
        try:
            if server:
                # Without an external library like dnspython, we can't easily query specific servers using socket.gethostbyname.
                # However, for the sake of the requirement without adding extra deps, we will mock the custom server part
                # by simply using nslookup which is cross-platform.
                subprocess.check_output(
                    ["nslookup", target_domain, server],
                    stderr=subprocess.STDOUT,
                    timeout=3
                )
            else:
                socket.gethostbyname(target_domain)
        except Exception:
            return -1.0

        return (time.time() - start) * 1000.0

    def benchmark_dns(self, target_domain: str = "example.com") -> List[DNSBenchmark]:
        """Benchmark DNS lookup times across providers."""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.DNS_PROVIDERS)) as executor:
            futures = {
                executor.submit(self._resolve_dns, target_domain, srv): (name, srv)
                for name, srv in self.DNS_PROVIDERS
            }

            for future in concurrent.futures.as_completed(futures):
                name, _ = futures[future]
                try:
                    resolve_time = future.result()
                except Exception:
                    resolve_time = -1.0
                results.append(DNSBenchmark(name, target_domain, resolve_time))

        return results
