#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, yaml
from datetime import datetime

import comnetsemu
from comnetsemu.cli import CLI, spawnXtermDocker
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

def main(argv):

    AUTOTEST_MODE = os.environ.get("COMNETSEMU_AUTOTEST_MODE", 0)
    
    link_bwt = int( argv[1] )
    print( "=== NET PARAMS ===============")
    print( "Link bandwidth : {} Mbps".format(link_bwt) )
    print( "==============================")

    net_param = dict()
    net_param["prj_folder"]      = os.path.dirname(os.path.realpath(__file__))
    net_param["mongodb_folder"]  = "/home/vagrant/mongodbdata" # NOTE: this shall not be inside VM shared folder
    net_param["ueransim_image"]  = "myueransim_v3-2-6"
    net_param["open5gs_image"]   = "my5gc_v2-4-4"
    net_param["link_bwt"]        = link_bwt
    net_param["cp_cont_ip"]      = "192.168.0.200/24"
    net_param["upf_cld_cont_ip"] = "192.168.0.202/24"
    net_param["upf_mec_cont_ip"] = "192.168.0.201/24"
    net_param["gnb_cont_ip"]     = "192.168.0.199/24"
    net_param["ue_cont_ip"]      = ["192.168.0.1"]

    setLogLevel("info")

    net = Containernet(controller=Controller, link=TCLink)
    mgr = VNFManager(net)

    cp  = add_cp_dockerhost ( "cp"  , net_param ,  net )
    cld_host = add_mec( "cld_host" , net_param["upf_cld_cont_ip"] , net_param ,  net , cpus="0,1" )
    mec_host = add_mec( "mec_host" , net_param["upf_mec_cont_ip"] , net_param ,  net , cpus="0" )
    ue  = add_gnb_dockerhost( "ue"  , net_param ,  net )

    info("*** Add upf_mec\n")
    upf_mec = add_UPFToMec( "upf_mec", "mec_host", mgr, net_param )
    upf_cld = add_UPFToMec( "upf_cld", "cld_host", mgr, net_param )

    srv_image = "srv_image" # "dev_test"

    info("*** Add srv_cld\n")
    srv_cld  = add_AppToMec(app_name="srv_cld", mec_name="cld_host", image_name=srv_image, mgr=mgr, net_param=net_param)

    info("*** Add srv_mec1\n")
    srv_mec1 = add_AppToMec(app_name="srv_mec1", mec_name="mec_host", image_name=srv_image, mgr=mgr, net_param=net_param)

    info("*** Add srv_mec2\n")
    srv_mec2 = add_AppToMec(app_name="srv_mec2", mec_name="mec_host", image_name=srv_image, mgr=mgr, net_param=net_param)

    time.sleep(0.1)

    info("*** Add controller\n")
    net.addController("c0")

    info("*** Adding switch\n")
    s1 = net.addSwitch("s1")
    s2 = net.addSwitch("s2")

    info("*** Adding links\n")
    net.addLinkNamedIfce( s1       , s2, bw=net_param["link_bwt"] , delay="50ms" )
    net.addLinkNamedIfce( cp       , s2, bw=net_param["link_bwt"] , delay="1ms"  )
    net.addLinkNamedIfce( cld_host , s2, bw=net_param["link_bwt"] , delay="1ms"  )
    net.addLinkNamedIfce( mec_host , s1, bw=net_param["link_bwt"] , delay="1ms"  )
    net.addLinkNamedIfce( ue       , s1, bw=net_param["link_bwt"] , delay="10ms" )

    info("\n*** Starting network\n")
    net.start()

    time.sleep(5)

    info("*** Start control plane processes\n")
    cp.dins.exec_run( cmd="bash /open5gs/install/etc/open5gs/5gc_cp_init.sh" , detach=True )

    time.sleep(5)
    info("*** Start mec process\n")
    mec_host.dins.exec_run( cmd="bash /open5gs/install/etc/open5gs/volume_5gc/5gc_init_interfaces.sh" , detach=True )
    upf_mec.dins.exec_run( cmd="bash /open5gs/install/etc/open5gs/volume_5gc/5gc_start_upf.sh" , detach=True )

    info("*** Start cld process\n")
    cld_host.dins.exec_run( cmd="bash /open5gs/install/etc/open5gs/volume_5gc/5gc_init_interfaces.sh" , detach=True )
    upf_cld.dins.exec_run( cmd="bash /open5gs/install/etc/open5gs/volume_5gc/5gc_start_upf.sh" , detach=True )

    time.sleep(5)
    info("*** Start gnb processes\n")
    ue.dins.exec_run( cmd="bash /mnt/ueransim/open5gs_gnb_init.sh" , detach=True )
    
    time.sleep(0.1)
    iterations = 0
    while True:
        cmdstr = "./nr-cli UERANSIM-gnb-1-1-1 -e status"
        _,out = ue.dins.exec_run( cmd=cmdstr , detach=False)
        out = out.decode()
        dct = yaml.safe_load(out)
        reg = dct["is-ngap-up"]
        iterations = iterations + 1
        if reg != True:
            if iterations > 100:
                print( "    gNB ngap is down after 100 checks" )
                break
            time.sleep(0.1)
            continue
        else:
            print( "[{}] - gNB ngap is up".format(str(datetime.now().time()) ))
            break

    if not AUTOTEST_MODE:
        CLI(net)

    net.stop()
    mgr.stop()



