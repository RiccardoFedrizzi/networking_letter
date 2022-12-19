## Code developed for the paper submitted to IEEE Networking Letters

We provide a way to emulate a MEC-enabled 5G network deployment in ComNetsEmu.

Tested Versions:
- Comnetsemu: v0.3.0 (Installed following either "Option 1" or "Option 3" from [here](https://git.comnets.net/public-repo/comnetsemu) )
- UERANSIM: v3.2.6
- Open5gs: v2.4.4

## Build Instructions

Clone the repository.

Build the necessary docker images:

```
cd build_images
./build.sh
```
Or alternatively download them from DockerHub

```
cd ../open5gs
./dockerhub_pull.sh
```

## Run experiments

To run the experiments please refer to the following files which contains the instructions as well.
- Test_scen0.py
- Test_scen1.py
- Test_scen2.py


### Contact

Author and main maintainer:
- Riccardo Fedrizzi - rfedrizzi@fbk.eu




