#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable-msg=C0103
# pylint: disable-msg=C0301
"""
View the status of a given xengine.

Created on Fri Jan  3 10:40:53 2014

@author: paulp
"""
import sys, logging, time, argparse

logger = logging.getLogger(__name__)
#logging.basicConfig(level=logging.INFO)

from corr2.katcp_client_fpga import KatcpClientFpga
from corr2.fpgadevice.tengbe import ip2str
import corr2.scroll as scroll

parser = argparse.ArgumentParser(description='Display the data unpack counters on the fengine.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument(dest='hosts', type=str, action='store',
                    help='comma-delimited list of f-engine hosts')
parser.add_argument('-p', '--polltime', dest='polltime', action='store',
                    default=1, type=int,
                    help='time at which to poll fengine data, in seconds')
parser.add_argument('-r', '--reset_count', dest='rstcnt', action='store_true',
                    default=False,
                    help='reset all counters at script startup')
args = parser.parse_args()

polltime = args.polltime

feng_hosts = args.hosts.lstrip().rstrip().replace(' ', '').split(',')

feng_hosts = ['roach02091b', 'roach020914', 'roach020958', 'roach020922']

tx_ips = {}

# create the devices and connect to them
ffpgas = []
for host in feng_hosts:
    feng_fpga = KatcpClientFpga(host)
    feng_fpga.get_system_information()
    if args.rstcnt:
        feng_fpga.registers.control.write(cnt_rst='pulse')
    ffpgas.append(feng_fpga)

def get_fpga_data(fpga):
    if not tx_ips.has_key(fpga.host):
        tx_ips[fpga.host] = {'ip0': {}, 'ip1': {}, 'ip2': {}, 'ip3': {}, 'port0': {}, 'port1': {}, 'port2': {}, 'port3': {}}
    for ctr in range(0,4):
        txip = fpga.device_by_name('txip%i'%ctr).read()['data']['ip']
        if not tx_ips[fpga.host]['ip%i'%ctr].has_key(txip):
            tx_ips[fpga.host]['ip%i'%ctr][txip] = 1
        else:
            tx_ips[fpga.host]['ip%i'%ctr][txip] += 1
    txport = fpga.registers.txpport01.read()['data']
    txport.update(fpga.registers.txpport23.read()['data'])
    for ctr in range(0,4):
        if not tx_ips[fpga.host]['port%i'%ctr].has_key(txport['port%i'%ctr]):
            tx_ips[fpga.host]['port%i'%ctr][txport['port%i'%ctr]] = 1
        else:
            tx_ips[fpga.host]['port%i'%ctr][txport['port%i'%ctr]] += 1

import signal
def signal_handler(sig, frame):
    print sig, frame
    for fpga in ffpgas:
        fpga.disconnect()
    scroll.screen_teardown()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)

# set up the curses scroll screen
scroller = scroll.Scroll(debug=False)
scroller.screen_setup()
# main program loop
STARTTIME = time.time()
last_refresh = STARTTIME - 3
try:
    while True:
        # get key presses from ncurses
        keypress, character = scroller.on_keypress()
        if keypress == -1:
            break
        elif keypress > 0:
#            if character == 'c':
#                for f in ffpgas:
#                    f.reset_counters()
            scroller.draw_screen()
        if time.time() > last_refresh + polltime:
            scroller.clear_buffer()
            scroller.add_line('Polling %i fengine%s every %s - %is elapsed.' %
                (len(ffpgas), '' if len(ffpgas) == 1 else 's',
                'second' if polltime == 1 else ('%i seconds' % polltime),
                time.time() - STARTTIME), 0, 0, absolute=True)
            start_pos = 20
            pos_increment = 15
            scroller.set_ypos(newpos=1)
            for ctr, fpga in enumerate(ffpgas):
                get_fpga_data(fpga)
                fpga_data = tx_ips[fpga.host]
                scroller.add_line(fpga.host)
                for ctr in range(0,4):
                    ipstr = '\tip%i: '%ctr
                    ip_addresses = fpga_data['ip%i'%ctr].keys()
                    ip_addresses.sort()
                    cntmin = pow(2,32) - 1
                    cntmax = -1
                    for ip in ip_addresses:
                        cntmin = min([fpga_data['ip%i'%ctr][ip], cntmin])
                        cntmax = max([fpga_data['ip%i'%ctr][ip], cntmax])
                        ipstr += ip2str(ip) + '[%5d], '%fpga_data['ip%i'%ctr][ip]
                    ipstr += 'spread[%2.2f], '%((cntmax-cntmin)/(cntmax*1.0)*100.0)
                    ports = fpga_data['port%i'%ctr].keys()
                    ports.sort()
                    for port in ports:
                        ipstr += str(port) + '[%5d], '%fpga_data['port%i'%ctr][port]
                    scroller.add_line(ipstr)
            scroller.draw_screen()
            last_refresh = time.time()
except Exception, e:
    for fpga in ffpgas:
        fpga.disconnect()
    scroll.screen_teardown()
    raise

# handle exits cleanly
for fpga in ffpgas:
    fpga.disconnect()
scroll.screen_teardown()
# end
