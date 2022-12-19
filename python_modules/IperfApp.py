#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import time , os , json
from datetime import datetime
from docker.models.containers import Container
import redis
from  python_modules.MonitorScenario import MonitorScenario
from  python_modules.UeRanSim import UeRanSim

class IperfApp:
    def __init__( self , mon:MonitorScenario ,  uersim:UeRanSim , apn_mec_name , apn_mec_ip , apn_cld_name, apn_cld_ip ):
        
        self.overall_time = 0
        self.sessions = []
        self.started_sessions = []
        self.uersim = uersim
        self.mon = mon

        self.redis_cli = mon.get_redis_cli()

        # IP and ports associated to the services are hardcoded (for the while)
        self.endpoints = dict()
        self.endpoints["srv_names"] = ["ue","srv_mec1","srv_mec2","srv_cld"]
        for n in self.endpoints["srv_names"]:
            self.endpoints[n]  = dict()

        self.endpoints["ue"]["c_name"] = "ue"
        self.endpoints["ue"]["cont"]   = mon.get_container( "ue" )

        self.endpoints["srv_mec1"]["c_name"]   = "srv_mec1"
        self.endpoints["srv_mec1"]["cont"]     = mon.get_container( "srv_mec1" )
        self.endpoints["srv_mec1"]["apn_name"] = apn_mec_name
        self.endpoints["srv_mec1"]["apn_ip"]   = apn_mec_ip
        self.endpoints["srv_mec1"]["port"]     = [51000] # A list to allow more separated streams, if needed

        self.endpoints["srv_mec2"]["c_name"]   = "srv_mec2"
        self.endpoints["srv_mec2"]["cont"]     = mon.get_container( "srv_mec2" )
        self.endpoints["srv_mec2"]["apn_name"] = apn_mec_name
        self.endpoints["srv_mec2"]["apn_ip"]   = apn_mec_ip
        self.endpoints["srv_mec2"]["port"]     = [52000] # A list to allow more separated streams, if needed

        self.endpoints["srv_cld"]["c_name"]   = "srv_cld"
        self.endpoints["srv_cld"]["cont"]     = mon.get_container( "srv_cld" )
        self.endpoints["srv_cld"]["apn_name"] = apn_cld_name
        self.endpoints["srv_cld"]["apn_ip"]   = apn_cld_ip
        self.endpoints["srv_cld"]["port"]     = [53000] # A list to allow more separated streams, if needed
        
        self.clean_all()
    ##############################################################################

    def wait_until_sessions_finish(self, retry=0.5):
        while self.check_running_iperfs():
            time.sleep(retry)
            

    def check_running_iperfs( self ):
        for key in self.endpoints["srv_names"]:
            top = self.mon.api_client.top( self.endpoints[key]["c_name"] )
            p_names = [p[-1] for p in top['Processes']]
            for p in p_names:
                if "iperf3 " in p:
                    return True
                if "iperf " in p:
                    return True
            return False

    def clean_all( self ):
        self.sessions = []
        self.started_sessions = []
        self.stop_iperf_servers()
        self.stop_iperf_clients()
        self.remove_iperf_logs()

    def reset_sessions(self):
        self.sessions = []
        self.started_sessions = []

    def stop_iperf_clients( self ):
        print( "*** Stop iperf clients" )
        for key in self.endpoints["srv_names"]:
            self.endpoints[key]["cont"].exec_run( cmd="python3 /mnt/volume_util/pskill.py 'iperf3 -c'" , detach=False )

    def stop_iperf_servers( self  ):
        print( "*** Stop iperf servers" )
        for key in self.endpoints["srv_names"]:
            self.endpoints[key]["cont"].exec_run( cmd="python3 /mnt/volume_util/pskill.py 'iperf3 -s'" , detach=False )

    def remove_iperf_logs( self  ):
        matching_files = [file for file in os.listdir("log") if file.startswith("iperf")]
        for f in matching_files: os.remove( "log/"+f )


    def start_session( self, ue_id:int, srv_name:str , sst:str , prot:str , ul_dl:str , bwt:float , t_dur:int ):
        apn_name = self.endpoints[srv_name]["apn_name"]
        srv_ip   = self.endpoints[srv_name]["apn_ip"]
        port     = self.endpoints[srv_name]["port"][0]
        cli_ip   = self.uersim.get_ue_address( ue_id , apn=apn_name , sst=sst )
        
        session = dict()
        session["id"] = len( self.sessions )
        session["ue_id"] = ue_id
        session["apn"] = apn_name  # "mec" | "cld"
        session["prot"]  = prot    # "tcp" | "udp"
        session["port"]  = port
        session["ul_dl"] = ul_dl    # "ul"  | "dl"
        session["mbps"]  = bwt
        session["sst"]   = sst
        self.sessions.append( session )

        if cli_ip == None:
            print( f'ERROR: [IperfApp] UE {ue_id} is not connected' )

        if prot == 'udp':
            msgstr = f'{ue_id} {session["id"]} {cli_ip} {srv_ip} {port} {prot} {ul_dl} {bwt} {t_dur}'
            print(f'Starting iperf:{msgstr}')
            self.redis_cli.publish(f'start_iperf_{apn_name}', msgstr )
            self.redis_cli.publish(f'start_iperf_ue', msgstr )

        if prot == 'tcp':
            srv_file = f'iperf_srv_s{session["id"]}_u{ue_id}_{ul_dl}.json'
            cli_file = f'iperf_cli_s{session["id"]}_u{ue_id}_{ul_dl}.json'
            
            srv_cmd = f'iperf3 -s -B {srv_ip} -1 --interval 1 -p {port} -J --logfile /mnt/log/{srv_file} &'
            cli_cmd = f'iperf3 -c {srv_ip} -B {cli_ip} -p {port} -t {t_dur} -b {bwt}M {ul_dl} -J --interval 1 --logfile /mnt/log/{cli_file} &'
            print(f'Starting iperf:{ue_id} {session["id"]} {cli_ip} {srv_ip} {port} {prot} {ul_dl} {bwt} {t_dur}')
            session["t_started"] = time.time()

            self.endpoints[srv_name]["cont"].exec_run( cmd=srv_cmd , detach=True )
            self.endpoints["ue"]["cont"].exec_run( cmd=cli_cmd , detach=True )


    def parse_redis_udp_results( self , t_start_sim):
        result_keys = ["time", "bwt", "pkt_lost", "pkt_sent", "lost_perc", "latency"]
        for s in self.sessions:
            if s["prot"] != "udp":
                continue
            for k in result_keys:
                s[k] = []
            for sample in self.redis_cli.lrange( f'iperf:udp:{s["id"]}:ue{s["ue_id"]}', 0, -1 ):
                sample_dict = json.loads(sample)
                for k in result_keys:
                    if k == "time":
                        s[k].append(sample_dict[k] - t_start_sim)
                    else:
                        s[k].append(sample_dict[k])
        return self.sessions


    def parse_redis_tcp_results( self , t_start_sim):
        result_keys = ["time", "bwt", "rtt", "retx"]

        for s in self.sessions:
            with open( f'log/iperf_cli_s{s["id"]}_u{s["ue_id"]}_{s["ul_dl"]}.json', 'r') as outfile:
                data_cli = json.load( outfile )
            with open( f'log/iperf_srv_s{s["id"]}_u{s["ue_id"]}_{s["ul_dl"]}.json', 'r') as outfile:
                data_srv = json.load( outfile )

            tcp_cli=[]
            tcp_srv=[]
            for intervals in data_cli.get( 'intervals' ):
                for ii in intervals.get('streams'):
                    tcp_cli.append({"time" : s["t_started"] + float(ii.get('end') ) ,
                                    "retx" : int(ii.get('retransmits')) , 
                                    "rtt"  : float(ii.get('rtt')) /1e3 
                                    })
            for intervals in data_srv.get( 'intervals' ):
                for ii in intervals.get('streams'):
                    tcp_srv.append({"time"  : s["t_started"] + float(ii.get('end') ) ,
                                    "bwt"   : round(float(ii.get('bits_per_second')) )/1e6
                                    })
            for k in result_keys:
                s[k] = []
            for c in tcp_cli:
                s["time"].append( c["time"]-t_start_sim )
                s["rtt"].append(  c["rtt"]  )
                s["retx"].append( c["retx"] )
                while abs(tcp_srv[0]["time"] - c["time"]) > 0.9:
                    tmp = tcp_srv.pop(0)
                if abs(tcp_srv[0]["time"] - c["time"]) < 0.9:
                    tmp = tcp_srv.pop(0)
                    s["bwt"].append(tmp["bwt"])
        return self.sessions
