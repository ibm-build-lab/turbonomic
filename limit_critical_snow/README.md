# Limit Critical Snow

Prereqs:
- Python 3
- requests >= 2.22.0.     (pip3 install requests)
- vmt-connect >= 3.4.0 (pip3 install vmtconnect)
- csv_to_static_groups.py from https://github.com/vmturbo/csv_to_static_groups/tree/master/csv_to_static_groups

To run this file:
```bash
python3 limit_critical_snow.py -rc VCPU -fn vcpu_list -ns 10 -gp snow_group -t <hostname of turbonomic> --ignore_insecure_warning --encoded_creds <base64 username:password>

```

For more information run the command: `python3 limit_critical_snow.py -h`
