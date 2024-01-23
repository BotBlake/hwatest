import platform
import subprocess
from json import dump, dumps, loads
import re

try:
    import wmi
    print("Using Windows Management Instrumentation to obtain System Information")
    Windows = True
except ImportError:
    if platform.system() == "Windows":
        print("Please install wmi (Windows Management Instrumentation) before running this script!")
        exit(1)
    from distro import os_release_info
    Windows = False
    print("Using lshw to obtain System Information")

def get_os_info():
    os_element = {}
    if(Windows):
        c = wmi.WMI()
        for os in c.Win32_OperatingSystem():
            win_ver = re.search(r'\d+', os.Caption)
            if (win_ver):
                win_ver = win_ver.group()
            else:
                win_ver = "Unknown"
            os_element = {
                "pretty_name": os.Caption.strip().replace(" ","_"),
                "name":platform.system(),
                "version_id":win_ver,
                "version":os.Version.strip(),
                "version_codename":"unknown",
                "id":platform.system().lower(),
                #"home_url":"windows_unknown",
                #"support_url":"windows_unknown",
                #"bug_report_url":"windows_unknown",
                "codename":"unknown",
            }
    else:
        info = os_release_info()
        os_element = {
            "pretty_name": info["pretty_name"],
            "name": info["name"],
            "version_id": info["version_id"],
            "version": info["version"],
            "version_codename": info["version_codename"],
            "id": info["id"],
            "home_url": info["home_url"],
            "support_url": info["support_url"],
            "bug_report_url": info["bug_report_url"],
            "codename": info["codename"]
        }
    return os_element
def get_cpu_info():
    cpu_elements = []
    if(Windows):
        # Connect to the Windows Management Instrumentation
        c = wmi.WMI()
        # Retrieve information about processors (CPUs)
        for cpu in c.Win32_Processor():
            phys_id = cpu.ProcessorId.strip()
            phys_id = phys_id[-5] #Last 5Chars are CPUID (https://www.intel.de/content/www/de/de/support/articles/000006831/processors/processor-utilities-and-programs.html)
            cpu_element={
                "id": cpu.DeviceID.strip(),
                "class": "processor",
                "claimed": True,
                "product": cpu.Name.strip(),
                "vendor": cpu.Manufacturer.strip(),
                "physid": phys_id,
                #"businfo": None,
                #"units": "Hz",
                #"size": cpu.MaxClockSpeed, #Note that Intel does only Report MaxClock without TurboBoost
                #"capacity": None,
                "width": cpu.AddressWidth,
            }
            cpu_elements.append(cpu_element)
    else:
        try:
            cpu_info = subprocess.run(
            ["lshw", "-json", "-class", "cpu"],
            capture_output=True,
            )
            if cpu_info.returncode > 0:
                raise
        except Exception:
            print("Could not run 'lshw'! The 'lshw' program is needed to gather required system information. Please install it and try again.")
            exit(1)

        cpu_info = loads(cpu_info.stdout.decode())
        for cpu in cpu_info:
            cpu_element={
                "id": cpu["id"],
                "class": cpu["class"],
                "claimed": cpu["claimed"],
                "product": cpu["product"],
                "vendor": cpu["vendor"],
                "physid": cpu["physid"],
                "businfo": cpu["businfo"],
                "units": cpu["units"],
                "size": cpu["size"],
                "capacity": cpu["capacity"],
                "width": cpu["width"],
                "capabilities":cpu["capabilities"],
            }
            cpu_elements.append(cpu_element)
    return cpu_elements

