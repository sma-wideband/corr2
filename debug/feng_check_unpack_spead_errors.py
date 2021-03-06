# -*- coding: utf-8 -*-
"""
Created on Thu May 22 13:35:29 2014

This script pulls a snapshot from the unpack block on the f-engine and examines the spead data inside it to see if it matches
d-engine TVG data.

@author: paulp
"""

import numpy

import casperfpga

feng_hosts = ['roach02091b', 'roach020914', 'roach020958', 'roach020922']
f = casperfpga.KatcpClientFpga(feng_hosts[2])
f.get_system_information()
snaps = f.snapshots.names()
if snaps.count('unpack_spead0_ss') == 0:
    raise RuntimeError('The f-engine does not have the required snapshot compiled into it.')

snapdata = f.snapshots.unpack_spead0_ss.read(man_trig=True,circular_capture=True)['data']

# check the data
lastval = snapdata['dramp'][0] - 1
errors = False
for ctr, val in enumerate(snapdata['dramp']):
    if val == 0:
        if lastval != 511:
            errors = True
            print 'ERROR over rollover at %i'%ctr
    else:
        if val != lastval + 1:
            errors = True
            print 'ERROR in the ramp at %i'%ctr
    lastval = val
if errors:
    print 'DATA RAMP ERRORS ENCOUNTERED'

# check the time and pkt_time
errors = False
for ctr, p in enumerate(snapdata['dtime']):
    if p != snapdata['pkt_time'][ctr]:
        print 'ERROR:', ctr-1, snapdata['dtime'][ctr-1], numpy.binary_repr(snapdata['dtime'][ctr-1]), snapdata['pkt_time'][ctr-1]
        print 'ERROR:', ctr, p, numpy.binary_repr(p), snapdata['pkt_time'][ctr]
        errors = True
if errors:
    print 'TIME vs PKT_TIME ERRORS ENCOUNTERED'

# check the unique times and timestep
errors = False
unique_times = list(numpy.unique(snapdata['pkt_time']))
for ctr, utime in enumerate(unique_times[1:]):
    if utime != unique_times[ctr] + 2:
        print 'ERROR:', ctr, utime, unique_times[ctr-1]
        errors = True
if errors:
    print 'TIMESTEP ERRORS ENCOUNTERED'
