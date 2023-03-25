## Code developed for the paper published in IEEE Networking Letters

We provide a way to emulate a MEC-enabled 5G network deployment in ComNetsEmu (see reference paper below).

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

## Reference Paper

This work is described in details in the following paper:

Riccardo Fedrizzi, Cristina Emilia Costa, and Fabrizio Granelli, **"A Framework to define a Measurement-Based
Model of MEC Nodes in the 5G System"**, IEEE Networking Letters, 2023, in press

If you refer to our work or use it in your research activities, please refer to this paper.

## Contact

Author and main maintainer:
- Riccardo Fedrizzi - rfedrizzi@fbk.eu




