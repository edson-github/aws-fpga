#!/usr/bin/env python2.7

# Amazon FPGA Hardware Development Kit
#
# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the "License"). You may not use
# this file except in compliance with the License. A copy of the License is
# located at
#
#    http://aws.amazon.com/asl/
#
# or in the "license" file accompanying this file. This file is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or
# implied. See the License for the specific language governing permissions and
# limitations under the License.

'''
Pytest module:

Call using ```pytest test_drivers.py```

See TESTING.md for details.
'''

import os
from os.path import basename, dirname, realpath
import pytest
import sys
import traceback
import requests
import time
import signal
import subprocess
import re
try:
    import aws_fpga_utils
    import aws_fpga_test_utils
    from aws_fpga_test_utils.AwsFpgaTestBase import AwsFpgaTestBase
except ImportError as e:
    traceback.print_tb(sys.exc_info()[2])
    print "error: {}\nMake sure to source sdk_setup.sh".format(sys.exc_info()[1])
    sys.exit(1)

logger = aws_fpga_utils.get_logger(__name__)

class TestPyBindings(AwsFpgaTestBase):
    '''
    Pytest test class.

    NOTE: Cannot have an __init__ method.

    Test all example CLs with different strategies and clock recipes.
    '''

    def setup_class(self):
        '''
        Do any setup required for tests.
        '''
        AwsFpgaTestBase.setup_class(self, __file__)

        AwsFpgaTestBase.assert_sdk_setup()

        assert (
            AwsFpgaTestBase.running_on_f1_instance()
        ), f"This test must be run on an F1 instance. Running on {aws_fpga_test_utils.get_instance_type()}"
        self.cl_hello_world_agfi, cl_hello_world_afi = self.get_agfi_from_readme(
            'cl_hello_world'
        )

    def setup_method(self, test_method):
        os.putenv('BSWAPPER_AFI', self.cl_hello_world_agfi)
        os.putenv('BSWAPPER_SLOT', "0")
        os.putenv('BSWAPPER_REG', "0x500")

    def teardown_method(self, test_method):
        pass

    def stop_server(self):
        if hasattr(self, 'pid'):
            cmd = ['sudo', 'kill', '-2', str(self.pid)]
            logger.info(f"Signalling {self.pid}")
            logger.info(f"using command {cmd}")
            subprocess.call(cmd)

    def test_flask_app(self):
        server_script = os.environ['SDK_DIR'] + "/tests/test_py.sh"
        cmd = ['sudo', '-E',  server_script]
        try:
            logger.info(f"Starting server using {cmd}")
            server = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if  server.stdout is not None:
                server.stdout.flush()
                line = server.stdout.readline()
            mo = re.match("CHILDPID (\d+)?", line)
            if mo is not None:
                self.pid = mo.group(1)
                logger.info(f"Server PID: {self.pid}")
        except:
            logger.error(traceback.print_exc())
        max_retries = 30
        retry = 0
        while True:
            if retry >= max_retries:
                logger.info("Exceeded max retries...")
                self.stop_server()
                sys.exit(1)
            # Add sleep before first check as flask server may still be coming up.
            time.sleep(1)
            try:
                r1 = requests.get('http://127.0.0.1:5000/status')
                if r1.status_code != 200:
                    logger.info(f"Recived response {r1.status_code}")
                elif r1.text == "FPGA_STATUS_LOADED":
                    logger.info("Server ready")
                    break
                else:
                    logger.info("FPGA not loaded with AFI yet.")
            except:
                logger.info("Exception caught during status check.")
                logger.info(traceback.print_exc())
                logger.info("Retry status check...")
            retry += 1
        payload = { 'input_data' : '0x12345678'}
        r2 = requests.get('http://127.0.0.1:5000/', params=payload)
        logger.info("Stopping server")
        self.stop_server()
        if r2.status_code == 200:
            swapped_val = r2.text
            logger.info(f"Swapped value: {swapped_val}")
            if swapped_val != "0x78563412":
                logger.info("Swapped value not correct!")
                sys.exit(2)
        else:
            logger.info(f"Status received {r.status_code}")
            sys.exit(3)
