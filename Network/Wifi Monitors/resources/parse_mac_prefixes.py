def parse_oui_file(oui_path):
    vendors = {}
    with open(oui_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '(base 16)' in line:
                parts = line.strip().split('(base 16)')
                if len(parts) == 2:
                    raw_prefix = parts[0].strip().replace('-', '').lower()
                    if len(raw_prefix) == 6:
                        prefix = ':'.join([raw_prefix[i:i+2] for i in range(0, 6, 2)])
                        vendor = parts[1].strip().replace('"', '')
                        vendors[prefix] = vendor
    return vendors

def write_mac_vendors_py(vendor_dict, output_file='mac_vendors.py'):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Auto-generated MAC vendor prefix dictionary\n")
        f.write("MAC_VENDOR_PREFIXES = {\n")
        for prefix, vendor in sorted(vendor_dict.items()):
            f.write(f'    "{prefix}": "{vendor}",\n')
        f.write("}\n")

if __name__ == "__main__":
    parsed = parse_oui_file('oui.txt')  # Make sure oui.txt is in the same folder
    print(f"Parsed {len(parsed)} MAC vendor prefixes.")
    write_mac_vendors_py(parsed)
