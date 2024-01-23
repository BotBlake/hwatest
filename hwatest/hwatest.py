#!/usr/bin/env python3

# hwatest.py
# A CPU and Hardware Acceleration (GPU) tester for Jellyfin
#
#    Copyright (C) 2023 Joshua M. Boniface <joshua@boniface.me>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
###############################################################################

import hwitool
import platform


import click
import os
import urllib.request
import subprocess
import re
import concurrent.futures

from json import dump, dumps
from time import sleep

test_source_files = {
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

ffmpeg_streams = {
    "cpu-h264": r"{ffmpeg} -c:v h264 -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale=trunc(min(max(iw\,ih*a)\,{scale})/2)*2:trunc(ow/a/2)*2,format=yuv420p -c:v libx264 -preset veryfast -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "cpu-hevc": r"{ffmpeg} -c:v hevc -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale=trunc(min(max(iw\,ih*a)\,{scale})/2)*2:trunc(ow/a/2)*2,format=yuv420p -c:v libx265 -preset veryfast -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "nvenc-h264": r"{ffmpeg} -init_hw_device cuda=cu:{gpu} -hwaccel cuda -hwaccel_output_format cuda -c:v h264_cuvid -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale_cuda=-1:{scale}:yuv420p -c:v h264_nvenc -preset p1 -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "nvenc-hevc": r"{ffmpeg} -init_hw_device cuda=cu:{gpu} -hwaccel cuda -hwaccel_output_format cuda -c:v hevc_cuvid -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale_cuda=-1:{scale}:yuv420p -c:v hevc_nvenc -preset p1 -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "vaapi-h264": r"ffmpeg -init_hw_device vaapi=va:/dev/dri/by-path/{gpu}-render -hwaccel vaapi -hwaccel_output_format vaapi -c:v h264 -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale_vaapi=-1:{scale}:format=nv12 -c:v h264_vaapi -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "vaapi-hevc": r"ffmpeg -init_hw_device vaapi=va:/dev/dri/by-path/{gpu}-render -hwaccel vaapi -hwaccel_output_format vaapi -c:v hevc -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale_vaapi=-1:{scale}:format=nv12 -c:v hevc_vaapi -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "qsv-h264": r"{ffmpeg} -init_hw_device vaapi=va:/dev/dri/by-path/{gpu}-render -init_hw_device qsv=qs@va -hwaccel qsv -hwaccel_output_format qsv -c:v h264_qsv -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale_qsv=-1:{scale}:format=nv12 -c:v h264_qsv -preset veryfast -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
    "qsv-hevc": r"{ffmpeg} -init_hw_device vaapi=va:/dev/dri/by-path/{gpu}-render -init_hw_device qsv=qs@va -hwaccel qsv -hwaccel_output_format qsv -c:v hevc_qsv -i {video_path}/{video_file} -autoscale 0 -an -sn -vf scale_qsv=-1:{scale}:format=nv12 -c:v hevc_qsv -preset veryfast -b:v {bitrate} -maxrate {bitrate} -f null - -benchmark",
}

scaling = {
    "2160p": {
        "size": "2160",
        "bitrate": "79616000",
        "name": "2160p @ 80 Mbps",
    },
    "1080p": {
        "size": "1080",
        "bitrate": "9616000",
        "name": "1080p @ 10 Mbps",
    },
    "720p": {
        "size": "720",
        "bitrate": "3616000",
        "name": "720p @ 4 Mbps",
    },
}

debug = False


def run_ffmpeg(cmd, pid, is_cpu=False):
    # For workers wait 1/100th of a second before starting to ensure the first
    # worker can always start
    if pid > 1:
        sleep(0.01)

    if is_cpu:
        timeout = None
    else:
        timeout = 60

    split_cmd = cmd.split()
    # Timeout is 120s as this is 4x the length of the clip (and longer than any reasonable run should take)
    try:
        output = subprocess.run(
            split_cmd,
            stdin=subprocess.PIPE,
            capture_output=True,
            universal_newlines=True,
            timeout=timeout,
        )
        retcode = output.returncode
        ffmpeg_stderr = output.stderr
    except subprocess.TimeoutExpired:
        output = None
        retcode = 255
        ffmpeg_stderr = ""
        failure_reason = "timeout/stuck"
    except Exception as e:
        output = None
        retcode = 255
        ffmpeg_stderr = ""
        failure_reason = f"generic failure {e}"

    failure_reason = None
    if 0 < retcode < 255:
        # Figure out why we failed based on the ffmpeg output, the first error
        # found is canonical
        for line in ffmpeg_stderr:
            if re.search(r" failed: (.*)\([0-9]+\)", ffmpeg_stderr):
                failure_reason = (
                    re.search(r" failed: (.*)\([0-9]+\)", ffmpeg_stderr).group(1).strip()
                )
                break
            elif re.search(r" failed -> (.*): (.*)", ffmpeg_stderr):
                failure_reason = (
                    re.search(r" failed -> (.*): (.*)", ffmpeg_stderr).group(2).strip()
                )
                break
            elif re.search(r"^Error (.*)", ffmpeg_stderr):
                failure_reason = (
                    re.search(r"^Error (.*)", ffmpeg_stderr).group(1).strip()
                )
                break
        # If we can't find a good reason, it's just a generic failure
        if failure_reason is None:
            failure_reason = "generic failure"

    results = dict()
    time_s = 0.0
    for line in ffmpeg_stderr.split("\n"):
        if re.match(r"^bench: utime", line):
            timeline = line.split()
            time_s = float(timeline[3].split("=")[-1].replace("s", ""))

    if debug:
        click.echo(
            f">>>>> Worker {pid:02}: retcode: {retcode}, time: {time_s:.2f}s, failure reason: {failure_reason}"
        )

    if pid > 1:
        return (retcode, failure_reason, None)

    for line in ffmpeg_stderr.split("\n"):
        if re.match(r"^frame=", line):
            # We want to find the speed from the first frame after 500 out of 900
            if re.match(r"frame=\s*[5-9][0-9]+[0-9]+", line):
                line = re.sub(r"=\s*", "=", line)
                frameline = line.split()
                break

    for line in ffmpeg_stderr.split("\n"):
        if re.match(r"^bench: utime", line):
            timeline = line.split()
        if re.match(r"^bench: maxrss", line):
            rssline = line.split()

    try:
        results["workers"] = pid
        results["frame"] = int(frameline[0].split("=")[-1])
        results["speed"] = float(frameline[6].split("=")[-1].replace("x", ""))
        results["time_s"] = float(timeline[3].split("=")[-1].replace("s", ""))
        results["rss_kb"] = float(rssline[1].split("=")[-1].replace("kB", ""))
        return (retcode, failure_reason, results)
    except Exception:
        return (retcode, failure_reason, None)


def do_benchmark(ffmpeg, video_path, video_file, stream, scale, workers, gpu):
    stream_cmd = ffmpeg_streams[stream].format(
        ffmpeg=ffmpeg,
        video_path=video_path,
        video_file=video_file,
        scale=scaling[scale]["size"],
        bitrate=scaling[scale]["bitrate"],
        gpu=gpu,
    )

    is_cpu = re.match(r"^cpu-", stream) is not None

    results = None
    total_rets = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers + 1) as executor:
        future_to_results = {
            executor.submit(run_ffmpeg, stream_cmd, i, is_cpu): i
            for i in range(1, workers + 1, 1)
        }
        had_failure = False
        failure_reasons = set()
        for future in concurrent.futures.as_completed(future_to_results):
            retcode, failure_reason, result = future.result()
            total_rets += 1
            # Get the first test result (all others are None)
            if result is not None:
                results = result
            if retcode > 0 and retcode < 255:
                had_failure = True
            if failure_reason is not None:
                failure_reasons.add(failure_reason)
        failure_reasons = list(failure_reasons)

    if results is None:
        return (1, failure_reasons, results)
    elif had_failure is True or total_rets != workers:
        return (2, failure_reasons, results)
    else:
        return (0, failure_reasons, results)

