#!/usr/bin/env python3
"""
Script to verify if Kubernetes Service is distributing connections
across Weaviate pods properly for query load balancing.

Run this from inside a k8s pod to test load balancing behavior.
"""

import socket
import os
import sys
import subprocess
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Weaviate endpoint (change for your environment)
WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "weaviate.marco.svc.cluster.local")
WEAVIATE_PORT = int(os.environ.get("WEAVIATE_PORT", "80"))


def resolve_all_ips(hostname):
    """
    Resolve all IPs for a hostname using getent (bypasses Python DNS caching).
    Falls back to socket.getaddrinfo if getent is not available.
    """
    try:
        # Use getent to bypass Python's DNS cache
        result = subprocess.run(
            ["getent", "ahostsv4", hostname],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            ips = set()
            for line in result.stdout.strip().split('\n'):
                if line:
                    ip = line.split()[0]
                    ips.add(ip)
            return list(ips)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback to socket (may be cached)
    try:
        addrs = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        return list(set(addr[4][0] for addr in addrs))
    except Exception:
        return []


def make_connection_to_ip(ip, port):
    """Connect directly to a specific IP and port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        peer = sock.getpeername()[0]
        sock.close()
        return ip, peer, None
    except Exception as e:
        return ip, None, str(e)


def test_dns_resolution_all_ips():
    """Test if DNS returns all pod IPs (for headless service)."""
    print(f"\n=== DNS Resolution Test (All IPs) ===")
    print(f"Resolving all IPs for {WEAVIATE_URL}...")
    
    all_ips = resolve_all_ips(WEAVIATE_URL)
    
    if all_ips:
        print(f"\n✓ Found {len(all_ips)} IP(s):")
        for ip in all_ips:
            print(f"    {ip}")
    else:
        print("\n⚠️  Could not resolve any IPs!")
    
    return all_ips


def test_connections_to_all_ips(all_ips, port):
    """Test HTTP connections to each resolved IP."""
    print(f"\n=== Connection Test to All IPs ===")
    print(f"Testing connections to {len(all_ips)} IPs on port {port}...")
    
    results = []
    for ip in all_ips:
        target_ip, connected_ip, error = make_connection_to_ip(ip, port)
        if error:
            print(f"  {ip}: ❌ Connection failed - {error}")
            results.append((ip, False))
        else:
            print(f"  {ip}: ✓ Connected successfully")
            results.append((ip, True))
    
    successful = sum(1 for _, success in results if success)
    print(f"\n{successful}/{len(all_ips)} connections successful")
    
    return results


def test_round_robin_distribution(all_ips, port, num_connections=32):
    """Test if we can distribute connections across all IPs using round-robin."""
    print(f"\n=== Round-Robin Distribution Test ===")
    print(f"Distributing {num_connections} connections across {len(all_ips)} IPs...")
    
    connected_ips = []
    
    for i in range(num_connections):
        # Round-robin IP selection
        target_ip = all_ips[i % len(all_ips)]
        _, connected_ip, error = make_connection_to_ip(target_ip, port)
        if connected_ip:
            connected_ips.append(connected_ip)
        else:
            connected_ips.append(f"error:{target_ip}")
    
    counter = Counter(connected_ips)
    print("\nConnection Distribution:")
    for ip, count in counter.most_common():
        pct = count / num_connections * 100
        print(f"  {ip}: {count} ({pct:.1f}%)")
    
    successful_ips = [ip for ip in counter.keys() if not ip.startswith("error:")]
    if len(successful_ips) > 1:
        print(f"\n✓ Connections distributed to {len(successful_ips)} different pods")
        return True
    else:
        print("\n⚠️  Could not distribute connections")
        return False


def check_weaviate_nodes_via_ip(ip, port):
    """Check Weaviate cluster nodes via API using a specific IP."""
    try:
        import urllib.request
        import json
        
        url = f"http://{ip}:{port}/v1/nodes"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            nodes = data.get("nodes", [])
            return nodes
    except Exception:
        return None


def main():
    print("=" * 60)
    print("Weaviate Load Balancing Verification")
    print("=" * 60)
    print(f"Target: {WEAVIATE_URL}:{WEAVIATE_PORT}")
    
    # Step 1: Resolve all IPs
    all_ips = test_dns_resolution_all_ips()
    
    if not all_ips:
        print("\n❌ Failed to resolve any IPs. Check the hostname.")
        return
    
    # Step 2: Test connections to each IP
    connection_results = test_connections_to_all_ips(all_ips, WEAVIATE_PORT)
    working_ips = [ip for ip, success in connection_results if success]
    
    if not working_ips:
        print("\n❌ No working IPs found. Check that port is correct (should be 8080 for HTTP).")
        return
    
    # Step 3: Check cluster info via one of the working IPs
    print(f"\n=== Weaviate Cluster Info ===")
    nodes = check_weaviate_nodes_via_ip(working_ips[0], WEAVIATE_PORT)
    if nodes:
        print(f"Cluster has {len(nodes)} nodes:")
        for node in nodes:
            name = node.get("name", "unknown")
            status = node.get("status", "unknown")
            print(f"  - {name}: status={status}")
    else:
        print("Could not get cluster info")
    
    # Step 4: Test round-robin distribution
    success = test_round_robin_distribution(working_ips, WEAVIATE_PORT, 32)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if len(all_ips) > 1:
        print(f"✓ DNS resolved {len(all_ips)} IPs (headless service working)")
    else:
        print("⚠️  DNS resolved only 1 IP (not using headless service)")
    
    if len(working_ips) > 1:
        print(f"✓ {len(working_ips)} IPs are reachable on port {WEAVIATE_PORT}")
    else:
        print(f"⚠️  Only {len(working_ips)} IP(s) reachable on port {WEAVIATE_PORT}")
    
    if success:
        print("✓ Client-side round-robin distribution is working!")
        print("\n  To use in benchmark, implement client-side round-robin:")
        print(f"    1. Resolve all IPs for {WEAVIATE_URL}")
        print(f"    2. Each worker picks IP using: all_ips[worker_id % len(all_ips)]")
        print(f"    3. Connect directly to that IP on port {WEAVIATE_PORT}")
    else:
        print("⚠️  Could not achieve distributed connections")


if __name__ == "__main__":
    main()
