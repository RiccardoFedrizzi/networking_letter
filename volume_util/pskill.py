import psutil, sys
from psutil import Process

process_tag = sys.argv[1]

p_list = []
for p in psutil.process_iter():
    p_cmdline = ' '.join(p.cmdline())
    if process_tag in p_cmdline:
        p_list.append(p)

for p in p_list:
    p.kill()

        

