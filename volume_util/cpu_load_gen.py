#!/usr/bin/env python3
'''
Emulate CPU load in an APPContainer.

Input:
    - load [0-1]: Percentage of the DocherHost resources that we want to use

Assumption:
- The CPU resources allocated to a DocherHost (number of CPUs and percentage) does not change over time.
  If the resource allocation changes, "set_cpu_target()" should be called in ControllerThread.
  It is not considered a change over time of the number of CPUs allocated to the DockerHost.

'''

import os, psutil, redis, time, docker, json
import random

from threading import Condition, Thread, Event, RLock
import multiprocessing
from multiprocessing import Process

###################################################################################

"""
Monitor the CPU usage
"""
class MonitorThread(Thread):

    def __init__(self, pids, interval, tracing=False):
        # print(pids)
        # print(os.getpid())

        # Store the PIDs of the processes to monitor
        self.procs_to_monitor = []
        for p in pids:
            self.procs_to_monitor.append( psutil.Process(p) )
        self.procs_to_monitor.append( psutil.Process(os.getpid()) )

        # Parameters
        self.sampling_interval = interval  # sample time interval
        self.cpu_filtered = 0.5            # cpu load filtered
        self.alpha        = 1              # First order filter coefficient for CPU samples
        
        self.do_tracing = tracing
        self.trace = { "t_mon":[] , "mon_cpu_filter":[] , "mon_cpu":[] }

        super(MonitorThread, self).__init__()
        self.shutdown_flag = Event()
        self.paused = True  # Start paused.
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
                    self.state.wait()
                    self.cpu_filtered = 0.5 

            t = time.time()
            cpu_sample = 0
            for p in self.procs_to_monitor:
                psample = p.cpu_percent()
                cpu_sample += psample

            if self.alpha == 1:
                self.cpu_filtered = cpu_sample
            else:
                self.cpu_filtered = self.alpha * cpu_sample + (1 - self.alpha) * self.cpu_filtered
            
            if self.do_tracing:
                self.trace["t_mon"].append(t)
                self.trace["mon_cpu"].append(cpu_sample)
                self.trace["mon_cpu_filter"].append(self.cpu_filtered)
            
            time.sleep(self.sampling_interval)

###################################################################################

