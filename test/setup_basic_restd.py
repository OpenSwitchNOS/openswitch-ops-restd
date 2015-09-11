#!/usr/bin/env python

import os
import sys
import time
import pytest
import subprocess
import shutil
from halonvsi.docker import *
from halonvsi.halon import *
from halonutils.halonutil import *
from restdconfig import *

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

SWITCH_PREFIX = "s"

class myTopo(Topo):
    def build (self, hsts=0, sws=1, **_opts):

        self.hsts = hsts
        self.sws = sws

        switch = self.addSwitch("%s1" % SWITCH_PREFIX)


class configTest (HalonTest):
    def setupNet (self):
        self.net = Mininet(topo=myTopo(hsts = NUM_HOSTS_PER_SWITCH,
                                       sws = NUM_OF_SWITCHES,
                                       hopts = self.getHostOpts(),
                                       sopts = self.getSwitchOpts()),
                                       switch = SWITCH_TYPE,
                                       host = HalonHost,
                                       link = HalonLink,
                                       controller = None,
                                       build = True)

    def configure_switch (self):
        info("\nConfiguring switch IPs..")
        switch = self.net.switches[0]
        testid = switch.testid
        script_shared_local = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared/test_ct_runconfig.py'
        script_shared_local_runconfig = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared/runconfig.py'
        script_shared_test_file1 = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared' + '/config_test1'
        script_shared_test_file2 = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared' + '/config_test2'
        script_shared_test_file3 = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared' + '/empty_config.db'

        script_shared_docker = '/shared/test_ct_runconfig.py'

        shutil.copy2("test_ct_runconfig.py", script_shared_local)
        shutil.copy2("config_test1", script_shared_test_file1)
        shutil.copy2("config_test2", script_shared_test_file2)
        shutil.copy2("empty_config.db", script_shared_test_file3)
        info(switch.cmd('python ' + script_shared_docker))


@pytest.mark.skipif(False, reason="Does not cleanup dockers fully")
class Test_config:
    def setup (self):
        pass

    def teardown (self):
        pass

    def setup_class (cls):
        Test_config.test_var = configTest()

    def teardown_class (cls):
        Test_config.test_var.net.stop()

    def setup_method (self, method):
        pass

    def teardown_method (self, method):
        pass

    def __del__ (self):
        del self.test_var

    def test_run (self):
        self.test_var.configure_switch()