def get_hwinfo(all_results, ffmpeg):
    all_results["hwinfo"] = dict()

    # Get our OS information through HWI
    all_results["hwinfo"]["os"] = hwitool.get_os_info()

    # Get our FFmpeg information
    ffmpeg_output = subprocess.run(
        [ffmpeg, "-version"],
        capture_output=True,
    )
    if ffmpeg_output.returncode > 0:
        click.echo(
            "Could not run 'ffmpeg'! Ensure you specified a valid Jellyfin FFmpeg path and try again."
        )
        exit(1)
    ffmpeg_information = ffmpeg_output.stdout.decode().split("\n")
    all_results["hwinfo"]["ffmpeg"] = dict()
    all_results["hwinfo"]["ffmpeg"]["path"] = ffmpeg
    all_results["hwinfo"]["ffmpeg"]["version"] = re.match(
        r"ffmpeg version (.*) Copyright", ffmpeg_information[0]
    ).group(1)

    # Ported to "custom" hwitool, to fetch hardware information seperately
    cpu_output = hwitool.get_cpu_info()
    all_results["hwinfo"]["cpu"] = cpu_output

    memory_output = hwitool.get_memory_info()
    all_results["hwinfo"]["memory"] = memory_output

    gpu_output = hwitool.get_gpu_info()
    # Discard any GPUs we don't recognize (i.e. not NVIDIA, AMD, or Intel)
    for element in gpu_output.copy():
        if element["vendor"] not in [
            "NVIDIA Corporation",
            "Advanced Micro Devices, Inc. [AMD/ATI]",
            "Intel Corporation",
        ]:
            gpu_output.remove(element)

    all_results["hwinfo"]["gpu"] = gpu_output

    return all_results


