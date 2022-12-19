#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import redis, json
import numpy as np
import pandas as pd
from itertools import accumulate
from python_modules.MonitorScenario import MonitorScenario
from python_modules.IperfApp import IperfApp

class Results:
    def __init__( self , res_file ):
        self.results = dict()
        self.res_file = res_file
        self.df = pd.DataFrame()

    def collect_and_save_results( self, redis_cli, mon:MonitorScenario, iperf_app:IperfApp ):
        self.get_cpu_results(mon)
        self.get_traffic_traces( redis_cli, mon.start_sim)
        self.results["iperf"] = iperf_app.parse_redis_udp_results(mon.start_sim)
        self.results["iperf"] = iperf_app.parse_redis_tcp_results(mon.start_sim)
        
        print("*** Save results ...", end = '')
        with open( self.res_file, 'w') as outfile:
            json.dump( self.results, outfile , indent=2 )
        print(" done.")

    # Get CPU traces collected by CPUMonitorThread
    def get_cpu_results( self, mon:MonitorScenario ):
        self.results["cpu"] = mon.get_cpu_results()

    # Get traffic traces collected in redis
    def get_traffic_traces( self, redis_cli:redis.StrictRedis, t_start_sim):
        self.results["traffic"] = dict()
        for key in redis_cli.scan_iter("*"):
            if redis_cli.type(key) == 'TSDB-TYPE':
                ts = redis_cli.ts().range(key, 0, "+")
                time_stamp, val = map(list, zip(*ts))
                ksplit = key.split(":")
                self.results["traffic"][ksplit[0]] = dict()
                self.results["traffic"][ksplit[0]][ksplit[1]] = dict()
                self.results["traffic"][ksplit[0]][ksplit[1]]["time"] = [i/1e3-t_start_sim for i in time_stamp]
                self.results["traffic"][ksplit[0]][ksplit[1]]["val"]  = val

    ###########################################################
    def get_ue_list_iperf(self):
        ue_list = list(set([ sub["ue_id"] for sub in self.results["iperf"]]))
        return ue_list

    def get_iperf_rawdf(self, kpi="bwt" , ue_id:int=None ):
        """ Returns a df of iperf results; each column identifies an UE/SESSION """
        df = pd.DataFrame()
        for iperf in self.results["iperf"]:
            if iperf["ue_id"] != ue_id and ue_id != None:
                continue
            sid = iperf["id"]
            uid = iperf["ue_id"]
            time = iperf["time"]
            val  = iperf[kpi]
            df1 = Results.df_from_raw_samples(time=time, val=val,col_name=f'iperf:ue{uid}:s{sid}:{kpi}')
            df = df.join( df1, how="outer")
        return df

    def get_iperf_rawdf_collapsed(self, kpi:str, ue_id:int ):
        """ Return a df collapsing all the session for one UE in one column """
        time=[]
        val=[]
        for iperf in self.results["iperf"]:
            if iperf["ue_id"] is ue_id:
                time.extend( iperf["time"] )
                val.extend( iperf[kpi] )
        df = pd.DataFrame( { f'iperf:ue{ue_id}:{kpi}':val} , index=pd.to_timedelta(time , unit='S') )
        return df

