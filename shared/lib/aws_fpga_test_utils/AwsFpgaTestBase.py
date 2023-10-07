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
Base class for pytest modules

See TESTING.md for details.
'''


from __future__ import print_function
import boto3
import os
from os.path import basename, dirname, realpath, stat
import glob
import pytest
import re
import subprocess
import sys
import traceback
import json
try:
    import aws_fpga_test_utils
    from aws_fpga_test_utils import get_git_repo_root
    import aws_fpga_utils
except ImportError as e:
    traceback.print_tb(sys.exc_info()[2])
    print(f"error: {sys.exc_info()[1]}\nMake sure to source hdk_setup.sh")
    sys.exit(1)

logger = aws_fpga_utils.get_logger(__name__)

class AwsFpgaTestBase(object):
    '''
    Pytest test class.

    NOTE: Cannot have an __init__ method.

    Load AFI created by test_create_afi.py
    '''

    DCP_BUILD_STRATEGIES = [
        'BASIC',
        'DEFAULT',
        'EXPLORE',
        'TIMING',
        'CONGESTION']

    DCP_CLOCK_RECIPES = aws_fpga_test_utils.read_clock_recipes()

    DCP_URAM_OPTIONS = ['2', '3', '4']

    git_repo_dir = get_git_repo_root(dirname(__file__))
    WORKSPACE = git_repo_dir

    ADD_BATCH = False
    ADD_SIMULATOR = False
    ADD_EXAMPLEPATH = False
    ADD_RTENAME = False
    ADD_XILINX_VERSION = False

    msix_agfi = 'agfi-09c2a21805a8b9257'

    # sdk request timeout in seconds
    DEFAULT_REQUEST_TIMEOUT = 6000

    @classmethod
    def setup_class(cls, derived_cls, filename_of_test_class):
        AwsFpgaTestBase.s3_bucket = 'aws-fpga-jenkins-testing'
        AwsFpgaTestBase.__ec2_client = None
        AwsFpgaTestBase.__s3_client = None
        AwsFpgaTestBase.test_dir = dirname(realpath(filename_of_test_class))

        # SDAccel locations
        # Need to move to either a config file somewhere or a subclass
        AwsFpgaTestBase.xilinx_sdaccel_examples_prefix_path = "SDAccel/examples/xilinx"
        AwsFpgaTestBase.xilinx_sdaccel_examples_dir = f"{AwsFpgaTestBase.git_repo_dir}/{AwsFpgaTestBase.xilinx_sdaccel_examples_prefix_path}"
        AwsFpgaTestBase.xilinx_sdaccel_examples_list_file = (
            f"{AwsFpgaTestBase.WORKSPACE}/sdaccel_examples_list.json"
        )

        # Vitis locations
        # Need to move to either a config file somewhere or a subclass
        AwsFpgaTestBase.xilinx_vitis_examples_prefix_path = "Vitis/examples/xilinx"
        AwsFpgaTestBase.xilinx_vitis_examples_dir = f"{AwsFpgaTestBase.git_repo_dir}/{AwsFpgaTestBase.xilinx_vitis_examples_prefix_path}"
        AwsFpgaTestBase.xilinx_vitis_examples_list_file = (
            f"{AwsFpgaTestBase.WORKSPACE}/vitis_examples_list.json"
        )

        if 'WORKSPACE' in os.environ:
            assert os.environ['WORKSPACE'] == AwsFpgaTestBase.git_repo_dir, "WORKSPACE incorrect"
        else:
            os.environ['WORKSPACE'] = AwsFpgaTestBase.WORKSPACE
        if 'BUILD_TAG' not in os.environ:
            os.environ['BUILD_TAG'] = 'test'
            logger.info(f"Set BUILD_TAG to {os.environ['BUILD_TAG']}")
        AwsFpgaTestBase.instance_type = aws_fpga_test_utils.get_instance_type()
        AwsFpgaTestBase.num_slots = aws_fpga_test_utils.get_num_fpga_slots(AwsFpgaTestBase.instance_type)
        return

    @staticmethod
    def ec2_client():
        if not AwsFpgaTestBase.__ec2_client:
            AwsFpgaTestBase.__ec2_client = boto3.client('ec2')
        return AwsFpgaTestBase.__ec2_client

    @staticmethod
    def s3_client():
        if not AwsFpgaTestBase.__s3_client:
            AwsFpgaTestBase.__s3_client = boto3.client('s3')
        return AwsFpgaTestBase.__s3_client

    @staticmethod
    def assert_hdk_setup():
        assert (
            'AWS_FPGA_REPO_DIR' in os.environ
        ), f"AWS_FPGA_REPO_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/hdk_setup.sh"
        assert (
            os.environ['AWS_FPGA_REPO_DIR'] == AwsFpgaTestBase.git_repo_dir
        ), f"AWS_FPGA_REPO_DIR not set to the repo dir. source {AwsFpgaTestBase.git_repo_dir}/hdk_setup.sh"
        assert (
            'HDK_DIR' in os.environ
        ), f"HDK_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/hdk_setup.sh"
        assert os.environ['HDK_DIR'] == os.path.join(
            AwsFpgaTestBase.git_repo_dir, 'hdk'
        ), f"HDK_DIR incorrect. source {AwsFpgaTestBase.git_repo_dir}/hdk_setup.sh"

    @staticmethod
    def assert_sdk_setup():
        assert (
            'SDK_DIR' in os.environ
        ), f"SDK_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/sdk_setup.sh"
        assert os.environ['SDK_DIR'] == os.path.join(
            AwsFpgaTestBase.git_repo_dir, 'sdk'
        ), f"SDK_DIR incorrect. source {AwsFpgaTestBase.git_repo_dir}/sdk_setup.sh"

    @staticmethod
    def assert_sdaccel_setup():
        assert (
            'AWS_FPGA_REPO_DIR' in os.environ
        ), f"AWS_FPGA_REPO_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert (
            os.environ['AWS_FPGA_REPO_DIR'] == AwsFpgaTestBase.git_repo_dir
        ), f"AWS_FPGA_REPO_DIR not set to the repo dir. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert (
            'SDK_DIR' in os.environ
        ), f"SDK_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert os.environ['SDK_DIR'] == os.path.join(
            AwsFpgaTestBase.git_repo_dir, 'sdk'
        ), f"SDK_DIR incorrect. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert (
            'SDACCEL_DIR' in os.environ
        ), f"SDACCEL_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert os.environ['SDACCEL_DIR'] == os.path.join(
            AwsFpgaTestBase.git_repo_dir, 'SDAccel'
        ), f"SDACCEL_DIR incorrect. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert (
            os.environ.get('AWS_PLATFORM') != 'None'
        ), f"Environment Var AWS_PLATFORM not set. source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh"
        assert os.environ.get('XILINX_SDX') != 'None', "Environment Var XILINX_SDX not set. Please check the AMI."

    @staticmethod
    def assert_vitis_setup():
        assert (
            'AWS_FPGA_REPO_DIR' in os.environ
        ), f"AWS_FPGA_REPO_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert (
            os.environ['AWS_FPGA_REPO_DIR'] == AwsFpgaTestBase.git_repo_dir
        ), f"AWS_FPGA_REPO_DIR not set to the repo dir. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert (
            'SDK_DIR' in os.environ
        ), f"SDK_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert os.environ['SDK_DIR'] == os.path.join(
            AwsFpgaTestBase.git_repo_dir, 'sdk'
        ), f"SDK_DIR incorrect. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert (
            'VITIS_DIR' in os.environ
        ), f"VITIS_DIR not set. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert os.environ['VITIS_DIR'] == os.path.join(
            AwsFpgaTestBase.git_repo_dir, 'Vitis'
        ), f"VITIS_DIR incorrect. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert (
            os.environ.get('AWS_PLATFORM') != 'None'
        ), f"Environment Var AWS_PLATFORM not set. source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh"
        assert os.environ.get('XILINX_VITIS') != 'None', "Environment Var XILINX_VITIS not set. Please check the AMI."

    @staticmethod
    def running_on_f1_instance():
        '''
        Check to see if running on an F1 instance
        '''
        instance_type = aws_fpga_test_utils.get_instance_type()
        return re.match(r'f1\.', instance_type)


    @staticmethod
    def load_msix_workaround(slot=0):

        AwsFpgaTestBase.fpga_clear_local_image(slot)

        logger.info(f"Loading MSI-X workaround into slot {slot}")
        AwsFpgaTestBase.fpga_load_local_image(AwsFpgaTestBase.msix_agfi, slot)

        logger.info(f"Checking slot {slot} AFI Load status")
        assert AwsFpgaTestBase.check_fpga_afi_loaded(
            AwsFpgaTestBase.msix_agfi, slot
        ), f"{AwsFpgaTestBase.msix_agfi} not loaded in slot {slot}"

        AwsFpgaTestBase.fpga_clear_local_image(slot)

    @staticmethod
    def run_cmd(cmd, echo=False, check=True):
        if echo:
            logger.info(f"Running: {cmd}")
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdout_data, stderr_data) = p.communicate()
        stdout_lines = stdout_data.split('\n')
        stderr_lines = stderr_data.split('\n')
        if check and p.returncode:
            logger.error(
                f"Cmd failed with rc={p.returncode}\ncmd: {cmd}\nstdout:\n{stdout_data}\nstderr:\n{stderr_data}"
            )
        elif echo:
            logger.info(
                f"rc={p.returncode}\nstdout:\n{stdout_data}\nstderr:\n{stderr_data}\n"
            )
        return (p.returncode, stdout_lines, stderr_lines)

    @staticmethod
    def run_hdk_cmd(cmd, echo=False, check=True):
        source_hdk_cmd = (
            f"source {AwsFpgaTestBase.git_repo_dir}/hdk_setup.sh &> /dev/null"
        )
        cmd = f"{source_hdk_cmd} && {cmd}"
        return AwsFpgaTestBase.run_cmd(cmd, echo, check)

    @staticmethod
    def run_sdk_cmd(cmd, echo=False, check=True):
        source_sdk_cmd = (
            f"source {AwsFpgaTestBase.git_repo_dir}/sdk_setup.sh &> /dev/null"
        )
        cmd = f"{source_sdk_cmd} && {cmd}"
        return AwsFpgaTestBase.run_cmd(cmd, echo, check)

    @staticmethod
    def run_sdaccel_cmd(cmd, echo=False, check=True):
        source_sdaccel_cmd = (
            f"source {AwsFpgaTestBase.git_repo_dir}/sdaccel_setup.sh &> /dev/null"
        )
        cmd = f"{source_sdaccel_cmd} && {cmd}"
        return AwsFpgaTestBase.run_cmd(cmd, echo, check)

    @staticmethod
    def run_vitis_cmd(cmd, echo=False, check=True):
        source_vitis_cmd = (
            f"source {AwsFpgaTestBase.git_repo_dir}/vitis_setup.sh &> /dev/null"
        )
        cmd = f"{source_vitis_cmd} && {cmd}"
        return AwsFpgaTestBase.run_cmd(cmd, echo, check)

    @staticmethod
    def get_shell_version():
        shell_link = os.path.join(AwsFpgaTestBase.WORKSPACE, 'hdk/common/shell_stable')
        link = basename(os.readlink(shell_link))
        return re.sub('^shell_v', '0x', link)

    @staticmethod
    def get_cl_dir(cl):
        return f"{AwsFpgaTestBase.WORKSPACE}/hdk/cl/examples/{cl}"

    @staticmethod
    def get_cl_to_aws_dir(cl):
        return os.path.join(AwsFpgaTestBase.get_cl_dir(cl), 'build/checkpoints/to_aws')

    @staticmethod
    def get_cl_afi_id_filename(cl):
        return os.path.join(AwsFpgaTestBase.get_cl_dir(cl), 'build/create-afi/afi_ids.txt')

    @staticmethod
    def get_cl_scripts_dir(cl):
        return os.path.join(AwsFpgaTestBase.get_cl_dir(cl), 'build/scripts')

    @staticmethod
    def get_cl_s3_dcp_tag(cl, option_tag, xilinxVersion):
        '''
        @param option_tag: A tag that is unique for each build.
            Required because a CL can be built with different options such as clock recipes.
        '''
        assert option_tag != ''
        assert xilinxVersion != ''
        return f"jenkins/{os.environ['BUILD_TAG']}/cl/{xilinxVersion}/{cl}/{option_tag}/dcp"

    @staticmethod
    def get_cl_s3_afi_tag(cl, option_tag, xilinxVersion):
        '''
        @param option_tag: A tag that is unique for each build.
            Required because a CL can be built with different options such as clock recipes.
        '''
        assert option_tag != ''
        assert xilinxVersion != ''
        return f"jenkins/{os.environ['BUILD_TAG']}/cl/{xilinxVersion}/{cl}/{option_tag}/create-afi/afi_ids.txt"

    @staticmethod
    def get_sdaccel_xclbin_dir(examplePath):
        return os.path.join(AwsFpgaTestBase.get_sdaccel_example_fullpath(examplePath=examplePath), 'xclbin')

    @staticmethod
    def get_vitis_xclbin_dir(examplePath, target='hw'):
        return os.path.join(
            AwsFpgaTestBase.get_sdaccel_example_fullpath(examplePath=examplePath),
            f"build_dir.{target}.xilinx_aws-vu9p-f1_shell-v04261818_201920_3",
        )

    @staticmethod
    def get_sdaccel_example_s3_root_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx SDAccel example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        @param xilinxVersion: The Xilinx tool version
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        example_relative_path = os.path.relpath(examplePath, AwsFpgaTestBase.xilinx_sdaccel_examples_prefix_path)
        return f"jenkins/{os.environ['BUILD_TAG']}/SDAccel/{xilinxVersion}/{rteName}/{example_relative_path}/{target}"

    @staticmethod
    def get_vitis_example_s3_root_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx Vitis example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        @param xilinxVersion: The Xilinx tool version
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        example_relative_path = os.path.relpath(examplePath, AwsFpgaTestBase.xilinx_vitis_examples_prefix_path)
        return f"jenkins/{os.environ['BUILD_TAG']}/Vitis/{xilinxVersion}/{rteName}/{example_relative_path}/{target}"

    @staticmethod
    def get_sdaccel_example_s3_xclbin_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx SDAccel example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        @param xilinxVersion: The Xilinx tool version
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        root_tag = AwsFpgaTestBase.get_sdaccel_example_s3_root_tag(examplePath, target, rteName, xilinxVersion)

        return f"{root_tag}/xclbin"

    @staticmethod
    def get_vitis_example_s3_xclbin_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx Vitis example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        @param xilinxVersion: The Xilinx tool version
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        root_tag = AwsFpgaTestBase.get_vitis_example_s3_root_tag(examplePath, target, rteName, xilinxVersion)

        return f"{root_tag}/xclbin"

    @staticmethod
    def get_sdaccel_example_s3_dcp_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx SDAccel example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        @param xilinxVersion: The Xilinx tool version
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        root_tag = AwsFpgaTestBase.get_sdaccel_example_s3_root_tag(examplePath, target, rteName, xilinxVersion)

        return f"{root_tag}/dcp"

    @staticmethod
    def get_vitis_example_s3_dcp_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx Vitis example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        @param xilinxVersion: The Xilinx tool version
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        root_tag = AwsFpgaTestBase.get_vitis_example_s3_root_tag(examplePath, target, rteName, xilinxVersion)

        return f"{root_tag}/dcp"

    @staticmethod
    def get_sdaccel_example_s3_afi_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx SDAccel example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        root_tag = AwsFpgaTestBase.get_sdaccel_example_s3_root_tag(examplePath, target, rteName, xilinxVersion)

        return f"{root_tag}/create-afi/afi-ids.txt"

    @staticmethod
    def get_vitis_example_s3_afi_tag(examplePath, target, rteName, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx Vitis example
        @param target: The target to build. For eg: hw, hw_emu, sw_emu
        @param rteName: The runtime environment
        '''
        assert target != ''
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        root_tag = AwsFpgaTestBase.get_vitis_example_s3_root_tag(examplePath, target, rteName, xilinxVersion)

        return f"{root_tag}/create-afi/afi-ids.txt"

    @staticmethod
    def get_sdaccel_example_run_cmd(examplePath, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx SDAccel example
        @param xilinxVersion: The Xilinx tool version
        '''
        description = AwsFpgaTestBase.get_sdaccel_example_description(examplePath)
        if description.get("em_cmd", None):
            run_cmd = description.get("em_cmd", None)
        elif description.get("host_exe", None):
            run_cmd = f'./{description.get("host_exe", None)}'
            if description.get("cmd_args", None):
                if "PROJECT" in description.get(
                    "cmd_args", None
                ) or "BUILD" in description.get("cmd_args", None):
                    if "2019.1" not in xilinxVersion:
                        run_cmd += f' {description.get("cmd_args", None).replace("PROJECT", ".").replace("BUILD", "./xclbin")}'
                    else:
                        run_cmd += f' {description.get("cmd_args", None).replace(".xclbin", ".hw.xilinx_aws-vu9p-f1-04261818_dynamic_5_0.awsxclbin").replace("PROJECT", ".").replace("BUILD", "./xclbin")}'

                else:
                    run_cmd += (
                        f' {description.get("cmd_args", None)}'
                        if "2019.1" not in xilinxVersion
                        else f' {description.get("cmd_args", None).replace(".xclbin", ".hw.xilinx_aws-vu9p-f1-04261818_dynamic_5_0.xclbin")}'
                    )
        assert (
            run_cmd is not None
        ), f"Could not find run_cmd(em_cmd) or (host_exe) in the example description here {examplePath}"

        return run_cmd

    @staticmethod
    def get_vitis_example_run_cmd(examplePath, xilinxVersion):
        '''
        @param examplePath: Path of the Xilinx Vitis example
        @param xilinxVersion: The Xilinx tool version
        '''
        description = AwsFpgaTestBase.get_vitis_example_description(examplePath)

        host_description = description.get("host", None)
        assert (
            host_description is not None
        ), f"Could not find host key in the description.json here {examplePath}"

        launch_description = description.get("launch", None)
        assert (
            launch_description is not None
        ), f"Could not find launch/cmd_args key in the description.json here {examplePath}"

        if host_description.get("host_exe", None):
            run_cmd = f'./{host_description.get("host_exe", None)}'

        if launch_description[0].get("cmd_args", None):
            run_cmd += " {}".format(((launch_description[0].get("cmd_args", None).replace(".xclbin", ".awsxclbin")).replace(
                        "PROJECT", ".")).replace("BUILD", "./build_dir.hw.xilinx_aws-vu9p-f1_shell-v04261818_201920_3")).replace(
                "REPO_DIR", AwsFpgaTestBase.get_vitis_example_base_dir(xilinxVersion))

        assert (
            run_cmd is not None
        ), f"Could not find run_cmd(em_cmd) or (host_exe) in the example description here {examplePath}"

        return run_cmd

    @staticmethod
    def get_sdaccel_example_description(examplePath):
        '''
        @param examplePath: Path of the Xilinx SDAccel example
        '''

        example_description = AwsFpgaTestBase.assert_non_zero_file(os.path.join(AwsFpgaTestBase.get_sdaccel_example_fullpath(examplePath), "description.json"))

        with open(example_description) as json_data:
            return json.load(json_data)

    @staticmethod
    def get_vitis_example_description(examplePath):
        '''
        @param examplePath: Path of the Xilinx Vitis example
        '''

        example_description = AwsFpgaTestBase.assert_non_zero_file(os.path.join(AwsFpgaTestBase.get_vitis_example_fullpath(examplePath), "description.json"))

        with open(example_description) as json_data:
            return json.load(json_data)

    @staticmethod
    def get_sdaccel_example_fullpath(examplePath):
        return f"{AwsFpgaTestBase.WORKSPACE}/{examplePath}/"

    @staticmethod
    def get_vitis_example_fullpath(examplePath):
        return f"{AwsFpgaTestBase.WORKSPACE}/{examplePath}/"

    @staticmethod
    def get_vitis_example_base_dir(xilinxVersion):
        return f"{AwsFpgaTestBase.WORKSPACE}/Vitis/examples/xilinx_{xilinxVersion}/"

    @staticmethod
    def fetch_sdaccel_xclbin_folder_from_s3(examplePath, rteName, xilinxVersion):
        cwd = os.getcwd()
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''

        os.chdir(AwsFpgaTestBase.get_sdaccel_example_fullpath(examplePath))
        rc = os.system("aws s3 cp s3://{}/{} {} --recursive".format(AwsFpgaTestBase.s3_bucket, AwsFpgaTestBase.get_sdaccel_example_s3_xclbin_tag(examplePath=examplePath, target="hw", rteName=rteName, xilinxVersion=xilinxVersion), AwsFpgaTestBase.get_sdaccel_xclbin_dir(examplePath=examplePath)))
        assert rc == 0, "Error while copying from s3://{}/{} to {}".format(AwsFpgaTestBase.s3_bucket, AwsFpgaTestBase.get_sdaccel_example_s3_xclbin_tag(examplePath=examplePath, target="hw", rteName=rteName, xilinxVersion=xilinxVersion), AwsFpgaTestBase.get_sdaccel_xclbin_dir(examplePath=examplePath))
        xclbin_path = AwsFpgaTestBase.get_sdaccel_xclbin_dir(examplePath=examplePath)

        logger.debug(xclbin_path)
        assert os.path.exists(
            xclbin_path
        ), f"SDAccel Example xclbin path={xclbin_path} does not exist"

        os.chdir(cwd)
        return xclbin_path

    @staticmethod
    def fetch_vitis_xclbin_folder_from_s3(examplePath, rteName, xilinxVersion):
        cwd = os.getcwd()
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''

        os.chdir(AwsFpgaTestBase.get_vitis_example_fullpath(examplePath))
        rc = os.system("aws s3 cp s3://{}/{} {} --recursive".format(AwsFpgaTestBase.s3_bucket, AwsFpgaTestBase.get_vitis_example_s3_xclbin_tag(examplePath=examplePath, target="hw", rteName=rteName, xilinxVersion=xilinxVersion), AwsFpgaTestBase.get_vitis_xclbin_dir(examplePath=examplePath)))
        assert rc == 0, "Error while copying from s3://{}/{} to {}".format(AwsFpgaTestBase.s3_bucket, AwsFpgaTestBase.get_vitis_example_s3_xclbin_tag(examplePath=examplePath, target="hw", rteName=rteName, xilinxVersion=xilinxVersion), AwsFpgaTestBase.get_vitis_xclbin_dir(examplePath=examplePath))
        xclbin_path = AwsFpgaTestBase.get_vitis_xclbin_dir(examplePath=examplePath)

        logger.debug(xclbin_path)
        assert os.path.exists(
            xclbin_path
        ), f"Vitis Example xclbin path={xclbin_path} does not exist"

        os.chdir(cwd)
        return xclbin_path

    @staticmethod
    def get_sdaccel_xclbin_file(examplePath, rteName, xilinxVersion):
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        xclbin_path = AwsFpgaTestBase.fetch_sdaccel_xclbin_folder_from_s3(examplePath, rteName, xilinxVersion)
        logger.info(
            f"Checking that a non zero size xclbin file exists in {xclbin_path}"
        )

        return AwsFpgaTestBase.assert_non_zero_file(
            os.path.join(xclbin_path, '*.hw.*.xclbin')
        )

    @staticmethod
    def get_vitis_xclbin_file(examplePath, rteName, xilinxVersion):
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''
        xclbin_path = AwsFpgaTestBase.fetch_vitis_xclbin_folder_from_s3(examplePath, rteName, xilinxVersion)
        logger.info(
            f"Checking that a non zero size xclbin file exists in {xclbin_path}"
        )

        return AwsFpgaTestBase.assert_non_zero_file(
            os.path.join(xclbin_path, "*.xclbin")
        )

    @staticmethod
    def get_sdaccel_aws_xclbin_file(examplePath, rteName, xilinxVersion):
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''

        xclbin_path = AwsFpgaTestBase.fetch_sdaccel_xclbin_folder_from_s3(examplePath, rteName, xilinxVersion)
        logger.info(
            f"Checking that a non zero size awsxclbin file exists in {xclbin_path}"
        )
        return AwsFpgaTestBase.assert_non_zero_file(
            os.path.join(xclbin_path, '*.hw.*.awsxclbin')
        )

    @staticmethod
    def get_vitis_aws_xclbin_file(examplePath, rteName, xilinxVersion):
        assert examplePath != ''
        assert rteName != ''
        assert xilinxVersion != ''

        xclbin_path = AwsFpgaTestBase.fetch_vitis_xclbin_folder_from_s3(examplePath, rteName, xilinxVersion)
        logger.info(
            f"Checking that a non zero size awsxclbin file exists in {xclbin_path}"
        )
        return AwsFpgaTestBase.assert_non_zero_file(
            os.path.join(xclbin_path, "*.awsxclbin")
        )

    @staticmethod
    def assert_afi_available(afi):
        # Check the status of the afi
        logger.info(f"Checking the status of {afi}")
        afi_state = AwsFpgaTestBase.ec2_client().describe_fpga_images(FpgaImageIds=[afi])['FpgaImages'][0]['State']['Code']
        logger.info(f"{afi} state={afi_state}")
        assert afi_state == 'available'

    @staticmethod
    def assert_afi_public(afi):
        # Check the status of the afi
        logger.info(f"Checking that {afi} is public")
        loadPermissions = AwsFpgaTestBase.ec2_client().describe_fpga_image_attribute(FpgaImageId=afi, Attribute='loadPermission')['FpgaImageAttribute']['LoadPermissions']
        logger.info(f"{afi} loadPermissions:")
        for loadPermission in loadPermissions:
            if 'UserId' in loadPermission:
                logger.info(f"  UserId={loadPermission['UserId']}")
            else:
                logger.info(f"  Group={loadPermission['Group']}")
        is_public = AwsFpgaTestBase.ec2_client().describe_fpga_images(FpgaImageIds=[afi])['FpgaImages'][0]['Public']
        logger.info(f"  Public={is_public}")
        assert is_public, "{} is not public. To make public:\n{}".format(afi,
            "aws ec2 modify-fpga-image-attribute --fpga-image-id {} --load-permission \'Add=[{{Group=all}}]\'".format(afi))

    @staticmethod
    def get_agfi_from_readme(cl):
        cl_dir = f"{AwsFpgaTestBase.WORKSPACE}/hdk/cl/examples/{cl}"
        assert os.path.exists(cl_dir)
        agfi = (
            subprocess.check_output(
                f"""cat {cl_dir}/README.md | grep \'Pre-generated AGFI ID\' | cut -d \"|\" -f 3""",
                shell=True,
            )
            .lstrip()
            .rstrip()
        )
        afi = (
            subprocess.check_output(
                f"""cat {cl_dir}/README.md | grep \'Pre-generated AFI ID\'  | cut -d \"|\" -f 3""",
                shell=True,
            )
            .lstrip()
            .rstrip()
        )
        logger.info(f"AGFI from README: {agfi}")
        logger.info(f"AFI  from README: {afi}")
        return (agfi, afi)

    @staticmethod
    def exec_as_user(as_root, command):
        return f"sudo {command}" if as_root else command

    @staticmethod
    def fpga_clear_local_image(slot, request_timeout=6000, sync_timeout=180,
            as_root=True):
        logger.info(f"Clearing FPGA slot {slot}")
        cmd = f'{AwsFpgaTestBase.exec_as_user(as_root, "fpga-clear-local-image")} -S {slot} --request-timeout {request_timeout} --sync-timeout {sync_timeout}'
        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(cmd)
        assert rc == 0, f"Clearing FPGA slot {slot} failed."

    @staticmethod
    def fpga_load_local_image(agfi, slot, request_timeout=6000,
            sync_timeout=180, as_root=True):
        logger.info(f"Loading {agfi} into slot {slot}")
        cmd = f'{AwsFpgaTestBase.exec_as_user(as_root, "fpga-load-local-image")} -S {slot} -I {agfi} --request-timeout {request_timeout} --sync-timeout {sync_timeout}'
        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(cmd)
        assert rc == 0, f"Failed to load {agfi} in slot {slot}."

    @staticmethod
    def check_fpga_afi_loaded(agfi, slot):
        fpgaLocalImage = aws_fpga_test_utils.fpga_describe_local_image(slot)
        assert (
            fpgaLocalImage.statusName == 'loaded'
        ), f"{agfi} FPGA StatusName != loaded: {fpgaLocalImage.statusName}"
        assert (
            fpgaLocalImage.statusCode == '0'
        ), f"{agfi} status code != 0: {fpgaLocalImage.statusCode}"
        assert (
            fpgaLocalImage.errorName == 'ok'
        ), f"{agfi} FPGA ErrorName != ok: {fpgaLocalImage.errorName}"
        assert (
            fpgaLocalImage.errorCode == '0'
        ), f"{agfi} ErrorCode != 0: {fpgaLocalImage.errorCode}"
        assert (
            fpgaLocalImage.agfi == agfi
        ), f"Expected {agfi}, actual {fpgaLocalImage.agfi}"
        return fpgaLocalImage

    @staticmethod
    def fpga_get_virtual_led(slot, remove_dashes=False, as_root=True):
        cmd = f'{AwsFpgaTestBase.exec_as_user(as_root, "fpga-get-virtual-led")} -S {slot}'
        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(cmd)
        assert rc == 0, f"Failed to get virtual LEDs from slot {slot}."
        value = stdout_lines[1]
        if remove_dashes:
            value = re.sub('-', '', value)
        return value

    @staticmethod
    def fpga_get_virtual_dip_switch(slot, remove_dashes=False, as_root=True):
        cmd = f'{AwsFpgaTestBase.exec_as_user(as_root, "fpga-get-virtual-dip-switch")} -S {slot}'
        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(cmd)
        assert rc == 0, f"Failed to get virtual DIP switches from slot {slot}."
        value = stdout_lines[1]
        if remove_dashes:
            value = re.sub('-', '', value)
        return value

    @staticmethod
    def fpga_set_virtual_dip_switch(value, slot, as_root=True):
        value = re.sub('-', '', value)
        cmd = f'{AwsFpgaTestBase.exec_as_user(as_root, "fpga-set-virtual-dip-switch")} -S {slot} -D {value}'
        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(cmd)
        assert (
            rc == 0
        ), f"Failed to set virtual DIP switches in slot {slot} to {value}."

    @staticmethod
    def assert_non_zero_file(filter):

        filenames = glob.glob(filter)

        # Removing .link.xclbin found in Vitis2020.1

        filenames = [x for x in filenames if ".link." not in x]

        assert filenames, f"No {filter} file found in {os.getcwd()}"
        assert (
            len(filenames) == 1
        ), f"More than 1 {filter} file found: {len(filenames)}\n{filenames}"

        filename = filenames[0]
        assert os.stat(filename).st_size != 0, f"{filename} is 0 size"
        return filename

    @staticmethod
    def get_fio_tool_root():
        return os.path.join(AwsFpgaTestBase.WORKSPACE, 'sdk/tests/fio_dma_tools')

    @staticmethod
    def get_fio_tool_install_path():
        return os.path.join(AwsFpgaTestBase.get_fio_tool_root(), 'scripts/fio_github_repo')

    @staticmethod
    def get_fio_tool_install_script():
        return os.path.join(AwsFpgaTestBase.get_fio_tool_root(), 'scripts/fio_install.py')

    @staticmethod
    def get_fio_tool_run_script():
        return os.path.join(AwsFpgaTestBase.get_fio_tool_root(), 'scripts/fio')

    @staticmethod
    def get_fio_verify_script(driver='xdma'):
        return os.path.join(
            AwsFpgaTestBase.get_fio_tool_root(),
            f"scripts/{driver}_4-ch_4-1M_verify.fio",
        )

    @staticmethod
    def get_fio_read_benchmark_script(driver='xdma'):
        return os.path.join(
            AwsFpgaTestBase.get_fio_tool_root(),
            f"scripts/{driver}_4-ch_4-1M_read.fio",
        )

    @staticmethod
    def get_fio_write_benchmark_script(driver='xdma'):
        return os.path.join(
            AwsFpgaTestBase.get_fio_tool_root(),
            f"scripts/{driver}_4-ch_4-1M_write.fio",
        )

    @staticmethod
    def setup_fio_tools():
        '''Install and setup fio tools'''
        # If downloaded repo already, exists, delete it so we can fetch again
        if os.path.exists(AwsFpgaTestBase.get_fio_tool_install_path()):
            AwsFpgaTestBase.run_cmd(
                f"rm -rf {AwsFpgaTestBase.get_fio_tool_install_path()}", echo=True
            )

        logger.info("Installing fio_dma_tools")

        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(
            f"python {AwsFpgaTestBase.get_fio_tool_install_script()} {AwsFpgaTestBase.get_fio_tool_install_path()}",
            echo=True,
        )
        assert rc == 0
        assert os.path.exists(f"{AwsFpgaTestBase.get_fio_tool_run_script()}")

        (rc, stdout_lines, stderr_lines) = AwsFpgaTestBase.run_cmd(
            f"chmod +x {AwsFpgaTestBase.get_fio_tool_run_script()}"
        )
        assert rc == 0
