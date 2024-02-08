import os
import subprocess
import urllib.request
from hashlib import sha256
import zipfile
import tarfile


current_path = os.path.dirname(os.path.realpath(__file__))  # Get current script's directory
hwatest_path = os.path.join(current_path, "hwatest.py")

hwa_command = [
    "python3",
    hwatest_path,
]

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
manual_ffmpeg_files = {
    "windows" : {
        "url" : "https://github.com/jellyfin/jellyfin-ffmpeg/releases/download/v6.0.1-2/jellyfin-ffmpeg_6.0.1-2-portable_win64.zip",
        "sha256" : "e16bef692772d58955bed223f460e31c312ccc02208b8c9c51ed35e429fc5d42",
        "name" : "jellyfin-ffmpeg_6.0.1-2-portable_win64.zip",
    },
    "linux" : {
        "url" : "https://github.com/jellyfin/jellyfin-ffmpeg/releases/download/v6.0.1-2/jellyfin-ffmpeg_6.0.1-2_portable_linux64-gpl.tar.xz",
        "sha256" : "b17da23d5e1dfe148ffd5c082a51547ac5a73dcc9d4534fe63ebb450da43d5ed",
        "name" : "jellyfin-ffmpeg_6.0.1-2_portable_linux64-gpl.tar.xz",
    }
}

def download_source_files(sources): #Downloading Method from hwatest :D
    print("Files HAVE to be on a FAST DRIVE!")
    video_path = input("Enter path to Video Download folder: ")

    if not os.path.exists(video_path):
        os.makedirs(video_path)
        print(f"Directory '{video_path}' created successfully.")
    else:
        print(f"Directory '{video_path}' already exists.")

    video_path = os.path.abspath(video_path)

    print()
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
    print()
    return video_path

def download_ffmpeg(sources, platform):
    print("FFMPEG HAS to be on a FAST DRIVE!")
    ffmpeg_path = input("Enter path to FFMPEG Download folder: ")

    if not os.path.exists(ffmpeg_path):
        os.makedirs(ffmpeg_path)
        print(f"Directory '{ffmpeg_path}' created successfully.")
    else:
        print(f"Directory '{ffmpeg_path}' already exists.")

    ffmpeg_path = os.path.abspath(ffmpeg_path)

    print()
    sha265_required = sources[platform.lower()]["sha256"]
    download_url = sources[platform.lower()]["url"]
    download_name = sources[platform.lower()]["name"]

    ffmpeg_arch_path = f"{ffmpeg_path}/{download_name}"
    print(f'Downloading FFMPEG Portable for {platform} to "{ffmpeg_path}"... ', end=' ', flush=True)
    urllib.request.urlretrieve(download_url, ffmpeg_arch_path)
    print("done.")

    sha256_hash = sha256()  # Now Perform Checksumming
    with open(ffmpeg_arch_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    if (sha256_hash.hexdigest() != sha265_required):
        print("The download Failed! || SHA256 Checksum Missmatch")
        exit(1)
    
    if ffmpeg_arch_path.endswith('.zip'):
        with zipfile.ZipFile(ffmpeg_arch_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_path)
    elif ffmpeg_arch_path.endswith('.tar.gz'):
        with tarfile.open(ffmpeg_arch_path, 'r:gz') as tar_ref:
            tar_ref.extractall(ffmpeg_path)
    os.remove(ffmpeg_arch_path)

    if(platform.lower()=="windows"):
        ffmpeg_executable = f"{ffmpeg_path}/ffmpeg.exe"
    else:
        ffmpeg_executable = f"{ffmpeg_path}/ffmpeg"
    return ffmpeg_executable

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
    vid_scr = os.path.abspath(download_source_files(manual_source_files))
    hwa_command.append("--videos")
    hwa_command.append(vid_scr)

response = input("Do you want to install the FFMPEG Portable? (y/n): ")
if response.lower() == "y":
    ffmpeg_src = os.path.abspath(download_ffmpeg(manual_ffmpeg_files, system_os))
    hwa_command.append("--ffmpeg")
    hwa_command.append(ffmpeg_src)


print("You are now ready for hwatest!")
response = input("Do you want to start hwatest now? (you may be required to add manual values) (y/n): ")
if response.lower() == "y":
    vm_question = input("Do you run this script inside a Virtual environment? (y/n): ")
    if vm_question.lower() == "y":
        #hwa_command.append("--vm")
        print("Vm Mode doesnt yet exist on the Script! Its likely that this will not work!")
    command = " ".join(hwa_command)
    print(command)
    try:
        subprocess.run(hwa_command)
    except Exception as e:
        print("Error:", e)