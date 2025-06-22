import re
import os
import pyshark
from subprocess import call

ports, analyzedPackets, affectedPackets, prev_seq, isOutOfOrder = [], [], [], None, False
capture_file = "2021_10-06-11-20"

if not os.path.exists('original_pcaps'):
    os.makedirs('original_pcaps')

fix_cut_packet = call(["python", "pcap-fix.py", "--in", capture_file + ".pcap", "--pcapfix", "--pcapfix_dir", "original_pcaps", "--debug"])
cap = pyshark.FileCapture(capture_file + "-fixed.pcap", display_filter='udp')
ports = [p[p.transport_layer].dstport for p in cap if p[p.transport_layer].dstport != "53"]

for x in range(len(ports)):
    if ports.count(ports[x]) > 1:
        repeatedExists = True

if repeatedExists:
    ports = set(ports)

for port in ports:
    rtp_cap = pyshark.FileCapture(capture_file + "-fixed.pcap", display_filter='rtp', decode_as={'udp.port==' + port: 'rtp'})
    # rtp_cap.set_debug()

    for rtp_packet in rtp_cap:
        seq = rtp_packet.rtp.seq

        if prev_seq == None:
            prev_seq = rtp_packet.rtp.seq

        elif seq < prev_seq:
            isOutOfOrder = True
            newOrderStarted = True

        else:
            prev_seq = rtp_packet.rtp.seq
            isOutOfOrder = False
            newOrderStarted = True
        
        analyzedPackets.append([rtp_packet.number, seq, isOutOfOrder])

    rtp_cap.close()
    prev_seq = None
    isOutOfOrder = True

print(analyzedPackets)

if analyzedPackets:
    affectedPackets = [packet[0] for packet in analyzedPackets if packet[-1] == True]

print("-----------------------------")

print("The out-of-order packets begin at the following frame/s: \n")
print(affectedPackets)

