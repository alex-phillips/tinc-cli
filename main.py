#!/usr/bin/env python

from subprocess import call
import argparse
import yaml
import os
import sys
import requests
import stat
import re

parser = argparse.ArgumentParser(usage="main.py <network> <hostname>")
parser.add_argument("network", help="Network to configure")
parser.add_argument("hostname", help="Machine hostname")
parser.add_argument(
    "--config",
    help="The location of the configuration file",
    default=os.path.expanduser("~/.tinc/config"),
)
args = parser.parse_args()

args.config = args.config.rstrip('/')

try:
    with open(args.config, 'r') as ymlfile:
        config = yaml.load(ymlfile)
except:
    if not os.path.exists(os.path.dirname(args.config)):
        os.makedirs(os.path.dirname(args.config))
    print("Please edit the configuration file: %s" % args.config)
    sys.exit(2)

net_config = config['networks'][args.network]
host_config = net_config['hosts'][args.hostname]

net_location = net_config['dir'] if 'dir' in net_config else '/etc/tinc/{}'.format(
    args.network)

if not os.path.exists(net_location):
    os.makedirs(net_location)

print("Creating up/down scripts...")
with open("{}/tinc-up".format(net_location), "w") as handle:
    handle.write("""ip link set $INTERFACE up
ip addr add {host_subnet} dev $INTERFACE
ip route add {route} dev $INTERFACE
""".format(host_subnet=host_config['subnet'], route=net_config['route']))
st = os.stat("{}/tinc-up".format(net_location))
os.chmod("{}/tinc-up".format(net_location), st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

with open("{}/tinc-down".format(net_location), "w") as handle:
    handle.write("""ip route del {route} dev $INTERFACE
ip addr del {host_subnet} dev $INTERFACE
ip link set $INTERFACE down
""".format(host_subnet=host_config['subnet'], route=net_config['route']))
st = os.stat("{}/tinc-down".format(net_location))
os.chmod("{}/tinc-down".format(net_location), st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

host_list = []
for hostname in net_config['hosts']:
    host_list.append("ConnectTo = {}".format(hostname))
host_list = "\n".join(host_list)

print("Creating tinc.conf...")
with open("{}/tinc.conf".format(net_location), "w") as handle:
    handle.write("""Name = {hostname}
Interface = {interface}
AddressFamily = {address_family}
{host_list}
""".format(hostname=args.hostname, interface=net_config['interface'], address_family=net_config['address_family'], host_list=host_list))

if not os.path.exists("{}/hosts".format(net_location)):
    os.makedirs("{}/hosts".format(net_location))

if 'hosts_repo' in net_config:
    print("Attempting to download existing host keys...")
    for hostname in net_config['hosts']:
        if hostname == args.hostname:
            continue

        host_key_loc = "{}/hosts/{}".format(net_location, hostname)
        if os.path.exists(host_key_loc):
            print("Key file for {} exists. Skipping.".format(hostname))
            continue

        # Point to the raw files in the repo
        net_config['hosts_repo'] = "{}/master".format(net_config['hosts_repo'].replace('github.com', 'raw.githubusercontent.com').rstrip('/'))
        response = requests.get("{}/{}".format(net_config['hosts_repo'], hostname))
        if not response.status_code == 200:
            print("Host {} key doesn't exist. Skipping.".format(hostname))
            continue

        with open(host_key_loc, 'w') as handle:
            handle.write(str(response.content))

host_key = "{}/hosts/{}".format(net_location, args.hostname)
if not os.path.exists(host_key):
    cmd = 'tincd -c {} -n {} -K4096'.format(net_location, args.network)
    print("Executing command: {}".format(cmd))
    call(cmd.split(' '))
    with open(host_key, 'r') as original:
        data = [original.read()]

    if 'subnet' in host_config:
        data.insert(0, "Subnet = {}".format(host_config['subnet']))
    if 'address' in host_config:
        data.insert(0, "Address = {}".format(host_config['address']))
    with open(host_key, 'w') as new:
        new.write("\n".join(data))
else:
    with open(host_key, 'r') as original:
        data = original.read()

    if 'address' in host_config:
        if re.search('^Address = ', data):
            data = re.sub(r'^Address = .+', "Address = {}".format(host_config['address']), data)
        else:
            data = "Address = {}\n{}".format(host_config['address'], data)
    if 'subnet' in host_config:
        if re.search('^Subnet = ', data):
            data = re.sub(r'^Subnet = .+', "Subnet = {}".format(host_config['subnet']), data)
        else:
            data = "Subnet = {}\n{}".format(host_config['subnet'], data)

    with open(host_key, 'w') as handle:
        handle.write(data)

print("Done.")
