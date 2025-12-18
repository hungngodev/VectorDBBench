#!/usr/bin/env python3
"""
Script to verify if Kubernetes Service is distributing connections
across Weaviate pods properly for query load balancing.

Run this from inside a k8s pod to test load balancing behavior.
"""

import socket
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Weaviate endpoint (change for your environment)
WEAVIATE_URL = os.environ.get("WEAVIATE_URL", "weaviate.marco.svc.cluster.local")
WEAVIATE_PORT = int(os.environ.get("WEAVIATE_PORT", "80"))


def get_connection_target():
    """Create a new TCP connection and return the resolved IP."""
    try:
        # Each call to getaddrinfo can resolve to a different IP
        # if k8s Service uses round-robin
        addrs = socket.getaddrinfo(WEAVIATE_URL, WEAVIATE_PORT, socket.AF_INET, socket.SOCK_STREAM)
        if addrs:
            return addrs[0][4][0]  # Return IP address
    except Exception as e:
        return f"error: {e}"
    return "unknown"


def test_dns_resolution(num_resolutions=100):
    """Test if DNS returns different IPs (k8s should load balance)."""
    print(f"\n=== DNS Resolution Test ===")
    print(f"Resolving {WEAVIATE_URL}:{WEAVIATE_PORT} {num_resolutions} times...")
    
    ips = []
    for i in range(num_resolutions):
        ip = get_connection_target()
        ips.append(ip)
    
    counter = Counter(ips)
    print(f"\nIP Distribution:")
    for ip, count in counter.most_common():
        print(f"  {ip}: {count} ({count/num_resolutions*100:.1f}%)")
    
    if len(counter) == 1:
        print("\n⚠️  WARNING: All DNS resolutions returned the same IP!")
        print("   This could mean:")
        print("   1. Single pod is running")
        print("   2. DNS caching is happening")
        print("   3. Service type doesn't support load balancing for DNS")
    else:
        print(f"\n✓ Good: DNS returned {len(counter)} different IPs")
    
    return counter


def make_connection_in_process():
    """Function to run in separate process - simulates benchmark behavior."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        # Get IP before connecting
        addrs = socket.getaddrinfo(WEAVIATE_URL, WEAVIATE_PORT, socket.AF_INET, socket.SOCK_STREAM)
        ip = addrs[0][4][0] if addrs else "unknown"
        sock.connect((WEAVIATE_URL, WEAVIATE_PORT))
        # Get the actual peer address after connecting
        peer = sock.getpeername()[0]
        sock.close()
        return ip, peer
    except Exception as e:
        return "error", str(e)


def test_multiprocess_connections(num_processes=32):
    """Test if parallel processes get distributed to different pods."""
    print(f"\n=== Multi-Process Connection Test ===")
    print(f"Creating {num_processes} parallel processes (simulating benchmark)...")
    
    resolved_ips = []
    connected_ips = []
    
    with ProcessPoolExecutor(
        mp_context=mp.get_context("spawn"),
        max_workers=num_processes
    ) as executor:
        futures = [executor.submit(make_connection_in_process) for _ in range(num_processes)]
        for future in as_completed(futures):
            resolved, connected = future.result()
            resolved_ips.append(resolved)
            connected_ips.append(connected)
    
    print("\nResolved IP Distribution (DNS):")
    res_counter = Counter(resolved_ips)
    for ip, count in res_counter.most_common():
        print(f"  {ip}: {count}")
    
    print("\nConnected IP Distribution (actual connection):")
    conn_counter = Counter(connected_ips)
    for ip, count in conn_counter.most_common():
        print(f"  {ip}: {count}")
    
    if len(conn_counter) == 1 and "error" not in list(conn_counter.keys())[0]:
        print("\n⚠️  WARNING: All connections went to the same pod!")
        print("   The benchmark may not be testing distributed query performance.")
    elif len(conn_counter) > 1:
        print(f"\n✓ Good: Connections distributed to {len(conn_counter)} different pods")
    
    return res_counter, conn_counter


def check_weaviate_nodes():
    """Check Weaviate cluster nodes via API."""
    print(f"\n=== Weaviate Cluster Info ===")
    try:
        import urllib.request
        import json
        
        url = f"http://{WEAVIATE_URL}:{WEAVIATE_PORT}/v1/nodes"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            nodes = data.get("nodes", [])
            print(f"Cluster has {len(nodes)} nodes:")
            for node in nodes:
                name = node.get("name", "unknown")
                status = node.get("status", "unknown")
                shards = node.get("shards", [])
                print(f"  - {name}: status={status}, shards={len(shards)}")
            return nodes
    except Exception as e:
        print(f"Could not get cluster info: {e}")
        return None


def main():
    print("=" * 60)
    print("Weaviate Load Balancing Verification")
    print("=" * 60)
    print(f"Target: {WEAVIATE_URL}:{WEAVIATE_PORT}")
    
    # Check cluster info
    nodes = check_weaviate_nodes()
    
    # Test DNS resolution
    dns_counter = test_dns_resolution(100)
    
    # Test multi-process connections
    res_counter, conn_counter = test_multiprocess_connections(32)
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if nodes and len(nodes) > 1:
        print(f"✓ Weaviate cluster has {len(nodes)} nodes")
    else:
        print("⚠️  Could not verify multiple Weaviate nodes")
    
    unique_ips = len([ip for ip in conn_counter.keys() if "error" not in ip])
    if unique_ips > 1:
        print(f"✓ Connections are distributed to {unique_ips} different IPs")
        print("  Load balancing appears to be working!")
    else:
        print("⚠️  Connections are NOT distributed")
        print("  This explains why scaling isn't linear")
        print("\n  Possible fixes:")
        print("  1. Check k8s Service type (should be ClusterIP with default LB)")
        print("  2. Ensure sessionAffinity: None (default)")
        print("  3. Use headless service + client-side load balancing")


if __name__ == "__main__":
    main()
