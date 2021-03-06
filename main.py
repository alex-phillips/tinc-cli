#!/usr/bin/env python

from subprocess import call
import argparse
import yaml
import os
import sys
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
parser.add_argument(
    "--output",
    help="Output directory for the config files",
    default=None,
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
if args.output is not None:
    net_location = args.output

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

if not os.path.exists("{}/hosts".format(net_location)):
    os.makedirs("{}/hosts".format(net_location))

host_list = []
for hostname in net_config['hosts']:
    host_list.append("ConnectTo = {}".format(hostname))

    if hostname != args.hostname:
        print("{} - {}".format(hostname, args.hostname))
        remote_host_key = "{}/hosts/{}".format(net_location, hostname)
        if not os.path.exists(remote_host_key):
            print("Creating remote host file at hosts/{}".format(hostname))
            remote_host_conf = []
            if 'address' in net_config['hosts'][hostname]:
                remote_host_conf.append("Address = {}".format(net_config['hosts'][hostname]['address']))
            if 'subnet' in net_config['hosts'][hostname]:
                remote_host_conf.append("Subnet = {}".format(net_config['hosts'][hostname]['subnet']))
            if 'public_key' in net_config['hosts'][hostname]:
                remote_host_conf.append("")
                remote_host_conf.append("{}".format(net_config['hosts'][hostname]['public_key']))
            with open("{}/hosts/{}".format(net_location, hostname), "w") as handle:
                handle.write("\n".join(remote_host_conf))

host_list = "\n".join(host_list)

print("Creating tinc.conf...")
with open("{}/tinc.conf".format(net_location), "w") as handle:
    handle.write("""Name = {hostname}
Interface = {interface}
AddressFamily = {address_family}
{host_list}
""".format(hostname=args.hostname, interface=net_config['interface'], address_family=net_config['address_family'], host_list=host_list))

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
        if re.search('Address = ', data):
            data = re.sub(r'^Address = .+', "Address = {}".format(host_config['address']), data)
        else:
            data = "Address = {}\n{}".format(host_config['address'], data)
    if 'subnet' in host_config:
        if re.search('Subnet = ', data):
            data = re.sub(r'^Subnet = .+', "Subnet = {}".format(host_config['subnet']), data)
        else:
            data = "Subnet = {}\n{}".format(host_config['subnet'], data)

    with open(host_key, 'w') as handle:
        handle.write(data)

print("Done.")