"""
Thread to control the sleep time in load_gen_process()
"""
class ControllerThread(Thread):


    def __init__(self, monitor:MonitorThread, conn, interval, act_period, tracing=False):
        self.d_cli = docker.from_env()

        self.conn = conn
        self.monitor = monitor

        # Synchronization
        self.shutdown_flag = Event()
        self.cpu_lock = RLock()
        self.target_lock = RLock()

        # Parameters for PID control
        self.alpha_err   = 0.8     # First order filter coefficient (to filter out CPU measure approximation errors when the container CPU allocation is low)
        self.int_die_out = 0.98    # Limit for integral term (corrects overshooting)
        self.kp          = 0.0005  # proportional constant of th PID
        self.ki          = 0.0008  # integral constant of th PID
        self.kd          = 0.00025 # derivative constant of th PID

        self.sampling_interval = interval
        self.act_period        = act_period
        self.cpu_period_ub     = act_period
        self.working_point_init   = 0
        self.working_point_cor    = 0
        self.working_point_cor_ub = 0
        self.working_point_cor_lb = 0
        self.cpu_period           = 0

        self.tgt_cpu = 0   # Containers' target CPU requested
        self.CT      = 0.0 # Containers' target CPU rescaled taking into account the CPU limits (to meet the CPU monitored value)
        self.der_err = 0   # integral error
        self.int_err = 0   # integral error
        self.last_ts = time.time()  # last sampled time
        self.err_prev = 0
        self.do_tracing = tracing
        self.trace = { "t_ctr":[] , "P":[] , "I":[] , "D":[] , "cpu_tgt":[] , "cpu_ctrl":[] , "err":[] , "period":[] , "wp_cor":[]}

        super(ControllerThread, self).__init__()
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

    def get_cpu_target(self):
        with self.target_lock:
            return self.CT

    def set_cpu_target(self, tgt_cpu):
        with self.target_lock:
            cpu_scaling = self.cpu_scaling()
            ncpus = len( psutil.Process().cpu_affinity() )
            cpu_tgt_temp = tgt_cpu + 0.1
            if cpu_tgt_temp > 1.0:
                cpu_tgt_temp = 1.0
            self.cpu_period_ub = self.act_period * (tgt_cpu+(1-tgt_cpu)/2) * cpu_scaling / ncpus

            self.tgt_cpu = tgt_cpu
            self.CT = tgt_cpu * cpu_scaling
            self.set_working_point()

    def set_working_point(self):
        ncpus = len( psutil.Process().cpu_affinity() )
        self.working_point_init = self.act_period * self.CT / ncpus
        self.working_point_cor  = 0
        self.working_point_cor_ub = self.act_period - self.working_point_init
        self.working_point_cor_lb = -self.working_point_init
        self.cpu_period           = self.working_point_init

    def cpu_scaling(self):
        c_name = os.getenv('COMPONENT_NAME')
        h_conf = self.d_cli.containers.get(c_name).attrs["HostConfig"]
        if h_conf["CgroupParent"] == "":
            # This means the container is a DockerHost --> retrieve CpuQuota and CpuPerion
            CpuPeriod = h_conf["CpuPeriod"]
            CpuQuota  = h_conf["CpuQuota"]
        else:
            # This means the container is an APPContainer --> retrieve CpuQuota and CpuPeriod from its Host
            host_id = h_conf["CgroupParent"].replace( "/docker/" , "" )
            conf = self.d_cli.containers.get(host_id).attrs["HostConfig"]
            CpuPeriod = conf["CpuPeriod"]
            CpuQuota  = conf["CpuQuota"]

        return CpuQuota/CpuPeriod

    ########################
    def run(self):

        self.resume()
        self.shutdown_flag.clear()

        self.set_working_point()

        while not self.shutdown_flag.is_set():
            with self.state:
                if self.paused:
                    # Reset values going to sleep
                    self.int_err = 0
                    self.der_err = 0
                    self.err_prev = 0
                    self.last_ts = time.time()
                    self.set_working_point()
                    for c in self.conn:
                        c.send( ("no_load",None) )
                    self.state.wait()  # Block execution until notified.

            # Set the sleep_time in the load_gen_process()
            sleep_t = self.act_period - self.cpu_period
            for c in self.conn:
                c.send( ( "set_sleep_time", sleep_t ) )
            
            # Wait for MonitorThread to collect CPU stats and then read it (rescaling in the interval [0,1])
            time.sleep(self.sampling_interval)
            cpu = 0.01 * self.monitor.cpu_filtered

            # get all variables
            with self.target_lock, self.cpu_lock:
                CT = self.CT

            # Calculate current error
            if self.alpha_err == 1:
                err_cur = (CT - cpu)
            else:
                err_cur = self.alpha_err*self.err_prev + self.alpha_err*(CT - cpu)

            # Calculate integral error
            if self.int_die_out == 1:
                int_err = self.int_err + err_cur
            else:
                int_err = self.int_die_out * self.int_err + err_cur

            P = self.kp * err_cur
            I = self.ki * int_err
            if self.kd == 0:
                D = 0
            else:
                D = self.kd * (err_cur - self.err_prev)

            self.working_point_cor = P + I + D

            # Anti wind up control
            update_int_err = True
            if self.working_point_cor > self.working_point_cor_ub:
                self.working_point_cor = self.working_point_cor_ub
                update_int_err = False
            if self.working_point_cor < self.working_point_cor_lb:
                self.working_point_cor = self.working_point_cor_lb
                update_int_err = False

            self.cpu_period = self.working_point_init + self.working_point_cor
            if self.cpu_period < 0:
                self.cpu_period = 0
            if self.cpu_period > self.cpu_period_ub:
                self.cpu_period = self.cpu_period_ub

            # Update integral error only if anti wind up control doesn't enters into play
            if update_int_err:
                self.int_err  = int_err
            self.err_prev = err_cur

            # self.trace = { "t_ctr":[] , "P":[] , "I":[] , "D":[] , "cpu_tgt":[] , "cpu_ctrl":[] , "err":[] , "period":[] , "wp_cor":[]}
            if self.do_tracing:
                ts = time.time()
                self.trace["t_ctr"].append(ts)
                self.trace["P"].append(P)
                self.trace["I"].append(I)
                self.trace["D"].append(D)
                self.trace["cpu_ctrl"].append(cpu)
                self.trace["cpu_tgt"].append(CT)
                self.trace["err"].append(err_cur)
                self.trace["period"].append(self.cpu_period)
                self.trace["wp_cor"].append(self.working_point_cor)

