import socket
import requests

def test_connectivity():
    print("🌐 Testing network connectivity...")
    
    # Test basic internet
    try:
        requests.get("https://www.google.com", timeout=5)
        print("✅ Internet connectivity: OK")
    except:
        print("❌ Internet connectivity: Failed")
        return False
    
    # Test common tracker ports
    trackers = [
        ('tracker.opentrackr.org', 1337),
        ('open.tracker.cl', 1337),
        ('tracker.openbittorrent.com', 6969)
    ]
    
    for host, port in trackers:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            if result == 0:
                print(f"✅ {host}:{port} - Reachable")
            else:
                print(f"⚠️  {host}:{port} - Connection refused")
            sock.close()
        except Exception as e:
            print(f"❌ {host}:{port} - {e}")
    
    return True

test_connectivity()