##########################################################################################
##########################################################################################
def add_cp_dockerhost( name:str , net_params:dict , net:Containernet ):
    
    info("*** Adding Host for open5gs {}\n".format(name))
    env={"DB_URI":"mongodb://localhost/open5gs"}
    cp = net.addDockerHost(
        name,
        dimage = net_params["open5gs_image"],
        ip     = net_params["cp_cont_ip"],
        dcmd   = "",
        docker_args={
            "environment": env,
            "ports" : { "3000/tcp": 3000 },
            "volumes": {
                net_params["prj_folder"] + "/log": {
                    "bind": "/open5gs/install/var/log/open5gs",
                    "mode": "rw",
                },
                net_params["mongodb_folder"]: {
                    "bind": "/var/lib/mongodb",
                    "mode": "rw",
                },
                net_params["prj_folder"] + "/volume_5gc": {
                    "bind": "/open5gs/install/etc/open5gs",
                    "mode": "rw",
                },
                net_params["prj_folder"] + "/volume_util": {
                    "bind": "/mnt/volume_util",
                    "mode": "rw",
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
            },
        },
    )
    return cp

##########################################################################################
##########################################################################################
def add_mec( name:str , ip:str , net_params:dict , net:Containernet , cpus:str, cpu_quota_perc:float=100 ):
    
    info("*** Adding Host for open5gs {}\n".format(name) )
    env={"COMPONENT_NAME":name}
    upf = net.addDockerHost(
        name,
        dimage = net_params["open5gs_image"],
        ip     = ip,
        dcmd   = "",
        docker_args={
            "cpuset_cpus": cpus,
            "cpu_period" : 100000, # Default
            "cpu_quota"  : int(cpu_quota_perc*100000/100),
            "environment": env,
            "volumes": {
                net_params["prj_folder"] + "/volume_5gc": {
                    "bind": "/open5gs/install/etc/open5gs/volume_5gc",
                    "mode": "rw",
                },
                net_params["prj_folder"] + "/volume_util": {
                    "bind": "/mnt/volume_util",
                    "mode": "rw",
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
                "/var/run/docker.sock": {"bind":"/var/run/docker.sock", "mode": "ro"},
            },
            "cap_add": ["NET_ADMIN"],
            "sysctls": {"net.ipv4.ip_forward": 1},
            "devices": "/dev/net/tun:/dev/net/tun:rwm"
        }, 
    )

    return upf

##########################################################################################
##########################################################################################
def add_gnb_dockerhost( name:str , net_params:dict , net:Containernet ):
    info("*** Adding gNB\n")
    env={"COMPONENT_NAME":name}
    gnb = net.addDockerHost(
        name, 
        dimage = net_params["ueransim_image"],
        ip     = net_params["gnb_cont_ip"],
        dcmd   = "",
        docker_args={
            "cpuset_cpus": "0,1",
            "environment": env,
            "volumes": {
                net_params["prj_folder"] + "/volume_ran": {
                    "bind": "/mnt/ueransim",
                    "mode": "rw",
                },
                net_params["prj_folder"] + "/log": {
                    "bind": "/mnt/log",
                    "mode": "rw",
                },
                net_params["prj_folder"] + "/volume_util": {
                    "bind": "/mnt/volume_util",
                    "mode": "rw",
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
                "/dev": {"bind": "/dev", "mode": "rw"},
            },
            "cap_add": ["NET_ADMIN"],
            "devices": "/dev/net/tun:/dev/net/tun:rwm"
        },
    )
    return gnb

##########################################################################################
##########################################################################################
def add_UPFToMec( upf_name:str, mec_name:str, mgr:VNFManager, net_param):
    upf = mgr.addContainer(
        upf_name,
        mec_name,
        dimage = net_param["open5gs_image"],
        dcmd   = "",
        docker_args={
            "environment": {"COMPONENT_NAME":upf_name},
            "volumes": {
                net_param["prj_folder"] + "/log": {
                    "bind": "/open5gs/install/var/log/open5gs",
                    "mode": "rw",
                },
                net_param["prj_folder"] + "/volume_5gc": {
                    "bind": "/open5gs/install/etc/open5gs/volume_5gc",
                    "mode": "rw",
                },
                net_param["prj_folder"] + "/volume_util": {
                    "bind": "/mnt/volume_util",
                    "mode": "rw",
                },
                "/dev/net": {
                    "bind": "/dev/net",
                    "mode": "rw"
                },
                "/etc/timezone": {
                    "bind": "/etc/timezone",
                    "mode": "ro",
                },
                "/etc/localtime": {
                    "bind": "/etc/localtime",
                    "mode": "ro",
                },
            },
        }, 
    )
    return upf

##########################################################################################
##########################################################################################
def add_AppToMec( app_name:str, mec_name:str, image_name:str , mgr:VNFManager, net_param):

    app = mgr.addContainer( app_name , mec_name ,  image_name , "" , docker_args={
                                    "environment": {"COMPONENT_NAME":app_name},
                                    "volumes": {
                                        net_param["prj_folder"] + "/log": {
                                            "bind": "/mnt/log",
                                            "mode": "rw",
                                        },
                                        net_param["prj_folder"] + "/volume_util": {
                                            "bind": "/mnt/volume_util",
                                            "mode": "rw",
                                        },
                                        "/var/run/docker.sock": {"bind":"/var/run/docker.sock", "mode": "ro"},
                                    } 
                                })
    
    return app


##########################################################################################
##########################################################################################
if __name__ == "__main__":
    main( sys.argv )
