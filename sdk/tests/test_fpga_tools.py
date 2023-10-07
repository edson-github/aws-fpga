#! /user/bin/env python2.7

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

from __future__ import print_function
import logging
import os
from os.path import dirname, realpath
import pytest
import re
import subprocess
import sys
import time
import traceback
import ctypes
import multiprocessing.dummy
try:
    import aws_fpga_test_utils
    from aws_fpga_test_utils.AwsFpgaTestBase import AwsFpgaTestBase
    import aws_fpga_utils
    from base_sdk import BaseSdkTools
except ImportError as e:
    traceback.print_tb(sys.exc_info()[2])
    print(f"error: {sys.exc_info()[1]}\nMake sure to source sdk_setup.sh")
    sys.exit(1)

logger = aws_fpga_utils.get_logger(__name__)

class TestFpgaTools(BaseSdkTools):
    '''
    Pytest test class.

    NOTE: Cannot have an __init__ method.

    Test FPGA AFI Management tools described in ../userspace/fpga_mgmt_tools/README.md
    '''

    @pytest.mark.flaky(reruns=2, reruns_delay=5)
    def test_describe_local_image_slots(self):
        for slot in range(self.num_slots):
            self.fpga_clear_local_image(slot)

        logger.info("PCI devices:\n{}".format("\n".join(self.list_pci_devices())))

        logger.info("verify that the slots are in order")
        assert self.slot2device.values() == sorted(self.slot2device.values())

        (rc, stdout, stderr) = self.run_cmd("sudo fpga-describe-local-image-slots", echo=True)
        assert len(stdout) == self.num_slots + 1
        assert len(stderr) == 1
        for slot in range(self.num_slots):
            assert (
                stdout[slot]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            ), f"slot={slot}"

        # Test -H (display headers)
        (rc, stdout, stderr) = self.run_cmd("sudo fpga-describe-local-image-slots -H", echo=True)
        assert len(stdout) == self.num_slots * 2 + 1
        assert len(stderr) == 1
        for slot in range(self.num_slots):
            assert (
                stdout[slot * 2]
                == 'Type  FpgaImageSlot  VendorId    DeviceId    DBDF'
            ), f"slot={slot}"
            assert (
                stdout[slot * 2 + 1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            ), f"slot={slot}"

        # Test -M (Show the mbox physical function in the list of devices.)
        (rc, stdout, stderr) = self.run_cmd("sudo fpga-describe-local-image-slots -M", echo=True)
        assert len(stdout) == self.num_slots * 2 + 1
        assert len(stderr) == 1
        for slot in range(self.num_slots):
            assert (
                stdout[slot * 2]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            ), "slot={}\n{}".format(slot, "\n".join(stdout))
            assert (
                stdout[slot * 2 + 1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1041      {self.slot2mbox_device[slot]}'
            ), "slot={}\n{}".format(slot, "\n".join(stdout))

        # Test -H and -M (Show the mbox physical function in the list of devices.)
        (rc, stdout, stderr) = self.run_cmd("sudo fpga-describe-local-image-slots -H -M", echo=True)
        assert len(stdout) == self.num_slots * 3 + 1
        assert len(stderr) == 1
        for slot in range(self.num_slots):
            assert stdout[slot * 3 + 0] == 'Type  FpgaImageSlot  VendorId    DeviceId    DBDF'
            assert (
                stdout[slot * 3 + 1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            ), "slot={}\n{}".format(slot, "\n".join(stdout))
            assert (
                stdout[slot * 3 + 2]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1041      {self.slot2mbox_device[slot]}'
            ), "slot={}\n{}".format(slot, "\n".join(stdout))

    @pytest.mark.flaky(reruns=2, reruns_delay=5)
    def test_describe_local_image(self):
        for slot in range(self.num_slots):
            self.fpga_clear_local_image(slot)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-describe-local-image -S {slot}", echo=True
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
            ), "slot={}\n{}".format(slot, "\n".join(stdout))
            assert (
                stdout[1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            ), "slot={}\n{}".format(slot, "\n".join(stdout))

            # Test -H
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-describe-local-image -H -S {slot}", echo=True
            )
            assert len(stdout) == 5
            assert len(stderr) == 1
            assert stdout[0] == 'Type  FpgaImageSlot  FpgaImageId             StatusName    StatusCode   ErrorName    ErrorCode   ShVersion'
            assert (
                stdout[1]
                == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
            )
            assert stdout[2] == 'Type  FpgaImageSlot  VendorId    DeviceId    DBDF'
            assert (
                stdout[3]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            )

            # Test -M (Return FPGA image hardware metrics.)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-describe-local-image -M -S {slot}", echo=True
            )
            assert len(stdout) == 59
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
            )
            assert (
                stdout[1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            )
            assert stdout[2] == 'sdacl-slave-timeout=0'
            assert stdout[51] == 'Clock Group C Frequency (Mhz)'
            assert stdout[52] == '0  0  '
            assert stdout[-2].startswith('Cached agfis:')

            # Test -C (Return FPGA image hardware metrics (clear on read).)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-describe-local-image -C -M -S {slot}", echo=True
            )
            assert len(stdout) == 59
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
            )
            assert (
                stdout[1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            )
            assert stdout[2] == 'sdacl-slave-timeout=0'
            assert stdout[51] == 'Clock Group C Frequency (Mhz)'
            assert stdout[52] == '0  0  '

    @pytest.mark.flaky(reruns=2, reruns_delay=5)
    def test_load_local_image(self):
        for slot in range(self.num_slots):
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-load-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -I {self.cl_hello_world_agfi}",
                echo=True,
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f"AFI          {slot}       {self.cl_hello_world_agfi}  loaded            0        ok               0       {self.shell_version}"
            )
            assert (
                stdout[1]
                == f'AFIDEVICE    {slot}       0x1d0f      0xf000      {self.slot2device[slot]}'
            )
            self.fpga_clear_local_image(slot)

            # -A
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-load-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -I {self.cl_hello_world_agfi} -A",
                echo=True,
            )
            assert len(stdout) == 1
            assert len(stderr) == 1
            # Poll for it to be loaded
            while True:
                fpgaLocalImage = aws_fpga_test_utils.fpga_describe_local_image(slot)
                logger.info(f'status={fpgaLocalImage.statusName}')
                if fpgaLocalImage.statusName != 'loaded':
                    time.sleep(1)
                    continue
                (rc, stdout, stderr) = self.run_cmd(
                    f"sudo fpga-describe-local-image -S {slot}", echo=True
                )
                assert len(stdout) == 3
                assert len(stderr) == 1
                assert (
                    stdout[0]
                    == f"AFI          {slot}       {self.cl_hello_world_agfi}  loaded            0        ok               0       {self.shell_version}"
                )
                assert (
                    stdout[1]
                    == f'AFIDEVICE    {slot}       0x1d0f      0xf000      {self.slot2device[slot]}'
                )
                break
            self.fpga_clear_local_image(slot)

            # -H
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-load-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -I {self.cl_hello_world_agfi} -H",
                echo=True,
            )
            assert len(stdout) == 5
            assert len(stderr) == 1
            assert stdout[0] == 'Type  FpgaImageSlot  FpgaImageId             StatusName    StatusCode   ErrorName    ErrorCode   ShVersion'
            assert (
                stdout[1]
                == f"AFI          {slot}       {self.cl_hello_world_agfi}  loaded            0        ok               0       {self.shell_version}"
            )
            assert stdout[2] == 'Type  FpgaImageSlot  VendorId    DeviceId    DBDF'
            assert (
                stdout[3]
                == f'AFIDEVICE    {slot}       0x1d0f      0xf000      {self.slot2device[slot]}'
            )
            self.fpga_clear_local_image(slot)

            # -F
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-load-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -I {self.cl_hello_world_agfi} -F",
                echo=True,
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f"AFI          {slot}       {self.cl_hello_world_agfi}  loaded            0        ok               0       {self.shell_version}"
            )
            assert (
                stdout[1]
                == f'AFIDEVICE    {slot}       0x1d0f      0xf000      {self.slot2device[slot]}'
            )
            self.fpga_clear_local_image(slot)

    @pytest.mark.flaky(reruns=2, reruns_delay=5)
    def test_clear_local_image(self):
        for slot in range(self.num_slots):
            # Test clearing already cleared
            self.fpga_clear_local_image(slot)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-clear-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot}",
                echo=True,
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
            )
            assert (
                stdout[1]
                == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
            )

            # -A (async)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-clear-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -A",
                echo=True,
            )
            assert len(stdout) == 1
            assert len(stderr) == 1

            # Clear again immediately. It should fail because busy
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-clear-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -A",
                echo=True,
                check=False,
            )
            assert rc != 0
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert stdout[0] == 'Error: (3) busy'

            # Poll for cleared
            while True:
                fpgaLocalImage = aws_fpga_test_utils.fpga_describe_local_image(slot)
                logger.info(f'status={fpgaLocalImage.statusName}')
                if fpgaLocalImage.statusName != 'cleared':
                    time.sleep(1)
                    continue
                (rc, stdout, stderr) = self.run_cmd(
                    f"sudo fpga-describe-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot}",
                    echo=True,
                )
                assert len(stdout) == 3
                assert len(stderr) == 1
                assert (
                    stdout[0]
                    == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
                )
                assert (
                    stdout[1]
                    == f'AFIDEVICE    {slot}       0x1d0f      0x1042      {self.slot2device[slot]}'
                )
                break

    def test_afi_caching(self):
        for slot in range(self.num_slots):
            self.fpga_clear_local_image(slot)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-load-local-image --request-timeout {self.DEFAULT_REQUEST_TIMEOUT} -S {slot} -I {self.cl_dram_dma_agfi} -P",
                echo=True,
            )
            assert rc == 0
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-describe-local-image -M -S {slot}", echo=True
            )
            assert re.match(self.cl_dram_dma_agfi, stdout[-2].strip())

    @pytest.mark.skip(reason="No way to test right now.")
    def test_start_virtual_jtag(self):
        assert False
        # This doesn't return until a ctrl-c is sent to the process.
        for slot in range(self.num_slots):
            # Start it on an empty slot
            self.fpga_clear_local_image(slot)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-start-virtual-jtag -S {slot}", echo=True
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'AFI          {slot}       none                    cleared           1        ok               0       {self.shell_version}'
            )
            assert stdout[1] == 'AFIDEVICE    {}       0x1d0f      0x1042      {}'.format(self.slot2device[slot])

    @pytest.mark.flaky(reruns=2, reruns_delay=5)
    def test_get_virtual_led(self):
        # This is tested in the cl_hello_world example
        for slot in range(self.num_slots):
            # Start it on an empty slot
            self.fpga_clear_local_image(slot)
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-get-virtual-led -S {slot}", echo=True
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert stdout[0] == f'FPGA slot id {slot} have the following Virtual LED:'
            assert re.match('[01]{4}-[01]{4}-[01]{4}-[01]{4}', stdout[1])

    @pytest.mark.flaky(reruns=2, reruns_delay=5)
    def test_virtual_dip_switch(self):
        for slot in range(self.num_slots):
            # Start it on an empty slot
            self.fpga_clear_local_image(slot)
            # Set to a known value
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-set-virtual-dip-switch -S {slot} -D 0000000000000000",
                echo=True,
            )
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-get-virtual-dip-switch -S {slot}", echo=True
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'FPGA slot id {slot} has the following Virtual DIP Switches:'
            )
            assert stdout[1] == '0000-0000-0000-0000'

            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-set-virtual-dip-switch -S {slot} -D 1111111111111111",
                echo=True,
            )
            (rc, stdout, stderr) = self.run_cmd(
                f"sudo fpga-get-virtual-dip-switch -S {slot}", echo=True
            )
            assert len(stdout) == 3
            assert len(stderr) == 1
            assert (
                stdout[0]
                == f'FPGA slot id {slot} has the following Virtual DIP Switches:'
            )
            assert stdout[1] == '1111-1111-1111-1111'

    # Add extra delay in case we have a lot of slot loads
    @pytest.mark.flaky(reruns=2, reruns_delay=10)
    def test_parallel_slot_loads(self):
        def run_slot(slot):
            for afi in [self.cl_dram_dma_agfi, self.cl_hello_world_agfi, self.cl_dram_dma_agfi]:
                (rc, stdout, stderr) = self.run_cmd("sudo fpga-load-local-image -HS{} -I {}".format(slot, afi))
                assert rc == 0
                logger.info(stdout)


        slots = range(self.num_slots)
        pool = multiprocessing.dummy.Pool(len(slots))
        pool.map(run_slot, slots)
