import csv
import sys
from datetime import datetime
import os
import yaml
import meraki

# Read in global configuration from config.yaml file
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f.read())
    API_KEY = config.get("API_KEY")
    ORG_ID = config.get("ORG_ID")

# Instantiate a Meraki dashboard API session
dashboard = meraki.DashboardAPI(
    api_key=API_KEY,
    # base_url='https://api-mp.meraki.com/api/v1/',
    output_log=True,
    log_file_prefix=os.path.basename(__file__)[:-3],
    log_path='logs',
    print_console=False
)

def get_mode():
    try:
        arg = sys.argv[1]
    except Exception as e:
        print(f"status: mode not specified.  Defaulting to `DEV` mode  ")
        return "DEV"
    if arg == "PROD":
        return "PROD"
    else:
        return "DEV"

def write_csv(org, data):
    # Write to file
    MODE = get_mode()
    todays_date = f'{datetime.now():%Y-%m-%d_%H_%M}'
    file_name = f"{org}-switchports-{todays_date}-{MODE}.csv"
    output_file = open(f'{file_name}', mode='w', newline='\n')
    field_names = data[0].keys()
    csv_writer = csv.DictWriter(output_file, field_names, delimiter=',', quotechar='"',
                                quoting=csv.QUOTE_ALL)
    csv_writer.writeheader()
    csv_writer.writerows(data)
    output_file.close()
    print(f'status: found {len(data)} ports matching `PRINTER`')
    print(f"status: writing file {file_name}")


def update_ports(switch):
    MODE = get_mode()
    ports = dashboard.switch.getDeviceSwitchPorts(switch['serial'])
    all_port_responses = []
    
    for port in ports:
        if port["name"] == "PRINTER":
            print(f"status: PRINTER found on port {port['portId']} -- reading...")

            # desired config changes to ports
            port["accessPolicyType"] = "Open"
            port["linkNegotiation"] = "100 Megabit full duplex (forced)"
            port["type"] = "access"

            if MODE == "PROD":
                response = dashboard.switch.updateDeviceSwitchPort(
                    serial=switch['serial'],
                    **port # all other port parameters including those updated on the lines above
                    )
                print(f"status: PRINTER found on port {port['portId']} -- updating...")
            else:
                # document existing port configurations
                response = port
            
            response_details = {}
            response_details["switch_name"] = switch["name"]
            response_details["switch_serial"] = switch["serial"]
            response_details["switch_model"] = switch["model"]
            response_details["switch_lanIp"] = switch["lanIp"]

            for name, details in response.items():
                response_details[name] = details
            
            all_port_responses.append(response_details)
            
    return all_port_responses
            


def main():
    # create a master list
    data = []

    # Get list of organizations to which API key has access
    organizations = dashboard.organizations.getOrganizations()
    
    # Iterate through list of orgs
    for org in organizations:
        org_id = org['id']
        
        print(f"status: found {org.get('name')} - {org['id']}")
        if org['id'] == ORG_ID:
            # Get list of devices in organization
            print(f'\nstatus: analyzing organization {org["name"]}:')
            try:
                devices = dashboard.organizations.getOrganizationDevices(organizationId=ORG_ID)
            except meraki.APIError as e:
                print(f'Meraki API error: {e}')
                print(f'status code = {e.status}')
                print(f'reason = {e.reason}')
                print(f'error = {e.message}')
                continue
            except Exception as e:
                print(f'some other error: {e}')
                continue
            
            switches = [device for device in devices if device['model'][:2] in ('MS') and device['networkId'] is not None]
            # switches = [{"serial": "Q2HP-YYCL-JBVP"}]

            for switch in switches:
                print(f"status: processing device name:{switch['name']} - serial:{switch['serial']}")
                response_details = update_ports(switch)
                for response in response_details:
                    data.append(response)
        
            write_csv(org=ORG_ID, data=data)


if __name__ == "__main__":
    main()