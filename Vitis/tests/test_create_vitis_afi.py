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

Call using ```pytest test_create_vitis_afi.py```

See TESTING.md for details.
'''


from __future__ import print_function
from __builtin__ import str
import boto3
import os
from os.path import basename, dirname, realpath
import pytest
import re
import sys
import traceback
import json

try:
    import aws_fpga_test_utils
    from aws_fpga_test_utils.AwsFpgaTestBase import AwsFpgaTestBase
    import aws_fpga_utils
except ImportError as e:
    traceback.print_tb(sys.exc_info()[2])
    print(
        f"error: {sys.exc_info()[1]}\nMake sure to source shared/bin/setup_test_env.sh"
    )
    sys.exit(1)

logger = aws_fpga_utils.get_logger(__name__)

class TestCreateVitisAfi(AwsFpgaTestBase):
    '''
    Pytest test class.

    NOTE: Cannot have an __init__ method.

    Create AFI from xclbin.
    '''

    ADD_EXAMPLEPATH = True
    ADD_RTENAME = True
    ADD_XILINX_VERSION = True

    @classmethod
    def setup_class(cls):
        '''
        Do any setup required for tests.
        '''
        AwsFpgaTestBase.setup_class(cls, __file__)

        AwsFpgaTestBase.assert_sdk_setup()
        AwsFpgaTestBase.assert_vitis_setup()

        return

    def call_create_afi_script(self, examplePath, xclbin, target, rteName, xilinxVersion):

        full_example_path = self.get_vitis_example_fullpath(examplePath=examplePath)
        logger.info(f"Vitis Example path={full_example_path}")

        assert os.path.exists(
            full_example_path
        ), f"Vitis Example path={full_example_path} does not exist"

        os.chdir(full_example_path)

        xclbin_basename = os.path.basename(xclbin)
        xclbin_filename = os.path.splitext(xclbin_basename)[0]
        aws_xclbin_filename_rte = xclbin_filename

        aws_xclbin_path = AwsFpgaTestBase.get_vitis_xclbin_dir(examplePath)
        aws_xclbin_basename = os.path.join(aws_xclbin_path, aws_xclbin_filename_rte)

        cmd = "{}/Vitis/tools/create_vitis_afi.sh -s3_bucket={} -s3_dcp_key={} -xclbin={} -o={}".format(
                self.WORKSPACE,
                self.s3_bucket,
                self.get_vitis_example_s3_dcp_tag(examplePath=examplePath, target=target, rteName=rteName, xilinxVersion=xilinxVersion),
                xclbin,
                aws_xclbin_basename
            )

        logger.info(cmd)
        rc = os.system(cmd)
        assert rc == 0, "Error encountered while running the create_vitis_afi.sh script"

        logger.info(
            f"Checking that a non zero size aws_xclbin file exists in {aws_xclbin_path}"
        )
        aws_xclbin = self.assert_non_zero_file(os.path.join(aws_xclbin_path, "*.awsxclbin"))
        logger.info(f"Uploading aws_xclbin file: {aws_xclbin}")

        aws_xclbin_key = os.path.join(self.get_vitis_example_s3_xclbin_tag(examplePath=examplePath, target=target, rteName=rteName, xilinxVersion=xilinxVersion), basename(aws_xclbin))
        self.s3_client().upload_file(aws_xclbin, self.s3_bucket, aws_xclbin_key)

        create_afi_response_file = self.assert_non_zero_file(os.path.join(full_example_path, "*afi_id.txt"))

        create_afi_response_file_key = self.get_vitis_example_s3_afi_tag(examplePath=examplePath, target=target, rteName=rteName, xilinxVersion=xilinxVersion)

        logger.info(f"Uploading create_afi output file: {create_afi_response_file}")
        self.s3_client().upload_file(create_afi_response_file, self.s3_bucket, create_afi_response_file_key)

        return json.load(open(create_afi_response_file))


    def test_create_vitis_afi(self, examplePath, rteName, xilinxVersion, target="hw"):

        xclbin = self.get_vitis_xclbin_file(examplePath, rteName, xilinxVersion)
        create_afi_response = self.call_create_afi_script(examplePath, xclbin, target, rteName, xilinxVersion)

        afi = create_afi_response.get("FpgaImageId", None)

        assert (
            afi is not None
        ), f"AFI ID not available in create_afi response:{str(create_afi_response)}"

        # Wait for the AFI to complete
        rc = os.system(
            f"{self.WORKSPACE}/shared/bin/scripts/wait_for_afi.py --afi {afi}"
        )
        assert rc == 0, f"Error while waiting for afi={afi}"

        self.assert_afi_available(afi)