###################################################################################
"""
Function executed by the processes launched to generate the CPU load
"""
def load_gen_process(target_core, conn, act_period_in):
    process = psutil.Process(os.getpid())
    process.cpu_affinity([target_core])

    act_period = act_period_in
    sleep_time = act_period_in
    while True:
        if conn.poll():
            a,b = conn.recv()
            if a == "set_sleep_time":
                sleep_time = b
            if a == "no_load":
                sleep_time = act_period
        
        interval = time.time() + act_period - sleep_time
        while time.time() < interval:
            r = random.random()
            pr = 213123
            _ = pr * r
            pr = pr + 1

        time.sleep( sleep_time )


###################################################################################
"""
- Start the processes to generate the CPU load and the control threads.
- Oversees the load generation using redis messages.
"""
def main(  ):
    c_name = os.getenv('COMPONENT_NAME')

    d_cli = docker.from_env()
    redis_ip = d_cli.containers.get("my-redis").attrs['NetworkSettings']['IPAddress']

    r = redis.StrictRedis(host=redis_ip, port=6379, password="", decode_responses=True)
    rp = r.pubsub()
    rp.subscribe(f'{c_name}_cpu_stress',f'{c_name}_cpu_load','start_cpu_follow_throughput','stop_cpu_follow_throughput')

    actuation_period = 0.05
    sampling_interval_mon  = 0.2    # Less is not good if I want low loads with very limited hosts (e.g. mec_host with 20% of 1 CPU)
    sampling_interval_ctrl = 0.2

    cpus = psutil.Process().cpu_affinity()
    proc_pid_list = []
    conn_parent_list = []
    conn_child_list  = []
    for cpu in cpus:
        print(cpu)
        conn_parent,conn_child = multiprocessing.Pipe()
        conn_parent_list.append( conn_parent )
        conn_child_list.append( conn_child   )
        p = Process( target=load_gen_process, args=( cpu, conn_child, actuation_period ) )
        p.start()
        proc_pid_list.append( p.pid )

    monitor = MonitorThread( proc_pid_list, interval=sampling_interval_mon )
    monitor.start()
    monitor.pause()

    control = ControllerThread( monitor, conn_parent_list, sampling_interval_ctrl, actuation_period )
    control.set_cpu_target( 0 )
    control.start()
    control.pause()

    while True:
        message = rp.get_message()

        for message in rp.listen():
            if message["type"] == "subscribe":
                continue

            if message["channel"] == f'{c_name}_cpu_load':
                if message["data"] == "enable_tracing":
                    control.do_tracing = True
                    monitor.do_tracing = True
                    continue
                if message["data"] == "reset_control_traces":
                    for k in control.trace:
                        control.trace[k] = []
                    for k in monitor.trace:
                        monitor.trace[k] = []
                    continue
                if message["data"] == "save_control_traces":
                    traces = {**control.trace,**monitor.trace}
                    with open( "/mnt/volume_util/load_gen_trace.json", 'w') as outfile:
                        json.dump( traces, outfile , indent=2 )
                    continue

                load = float(message["data"])
                if load > 0:
                    control.set_cpu_target(load)
                    monitor.resume()
                    control.resume()
                else:
                    control.set_cpu_target(0)
                    monitor.pause()
                    control.pause()

if __name__ == '__main__':
    main(  )
