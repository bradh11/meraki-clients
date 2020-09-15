# Meraki Script Examples
This repository is a colleciton of scripts which are built upon the Cisco Meraki Python SDK and will help achieve operational efficiencies with a number of items such as eporting a list of all clients in an Organization, or updating switch port configurations based on a conditional check "Our example checks if the port name is `PRINTERS`".

### Pre Requisites:
1. Python 3.7 or later
2. install dependencies `pip install -r requirements.txt`

### Getting started - Export all clients in the org to CSV:
1. copy `config.yaml.example` to `config.yaml`
2. update the config file to include your Meraki API Key.  if you do not have one, it might need to be enabled for your account via the Dashboard under your user profile.  Please keep this API key safe and never allow anyone else access to it.  If you believe your key may have been compromised, please revoke it immediately and generate a new one.
3. get your ORG ID and update it in the config file.  This will limit the scope of your API calls so they do not apply to other Organizations that you might have access to.
4. run the get clients script:  `python main.py` - if you have not updated your ORG ID in the config file, a list of valid orgs will show up for you.
5. once the script is complete it will create a folder with the ORG ID with datetime.  Inside the folder will be a separate file for each network.  In addition, an aggregate csv file report will be created in the root directory of the script for all clients in all networks.

### Getting started - update port configurations which match name: PRINTER:
This script will update all ports with the name `PRINTER` and set the following paramters on those ports:
* set the linkNegotiation to `100 Megabit full duplex (forced)`
* set the port type to `access`
* set the accessPolicyType to `Open`
* keeps all remaining settings applied on the port the same as they were prior to the change

1. copy `config.yaml.example` to `config.yaml`
2. update the config file to include your Meraki API Key.  if you do not have one, it might need to be enabled for your account via the Dashboard under your user profile.  Please keep this API key safe and never allow anyone else access to it.  If you believe your key may have been compromised, please revoke it immediately and generate a new one.
3. get your ORG ID and update it in the config file.  This will limit the scope of your API calls so they do not apply to other Organizations that you might have access to.
4. run the update printers script:  `python update_printers.py`
5. once the script is done, a report of all changes applied will be reported in a csv file which is date timestamped.