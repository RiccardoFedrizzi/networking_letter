#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import docker, psutil, time
import dateutil.parser
import numpy as np
from threading import Condition, Thread, Event


class CPUMonitorThread(Thread):
    """
       Monitors the CPU status of the containers
    """

    def __init__(self, c_names, containers):
        
        self.shutdown_flag = Event()
        self.c_names = c_names
        self.containers = containers
        self.start_sim = 0

        self.api_client = docker.APIClient(base_url='unix:///var/run/docker.sock')
        self.stats_obj = dict()
        for cn in self.c_names:
            self.stats_obj[cn] = self.api_client.stats(cn , decode=True, stream=True)

        self.results = dict()
        self.results["sys"] = dict()
        self.results["sys"]["time"] = []
        self.results["sys"]["cpu_perc"] = []

        for c in self.c_names:
            self.results[c] = dict()
            self.results[c]["time"] = []
            self.results[c]["time_delta"] = []
            self.results[c]["cpu_sys_perc"]  = []
            self.results[c]["cpu_period"] = []
            self.results[c]["cpu_quota"]  = []
            self.results[c]["cpu_delta"]  = []
            self.results[c]["cpu_throttle_delta"] = []
            self.results[c]["mem_rss"] = []

        super(CPUMonitorThread, self).__init__()
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

    def get_results(self):
        res=dict()
        res = self.results
        for c_name in self.c_names:
            res[c_name]["cpu_perc"] = self.get_container_cpu_usage( c_name )
        return res


    def get_container_cpu_usage( self, c_name:str ):
        cpu_quota  = np.array( self.results[c_name]["cpu_quota"])
        cpu_period = np.array( self.results[c_name]["cpu_period"])
        time_delta = np.array( self.results[c_name]["time_delta"])
        cpu_delta  = np.array( self.results[c_name]["cpu_delta"])
        cpu_period[cpu_period <= 0] = 100000
        cpu_quota[ cpu_quota  <= 0] = 100000
        cpu_delta_max = (cpu_quota/cpu_period) * time_delta
        cont_cpu_perc = 100 * cpu_delta / cpu_delta_max        
        return list(cont_cpu_perc)


    def get_last_cpu_usage( self , c_name ):
        if len(self.results[c_name]["time_delta"]) == 0:
            return 0
        time_delta = self.results[c_name]["time_delta"][-1]
        cpu_delta  = self.results[c_name]["cpu_delta"][-1]
        cpu_period = self.results[c_name]["cpu_period"][-1]
        cpu_quota  = self.results[c_name]["cpu_quota"][-1]
        
        if cpu_period <= 0: cpu_period = 100000
        if cpu_quota  <= 0: cpu_quota  = 100000
        cpu_delta_max = (cpu_quota/cpu_period) * time_delta
        cont_cpu_perc = 100 * cpu_delta / cpu_delta_max
        return cont_cpu_perc


    def run(self):
        self.shutdown_flag.clear()
        self.resume()

        for c_name in self.c_names:
            next(self.stats_obj[c_name])

        while not self.shutdown_flag.is_set():
            with self.state:
                if self.paused:
                    self.state.wait()  # Block execution until notified.
            
            sample_time = time.time() - self.start_sim
            self.results["sys"]["time"].append( sample_time  )
            self.results["sys"]["cpu_perc"].append( psutil.cpu_percent() )

            for c_name in self.c_names:
                stat = next(self.stats_obj[c_name])

                sample_time = time.time() - self.start_sim
                t_read    = dateutil.parser.isoparse( stat["read"] )
                t_preread = dateutil.parser.isoparse( stat["preread"] )
                diff = t_read - t_preread
                timeDelta = diff.seconds*1e6 + diff.microseconds

                cpupercentage = 0.0

                prestats = stat['precpu_stats']
                cpustats = stat['cpu_stats']

                prestats_totalusage = prestats['cpu_usage']['total_usage']
                stats_totalusage = cpustats['cpu_usage']['total_usage']

                if 'system_cpu_usage' in prestats:
                    prestats_syscpu = prestats['system_cpu_usage']
                else:
                    continue
                stats_syscpu = cpustats['system_cpu_usage']

                cpuDelta = stats_totalusage - prestats_totalusage
                systemDelta = stats_syscpu - prestats_syscpu

                if cpuDelta > 0 and systemDelta > 0:
                    cpupercentage = (cpuDelta / systemDelta) * 100

                CpuPeriod = self.containers[c_name].attrs["HostConfig"]["CpuPeriod"]
                CpuQuota  = self.containers[c_name].attrs["HostConfig"]["CpuQuota"]

                cpuDelta_micro_sec = cpuDelta / 1e3
                cpu_throttle_delta = (cpustats["throttling_data"]["throttled_time"] - prestats["throttling_data"]["throttled_time"]) / 1e3

                self.results[c_name]["time"].append( sample_time )
                self.results[c_name]["cpu_sys_perc"].append( cpupercentage )
                self.results[c_name]["time_delta"].append( timeDelta )
                self.results[c_name]["cpu_delta"].append( cpuDelta_micro_sec )
                self.results[c_name]["cpu_period"].append( CpuPeriod )
                self.results[c_name]["cpu_quota"].append( CpuQuota )
                self.results[c_name]["cpu_throttle_delta"].append( cpu_throttle_delta )