#! /usr/bin/env python3

import subprocess, time, redis, re, json
from collections import namedtuple
from threading import Condition, Thread, Event, RLock

r = redis.StrictRedis(host="172.17.0.6", port=6379, password="", decode_responses=True)
rp = r.pubsub()
msg_tuple = namedtuple('msg_tuple', ['ue_id','ses_id','cli_ip','srv_ip', 'port', 'prot', 'ul_dl', 'bwt', 't_dur'])
tcp_report_tuple_client = namedtuple('upd_report_tuple', ['time','retx','rtt'])

def start_udp_iperf( m:msg_tuple ):
    p = subprocess.Popen(['iperf', '-c', m.srv_ip, '-B', m.cli_ip, '-p', m.port, '-u', '-i', '1', '-e', '-b', f'{m.bwt}M', '-t', m.t_dur], 
                            stdout=subprocess.PIPE,
                            universal_newlines=True )
    with p.stdout as pipe:
        for line in pipe:
            pass
            
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


#####################################################################

if __name__ == "__main__":
    
    rp.subscribe('start_iperf_ue')

    for message in rp.listen():
        if message["type"] == "subscribe":
            continue
        if message["channel"] == "start_iperf_ue":
            msg_par = msg_tuple._make(message['data'].split())
            iperf_session = IperfThread(msg_par)
            iperf_session.start()

