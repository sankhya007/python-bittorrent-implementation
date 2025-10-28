from torrent import bencode, bdecode

def enhance_ubuntu_torrent():
    input_path = "ubuntu-25.10-desktop-amd64.iso.torrent"
    output_path = "ubuntu_enhanced.torrent"
    
    with open(input_path, 'rb') as f:
        torrent_data = bdecode(f.read())
    
    # Add public trackers that always have peers
    public_trackers = [
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
    
    if b'announce-list' in torrent_data:
        torrent_data[b'announce-list'].extend(public_trackers)
    else:
        torrent_data[b'announce-list'] = public_trackers
    
    with open(output_path, 'wb') as f:
        f.write(bencode(torrent_data))
    
    print(f"✅ Enhanced torrent saved: {output_path}")
    return output_path

enhanced_file = enhance_ubuntu_torrent()