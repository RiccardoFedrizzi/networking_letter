#!/bin/bash

if [[ -z "$COMPONENT_NAME" ]]; then
	echo "Error: COMPONENT_NAME environment variable not set"; exit 1;

elif [[ "$COMPONENT_NAME" =~ ^cld_host$ ]]; then
    ip tuntap add name ogstun mode tun
    ip addr add 10.1.0.1/16 dev ogstun
    ip link set ogstun up
    iptables -t nat -A POSTROUTING -s 10.1.0.1/16 ! -o ogstun -j MASQUERADE

elif [[ "$COMPONENT_NAME" =~ ^mec_host$ ]]; then
    ip tuntap add name ogstun mode tun
    ip addr add 10.2.0.1/16 dev ogstun
    ip link set ogstun up
    iptables -t nat -A POSTROUTING -s 10.2.0.1/16 ! -o ogstun -j MASQUERADE

else
	echo "Error: Invalid component name: '$COMPONENT_NAME'"
fi
