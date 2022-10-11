import vmtconnect as vconn
import json
import csv
import os
import argparse
import requests
import sys
import csv_to_static_groups

from requests.packages.urllib3.exceptions import InsecureRequestWarning

# _msg Variables
LOGGER = None
QUIET = True
TRACE = True
WARN = True

def getSortedCriticalList(conn, reasonCommidity, numSorted):
    actions = conn.get_actions(fetch_all=True)

    # Obtains the critical uuids based on the reasonCommidity value
    critical_uuids = [x['target']['uuid'] for x in actions
        if x['risk'].get('reasonCommodity') is not None
            # Potentially check for On-prem vs. On-cloud
            if x['risk']['severity'] == 'CRITICAL' and x['risk']['reasonCommodity'] == reasonCommidity] # CPU, VCPU, VMem, SegmentationCommodity, SoftwareLicenseCommodity

    # Obtains a list of entity stats
    vm_stats = conn.get_entity_stats(critical_uuids, stats=[reasonCommidity], related_type="VirtualMachine", pager=True, fetch_all=True)

    # Determines the vcpu percentile
    for x in vm_stats:
        for y in x['stats']:
            i = [item for item in y['statistics'] if item.get('name') == reasonCommidity]
            if len(i) > 0 and i[0]['values']['avg'] != 0: 
                x["v_percentile"] = i[0]['capacity']['avg'] / i[0]['values']['avg']
            else:
                x["v_percentile"] = -1 # divide by 0 issue / skip VM

    # Sorts the vm_stats based on the vcpu_percentile (capacity-avg/values-avg)
    sorted_vms = sorted(vm_stats, key=lambda x: x["v_percentile"], reverse=True)    

    # Take first 10 entries
    sorted_vms = sorted_vms[:int(numSorted)]

    return sorted_vms


def createCriticalCSV(fileName,sorted_vms, group_name):
    # open the file in the write mode
    # f = open('vcpu_vm_group.csv', 'w')
    f = open(fileName+'.csv', 'w')

    # create the csv writer
    writer = csv.writer(f)

    # create header in csv file
    writer.writerow(["Entity Type", "Entity Name", "Department"])

    for vm in sorted_vms:
        # write a row to the csv file
        writer.writerow([vm["className"], vm["displayName"], group_name])

    # close the file
    f.close()

def _msg(msg, end='\n', logger=None, level=None, exc_info=False, warn=False,
         error=False):
    """Message handler"""
    global LOGGER, QUIET, TRACE, WARN

    empty_trace = (None, None, None)

    if logger is None:
        logger = LOGGER

    if TRACE and sys.exc_info() != empty_trace:
        exc_info = True

    if warn:
        level = "warn"

    if logger:
        if level == 'critical':
            logger.critical(msg, exc_info=exc_info)
        elif level == 'error':
            logger.error(msg, exc_info=exc_info)
        elif level == 'warn' or level == 'warning':
            logger.warning(msg, exc_info=exc_info)
        elif level == 'debug':
            logger.debug(msg, exc_info=exc_info)
        else:
            logger.info(msg, exc_info=exc_info)

    if not QUIET or error:
        if warn and not WARN:
            pass
        else:
            if warn:
                msg = "Warning: {}".format(msg)
            print(msg, end=end)

def main(conn, reason_commidity, file_name, num_sorted, group_name):
    """
        Parses groups from CSV and adds/updates/deletes groups.
        Efficiently collects group and entity uuids to minimize api requests.

    Args:
        conn (VMTConnection): VMTConnection instance to target Turbonomic Server
        csv_file (str): CSV file name
        reason_commodity (str): Turbonomic reason commodity type for critical
        list_length (int): Number of critical sorted
        group_name (str): Name of the group to be created in Turbonomic

    Returns:
        Dictionary with change events and totals for each change category

        e.g. ::

            {"Change Category A": {
                 "total": int
                 "events":[
                     {"group name": str,
                      "message": str}
                    ]
                }}

    """

    sortedCritical = getSortedCriticalList(conn,reason_commidity, num_sorted)
    createCriticalCSV(file_name, sortedCritical, group_name)

    # Enable sysout output
    csv_to_static_groups.QUIET = False

    # Enable verbose output
    csv_to_static_groups.VERBOSE = True
    csv_file = file_name+'.csv'
    changes = csv_to_static_groups.main(conn, csv_file, group_headers=['Department'])

    # Print Total Changes
    print("\n")
    for category, attr in changes.items():
        print("{}: {}".format(category, attr["total"]))




if __name__ == "__main__":
    # Credentials
    __TURBO_TARGET = "localhost"
    __TURBO_USER = "administrator"
    __TURBO_PASS = ""
    __TURBO_CREDS = b""

    # Parse Arguments
    arg_parser = argparse.ArgumentParser(description="Limit Critical ServiceNow change requests")
    arg_parser.add_argument("-rc", "--reason_commidity", action="store", required=True,
                            help=("VCPU, VMem, CPU, etc."))
    arg_parser.add_argument("-fn", "--file_name", action="store", required=True,
                            help=("Name of the csv file that will be created."))
    arg_parser.add_argument("-ns", "--num_sorted", action="store", required=True,
                            help=("Number of sorted critical resources"))      
    arg_parser.add_argument("-gp", "--group_name", action="store", required=True,
                            help=("Name of the group to be created in Turbonomic"))              
    arg_parser.add_argument("-t", "--target", action="store", required=False,
                            help="Turbonomic server address. Default={}".format(__TURBO_TARGET),
                            default=__TURBO_TARGET)
    arg_parser.add_argument("--ignore_insecure_warning", action="store_true", required=False,
                            help="Suppress insecure HTTPS request warnings")
    arg_parser.add_argument("--encoded_creds", action="store", required=False,
                            help=("Base64 encoded credentials"))
    arg_parser.add_argument("-u", "--username", action="store", required=False,
                            help=("Turbonomic Username, Password will be prompted."))


    # Parse Arguments
    args_dict = vars(arg_parser.parse_args())

    # Overide credentials if passed as args
    if args_dict["encoded_creds"]:
        __TURBO_CREDS = args_dict["encoded_creds"].encode()
    elif args_dict["username"]:
        __TURBO_USER = args_dict["username"]
        try:
            __TURBO_PASS = getpass()
        except KeyboardInterrupt:
            print("\n")
            sys.exit()
   
    if args_dict["target"]:
        __TURBO_TARGET = args_dict["target"]

    # Supress insecure HTTPS warnings
    if args_dict["ignore_insecure_warning"]:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    try:
        # Make connection object
        conn = vconn.Session(__TURBO_TARGET, __TURBO_USER, __TURBO_PASS,
                             __TURBO_CREDS)
        __TURBO_USER = __TURBO_PASS = __TURBO_ENC = None
        # Execute main function
        change_summary = main(conn, 
                            reason_commidity=args_dict["reason_commidity"],
                            file_name=args_dict["file_name"],
                            num_sorted=args_dict["num_sorted"],
                            group_name=args_dict["group_name"])

    except KeyboardInterrupt:
        print("\n")
        pass
    except Exception as e:
        _msg("Fatal Error: {}".format(e), level="error", error=True)
