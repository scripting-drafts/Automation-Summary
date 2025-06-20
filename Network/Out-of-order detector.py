import os
import pyshark
from subprocess import call
from tqdm import tqdm

ports, repeatedExists, prev_seq, isOutOfOrder, newOrderStarter, analyzedPackets, affectedPackets, affectedRanges = [], False, None, False, False, [], [], []
capture_file = "capture.pcap"

# if not os.path.exists('original_pcaps'):
#     os.makedirs('original_pcaps')

if not os.path.exists("fixed_" + capture_file):
    fix_cut_packet = call(["pcapfix", capture_file])

cap = pyshark.FileCapture("fixed_" + capture_file, display_filter='udp')

print("Reading ports")
valid_packets = [p for p in tqdm(cap) if p[p.transport_layer] is not None]
ports = [p[p.transport_layer].dstport for p in tqdm(valid_packets) if p[p.transport_layer].dstport != "53"]

if repeatedExists == False:
    for x in range(len(ports)):
        if ports.count(ports[x]) > 1:
            repeatedExists = True

if repeatedExists:
    ports = set(ports)

print("Analyzing traces...")
for port in tqdm(ports):
    rtp_cap = pyshark.FileCapture("fixed_" + capture_file, display_filter='rtp', decode_as={'udp.port==' + port: 'rtp'})
    # rtp_cap.set_debug()
    for rtp_packet in rtp_cap:
        length = rtp_packet.length
        if length == "85" or length == "73":
            seq = int(rtp_packet.rtp.seq)
            ssrc = rtp_packet.rtp.ssrc

            if prev_seq == None:
                prev_seq = seq
                prev_ssrc = ssrc

            elif seq < prev_seq and ssrc == prev_ssrc:
                isOutOfOrder = True
                
                if analyzedPackets[-1][-2] == False:
                    newOrderStarter = True

            elif seq == prev_seq + 1:
                prev_seq = seq
                prev_ssrc = ssrc

            elif seq != prev_seq + 1 and seq > prev_seq:
                prev_seq = seq
                prev_ssrc = ssrc
                
                if isOutOfOrder == True:
                    isOutOfOrder = False

                # print(rtp_packet.number, "Packets dropped")

            elif prev_seq == 65535 and seq == 0:
                prev_seq = seq
                prev_ssrc = ssrc
                # print(rtp_packet.number, "seq_num turnover")

            analyzedPackets.append([rtp_packet.number, seq, isOutOfOrder, newOrderStarter])
            isOutOfOrder = False
            newOrderStarter = False

    rtp_cap.close()
    prev_seq = None

# if analyzedPackets:
#     affectedPackets = [packet[0] for packet in analyzedPackets if packet[-2] == True]
#     starters = [packet[0] for packet in analyzedPackets if packet[-1] == True]
   
print("-----------------------------")

if analyzedPackets:
    for packet in analyzedPackets:
        if packet[-1] == True:
            starter = packet
        elif packet[-1] != True and packet[-2] == True:
            affected = packet
        elif packet[0] != analyzedPackets[0][0] and packet[-2] == False and analyzedPackets[analyzedPackets.index(packet) - 1][-2] == True:
            last = analyzedPackets[analyzedPackets.index(packet) - 1]
            affectedRanges.append([starter, last])

    for x in affectedRanges:
        if affectedRanges.count(x) > 1:
            affectedRanges.remove(x)

    if affectedRanges:
        print("The following ranges are out of order:")

        for affectedRange in sorted(affectedRanges, key=lambda x:x[0], reverse=True):
            print("frame", affectedRange[0][0], "-", affectedRange[1][0], "| seq_num", affectedRange[0][1], "-", affectedRange[1][1])
    else:
        print("No out-of-order packets detected")
