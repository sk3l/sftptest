#!/opt/bb/bin/python3.5

import concurrent.futures
import json
import os
import random
import threading

from sftp_account import sftp_account
from sftp_consumer import sftp_result

#class sftp_job:
#
#    def __init__(self, account, op, fname):
#        self.account_   = account
#        self.operation_ = op
#        self.file_name_ = fname

class sftp_producer:

    def __init__(self, threadpool, callback, acctlist):
        self.thread_pool_   = threadpool 
        self.thread_cback_  = callback
        self.account_list_  = acctlist
        self.trans_count_   = 0
        self.future_list_   = []
        self.stop_          = threading.Event()

        # keep the accounts hashed by name
        self.account_map_   = {}
        for account in self.account_list_:
            self.account_map_[account.name_] = account

    # Main producer thread method for working through a pre-prepared set of
    # SFTP file operations from among the specified account list
    def start_scripted(self, scriptloc):

        # Perform SFTP tranfers, working off of the input script,
        # of until a count/time limit has been reached
        try:
            workScript = None
            with open(scriptloc, "r") as scriptf:
                workScript = json.load(scriptf)
    
            for job in workScript["Jobs"]:
                if self.stop_.isSet():
                    break
                
                if not job["Account"] in self.account_map_:
                    print(
                    "WARNING: encountered unknown account {0} in work script.".format(
                        job["Account"]))
                    continue
                account     = self.account_map_[job["Account"]]
    
                operation   = job["Operation"]
                cmd         = operation["Command"]
                params      = operation["Parameters"]
 
                # Post the job on the thread pool
                self.future_list_.append(
                    self.thread_pool_.submit(self.thread_cback_, account, cmd, params))
                

            self.trans_count_ += 1
        except Exception as e:
            print(
            "Encountered an error in start_scripted thread: {0}".format(
            e))
            return 64

    # Main producer thread method for creating a set of randomized SFTP file
    # operations from among the specified account list
    def start_random(self, translimit):
        try:
            random.seed()
            while self.trans_count_ < translimit:

                if self.stop_.isSet():
                    break
               
                # Select a random account, file and cmd 
                i = random.randrange(0, len(self.account_list_))
                account = self.account_list_[i]
                
                i = random.randrange(0, len(account.file_list_))
                fname = account.file_list_[i]
               
                with account.file_locks_[fname]:
                
                    (pathstr,filestr) = os.path.split(fname)
                
                    cmd = "PUT"
                    params = {"LocalPath": fname, "RemotePath": filestr} 
                    if random.random() > .5: #and fname in account.file_put_map_:
                        cmd = "GET"
    
                    # Post the job on the thread pool
                    self.future_list_.append(
                        self.thread_pool_.submit(
                            self.thread_cback_, account, cmd, params))
    
                self.trans_count_ += 1
        except Exception as e:
            print(
            "Encountered error in start_random thread: {0}".format(
                e))
            return 64


    def stop(self):
        self.stop_.set()

    def wait_for_consumer(self):
       
        retry_list = []
        i = 1
        for job in self.future_list_:
            try:
                res = job.result()
                if not res.complete_:
                    retry_list.append(res)
            except Exception as e:
                print(
                "Encountered error waiting for job {0} in sftp_producer: {1}".format(
                i, e))

        self.future_list_ = []
        # Resubmit the retries
        for res in retry_list:
            self.future_list_.append(
                self.thread_pool_.submit(
                    self.thread_cback_, res.account_, res.command_,res.parameters_))

        if len(self.future_list_) > 0:
            return False
        else:
            return True
