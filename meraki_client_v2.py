#!/usr/bin/python3

READ_ME = """
=== PREREQUISITES ===
Run in Python 3
 
Install both requests & Meraki Dashboard API Python modules:
pip[3] install --upgrade aiohttp
pip[3] install --upgrade requests
pip[3] install --upgrade meraki
pip[3] install --upgrade pyyaml 
=== DESCRIPTION ===
Exports CSV of org-wide client data.
Prerequisites: 1) enable detailed traffic analysis & report specific hostnames
on the Network-wide > General page; 2) ensure org has PII endpoints' API calls

"""

from aiohttp import ClientSession, TCPConnector
import asyncio
import csv
from datetime import datetime
import json
import sys
import os
import time
import meraki
import yaml

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f.read())
    API_KEY = config.get("API_KEY")
    ORG_ID = config.get("ORG_ID")

# Initialize the dashboard API
dashboard = meraki.DashboardAPI(api_key=API_KEY, 
        print_console=False,
        output_log=True,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='logs',)

def print_help():
    lines = READ_ME.split("\n")
    for line in lines:
        print("# {0}".format(line))


async def fetch(session, url, headers):
    while True:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.text()
            else:
                # print(response.status)
                time.sleep(1)


async def post(session, url, data, headers):
    async with session.post(url, data=data, headers=headers) as response:
        return await response.text()


# Asynchronous function to get all clients of a list of Meraki serials


async def get_clients_from_serials(loop, session, serials, api_key, arg_time):
    # Limit to max of 30 days
    if arg_time > 2592000:
        arg_time = 2592000

    tasks = []
    for serial in serials:
        task = asyncio.ensure_future(
            fetch(
                session,
                "https://api.meraki.com/api/v0/devices/{0}/clients?timespan={1}".format(
                    serial, arg_time
                ),
                {"X-Cisco-Meraki-API-Key": api_key, "Content-Type": "application/json"},
            )
        )
        tasks.append(task)
    responses = await asyncio.gather(*tasks)
    return responses


# Asynchronous function to get all client data from a list of identifiers


async def get_client_data_from_identifiers(loop, session, identifiers, api_key, net_id):
    tasks = []
    for identifier in identifiers:
        task = asyncio.ensure_future(
            fetch(
                session,
                "https://api.meraki.com/api/v0/networks/{0}/clients/{1}".format(
                    net_id, identifier
                ),
                {"X-Cisco-Meraki-API-Key": api_key, "Content-Type": "application/json"},
            )
        )
        tasks.append(task)
    responses = await asyncio.gather(*tasks)
    return responses


# Asynchronous function to write network's clients' data to CSV


async def output_clients_info(
    loop,
    session,
    search_identifiers,
    devices,
    device_macs,
    api_key,
    network,
    mr_clients_usage,
    ms_clients_usage,
    mx_clients_usage,
    csv_writer,
):
    all_data = await get_client_data_from_identifiers(
        loop, session, search_identifiers.keys(), api_key, network["id"]
    )
    for data in all_data:
        data = json.loads(data)

        # Format certain parameters for better readability & more informative output
        if data:
            identifier = data["id"]
            data["network"] = network["name"]
            data["networkId"] = network["id"]
            data["mdnsName"] = search_identifiers[identifier]["mdnsName"]
            data["dhcpHostname"] = search_identifiers[identifier]["dhcpHostname"]
            data["firstSeen"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime(data["firstSeen"])
            )
            data["lastSeen"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime(data["lastSeen"])
            )

            # Usage data from perspective of Meraki devices
            if identifier in mr_clients_usage:
                data["sent"] = round(mr_clients_usage[identifier]["sent"])
                data["recv"] = round(mr_clients_usage[identifier]["recv"])
            elif identifier in ms_clients_usage:
                data["sent"] = round(ms_clients_usage[identifier]["sent"])
                data["recv"] = round(ms_clients_usage[identifier]["recv"])
            else:
                data["sent"] = round(mx_clients_usage[identifier]["sent"])
                data["recv"] = round(mx_clients_usage[identifier]["recv"])

            # Add client's recently (last) connected to Meraki device's serial, name, & model
            recent_device_mac = data["recentDeviceMac"]
            if recent_device_mac:
                recent_device = devices[device_macs.index(recent_device_mac)]
                data["recentDeviceSerial"] = recent_device["serial"]
                data["recentDeviceName"] = recent_device["name"]
                data["recentDeviceModel"] = recent_device["model"]

            # Write line to CSV output file
            csv_writer.writerow(data)


# Main asynchronous function


