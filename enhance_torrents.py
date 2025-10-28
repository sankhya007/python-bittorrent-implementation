from torrent import bencode, bdecode
import os

def enhance_debian_torrent():
    input_path = "C:\Users\Asus\personal_torrent_client\torrents\debian-13.1.0-amd64-netinst.iso.torrent"
    output_path = "debian_enhanced.torrent"
    
    print(f"📁 Enhancing: {input_path}")
    
    # Read the original torrent
    with open(input_path, 'rb') as f:
        torrent_data = bdecode(f.read())
    
    print("✅ Original torrent loaded")
    
    # Add popular public trackers
    additional_trackers = [
        [b"udp://tracker.opentrackr.org:1337/announce"],
        [b"udp://open.tracker.cl:1337/announce"], 
        [b"udp://9.rarbg.com:2810/announce"],
        [b"udp://tracker.openbittorrent.com:6969/announce"],
        [b"http://tracker.openbittorrent.com:80/announce"],
        [b"udp://opentracker.i2p.rocks:6969/announce"],
        [b"udp://tracker.torrent.eu.org:451/announce"],
        [b"udp://tracker.internetwarriors.net:1337/announce"],
        [b"http://tracker.dler.org:6969/announce"],
        [b"udp://exodus.desync.com:6969/announce"]
    ]
    
    # Add trackers to torrent
    if b'announce-list' in torrent_data:
        torrent_data[b'announce-list'].extend(additional_trackers)
    else:
        torrent_data[b'announce-list'] = additional_trackers
    
    # Also add as individual announce for compatibility
    torrent_data[b'announce'] = b"udp://tracker.opentrackr.org:1337/announce"
    
    # Save enhanced torrent
    with open(output_path, 'wb') as f:
        f.write(bencode(torrent_data))
    
    print(f"✅ Enhanced torrent saved as: {output_path}")
    print(f"📊 Added {len(additional_trackers)} additional trackers")
    
    return output_path

# Run the enhancement
enhanced_file = enhance_debian_torrent()