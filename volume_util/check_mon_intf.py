import sys, json, time, psutil


def mon( itf_str ):
    a=psutil.net_io_counters(pernic=True,nowrap=True)
    b=psutil._common.snetio
    b = a[ itf ]
    b_dict = a[ itf ]._asdict()


def mon2( itf_list ):
    a = psutil.net_io_counters(pernic=True)

    monit = dict()

    for i in itf_list:
        b_dict = a[ i ]._asdict()
        monit[i] = b_dict

    monit["time"] = time.time()
    print( json.dumps( b_dict , indent=2) )


if __name__ == "__main__":
    itf = list(sys.argv[1:])
    mon2( itf )

