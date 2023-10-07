#!/usr/bin/env python

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
import os
import sys
import platform
import glob
import argparse
import logging

dpdk_git = "https://github.com/DPDK/dpdk.git"

# Use a SHA that is "known good" for SPP testing
dpdk_ver = "v20.02"

# Patch file directory
patches_dir = "../patches/spp-dpdk/master"

# DPDK make config target
make_tgt = "x86_64-native-linuxapp-gcc"

# Logger
logger = logging.getLogger('logger')

def print_success(scripts_path, install_path):
    print("")
    print("DPDK installation and build complete!")
    print("A simple loopback test may be run via the following steps:")
    print("  sudo fpga-load-local-image -S 0 -I <SDE loopback CL AGFI>")
    print(f"  sudo {scripts_path}/virtual_ethernet_setup.py {install_path}/dpdk 0")
    print(f"  cd {install_path}/dpdk")
    print(
        f"  sudo ./{make_tgt}/app/testpmd -l 0-1  -- --port-topology=loop --auto-start --tx-first --stats-period=3"
    )

def cmd_exec(cmd):
    # Execute the cmd, check the return and exit on failures
    ret = os.system(cmd)
    if ret != 0:
        logger.error("cmd='%s' failed with ret=%d, exiting" % (cmd, ret))
        sys.exit(1)

def install_dpdk_dep():
    distro = platform.linux_distribution()
    if (distro[0] == "Ubuntu"):
        cmd_exec("apt -y install libnuma-dev")
        cmd_exec("apt -y install libpcap-dev")
    else:
        cmd_exec("yum -y install numactl-devel.x86_64")
        cmd_exec("yum -y install libpcap-devel") 

def install_dpdk(install_path):
    logger.debug(f"install_dpdk: install_path={install_path}")

    if os.path.exists(install_path):
        # Allow the user to remove an already existing install_path
        logger.error(f"install_path={install_path} allready exists.")
        logger.error("Please specify a different directory or remove the existing directory, exiting")
        sys.exit(1)

    # Install DPDK dependencies
    install_dpdk_dep()

    # Stash away the current working directory
    cwd = os.getcwd()
    scripts_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    logger.debug(f"scripts directory path is {scripts_path}")

    # Make the install_path directory
    cmd_exec(f"mkdir {install_path}")

    # Construct the path to the git patch files
    patches_path = f"{scripts_path}/{patches_dir}"
    logger.info(f"Patches will be installed from {patches_path}")

    # Read in the patch filenames
    patchfiles = []
    for patchfile in sorted(glob.iglob(f"{patches_path}/000*.patch")):
        logger.debug(f"found patchfile={patchfile}")
        patchfiles.append(os.path.abspath(patchfile))

    # cd to the install_path directory
    os.chdir(f"{install_path}")

    # Clone the DPDK repo
    logger.info(f"Cloning {dpdk_ver} version of {dpdk_git} into {install_path}")
    cmd_exec(f"git clone -b {dpdk_ver} {dpdk_git}")

    # cd to the dpdk directory 
    os.chdir("dpdk")

    # Check that the patches can be applied
    # for patchfile in patchfiles:
    #    logger.debug("Checking git apply patch for patchfile=%s" % patchfile)
    #    cmd_exec("git apply --check %s" % (patchfile))

    # Apply the patches
    for patchfile in patchfiles:
        logger.info(f"Applying patch for patchfile={patchfile}")
        cmd_exec(f"git am {patchfile}")

    # Configure the DPDK build
    cmd_exec(f"make install T={make_tgt}")

    # cd back to the original directory
    os.chdir(f"{cwd}")

    # Print a success message
    print_success(scripts_path, install_path)

def main():
    parser = argparse.ArgumentParser(
        description="Installs the DPDK (master) and applies DPDK SPP PMD related patches.")
    parser.add_argument('install_path', metavar='INSTALL_DIR', type=str,
        help = "specify the full installation directory path")
    parser.add_argument('--debug', action='store_true', required=False,
        help='Enable debug messages')
    args = parser.parse_args()

    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging_format = '%(levelname)s:%(asctime)s: %(message)s'

    logger.setLevel(logging_level)

    fh = logging.StreamHandler()

    fh.setLevel(logging_level)
    formatter = logging.Formatter(logging_format)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    install_dpdk(args.install_path)

if __name__ == '__main__':
    main()
