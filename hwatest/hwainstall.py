import os
import subprocess

#Fetch Basic info:
packages = ["click", "distro"]
additional_software = []
if(os.name == "nt"):  # Windows
    system_os = "Windows"
    packages.append("wmi")
else:
    system_os = "Linux"
    additional_software.append("lshw")

# Inform the user
print("This is hwa_install.")
print(f"We detected that you are on {system_os}.")
if additional_software:
    print(f"Installing Python Packages {packages} as well as {additional_software}")
else:
    print(f"Installing Python Packages {packages}!")
print("")
input("Note: Please install on a fast drive for reliable test results! (Enter to continue)")
print()

if(system_os == "Linux"):  # Installing lshw for Linux)
    # Check if lshw is installed
    try:
        subprocess.check_output(["lshw", "--version"])
        print("lshw already installed! Skipped installation.")
    except subprocess.CalledProcessError:
        print("lshw not found. Installing...")
        subprocess.run(["sudo", "apt-get", "install", "lshw", "-y"])

# Install required packages
for package in packages:
    try:
        # Check if package is already available
        subprocess.check_output(["pip", "show", package])
    except subprocess.CalledProcessError:
        print(f"{package} not found. Installing...")
        subprocess.run(["pip", "install", package])
print()
print("You are now ready for hwatest!")