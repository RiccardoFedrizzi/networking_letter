#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import docker, yaml
import time
from datetime import datetime
from docker.models.containers import Container

class UeRanSim:
    def __init__(self, imsi_list:list , ue_container_name:str ):
        self.imsi_list = imsi_list
        self.num_ues = len(imsi_list)
        self.d_client = docker.from_env()
        self.ue_cont = self.d_client.containers.list(filters={'name':ue_container_name})[0]
        self.ue_status = dict()
        self.ue_status["ue_pid"] = [None]  * self.num_ues
        self.ue_status["ue_reg"] = [False] * self.num_ues

    def stop_all_ues( self ):
        """  Stop all UEs (i.e.: remove nr-ue process) """
        print("[{}] - Stop All UEs:".format(str(datetime.now().time())) )
        self.ue_cont.exec_run( cmd='python3 /mnt/volume_util/pskill.py nr-ue' , detach=False )
        self.ue_status["ue_pid"] = [None]  * self.num_ues
        self.ue_status["ue_reg"] = [False] * self.num_ues

    def stop_ue( self, ue_id:int ):
        """  Stop an UE (i.e.: remove nr-ue process) """

        print("[{}] - Stop UE {:n}:".format(str(datetime.now().time()), ue_id) )

        self.ue_cont.exec_run( cmd=f'python3 /mnt/volume_util/pskill.py open5gs-ue{ue_id}' , detach=False )
        self.ue_status["ue_pid"][ue_id] = None
        self.ue_status["ue_reg"][ue_id] = False


    def start_ue( self, ue_id:int , apn:str="", sst:str="", sd:str=""):
        """  Start an UE (i.e.: start the nr-ue process) """

        imsi = "imsi-{}".format( self.imsi_list[ue_id] )

        print("[{}] - Start UE {:n} | imsi:{} | apn:{}".format(str(datetime.now().time()), ue_id , imsi , apn) )

        if apn == "":
            ue_conf_file_input = "open5gs-ue.yaml"
        elif apn == "all":
            ue_conf_file_input = "open5gs-ue-init-both-pdu.yaml"
        else:
            ue_conf_file_input = "open5gs-ue-init-pdu.yaml"

        ue_conf_file_name = "open5gs-ue{:n}.yaml".format(ue_id)

        cmdstr =  "bash -c \"cp /mnt/ueransim/{} /UERANSIM/config/{}\"".format(ue_conf_file_input,ue_conf_file_name)
        self.ue_cont.exec_run( cmd=cmdstr , detach=False )

        cmdstr =  "bash -c \"sed -i 's|UE_IMSI|'{}'|g' /UERANSIM/config/{}\"".format( imsi , ue_conf_file_name )
        self.ue_cont.exec_run( cmd=cmdstr , detach=False )

        cmdstr =  "bash -c \"sed -i 's|UE_APN|'{}'|g'   /UERANSIM/config/{}\"".format( apn , ue_conf_file_name ) 
        self.ue_cont.exec_run( cmd=cmdstr , detach=False )

        cmdstr =  "bash -c \"sed -i 's|UE_SST|'{}'|g'   /UERANSIM/config/{}\"".format( sst , ue_conf_file_name ) 
        self.ue_cont.exec_run( cmd=cmdstr , detach=False )

        cmdstr =  "bash -c \"sed -i 's|UE_SD|'{}'|g'   /UERANSIM/config/{}\"".format( sd , ue_conf_file_name ) 
        self.ue_cont.exec_run( cmd=cmdstr , detach=False )

        cmdstr =  "bash -c \"/UERANSIM/build/nr-ue -c /UERANSIM/config/{} > /mnt/log/ue{:n}.log 2>&1\"".format(ue_conf_file_name,ue_id)
        self.ue_cont.exec_run( cmd=cmdstr , detach=True )

        # Update PID for new UE
        while True:
            _,out = self.ue_cont.exec_run( cmd="bash -c \"ps -ef | grep nr-ue | grep -v bash | grep open5gs-ue{:n}.yaml\"".format(ue_id) , detach=False )
            out = out.decode()
            if out.count('\n') > 0:
                self.ue_status["ue_pid"][ue_id] = out.split()[1]
                break


    def check_ues_started( self , ue_ids:list ):
        for i in ue_ids:
            _,out = self.ue_cont.exec_run( cmd="bash -c \"ps -ef | grep nr-ue | grep -v bash | grep open5gs-ue{:n}.yaml\"".format(i) , detach=False )
            out = out.decode()
            if out.count('\n') > 0:
                self.ue_stats["ue_pid"][i] = out.split()[1]
            else:
                self.ue_stats["ue_pid"][i] = None
                self.ue_stats["ue_reg"][i] = False


    def check_ues_registration( self ,  ue_ids:list ):
        """ Check the registration of UEs.
            - Updates ue_stats["ue_reg"]
            - Returns the list of UEs that are not RM-REGISTERED."""

        print("[{}] - Check registration for UE ids {}".format(datetime.now().time() , str(ue_ids)) ) 
    
        ue_to_check = []+ue_ids
        ue_not_registered = []

        startime = time.time()

        while len(ue_to_check) > 0:
            for i in ue_to_check:
                if self.ue_status["ue_pid"][i] == None:
                    ue_not_registered.append(i)
                    ue_to_check.remove(i)
                    self.ue_status["ue_reg"][i] = False
                    continue
                cmdstr = "./nr-cli imsi-" + self.imsi_list[i] + " -e status"
                _,out = self.ue_cont.exec_run( cmd=cmdstr , detach=False)
                out = out.decode()
                if out.split()[0] == "ERROR:":
                    self.ue_status["ue_reg"][i] = False
                    ue_not_registered.append(i)
                    ue_to_check.remove(i)
                    continue
                dct = yaml.safe_load(out)
                reg = dct["rm-state"]
                if reg != "RM-REGISTERED":
                    continue
                else:
                    ue_to_check.remove(i)
                    self.ue_status["ue_reg"][i] = True
                    break
            
            if time.time() - startime > 10:
                ue_not_registered = sorted( ue_not_registered + ue_to_check)
                print( "    - After 10 seconds those UEs are not connected {}".format(str(ue_not_registered)) )
                break
        
        return ue_not_registered


    def wait_ue_connection_up( self, ue_id:int , apn:str):
        done = False
        while done == False:
            done = self.check_ue_connection( ue_id , apn )


    def check_ue_connection( self, ue_id , apn:str  ):
        dct = self.get_ps_list( ue_id )
        if dct == None:
            return False

        for k,vals in dct.items():
            if vals["apn"] == apn and vals['state']=='PS-ACTIVE':
                return True

        return False


    def get_ps_list( self, ue_id ):
        imsi = "imsi-{}".format( self.imsi_list[ue_id] )
        cmdstr = "./nr-cli " + imsi + " -e ps-list"
        _,out =  self.ue_cont.exec_run( cmd=cmdstr , detach=False)
        dct = yaml.safe_load( out.decode() )
        return dct


    def get_ue_address( self , ue_id , apn:str , sst:str ):
        dct = self.get_ps_list( ue_id )
        if dct == None:
            return None
        for _,vals in dct.items():
            if vals["apn"] == apn and vals['s-nssai']["sst"] == int(sst) and vals["state"]=='PS-ACTIVE':
                return vals["address"]
        return None
