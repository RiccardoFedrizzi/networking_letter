import redis
from redis.client import PubSub
import sys, time, psutil


def get_intf_sample():
    val = psutil.net_io_counters(pernic=True)

    return val["ogstun"].bytes_recv , time.time()


def mon_intf( rp:PubSub ,last_sample_traffic , last_sample_time):

    while True:
        cur_traffic , cur_sample_time = get_intf_sample()
        bit_rate = (cur_traffic-last_sample_traffic) * 8 / 1e6 / (cur_sample_time-last_sample_time)
        r.ts().add(f'{host_name}:ogstun_recv', "*", bit_rate ) 

        last_sample_traffic = cur_traffic
        last_sample_time    = cur_sample_time

        message = rp.get_message()
        if message:
            if message["type"] == "subscribe":
                continue
            if message["channel"] == "throughput_monitoring":
                if message['data'] == "stop":
                    wait_command_loop(rp)

        time.sleep(1)


def wait_command_loop(rp:PubSub):
    last_sample_traffic , last_sample_time = get_intf_sample()
    for message in rp.listen():
        if message["type"] == "subscribe":
            continue
        if message["channel"] == "throughput_monitoring":
            if message['data'] == "start":
                mon_intf(rp,last_sample_traffic , last_sample_time)


if __name__ == "__main__":
    host_name = sys.argv[1]

    r = redis.StrictRedis(host="172.17.0.6", port=6379, password="", decode_responses=True)

    rp = r.pubsub()
    rp.subscribe('throughput_monitoring')

    last_sample_traffic = 0
    last_sample_time    = 0

    wait_command_loop( rp )