async def get_org_clients(loop, api_key, org_id, arg_time, csv_writer):
    # Obtain list of org's
    orgs = dashboard.organizations.getOrganizations()
    print(f"status: found the following orgs with this API key")
    for org in orgs:
        print(org.get("id"), org.get("name"))
    # networks = meraki.getnetworklist(api_key, org_id, suppressprint=True)
    networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id,  suppressprint=True)
    conn = TCPConnector(limit=4)
    async with ClientSession(connector=conn, loop=loop) as session:

        # Iterate through all networks
        for network in networks:
            # devices = meraki.getnetworkdevices(
            #     api_key, network["id"], suppressprint=True
            # )
            devices = dashboard.networks.getNetworkDevices(networkId=network["id"])
            # Create lists of appliance, switch, & wireless devices
            mx_devices = []
            ms_devices = []
            mr_devices = []
            for x in range(len(devices)):
                device = devices[x]
                if device["model"][:2] in ("MX", "vM", "Z1", "Z3"):
                    mx_devices.append(device)
                elif device["model"][:2] == "MS":
                    ms_devices.append(device)
                elif device["model"][:2] == "MR":
                    mr_devices.append(device)

            # For Meraki devices, filter out later since they are strictly speaking not client devices
            device_macs = [device["mac"] for device in devices]

            # Obtain list of actual clients for appliance, switch, & wireless devices
            mx_serials = [device["serial"] for device in mx_devices]
            mx_serial_clients = await get_clients_from_serials(
                loop, session, mx_serials, api_key, arg_time
            )
            mx_device_clients = [json.loads(output) for output in mx_serial_clients]
            mx_clients = [
                client for mx_device in mx_device_clients for client in mx_device
            ]

            ms_serials = [device["serial"] for device in ms_devices]
            ms_serial_clients = await get_clients_from_serials(
                loop, session, ms_serials, api_key, arg_time
            )
            ms_device_clients = [json.loads(output) for output in ms_serial_clients]
            ms_clients = [
                client for ms_device in ms_device_clients for client in ms_device
            ]

            mr_serials = [device["serial"] for device in mr_devices]
            mr_serial_clients = await get_clients_from_serials(
                loop, session, mr_serials, api_key, arg_time
            )
            mr_device_clients = [json.loads(output) for output in mr_serial_clients]
            mr_clients = [
                client for mr_device in mr_device_clients for client in mr_device
            ]

            # Build dicts for usage metrics; each client's usage is the aggregate across all other devices of the same family
            mx_clients_usage = {}
            for client in mx_clients:
                identifier = client["id"]
                if identifier in mx_clients_usage:
                    mx_clients_usage[identifier]["sent"] += client["usage"]["sent"]
                    mx_clients_usage[identifier]["recv"] += client["usage"]["recv"]
                else:
                    mx_clients_usage[identifier] = client["usage"]
            ms_clients_usage = {}
            for client in ms_clients:
                identifier = client["id"]
                if identifier in ms_clients_usage:
                    ms_clients_usage[identifier]["sent"] += client["usage"]["sent"]
                    ms_clients_usage[identifier]["recv"] += client["usage"]["recv"]
                else:
                    ms_clients_usage[identifier] = client["usage"]
            mr_clients_usage = {}
            for client in mr_clients:
                identifier = client["id"]
                if identifier in mr_clients_usage:
                    mr_clients_usage[identifier]["sent"] += client["usage"]["sent"]
                    mr_clients_usage[identifier]["recv"] += client["usage"]["recv"]
                else:
                    mr_clients_usage[identifier] = client["usage"]

            # Iterate through clients' data & output to CSV file
            all_clients = mx_clients + ms_clients + mr_clients
            unique_identifiers = set([client["id"] for client in all_clients])
            search_identifiers = {}
            for client in all_clients:
                identifier = client["id"]
                if (
                    identifier in unique_identifiers
                    and client["mac"] not in device_macs
                ):
                    unique_identifiers.discard(identifier)
                    search_identifiers[identifier] = client
                    if client["description"]:
                        print(
                            "Found client {0} on network {1}".format(
                                client["description"], network["name"]
                            )
                        )
                    else:
                        print("Found client on network {0}".format(network["name"]))
            await output_clients_info(
                loop,
                session,
                search_identifiers,
                devices,
                device_macs,
                api_key,
                network,
                mr_clients_usage,
                ms_clients_usage,
                mx_clients_usage,
                csv_writer,
            )


def main(API_KEY, ORG_ID, arg_time):
    # Set default values for command line arguments
    api_key = API_KEY
    org_id = ORG_ID

    # Check if all required parameters have been input
    if api_key == None or org_id == None:
        print(f"status: Looks like we are missing either your API key or your ORG_ID.  Please supply those int he config.yaml file.")
        sys.exit(2)
    if arg_time == None:
        arg_time = 86400
    elif arg_time > 2592000:
        arg_time = 2592000

    # ensure arg_time is an integer
    arg_time = int(arg_time)

    # Set the CSV output file and write the header row
    timenow = "{:%Y%m%d_%H%M%S}".format(datetime.now())
    file_name = "org_{0}_clients_{1}.csv".format(org_id, timenow)
    output_file = open(file_name, mode="w", newline="\n")
    field_names = [
        "network",
        "networkId",
        "id",
        "description",
        "mdnsName",
        "dhcpHostname",
        "mac",
        "ip",
        "ip6",
        "sent",
        "recv",
        "firstSeen",
        "lastSeen",
        "manufacturer",
        "os",
        "user",
        "vlan",
        "switchport",
        "ssid",
        "wirelessCapabilities",
        "smInstalled",
        "recentDeviceMac",
        "recentDeviceSerial",
        "recentDeviceName",
        "recentDeviceModel",
        "clientVpnConnections",
        "lldp",
        "cdp",
        "status"
    ]
    csv_writer = csv.DictWriter(output_file, fieldnames=field_names, restval="")
    csv_writer.writeheader()

    # Run asynchronously
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        get_org_clients(loop, api_key, org_id, arg_time, csv_writer)
    )

    output_file.close()
    print("Data written to file {0}".format(file_name))


if __name__ == "__main__":


    main(API_KEY=API_KEY, ORG_ID=ORG_ID, arg_time=None)
