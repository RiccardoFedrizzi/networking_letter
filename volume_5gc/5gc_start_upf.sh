#!/bin/bash

if [[ -z "$COMPONENT_NAME" ]]; then
	echo "Error: COMPONENT_NAME environment variable not set"; exit 1;

elif [[ "$COMPONENT_NAME" =~ ^upf_cld$ ]]; then
    cp /open5gs/install/etc/open5gs/volume_5gc/upf_cld.yaml  /open5gs/install/etc/open5gs/upf.yaml


elif [[ "$COMPONENT_NAME" =~ ^upf_mec$ ]]; then
    cp /open5gs/install/etc/open5gs/volume_5gc/upf_mec.yaml  /open5gs/install/etc/open5gs/upf.yaml

else
	echo "Error: Invalid component name: '$COMPONENT_NAME'"
fi

./install/bin/open5gs-upfd
