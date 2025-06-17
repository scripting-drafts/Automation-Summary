import pandas as pd
import csv

LOG_FILE = "wifi_log.csv"
CLEAN_FILE = "log_cleaned.csv"

def clean_log():
    
    f = open(LOG_FILE, 'r').readlines()
    lines = [
        'time;millis;event;ip;hostname;'
    ]

    for line in f:
        lines.append(';'.join([x.replace('', 'unknown') for x in line.split(',') if x == '']))
    
    with open(CLEAN_FILE, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(lines)

    print(f"Cleaned log saved to {CLEAN_FILE}")

if __name__ == "__main__":
    clean_log()