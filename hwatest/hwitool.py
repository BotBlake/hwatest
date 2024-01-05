import platform
from json import dump, dumps
import wmi
import re

def get_os_info():
    if(platform.system() == "Windows"):
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
        return os_element
    else:
        print("Linux is not Supported yet!")
        exit(1)
def get_cpu_info():
    cpu_elements = []

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
            "units": "Hz",
            "size": cpu.MaxClockSpeed, #Note that Intel does only Report MaxClock without TurboBoost
            #"capacity": None,
            "width": cpu.AddressWidth,
        }
        cpu_elements.append(cpu_element)
    return cpu_elements


def get_gpu_info():
    gpu_elements = []

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
    return gpu_elements

def get_memory_info():
    memory_elements = []

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
    if(platform.system() == "Windows"):
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
    else:
        print("Sorry. Other OS's then Windows are still W.I.P.")