def benchmark(ffmpeg, video_path, gpu_idx):
    video_files = list()

    all_results = dict()
    all_results = get_hwinfo(all_results, ffmpeg)
    gpu_used = int()
    if len(all_results["hwinfo"]["gpu"]) > 1:
        if gpu_idx is None:
            click.echo(
                "Warning! Your system has more than one viable GPU and we cannot test multiple GPUs simultaneously."
            )
            click.echo(
                'Please re-run the test specifying the desired GPU index number with the "--gpu" option.'
            )
            click.echo()
            click.echo("Found GPUs:")
            for idx, gpu in enumerate(all_results["hwinfo"]["gpu"]):
                click.echo(
                    f"  {idx}: {gpu['vendor']} {gpu['product']} bus ID {gpu['businfo']}"
                )
            exit(1)
        else:
            try:
                gpu = all_results["hwinfo"]["gpu"][gpu_idx]
                gpu_used = gpu_idx
            except Exception:
                click.echo(
                    'Invalid GPU index selected. Please re-run the test with the correct "--gpu" option.'
                )
                click.echo()
                click.echo("Found GPUs:")
                for idx, gpu in enumerate(all_results["hwinfo"]["gpu"]):
                    click.echo(
                        f"  {idx}: {gpu['vendor']} {gpu['product']} bus ID {gpu['businfo']}"
                    )
                exit(1)

        # Handle nVidia multi-card, which needs a sequential ID instead of a bus ID; pass this as an idx to benchmark
        if gpu["vendor"] == "NVIDIA Corporation":
            gpu_arg = [g for g in all_results["hwinfo"]["gpu"] if g["vendor"] == "NVIDIA Corporation"].index(gpu)
        else:
            gpu_arg = gpu["businfo"].replace("@", "-")

    else:
        gpu_used = 0
        gpu = all_results["hwinfo"]["gpu"][0]
        if gpu["vendor"] == "NVIDIA Corporation":
            gpu_arg = 0
        else:
            gpu_arg = gpu["businfo"].replace("@", "-")

    click.echo(f'''Using GPU "{gpu['vendor']} {gpu['product']}"''')
    click.echo()

    for video in test_source_files.values():
        video_url = video["url"]
        video_filename = video_url.split("/")[-1]
        video_filesize = video["size"]
        video_filepath = f"{video_path}/{video_filename}"

        if not os.path.exists(video_filepath):
            click.echo(f'File not found: "{video_filepath}"')
            file_invalid = True
        else:
            actual_filesize = int(
                os.stat(video_filepath).st_size / (1024 * 1024)
            )
            if actual_filesize != video_filesize:
                click.echo(
                    f'File "{video_filepath}" size is invalid: {actual_filesize}MB not {video_filesize}MB'
                )
                file_invalid = True
            else:
                file_invalid = False

        if file_invalid:
            click.echo(
                f'Downloading "{video_filename}" ({video_filesize}MB) to "{video_path}"... ',
                nl="",
            )
            urllib.request.urlretrieve(video_url, f"{video_path}/{video_filename}")
            click.echo("done.")
        else:
            click.echo(
                f'Found valid test file "{video_path}/{video_filename}" ({video_filesize}M).'
            )

        video_files.append(video_filename)

    click.echo()

