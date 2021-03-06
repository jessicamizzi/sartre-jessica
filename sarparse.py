#! /usr/bin/env python
import datetime
from collections import namedtuple
import time
import gzip

def parse_timelog(filename):
    """
    Load in a file with lines like 'scriptname stagename timestamp' and
    parse the times.
    """
    d = {}

    typ = namedtuple('TimelogEntry', 'script stage timestamp')

    parsed = []
    for line in open(filename):
        script, stage, tstamp = line.strip().split(' ', 2)
        tstamp = datetime.datetime.strptime(tstamp, '%a %b %d %H:%M:%S %Z %Y')
        parsed.append(typ(script, stage, tstamp))

    return d, parsed


def parse_sar_cpu(filename):
    """
    Parse the 'sar' CPU load format:

    09:40:03 PM     CPU     %user     %nice   %system   %iowait    %steal     %idle
    """
    parsed = []

    typ = namedtuple('CPUUsage', 'time cpu puser pnice psystem piowait '
                     'psteal pidle')
    
    for n, line in enumerate(gzip.open(filename)):
        if not line.strip():            # skip blank lines
            continue
        if n < 3:                       # skip headers
            continue
        if line.startswith('Average'):  # skip footer and blank lines
            continue
        if "%user" in line:             # skip reintroduced headers
            continue

        line = line.strip().split()
        assert len(line) == 9, len(line)
        line2 = [line[0] + ' ' + line[1], line[2]]
        line2.extend(( float(x) for x in line[3:]))

        t = typ(*line2)
        parsed.append(t)

    return parsed


def parse_sar_ram(filename):
    """
    Parse the 'sar' RAM usage output format ('-r').

    09:40:03 PM kbmemfree kbmemused  %memused kbbuffers  kbcached  kbcommit   %commit kbactive   kbinact   kbdirty
    """
    parsed = []

    typ = namedtuple('MemoryUsage', 'time kbmemfree kbmemused pmemused '
                     'kbbuffers kbcached kbcommit pcommit kbactive kbinact')
    
    for n, line in enumerate(gzip.open(filename)):
        if not line.strip():            # skip blank lines
            continue	
        if n < 3:                       # skip header
            continue
        if line.startswith('Average'):  # skip footer and blank lines
            continue
        if "kbmemfree" in line:         # skip reintroduced headers
            continue

        line = line.strip().split()
        assert len(line) >= 11, len(line)
        line2 = [line[0] + ' ' + line[1]]
        line2.extend(( float(x) for x in line[2:11]))

        t = typ(*line2)
        parsed.append(t)

    return parsed

def parse_sar_disk(filename, device):
    """
    Parse the 'sar' disk usage output ('-d').

    06:21:38 PM       DEV       tps  rd_sec/s  wr_sec/s  avgrq-sz  avgqu-sz     await     svctm     %util    
    """
    parsed = []

    typ = namedtuple('DeviceStats', 'time dev tps reads writes avgrqsz '
                     'avgqusz await svctm putil')
    
    for n, line in enumerate(gzip.open(filename)):
        if n < 3:                       # skip headers
            continue
        if line.startswith('Average'):  # skip footers
            continue
        if not line.strip():            # skip empty lines
            continue

        line = line.strip().split()

        if line[2] != device:    # pick out a particular device?
            continue
 
        assert len(line) == 11, len(line)
        line2 = [line[0] + ' ' + line[1], line[2]]
        line2.extend(( float(x) for x in line[3:]))

        t = typ(*line2)
        parsed.append(t)

    return parsed

def parse_sartime(t):
    """
    convert a 'sar' timestamp into a hour/minute/second:

    06:21:38 PM
    """
    t = t.split(' ')[0]
    hour, minute, second = t.split(':')
    return int(hour), int(minute), int(second)

def get_sar_start_time(sar_data, timelog_timestamp):
    """
    Since 'sar' timestamp output is braindead and has neither date nor
    timezone, register it to our timelog timestamp.  Assume same
    day/hour for start. BORK BORK BORK @CTB.
    """
    sar_time = sar_data[0][0]

    hour, minute, second = parse_sartime(sar_time)

    d = datetime.datetime(timelog_timestamp.year,
                          timelog_timestamp.month,
                          timelog_timestamp.day,
                          timelog_timestamp.hour,
                          int(minute),
                          int(second))

    return d

def make_timediff(sar_data):
    """
    Calculate 'sar' sampling frequency in seconds. Must be less than 1 hr.

    Assume the first two times are immediately adjacent (don't use disk
    output!)
    """
    t1 = parse_sartime(sar_data[0][0])
    t2 = parse_sartime(sar_data[1][0])

    assert t1[0] == t2[0]
    secdiff = (t2[1] - t1[1]) * 60 + t2[2] - t1[2]

    return secdiff

def fixtime(sar_data, start, secdiff):
    "Fix the hh::mm::ss timestamps output by 'sar' to full datetimes."
    delta = datetime.timedelta(0, secdiff)

    currentime = start 

    sar_data2 = []
    for x in sar_data:
        sar_data2.append(x._replace(time=currentime))
        currentime += delta

    return sar_data2

def make_time(x, start=None):
    "Convert datetimes into seconds with time.mktime, optionally - start."
    sub = 0
    if start:
        sub = time.mktime(start.timetuple())
    return time.mktime(x.timetuple()) - sub
