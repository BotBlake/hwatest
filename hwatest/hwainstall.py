import os
import subprocess
import urllib.request

packages = ["click", "distro"]
additional_software = []
manual_source_files = {
    "2160p-hevc": {
        "url": "https://repo.jellyfin.org/jellyfish/media/jellyfish-120-mbps-4k-uhd-hevc-10bit.mkv",
        "size": 429,
    },
    "2160p-h264": {
        "url": "https://repo.jellyfin.org/jellyfish/media/jellyfish-120-mbps-4k-uhd-h264.mkv",
        "size": 431,
    },
    "1080p-hevc": {
        "url": "https://repo.jellyfin.org/jellyfish/media/jellyfish-40-mbps-hd-hevc-10bit.mkv",
        "size": 143,
    },
    "1080p-h264": {
        "url": "https://repo.jellyfin.org/jellyfish/media/jellyfish-40-mbps-hd-h264.mkv",
        "size": 142,
    },
}


def download_source_files(sources): #Downloading Method from hwatest :D
    print("Files HAVE to be on a FAST DRIVE!")
    video_path = input("Enter path to Download folder: ")

    if not os.path.exists(video_path):
        os.makedirs(video_path)
        print(f"Directory '{video_path}' created successfully.")
    else:
        print(f"Directory '{video_path}' already exists.")

    print()
    video_files = list()
    for video in sources.values():
        video_url = video["url"]
        video_filename = video_url.split("/")[-1]
        video_filesize = video["size"]
        video_filepath = f"{video_path}/{video_filename}"

        if not os.path.exists(video_filepath):
            print(f'File not found: "{video_filepath}"')
            file_invalid = True
        else:
            actual_filesize = int(
                os.stat(video_filepath).st_size / (1024 * 1024)
            )
            if actual_filesize != video_filesize:
                print(
                    f'File "{video_filepath}" size is invalid: {actual_filesize}MB not {video_filesize}MB'
                )
                file_invalid = True
            else:
                file_invalid = False

        if file_invalid:
            print(f'Downloading "{video_filename}" ({video_filesize}MB) to "{video_path}"... ', end=' ', flush=True)
            urllib.request.urlretrieve(video_url, f"{video_path}/{video_filename}")
            print("done.")
        else:
            print(
                f'Found valid test file "{video_path}/{video_filename}" ({video_filesize}M).'
            )
        video_files.append(video_filename)
    print()
    return video_files




#Fetch Basic info:
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

response = input("Do you want to pre Download the Video Files? (y/n): ")
if response.lower() == "y":
    download_source_files(manual_source_files)


print("You are now ready for hwatest!")