def get_gpu_info():
    gpu_elements = []
    if(Windows):
        # Connect to the Windows Management Instrumentation
        c = wmi.WMI()
        # Retrieve information about video controllers (GPUs)
        for i, gpu in enumerate(c.Win32_VideoController()):
            vendor = gpu.AdapterCompatibility.strip() #Checking the AdapterCompatibility for Intel, Amd or NVIDIA (based on known Values)
            if vendor == "NVIDIA": #Nvidia is reporting different, so we need to correct it
                vendor="NVIDIA Corporation"
            elif(vendor=="Advanced Micro Devices, Inc."): #also correcting AMD slightly
                vendor="Advanced Micro Devices, Inc. [AMD/ATI]"

            configuration = {
                "driver":gpu.DriverVersion.strip(),
                #latency:None,
            }
            gpu_element={
                "id":"GPU"+str(i+1), #Index needs to start at 1 (for hwatest.py)
                "class":"display",
                #"claimed":True,
                #"handle":None,
                "description":gpu.creationClassName.strip(),
                "product":gpu.Caption.strip(),
                "vendor":vendor,
                "physid":gpu.DeviceID.strip(),
                "businfo":gpu.PNPDeviceID.strip(),
                #"version": None,
                "width":gpu.CurrentBitsPerPixel,
                #"clock":None,
                "configuration": configuration,
            }
            gpu_elements.append(gpu_element)
    else:
        try:
            gpu_info = subprocess.run(
            ["lshw", "-json", "-class", "display"],
            capture_output=True,
            )
            if gpu_info.returncode > 0:
                raise
        except Exception:
            print("Could not run 'lshw'! The 'lshw' program is needed to gather required system information. Please install it and try again.")
            exit(1)

        gpu_info = loads(gpu_info.stdout.decode())
        for gpu in gpu_info:
            gpu_element = {
                "id": gpu["id"],
                "class": gpu["class"],
                "claimed": gpu["claimed"],
                "handle": gpu["handle"],
                "description": gpu["description"],
                "product": gpu["product"],
                "vendor": gpu["vendor"],
                "physid": gpu["physid"],
                "businfo": gpu["businfo"],
                "version": gpu["version"],
                "width": gpu["width"],
                "clock": gpu["clock"],
                "configuration": gpu["configuration"],
                "capabilities": gpu["capabilities"]
            }
            gpu_elements.append(gpu_element)
    return gpu_elements

def get_memory_info():
    memory_elements = []
    if(Windows):
        # Connect to the Windows Management Instrumentation
        c = wmi.WMI()
        # Retrieve information about physical memory
        for mem in c.Win32_PhysicalMemory():
            memory_element={
                "id":mem.Tag.strip().replace(" ","_"),
                "class":"memory",
                "claimed":True,
                "description":mem.Description, #<- This sadly is in the OS's set Language
                'physid':mem.DeviceLocator.strip(),
                "units":"bytes",
                'size':int(mem.Capacity),
            }
            memory_elements.append(memory_element)
    else:
        try:
            mem_info = subprocess.run(
            ["lshw", "-json", "-class", "memory"],
            capture_output=True,
            )
            if mem_info.returncode > 0:
                raise
        except Exception:
            print("Could not run 'lshw'! The 'lshw' program is needed to gather required system information. Please install it and try again.")
            exit(1)

        mem_info = loads(mem_info.stdout.decode())
        for stick in mem_info:
            memory_element = {
                "id": stick["id"],
                "class": stick["class"],
                "claimed": stick["claimed"],
                "description": stick["description"],
                "physid": stick["physid"],
                "units": stick["units"],
                "size": stick["size"],
            }
            memory_elements.append(memory_element)
    return memory_elements

def format_bytes(num_bytes):
    units = ['byte', 'kilobyte', 'megabyte', 'gigabyte', 'terrabyte', 'pettabyte']
    unit_index = 0

    while num_bytes >= 1024 and unit_index < len(units) - 1:
        num_bytes /= 1024.0
        unit_index += 1

    return units[unit_index], float(num_bytes)

if __name__ == "__main__":
    all_results= dict()
    all_results["hwinfo"] = dict()
    print("HWI_Tool for Windows and Linux: (wmi / lshw)")
    all_results["hwinfo"]["os"] = get_os_info()
    all_results["hwinfo"]["cpu"] =get_cpu_info()
    all_results["hwinfo"]["memory"] = get_memory_info()
    gpu_output = get_gpu_info()
    # Discard any GPUs we don't recognize (i.e. not NVIDIA, AMD, or Intel)
    for element in gpu_output.copy():
        if element["vendor"] not in [
            "NVIDIA Corporation",
            "Advanced Micro Devices, Inc. [AMD/ATI]",
            "Intel Corporation",
        ]:
            gpu_output.remove(element)
    all_results["hwinfo"]["gpu"] = gpu_output

    print(dumps(all_results, indent="\t"))
    with open("./results.json", "w") as fh:
        dump(all_results, fh, indent="\t")