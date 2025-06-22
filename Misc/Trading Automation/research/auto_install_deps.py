import subprocess
import sys
import os

def main():
    if len(sys.argv) != 2:
        print("Usage: python auto_install_deps.py your_script.py")
        sys.exit(1)
    script = sys.argv[1]
    if not os.path.isfile(script):
        print(f"Script not found: {script}")
        sys.exit(1)

    while True:
        proc = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        _, stderr = proc.communicate()
        if proc.returncode == 0:
            print("\nScript ran successfully. All dependencies are installed.")
            break
        # Look for missing module error
        missing = None
        for line in stderr.splitlines():
            if "ModuleNotFoundError" in line and "No module named" in line:
                # Example: ModuleNotFoundError: No module named 'requests'
                missing = line.split("'")[1]
                break
        if missing:
            print(f"Missing dependency detected: {missing}. Installing with --break-system-packages...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "--break-system-packages", missing
                ])
            except Exception as e:
                print(f"Failed to install {missing}: {e}")
                sys.exit(1)
            print("Retrying script...")
        else:
            print("Script error was not a missing dependency. See error output below:")
            print(stderr)
            break

if __name__ == "__main__":
    main()
