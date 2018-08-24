#!/usr/bin/env python

import argparse
import yaml
import os
import sys

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

with open("{}/tinc-down".format(net_location), "w") as handle:
    handle.write("""ip route del {route} dev $INTERFACE
ip addr del {host_subnet} dev $INTERFACE
ip link set $INTERFACE down
""".format(host_subnet=host_config['subnet'], route=net_config['route']))

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

print("Done.")
