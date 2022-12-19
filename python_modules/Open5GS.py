import pymongo
import random
import bson

class Open5GS:
    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.myclient = pymongo.MongoClient("mongodb://" + str(self.server) + ":" + str(self.port) + "/")

    def _GetSubscribers(self):
        mydb = self.myclient["open5gs"]
        mycol = mydb["subscribers"]
        subs_list = []
        for x in mycol.find():
            # print(x)
            subs_list.append(x)
            pass

        return subs_list

    def _GetSubscriber(self, imsi):
        mydb = self.myclient["open5gs"]
        mycol = mydb["subscribers"]
        myquery = { "imsi": str(imsi)}
        mydoc = mycol.find(myquery)
        for x in mydoc:
            # print(x)
            return x

    def _AddSubscriber(self, sub_data):
        mydb = self.myclient["open5gs"]
        mycol = mydb["subscribers"]

        x = mycol.insert_one(sub_data)
        return x.inserted_id

    def _UpdateSubscriber(self, imsi, sub_data):
        mydb = self.myclient["open5gs"]
        mycol = mydb["subscribers"]
        print("Attempting to update IMSI " + str(imsi))
        newvalues = { "$set": sub_data }
        myquery = { "imsi": str(imsi)}
        x = mycol.update_one(myquery, newvalues)
        print(x)
        return True

    def _DeleteSubscriber(self, imsi):
        mydb = self.myclient["open5gs"]
        mycol = mydb["subscribers"]
        myquery = { "imsi": str(imsi)}
        x = mycol.delete_many(myquery)
        return x.deleted_count



    #####################################################
    def getSubscribersImsiList(self):
        subs = self._GetSubscribers()
        s_list=[]
        for s in subs:
            s_list.append(s["imsi"])
        return s_list


    def addSubscriber( self , profile:dict ):
        if "imsi" in profile.keys():
            imsi_list = self.getSubscribersImsiList()
            if profile["imsi"] in imsi_list:
                print( "A subscriber with this IMSI is already there." )
            else:
                x = self._AddSubscriber(profile.copy())
        else:
            print( "IMSI is required." )


    def removeAllSubscribers(self):
        print("*** Open5GS: Removing all subscribers")
        subs = self._GetSubscribers()
        for s in subs:
            self._DeleteSubscriber(s["imsi"])


    def removeAllSubscribers_ByObjID(self):
        mydb = self.myclient["open5gs"]
        mycol = mydb["subscribers"]
        for c in mycol.find():
            aa = c["_id"]
            myquery = { "_id": aa }
            mycol.delete_many(myquery)


    ### Saved Profiles ############################################
    
    def getProfile_OneUe_maxThr(self ,  max_thr:int, sst=1 ):
        profile = dict()
        profile = {
            'subscribed_rau_tau_timer': 12,
            'network_access_mode': 0,
            'subscriber_status': 0,
            'access_restriction_data': 32,
            'slice': [ 
                self.slice_1_5QI_8_max_thr( max_thr , sst )
            ],
            'ambr': {
                'uplink': {'value': 1, 'unit': 2},
                'downlink': {'value': 1, 'unit': 2}
            },
            'security': {
                'k': '8baf473f2f8fd09487cccbd7097c6862',
                'amf': '8000',
                'op': '11111111111111111111111111111111',
                'opc': None
            },
            'msisdn': [],
            'schema_version': 1,
            '__v': 0
        }
        return profile

    def getProfileDefault(self):
        profile = dict()
        profile = {
            'subscribed_rau_tau_timer': 12,
            'network_access_mode': 0,
            'subscriber_status': 0,
            'access_restriction_data': 32,
            'slice': [ 
                self.slice_1_5QI_8(),
                self.slice_2_5QI_1(),
                self.slice_3_GBR()
            ],
            'ambr': {
                'uplink': {'value': 1, 'unit': 2},
                'downlink': {'value': 1, 'unit': 2}
            },
            'security': {
                'k': '8baf473f2f8fd09487cccbd7097c6862',
                'amf': '8000',
                'op': '11111111111111111111111111111111',
                'opc': None
            },
            'msisdn': [],
            'schema_version': 1,
            '__v': 0
        }
        return profile

    ### Slices #################################

    def slice_1_5QI_8_max_thr(self, max_thr:int, sst:int ):
        slice = dict()
        slice = {
            'sst': sst,
            'default_indicator': True,
            'sd': '000001',
            'session': [
                {
                    'name': 'mec',
                    'type': 3,
                    'pcc_rule': [],
                    'ambr':  {
                        'uplink': {'value': max_thr, 'unit': 2},  
                        'downlink': {'value': max_thr, 'unit': 2}
                    },
                    'qos': {
                        'index': 8,
                        'arp': {'priority_level': 15, 'pre_emption_capability': 1, 'pre_emption_vulnerability': 1}
                    }
                },
                {
                    'name': 'cld',
                    'type': 3,
                    'pcc_rule': [],
                    'ambr': {
                        'uplink': {'value': max_thr, 'unit': 2},
                        'downlink': {'value': max_thr, 'unit': 2}
                    },
                    'qos': {
                        'index': 8,
                        'arp': {'priority_level': 15, 'pre_emption_capability': 1, 'pre_emption_vulnerability': 1}
                    }
                }
            ]
        }
        return slice

    def slice_1_5QI_8(self):
        slice = dict()
        slice = {
            'sst': 1,
            'default_indicator': True,
            'sd': '000001',
            'session': [
                {
                    'name': 'mec',
                    'type': 3,
                    'pcc_rule': [],
                    'ambr':  {
                        'uplink': {'value': 5, 'unit': 2},  
                        'downlink': {'value': 5, 'unit': 2}
                    },
                    'qos': {
                        'index': 8,
                        'arp': {'priority_level': 15, 'pre_emption_capability': 1, 'pre_emption_vulnerability': 1}
                    }
                },
                {
                    'name': 'cld',
                    'type': 3,
                    'pcc_rule': [],
                    'ambr': {
                        'uplink': {'value': 5, 'unit': 2},
                        'downlink': {'value': 5, 'unit': 2}
                    },
                    'qos': {
                        'index': 8,
                        'arp': {'priority_level': 15, 'pre_emption_capability': 1, 'pre_emption_vulnerability': 1}
                    }
                }
            ]
        }
        return slice

    def slice_2_5QI_1(self):
        slice = dict()
        slice = {
            'sst': 2,
            'default_indicator': True,
            'sd': '000001',
            'session': [
                {
                    'name': 'mec',
                    'type': 3,
                    'pcc_rule': [],
                    'ambr':  {
                        'uplink': {'value': 5, 'unit': 2},  
                        'downlink': {'value': 5, 'unit': 2}
                    },
                    'qos': {
                        'index': 1,
                        'arp': {'priority_level': 1, 'pre_emption_capability': 1, 'pre_emption_vulnerability': 1}
                    }
                },
                {
                    'name': 'cld',
                    'type': 3,
                    'pcc_rule': [],
                    'ambr': {
                        'uplink': {'value': 5, 'unit': 2},
                        'downlink': {'value': 5, 'unit': 2}
                    },
                    'qos': {
                        'index': 1,
                        'arp': {'priority_level': 1, 'pre_emption_capability': 1, 'pre_emption_vulnerability': 1}
                    }
                }
            ]
        }
        return slice

    def slice_3_GBR(self):
        slice = dict()
        slice = {
            'sst': 3,
            'default_indicator': True,
            'sd': '000001',
            'session': [
                {
                    'name': 'mec',
                    'type': 3,
                    'pcc_rule': [
                        {
                            'qos': {
                                'index': 1,
                                'gbr': {
                                    'uplink': {'value': 5, 'unit': 2}, 
                                    'downlink': {'value': 5, 'unit': 2}
                                },
                                'mbr': {
                                    'uplink': {'value': 5, 'unit': 2},
                                    'downlink': {'value': 5, 'unit': 2}
                                },
                                'arp': {
                                    'priority_level': 1,
                                    'pre_emption_capability': 2,
                                    'pre_emption_vulnerability': 2}
                                },
                                'flow': []
                            }
                        ],
                    'ambr': {
                        'uplink': {'value': 5, 'unit': 2},
                        'downlink': {'value': 5, 'unit': 2}
                    },
                    'qos': {
                        'index': 1,
                        'arp': {
                            'priority_level': 1,
                            'pre_emption_capability': 1,
                            'pre_emption_vulnerability': 1
                        }
                    }
                },
                {
                    'name': 'cld',
                    'type': 3,
                    'pcc_rule': [
                        {
                            'qos': {
                                'index': 1,
                                'gbr': {
                                    'uplink': {'value': 5, 'unit': 2}, 
                                    'downlink': {'value': 5, 'unit': 2}
                                },
                                'mbr': {
                                    'uplink': {'value': 5, 'unit': 2},
                                    'downlink': {'value': 5, 'unit': 2}
                                },
                            'arp': {
                                'priority_level': 1,
                                'pre_emption_capability': 2,
                                'pre_emption_vulnerability': 2
                            }
                        },
                        'flow': []
                        }
                    ],
                    'ambr': {
                        'uplink': {'value': 5, 'unit': 2},
                        'downlink': {'value': 5, 'unit': 2}
                    },
                    'qos': {
                        'index': 1,
                        'arp': {
                            'priority_level': 1,
                            'pre_emption_capability': 1,
                            'pre_emption_vulnerability': 1
                        }
                    }
                }
            ]
        }
    
        return slice