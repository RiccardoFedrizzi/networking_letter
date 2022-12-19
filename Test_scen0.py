"""
Experiment to test the environment

Scenario:
- cld_host: no active services
- mec:host:
    - srv_mec1
    - srv_mec2

Execution:
- Deploy the network
    $ sudo python3 net_deploy.py 100
- Run the experiment
    $ python3 Test_scen0.py
"""

import time, sys
from  python_modules.UeRanSim import UeRanSim
from  python_modules.Open5GS  import Open5GS
from  python_modules.MonitorScenario  import MonitorScenario
from  python_modules.IperfApp import IperfApp
from  python_modules.Results  import Results

def main(argv):

    uersim = UeRanSim(  ["001010000001001"] , "ue" )
    mon    = MonitorScenario()
    iperf  = IperfApp( mon , uersim , apn_mec_name="mec" , apn_mec_ip="10.2.0.1" , apn_cld_name="cld", apn_cld_ip="10.1.0.1" )
    o5gs   = Open5GS( "172.17.0.2" ,"27017")

    t_cpu   = 20
    t_iperf = 20
    t_wait  = 10
    res    = Results( f'results/Res_scenario0.json' )

    # Ensure to clean up 
    iperf.clean_all()
    mon.clean_redis()
    uersim.stop_all_ues()
    o5gs.removeAllSubscribers()
    mon.update_host_resources(h_name="mec_host",sys_cpu_perc=1)

    # Init process for generating load
    mon.start_cpu_load_gen_process("srv_mec2")

    # Start Monitors
    print(f"*** Start Simulation")
    mon.set_start_time()
    mon.start_all_monitors()

    time.sleep(t_wait)

    # Init subscribers
    print(f"*** Open5GS: Adding subscriber for UE 1")
    p = o5gs.getProfile_OneUe_maxThr( 100  )
    p["imsi"] = uersim.imsi_list[0]
    o5gs.addSubscriber(p)

    time.sleep(t_wait)

    uersim.start_ue( 0 , apn="all", sst="1", sd="1")

    time.sleep(t_wait)

    # Test Generate CPU
    print("*** Start CPU load test")
    mon.set_cpu_load( "srv_mec2" , 0.8 )
    time.sleep(t_cpu)
    mon.set_cpu_load( "srv_mec2" , 0.0 )
    mon.update_host_resources(h_name="mec_host",sys_cpu_perc=0.375)
    mon.set_cpu_load( "srv_mec2" , 0.8 )
    time.sleep(t_cpu)
    mon.set_cpu_load( "srv_mec2" , 0.0 )
    mon.update_host_resources(h_name="mec_host",sys_cpu_perc=1)

    time.sleep(t_wait)

    # Test Generate Data Traffic 
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=40 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=50 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=60 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=70 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=80 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)

    mon.update_host_resources(h_name="mec_host",sys_cpu_perc=0.375)
    time.sleep(t_wait)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=40 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=50 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=60 , t_dur=t_iperf ) 
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=70 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)
    iperf.start_session( ue_id=0, srv_name="srv_mec1" , sst="1" , prot="tcp" , ul_dl="ul" , bwt=80 , t_dur=t_iperf )
    iperf.wait_until_sessions_finish(0.5)

    time.sleep(5)

    ##########################################
    # End simulation and collect results
    mon.stop_all_monitors()
    res.collect_and_save_results( mon.redis_cli, mon, iperf )


##########################################################################################
##########################################################################################
if __name__ == "__main__":
    main( sys.argv )
