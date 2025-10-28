import socket
import requests
import subprocess
import sys
import time

def test_dns_resolution():
    """Test DNS resolution for common trackers"""
    print("🔍 Testing DNS resolution...")
    
    domains = [
        'tracker.opentrackr.org',
        'open.tracker.cl', 
        'tracker.openbittorrent.com',
        'tracker.torrent.eu.org',
        'tracker.dler.org',
        'exodus.desync.com'
    ]
    
    all_resolved = True
    for domain in domains:
        try:
            ip = socket.gethostbyname(domain)
            print(f"✅ {domain} -> {ip}")
        except socket.gaierror as e:
            print(f"❌ {domain} - DNS resolution failed: {e}")
            all_resolved = False
            
    return all_resolved

def test_basic_internet():
    """Test basic internet connectivity"""
    print("\n🌐 Testing basic internet connectivity...")
    
    test_urls = [
        "https://www.google.com",
        "https://www.cloudflare.com", 
        "https://www.github.com"
    ]
    
    internet_ok = False
    for url in test_urls:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = (time.time() - start_time) * 1000
            if response.status_code == 200:
                print(f"✅ {url} - OK ({response_time:.0f}ms)")
                internet_ok = True
                break
            else:
                print(f"⚠️  {url} - Status {response.status_code} ({response_time:.0f}ms)")
        except requests.exceptions.Timeout:
            print(f"❌ {url} - Timeout after 10s")
        except requests.exceptions.ConnectionError:
            print(f"❌ {url} - Connection error")
        except Exception as e:
            print(f"❌ {url} - {e}")
    
    return internet_ok

def test_tracker_connectivity():
    """Test connectivity to common BitTorrent trackers"""
    print("\n📡 Testing BitTorrent tracker connectivity...")
    
    # Common BitTorrent trackers with their standard ports
    trackers = [
        ('udp://tracker.opentrackr.org', 1337, 'UDP'),
        ('udp://open.tracker.cl', 1337, 'UDP'),
        ('udp://tracker.openbittorrent.com', 6969, 'UDP'),
        ('udp://tracker.torrent.eu.org', 451, 'UDP'),
        ('udp://tracker.internetwarriors.net', 1337, 'UDP'),
        ('http://tracker.dler.org', 6969, 'HTTP'),
        ('udp://exodus.desync.com', 6969, 'UDP'),
        ('udp://9.rarbg.com', 2810, 'UDP'),
        ('udp://opentracker.i2p.rocks', 6969, 'UDP')
    ]
    
    successful_trackers = 0
    
    for tracker_url, port, protocol in trackers:
        hostname = tracker_url.replace('udp://', '').replace('http://', '').replace('https://', '').split('/')[0]
        
        try:
            # Test 1: DNS resolution
            try:
                ip = socket.gethostbyname(hostname)
                dns_status = f"-> {ip}"
            except socket.gaierror:
                print(f"❌ {tracker_url}:{port} ({protocol}) - DNS failed")
                continue
            
            # Test 2: TCP port connectivity (for HTTP trackers or general reachability)
            if protocol == 'HTTP' or True:  # Test TCP for all trackers
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                start_time = time.time()
                result = sock.connect_ex((ip, port))
                connect_time = (time.time() - start_time) * 1000
                
                if result == 0:
                    print(f"✅ {tracker_url}:{port} ({protocol}) {dns_status} - Reachable ({connect_time:.0f}ms)")
                    successful_trackers += 1
                    sock.close()
                else:
                    # TCP failed, but UDP might still work
                    print(f"⚠️  {tracker_url}:{port} ({protocol}) {dns_status} - TCP refused (UDP may work)")
                    sock.close()
                    
            # Note: UDP testing would require actual tracker protocol communication
            # which is complex for a simple connectivity test
            
        except socket.timeout:
            print(f"❌ {tracker_url}:{port} ({protocol}) - Connection timeout")
        except Exception as e:
            print(f"❌ {tracker_url}:{port} ({protocol}) - Error: {e}")
    
    print(f"\n📊 Tracker summary: {successful_trackers}/{len(trackers)} trackers reachable")
    return successful_trackers > 0

def test_firewall_ports():
    """Test common BitTorrent ports"""
    print("\n🔥 Testing common BitTorrent ports...")
    
    common_ports = [6881, 6882, 6883, 6884, 6885, 6886, 6887, 6888, 6889, 6890]
    
    # Test if we can bind to these ports (not already in use)
    available_ports = []
    for port in common_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.close()
            available_ports.append(port)
            print(f"✅ Port {port} - Available")
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"⚠️  Port {port} - In use (normal if other torrent clients running)")
            else:
                print(f"❌ Port {port} - Blocked: {e}")
        except Exception as e:
            print(f"❌ Port {port} - Error: {e}")
    
    print(f"📊 Port summary: {len(available_ports)}/{len(common_ports)} ports available")
    return len(available_ports) > 0

def check_system_connectivity():
    """Check system-level network connectivity"""
    print("\n💻 Testing system network configuration...")
    
    # Test local network
    try:
        socket.gethostbyname("localhost")
        print("✅ Localhost resolution - OK")
    except:
        print("❌ Localhost resolution - Failed")
        return False
    
    # Test gateway/router (usually .1 or .254 in local network)
    try:
        # Try common gateway addresses
        test_ips = ["192.168.1.1", "192.168.0.1", "10.0.0.1", "192.168.1.254"]
        for ip in test_ips:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, 80))
            if result == 0:
                print(f"✅ Local gateway {ip} - Reachable")
                sock.close()
                break
            sock.close()
        else:
            print("⚠️  Local gateway - Not detected (may be normal)")
    except:
        print("⚠️  Local gateway - Test skipped")
    
    return True

def test_connectivity():
    """Comprehensive network connectivity test for BitTorrent"""
    print("=" * 60)
    print("🌐 COMPREHENSIVE NETWORK CONNECTIVITY TEST")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test 1: System connectivity
    if not check_system_connectivity():
        all_tests_passed = False
    
    # Test 2: DNS resolution
    if not test_dns_resolution():
        all_tests_passed = False
    
    # Test 3: Basic internet
    if not test_basic_internet():
        print("❌ CRITICAL: No internet connectivity")
        all_tests_passed = False
        return all_tests_passed
    
    # Test 4: Tracker connectivity  
    if not test_tracker_connectivity():
        print("⚠️  WARNING: Limited tracker connectivity")
        # Don't fail overall test for this
    
    # Test 5: Port availability
    if not test_firewall_ports():
        print("⚠️  WARNING: Limited port availability")
        # Don't fail overall test for this
    
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("🎉 ALL CRITICAL TESTS PASSED - Network ready for BitTorrent!")
    else:
        print("⚠️  Some tests failed - Check network configuration")
    print("=" * 60)
    
    return all_tests_passed

if __name__ == "__main__":
    # Only run tests if script is executed directly
    test_connectivity()