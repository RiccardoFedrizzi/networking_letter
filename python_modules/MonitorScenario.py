#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import docker, redis, time
from docker.models.containers import Container
from python_modules.CPUMonitorThread import CPUMonitorThread

class MonitorScenario:
    def __init__( self  ):
        self.d_client = docker.from_env()
        self.api_client = docker.APIClient(base_url='unix:///var/run/docker.sock')

        # Restart redis container to collect measures sent from inside other containers
        if self.d_client.containers.list(filters={'name':"my-redis"}) != []:
            self.d_client.containers.get("my-redis").stop()
            self.d_client.containers.prune()
        self.d_client.containers.run( "redislabs/redistimeseries" ,  name="my-redis", ports={"6379/tcp": 6379} , detach=True)
        self.redis_cli = redis.StrictRedis(host="172.17.0.6", port=6379, password="", decode_responses=True)

        self.start_sim = 0

        self.host_struct = {
            "mec_host": {"upf": "upf_mec" , "app": ["srv_mec1", "srv_mec2"]},
            "cld_host": {"upf": "upf_cld" , "app": ["srv_cld"]},
        }

        # Containers to monitor (hardcoded for the while)
        self.c_names = ["mec_host","cld_host","upf_mec","upf_cld","srv_mec1","srv_mec2","srv_cld","ue"]
        self.containers = dict()
        for c in self.c_names:
            self.containers[c] = self.d_client.containers.get(c)

        # Hosts to monitor for aggregated throughput
        self.hosts_to_monitor = ["mec_host","cld_host"]

        # Start processes to monitor host aggregated traffic
        for c in self.hosts_to_monitor:
            self.containers[c].exec_run( cmd=f'python3 /mnt/volume_util/pskill.py mon_redis.py' , detach=False )
            self.containers[c].exec_run( cmd=f'python3 /mnt/volume_util/mon_redis.py {c}' , detach=True )

        # Init ALL containers to ensure no CPU quota is imposed at the beginning
        for c in self.c_names:
            self._update_container( c , cpu_period_in=100000 , cpu_quota_in=-1 )

        self.cpu_monitor = CPUMonitorThread(self.c_names, self.containers)


    ##############################################################################


    def set_start_time( self  ):
        t_start = time.time()
        self.start_sim = t_start
        self.cpu_monitor.start_sim = t_start

    def start_cpu_monitor( self ):
        self.cpu_monitor.start()

    def stop_cpu_monitor( self ):
        self.cpu_monitor.stop()
        self.cpu_monitor.join()

    def start_all_monitors( self ):
        self.cpu_monitor.start()
        self.redis_cli.publish('throughput_monitoring', "start" )

    def stop_all_monitors(self):
        self.stop_cpu_monitor()
        self.redis_cli.publish('throughput_monitoring', "stop" )

    def get_redis_cli(self):
        return self.redis_cli
        
    def clean_redis(self):
        for key in self.redis_cli.scan_iter("*"):
            self.redis_cli.delete(key)

    def get_container( self, c_name:str  ):
        cList = self.d_client.containers.list(filters={'name':c_name})
        if len( cList ) > 1:
            raise Exception("Error: container name \"{}\" does not return an unique container instance.".format(c_name) )
        if len( cList ) == 0:
            raise Exception("Error: no container found filtering by name \"{}\".".format(c_name) )
        return cList[0]


    def update_host_resources( self, h_name:str, sys_cpu_perc:float ):
        if h_name not in self.host_struct:
            print(f'Error: Update called for host "{h_name}" but it is not in the list of availavle hosts: {self.host_struct.keys() }.')
            return
        cpu_period_new = 100000
        cpu_quota_new  = int( cpu_period_new*sys_cpu_perc )
        
        self._update_container( h_name, cpu_period_in=cpu_period_new , cpu_quota_in=cpu_quota_new )

        # childs = list( self.host_struct[h_name].values() )
        # for cn in childs:
        #     if type(cn) is list:
        #         for tmp in cn:
        #            self._update_container( tmp, cpu_period_in=cpu_period_new , cpu_quota_in=cpu_quota_new )
        #     else:
        #         self._update_container( cn, cpu_period_in=cpu_period_new , cpu_quota_in=cpu_quota_new )


    def _update_container( self, c_name:str , cpu_period_in:int , cpu_quota_in:int  ):
        self.containers[c_name].update( cpu_period=cpu_period_in , cpu_quota=cpu_quota_in )
        self.containers[c_name] = self.get_container( c_name )
        return self.containers[c_name]


    def is_process_running ( self, c_name:str, process_tag:str):
        top = self.api_client.top( c_name )
        p_names = [p[-1] for p in top['Processes']]
        for p in p_names:
            if process_tag in p:
                return True
        return False

    def start_cpu_load_gen_process( self, c_name:str ):
        script = "cpu_load_gen.py"
        self.containers[c_name].exec_run( cmd=f'python3 /mnt/volume_util/pskill.py {script}' , detach=False )
        self.containers[c_name].exec_run( cmd=f'python3 /mnt/volume_util/{script}' , detach=True )
    
    def set_cpu_load( self, c_name:str, load:float ):
        self.redis_cli.publish(f'{c_name}_cpu_load', str(load) )

    def start_cpu_follow_thr( self ):
        self.redis_cli.publish('start_cpu_follow_throughput' , str(0.0) )

    def stop_cpu_follow_thr( self ):
        self.redis_cli.publish('stop_cpu_follow_throughput' , str(0.0) )

    def get_container_cpu_usage( self, c_name:str ):    
        return self.cpu_monitor.get_container_cpu_usage(c_name)

    def get_last_cpu_usage( self, c_name:str ):    
        return self.cpu_monitor.get_last_cpu_usage(c_name)

    def get_cpu_results( self ):
        return self.cpu_monitor.get_results()
