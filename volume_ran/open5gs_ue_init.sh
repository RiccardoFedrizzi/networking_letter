#!/bin/bash

# export IP_ADDR=$(awk 'END{print $1}' /etc/hosts)

#sleep 25
# sleep $1
cp /mnt/ueransim/open5gs-ue.yaml /UERANSIM/config/open5gs-ue.yaml

sed -i 's|UE_IMSI|'$UE_IMSI'|g' /UERANSIM/config/open5gs-ue.yaml
sed -i 's|UE_APN|'$UE_APN'|g'   /UERANSIM/config/open5gs-ue.yaml

./nr-ue -c /UERANSIM/config/open5gs-ue.yaml > /mnt/log/$COMPONENT_NAME.log 2>&1

# ./nr-ue -c /mnt/ueransim/open5gs-ue_1.yaml > /mnt/log/ue1.log 2>&1