#Here the Test section is Build!

    all_results["tests"]=[]
    for stream in ffmpeg_streams.items():
        invalid_results = False
        stream_type = stream[0]
        stream_method = stream_type.split("-")[0]
        stream_encode = stream_type.split("-")[1]
        supported_vendors = [gpu["vendor"] for gpu in all_results["hwinfo"]["gpu"]]
        if (
            (stream_method == "nvenc" and "NVIDIA Corporation" not in supported_vendors)
            or (
                stream_method == "vaapi"
                and "Advanced Micro Devices, Inc. [AMD/ATI]" not in supported_vendors
            )
            or (stream_method == "qsv" and "Intel Corporation" not in supported_vendors)
        ):
            continue

        resolutions_elements = []
        click.echo(f"> Running {stream_type} encoder tests")

        for test_source in test_source_files.items():
            source_filename = test_source[1]["url"].split("/")[-1]
            source = test_source[0]
            source_encode = source.split("-")[1]
            source_resolution = source.split("-")[0]
            if stream_encode != source_encode:
                continue
            click.echo(f'>> Running tests with source file "{source_filename}"')

            for scale in scaling.items():
                target_resolution = scale[0]

                resolution_element = dict()
                
                target_scale_name = scale[1]["name"]
                if int(target_resolution.replace("p", "")) > int(
                    source_resolution.replace("p", "")
                ):
                    continue
                
                target_text = f"{source_resolution} -> {target_scale_name}"
                click.echo(f">>> Running {target_text} tests")

                workers = 1
                max_streams = 0
                scaleback = False
                results = {"speed": 2.0}
                average_speed = 2.0
                single_worker_speed = None
                single_worker_rss_kb = 0.0
                runs = None
                while average_speed > 1:
                    click.echo(
                        f">>>> Running test with {workers} simultaneous stream(s)..."
                    )
                    code, failure_reasons, results = do_benchmark(
                        ffmpeg,
                        video_path,
                        source_filename,
                        stream_type,
                        target_resolution,
                        workers,
                        gpu_arg,
                    )

                    if code > 0 and workers == 1:
                        click.echo(
                            f">>>> First worker failed (failure reason(s): {', '.join(failure_reasons)}) with one worker, aborting further tests with this stream type"
                        )
                        invalid_results = True
                        break
                    elif code > 0:
                        if workers > max_streams + 1:
                            click.echo(
                                f">>>> More than one worker failed (failure reason(s): {', '.join(failure_reasons)}) with a large worker delta, scaling back and retrying"
                            )
                            workers -= int((workers - max_streams) / 2)
                            results = {"speed": 2.0}
                            scaleback = True
                            sleep(1)
                            continue
                        else:
                            click.echo(
                                f">>>> More than one worker failed (failure reason(s): {'. '.join(failure_reasons)}) with a small worker delta, aborting further tests at this encoding"
                            )
                            break

                    if not runs:
                        runs=[]
                    runs.append(results)
                    total_speed=0
                    total_frame=0
                    total_time=0
                    #Detect wether the script works correctly on large worker amount (adressing bug)
                    if workers > 10:
                        speed_values = [run["speed"] for run in runs[-10:]]
                        last10_average_speed=sum(speed_values)/len(speed_values)
                        if (last10_average_speed / speed_values[0]) < 0.3: #if the average speed has not gone down more then 0.3 in 10 runs
                            print("-- Infinite Bug Found -- You might want to restart the script!")
                            exit(1)
                        else:
                            print("-- No Infinite Bug happened in this Run --")

                    for worker_results in runs:
                        total_speed += worker_results["speed"]
                        total_frame += worker_results["frame"]
                        total_time += worker_results["time_s"]
                    average_frame = total_frame / workers
                    average_speed = total_speed / workers
                    average_time = total_time / workers
                    click.echo(
                        f">>>> Average worker speed: {average_speed}x @ frame {average_frame}, average time {average_time}s"
                    )
                    if workers == 1:
                        single_worker_speed = results["speed"]
                        single_worker_rss_kb = results["rss_kb"]
                    if results["speed"] >= 4 and not scaleback:
                        max_streams = workers
                        workers *= 4
                        sleep(1)
                    elif results["speed"] >= 2 and not scaleback:
                        max_streams = workers
                        workers *= 2
                        sleep(1)
                    elif results["speed"] > 1:
                        max_streams = workers
                        workers += 1
                        sleep(1)
                    else:
                        break
                if invalid_results:
                    break
                else:
                    if not failure_reasons:
                        failure_reasons = ["performance"]
                    click.echo(
                        f">>> Found max streams for {stream_type} {target_text}: {max_streams}; failure reason(s): {failure_reasons}"
                    )
                    print_results = dict()
                    print_results["max_streams"] = max_streams
                    print_results["failure_reasons"] = failure_reasons
                    print_results["single_worker_speed"] = single_worker_speed
                    print_results["single_worker_rss_kb"] = single_worker_rss_kb
                    resolution_element = {
                    "scale_from": source_resolution, 
                    "scale_to": target_resolution,
                    "runs": runs,
                    "results": print_results,
                    }
                    runs = None
                    resolutions_elements.append(resolution_element)
                    sleep(1)
            if invalid_results:
                print_results = dict()
                print_results["failure_reasons"] = failure_reasons
                resolution_element = {"results": print_results}
                resolutions_elements.append(resolution_element)
                break
        #Differenciating CPU/GPU stream and searching/adding "driver limit" failure reason
            
        if re.match(r"^cpu-", stream_type):
            selected_device = "selected_cpu"
            selected_device_index = 0
        else:
            selected_device = "selected_gpu"
            selected_device_index = gpu_used
            #if (gpu['vendor']=="NVIDIA Corporation"):
            #    patched_driver = any(resolution["results"]["max_streams"] > 5 for resolution in resolutions_elements)
            #    if not patched_driver:
            #        for resolution in resolutions_elements:
            #            resolution["results"]["failure_reasons"].append("driver limit")
        #appending codec results to all_results
        all_results["tests"].append({
            "codec": stream_type,
            selected_device: selected_device_index,
            "resolutions": resolutions_elements,
        })
    return all_results




CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=120)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--ffmpeg",
    "ffmpeg_path",
    type=click.Path(dir_okay=False, exists=True, executable=True),
    default="/usr/lib/jellyfin-ffmpeg/ffmpeg",
    show_default=True,
    required=False,
    help="Path to the Jellyfin FFmpeg binary.",
)
@click.option(
    "--videos",
    "video_path",
    type=click.Path(file_okay=False),
    default="~/hwatest",
    show_default=True,
    required=True,
    help="Directory to store temporary video files.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False),
    default="-",
    show_default=True,
    required=False,
    help="Path to the output JSON file ('-' for stdout).",
)
@click.option(
    "--gpu",
    "gpu_idx",
    type=int,
    default=None,
    show_default=True,
    required=False,
    help="The specific GPU to test in a multi-GPU system.",
)
@click.option(
    "--debug",
    "debug_flag",
    is_flag=True,
    default=False,
    help="Enable additional debug output.",
)
def cli(ffmpeg_path, video_path, output_path, gpu_idx, debug_flag):
    """
    A CPU and Hardware Acceleration (GPU) tester for Jellyfin

    This program runs a series of standardized tests to determine how video
    transcoding will perform on your hardware, with the goal being to provide
    a maximum number of simultaneous streams that can be expected to perform
    adequately (i.e. at at least 1x realtime transcode speed).

    It will run through several possible transcoding methods using Jellyfin's
    FFmpeg binary build, including CPU software transcoding, nVidia NVENC,
    Intel QSV, and AMD AMF, and report the results of any compatible method(s),
    along with anonymous system hardware information in a standardized format.

    To perform the test, the program will download four standardized test files
    totalling 1145 MB from the Jellyfin mirror (credit to jell.yfish.us for the
    original files and www.larmoire.info for the active mirror we could clone).
    The location of these temporary files is set by the "--videos" option.

    The results will be output in JSON format to the output path, either stdout
    (the default) or the path specified by the "--output" option. You can then
    share your results to https://hwa.jellyfin.org to help us build a database
    of available hardware and how well it will perform.

    * NOTE: Obtaining hardware info requires the "lshw" program. Please install
    it before running HWA Tester. On Debian/Ubuntu/derivatives it can be
    installed with "sudo apt install lshw". For other Linux distributions,
    consult your local package manager database.

    * NOTE: For nVidia consumer GPUs, ensure you have applied the driver unlock
    patch to raise the simultaneous stream limit, or you will get erroneous
    (very low) numbers of simultaneous streams in your results.

    * WARNING: This benchmark will be quite stressful on your system and will
    take a very long time to run, especially on lower-end hardware. Ensure you
    run it on a lightly-loaded system and do not perform any heavy workloads,
    including streaming videos in Jellyfin, while the test is running, to
    avoid compromising the results. It is recommended to run the test overnight.
    """

    global debug
    debug = debug_flag

    ffmpeg_path = os.path.expanduser(ffmpeg_path)
    click.echo(f'''Using Jellyfin FFmpeg binary "{ffmpeg_path}"''')
    video_path = os.path.expanduser(video_path)
    click.echo(f'''Using temporary video directory "{video_path}"''')
    output_path = os.path.expanduser(output_path)
    click.echo(f'''Using JSON output file "{output_path}"''')

    if not os.path.exists(video_path):
        os.mkdir(video_path)

    results = benchmark(ffmpeg_path, video_path, gpu_idx)

    click.echo()
    click.echo("Benchmark finished, outputting results...")
    if output_path == "-":
        click.echo()
        click.echo(dumps(results, indent=4))
    else:
        with open(output_path, "w") as fh:
            dump(results, fh, indent=4)


def main():
    return cli(obj={})


if __name__ == "__main__":
    main()