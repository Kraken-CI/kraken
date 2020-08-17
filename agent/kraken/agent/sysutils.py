import socket
import fcntl
import struct
import array


def get_ifaces():
    max_possible = 128 # arbitrary. raise if needed.
    obytes = max_possible * 32
    deb = b'\0'

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    names = array.array('B', deb * obytes)
    outbytes = struct.unpack('iL', fcntl.ioctl(
        s.fileno(),
        0x8912,  # SIOCGIFCONF
        struct.pack('iL', obytes, names.buffer_info()[0])
    ))[0]

    namestr = names.tostring()

    lst = []
    for i in range(0, outbytes, 40):
        name = namestr[ i: i+16 ].split( deb, 1)[0]
        name = name.decode()
        #iface_name = namestr[ i : i+16 ].split( deb, 1 )[0]
        ip   = namestr[i+20:i+24]
        ip = f'{ip[0]}.{ip[1]}.{ip[2]}.{ip[3]}'
        lst.append((name, ip))
    return lst


def get_my_ip(dest_addr):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect((dest_addr, 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = None
    finally:
        s.close()
    return ip
