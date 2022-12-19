#! /usr/bin/env python3

# import redis
# from redis.client import PubSub
import time, json, sys, subprocess, re, redis
from collections import namedtuple
from threading import Condition, Thread, Event, RLock

r = redis.StrictRedis(host="172.17.0.6", port=6379, password="", decode_responses=True)
rp = r.pubsub()
rp.subscribe('start_iperf')
msg_tuple = namedtuple('msg_tuple', ['ue_id','ses_id','cli_ip','srv_ip', 'port', 'prot', 'ul_dl', 'bwt', 't_dur'])
upd_report_tuple = namedtuple('upd_report_tuple', ['time','bwt','pkt_lost','pkt_sent', 'lost_perc', 'latency'])
tcp_report_tuple_server = namedtuple('upd_report_tuple', ['time','bwt'])


def start_udp_iperf(m:msg_tuple):
    global r, rp, msg_tuple, upd_report_tuple
    
    p = subprocess.Popen( ['iperf','-s', '-B', m.srv_ip, '-p', m.port, '-e', '-i', '1', '-u', '-x', 'CMSV', '-t', str(float(m.t_dur)+1) ], 
                            stdout=subprocess.PIPE,
                            universal_newlines=True )

    first_sample_rx = False
    with p.stdout as pipe:
        for line in pipe:
            l = line.strip()
            if l.startswith( "[ ID]" ): 
                break
        for line in pipe:
            pattern = r'\d+\.?\d*'
            lsplit = re.findall( pattern, line.strip() )
            if len( lsplit ) < 15:
                continue
            if first_sample_rx and float(lsplit[1])==0.0:
                continue
            rep = upd_report_tuple(time.time(),float(lsplit[4]), int(lsplit[6]), int(lsplit[7]), float(lsplit[8]), float(lsplit[9]))
            rep_dict = dict(rep._asdict())
            r.rpush(f'iperf:udp:{m.ses_id}:ue{m.ue_id}', json.dumps(rep_dict))
            first_sample_rx = True
        p.terminate()
        time.sleep(0.5)
        p.poll()

class IperfThread(Thread):
    def __init__(self, m:msg_tuple ):
        self.m = m
        self.shutdown_flag = Event()

        super(IperfThread, self).__init__()
        self.paused = True  # Start out paused.
        self.state = Condition()

    def pause(self):
        with self.state:
            self.paused = True  # Block self.

    def resume(self):
        with self.state:
            self.paused = False
            self.state.notify()  # Unblock self if waiting.

    def stop(self):
        self.shutdown_flag.set()

    def run(self):
        self.shutdown_flag.clear()
        self.resume()
        while not self.shutdown_flag.is_set():
            with self.state:
                if self.paused:
                    self.state.wait()  # Block execution until notified.
            if self.m.prot == "udp":
                start_udp_iperf( self.m )
            self.stop()


if __name__ == "__main__":

    apn = sys.argv[1]
    rp.subscribe(f'start_iperf_{apn}')

    for message in rp.listen():
        if message["type"] == "subscribe":
            continue
        if message["channel"] == f"start_iperf_{apn}":
            msg_par = msg_tuple._make(message['data'].split())
            iperf_session = IperfThread(msg_par)
            iperf_session.start()



