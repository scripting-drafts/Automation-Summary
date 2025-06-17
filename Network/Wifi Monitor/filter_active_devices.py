import pandas as pd
from datetime import datetime, timedelta

LOG_FILE = "wifi_log.csv"
OUTPUT_FILE = "active_devices_detailed.txt"

def clean_data():
    """Load and normalize the wifi_log.csv file, fixing headers and formatting."""
    expected_cols = ["time", "millis", "event", "ip", "hostname"]
    
    try:
        df = pd.read_csv(LOG_FILE, sep=";", dtype=str)
    except Exception as e:
        print(f"❌ Failed to read {LOG_FILE}: {e}")
        return pd.DataFrame(columns=expected_cols)

    # Handle missing or wrong headers
    if list(df.columns) != expected_cols:
        df.columns = expected_cols[:len(df.columns)] + [f"unknown_{i}" for i in range(len(df.columns) - len(expected_cols))]

    # Drop empty or malformed rows
    df = df.dropna(subset=["time", "millis", "event", "ip"])

    # Normalize millis
    df["millis"] = pd.to_numeric(df["millis"], errors="coerce")

    # Construct timestamp from time + millis
    def parse_timestamp(row):
        today = datetime.today().strftime("%Y-%m-%d")
        try:
            full_time = f"{today} {row['time']}.{int(row['millis']):03d}"
            return pd.to_datetime(full_time, format="%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            return pd.NaT

    df["timestamp"] = df.apply(parse_timestamp, axis=1)
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")
    return df

def get_active_devices(df):
    """Get devices whose last event was JOIN."""
    latest = df.groupby("ip").tail(1)
    active = latest[latest["event"] == "JOIN"].copy()
    return active

def format_timedelta(td):
    total = int(td.total_seconds())
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs}h{mins:02d}m{secs:02d}s"

def display_active_devices(df):
    now = pd.Timestamp.now()
    df["online_for"] = df["timestamp"].apply(lambda t: format_timedelta(now - t))

    if df.empty:
        print("⚠️  No active devices found.")
        return

    print("\n📡 CURRENTLY ACTIVE DEVICES")
    print("=" * 80)
    print(f"{'IP Address':<16} {'Hostname':<25} {'Joined At':<20} {'Online'}")
    print("=" * 80)
    for _, row in df.iterrows():
        ip = row["ip"]
        host = row["hostname"]
        joined = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        online = row["online_for"]
        print(f"{ip:<16} {host:<25} {joined:<20} {online}")
    print("=" * 80)

    with open(OUTPUT_FILE, "w") as f:
        for _, row in df.iterrows():
            line = f"{row['ip']:<16} {row['hostname']:<25} Joined: {row['timestamp']} Online: {row['online_for']}"
            f.write(line + "\n")
    print(f"\n✅ Saved active device list to: {OUTPUT_FILE}")

def get_most_active_devices(df, top_n=5):
    """Find IPs with the most total JOIN time events."""
    join_counts = df[df["event"] == "JOIN"].groupby("ip").size().sort_values(ascending=False)
    print("\n🔥 MOST ACTIVE DEVICES (by JOIN events)")
    print("=" * 50)
    print(f"{'IP Address':<16} {'JOINs':>5}")
    print("=" * 50)
    for ip, count in join_counts.head(top_n).items():
        print(f"{ip:<16} {count:>5}")
    print("=" * 50)

def get_least_active_devices(df, bottom_n=5):
    """Find IPs with the least total JOIN time events."""
    join_counts = df[df["event"] == "JOIN"].groupby("ip").size().sort_values()
    print("\n🌑 LEAST ACTIVE DEVICES (by JOIN events)")
    print("=" * 50)
    print(f"{'IP Address':<16} {'JOINs':>5}")
    print("=" * 50)
    for ip, count in join_counts.head(bottom_n).items():
        print(f"{ip:<16} {count:>5}")
    print("=" * 50)

def main():
    df = clean_data()
    active_df = get_active_devices(df)

    display_active_devices(active_df)
    get_most_active_devices(df)
    get_least_active_devices(df)

if __name__ == "__main__":
    main()
