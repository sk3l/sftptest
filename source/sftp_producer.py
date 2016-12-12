#!/opt/bb/bin/python3.5

import json
import logging
import os
import random
import time
import threading

from sftp_account import sftp_account

class sftp_producer:

    logger =  logging.getLogger('sftp_test.producer')
    def __init__(self):
        self.trans_count_   = 0
        self.stop_          = threading.Event()
        # keep the accounts hashed by name
        #self.account_map_   = {}
        #for account in self.account_list_:
        #    self.account_map_[account.name_] = account

    # Main producer thread method for working through a pre-prepared set of
    # SFTP file operations from among the specified account list
    def start_simulate(self, scriptloc, enqueuefunc, returnvals):

        # Perform SFTP tranfers, working off of the input script,
        # of until a count/time limit has been reached
        try:
            workScript = None
            with open(scriptloc, "r") as scriptf:
                workScript = json.load(scriptf)

            for action in workScript["Actions"]:
                if self.stop_.isSet():
                    break
                
                if not "Account" in action:
                    sftp_producer.logger.warn(
                    "Encountered unknown account in work script.")
                    continue
                account     = sftp_account.from_json_dict(action["Account"])
    
                operation   = action["Operation"]
                cmd         = operation["Command"]
                params      = operation["Parameters"]

                # Post the job on the work queue
                enqueuefunc(account, cmd, params)

                self.trans_count_ += 1
        except Exception as e:
            msg = "Encountered an error in start_simulate thread: {0}".format(e)
            sftp_producer.logger.error(msg)
            return 64

    # Main producer thread method for creating a set of randomized SFTP file
    # operations from among the specified account list
    def start_flood(self, acctlist, translimit, timelimit, rate, enqueuefunc, returnvals):
        try:
            random.seed()

            starttime = time.time()
            stoptime = 0
            if timelimit > 0:
                stoptime = time.time() + timelimit

            while True:

                # Implement a very primitive job throttle, enforcing 
                # a maximum number of jobs created per sec
                if rate > 0:
                    elapsed = time.time() - starttime
                    if (self.trans_count_ / elapsed) > rate :
                        time.sleep(.005)    # could be made more granular
                        continue

                if self.stop_.isSet():
                    break

                if translimit > 0 and self.trans_count_ >= translimit:
                    sftp_producer.logger.info(
                    ("Terminating SFTP flooding after {0} "
                    "transactions (trans limit={1} reached)".format(
                        self.trans_count_, translimit)))
                    break

                if stoptime > 0 and time.time() >= stoptime:
                    returnvals["timeout"] = True
                    sftp_producer.logger.info(
                    ("Terminating SFTP flooding after {0} "
                    "transactions (time limit={1} seconds reached)".format(
                        self.trans_count_, timelimit)))
                    break
               
                # Select a random account, file and cmd 
                i = random.randrange(0, len(acctlist))
                account = acctlist[i]
                
                i = random.randrange(0, len(account.file_list_))
                fname = account.file_list_[i]
               
                (pathstr,filestr) = os.path.split(fname)
            
                self.trans_count_ += 1
                cmd = "PUT"
                params = {
                    "LocalPath" : fname, 
                    "RemotePath": filestr, 
                    "SerialNo"  : self.trans_count_
                } 
                #if random.random() > .5: #and fname in account.file_put_map_:
                #    cmd = "GET"

                # Post the job on the work queue
                enqueuefunc(account, cmd, params)
   
        except Exception as e:
            msg = "Encountered error in start_flood thread: {0}".format(e)
            sftp_producer.logger.error(msg)
            return 64


    def stop(self):
        self.stop_.set()