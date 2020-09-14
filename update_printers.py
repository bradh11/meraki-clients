import csv
from datetime import datetime
import os
import yaml
import meraki

# Either input your API key below by uncommenting line 10 and changing line 16 to api_key=API_KEY,
# or set an environment variable (preferred) to define your API key. The former is insecure and not recommended.
# For example, in Linux/macOS:  export MERAKI_DASHBOARD_API_KEY=093b24e85df15a3e66f1fc359f4c48493eaa1b73
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f.read())
    API_KEY = config.get("API_KEY")
    ORG_ID = config.get("ORG_ID")


def write_csv(org, data):
    # Write to file
    todays_date = f'{datetime.now():%Y-%m-%d_%H_%M}'
    file_name = f"{org}-switchports-{todays_date}.csv"
    output_file = open(f'{file_name}', mode='w', newline='\n')
    field_names = data[0].keys()
    csv_writer = csv.DictWriter(output_file, field_names, delimiter=',', quotechar='"',
                                quoting=csv.QUOTE_ALL)
    csv_writer.writeheader()
    csv_writer.writerows(data)
    output_file.close()
    print(f'  - found {len(data)}')

def main():
    # Instantiate a Meraki dashboard API session
    dashboard = meraki.DashboardAPI(
        api_key=API_KEY,
        # base_url='https://api-mp.meraki.com/api/v1/',
        output_log=True,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='logs',
        print_console=False
    )

    # create a master list
    data = []

    # Get list of organizations to which API key has access
    organizations = dashboard.organizations.getOrganizations()
    
    # Iterate through list of orgs
    for org in organizations:
        org_id = org['id']
        
        print(f"status: checking {org['name']} - {org['id']}")
        if org['id'] == ORG_ID:
            # Get list of devices in organization
            print(f'\nAnalyzing organization {org["name"]}:')
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
                print(f"status: found device name:{switch['name']} - serial:{switch['serial']}")
                ports = dashboard.switch.getDeviceSwitchPorts(switch['serial'])

                for port in ports:
                    if port["name"] == "PRINTER":
                        print(f"status: PRINTER found on port {port['portId']} -- updating...")
                        response = dashboard.switch.updateDeviceSwitchPort(
                            serial=switch['serial'],
                            portId=port['portId'],
                            accessPolicyType = "Open",
                            linkNegotiation="100 Megabit full duplex (forced)",
                            type = "access"
                            )
                        
                        response_details = {}
                        response_details["switch_name"] = switch["name"]
                        response_details["switch_serial"] = switch["serial"]
                        response_details["switch_model"] = switch["model"]
                        response_details["switch_lanIp"] = switch["lanIp"]
                        for name, details in response.items():
                            response_details[name] = details
                        print(response_details)
                        data.append(response_details)
        
            write_csv(org=ORG_ID, data=data)


if __name__ == "__main__":
    main()