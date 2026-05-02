import os
import json
import subprocess
import requests
import sys
import urllib3
import argparse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def sanitize_folder_name(name, max_length=50):
    """Sanitize and truncate a string to be used as a folder name."""
    invalid_chars = r'\/:*?"<>|'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name[:max_length].strip()

def download_file(url, dest_path, headers=None):
    """Download a file from a URL to a destination path."""
    try:
        response = requests.get(url, headers=headers, stream=True, verify=False)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  Downloaded: {dest_path}")
    except requests.RequestException as e:
        print(f"  ERROR downloading {url}: {e}")

def run_asset_scripts(datablob_path, output_folder):
    """Run the three asset download scripts on a given DataBlob file path."""
    scripts = [
        "download_htr_assets.py",
        "download_png_assets.py",
        "download_jpg_assets.py",
    ]
    for script in scripts:
        script_path = os.path.join(SCRIPT_DIR, script)
        cmd = [sys.executable, script_path, datablob_path, "-o", output_folder]
        print(f"  Running: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR running {script}: {e}")
        except FileNotFoundError:
            print(f"  ERROR: Script not found: {script_path}")

def process_subroom(subroom, room_id, room_folder, auth_headers):
    """Process a single SubRoom: download assets, past versions, and run scripts."""
    subroom_name = sanitize_folder_name(
        subroom.get("Name", f"SubRoom_{subroom.get('SubRoomId', 'unknown')}")
    )
    subroom_id = subroom.get("SubRoomId")
    subroom_folder = os.path.join(room_folder, subroom_name)
    os.makedirs(subroom_folder, exist_ok=True)
    print(f"\n  Processing SubRoom: {subroom_name} (ID: {subroom_id})")

    # Download the DataBlob from CurrentSave
    current_save = subroom.get("CurrentSave") or {}
    datablob = current_save.get("DataBlob")
    if datablob:
        datablob_filename = os.path.basename(datablob)
        datablob_dest = os.path.join(subroom_folder, datablob_filename)
        download_file(f"https://cdn.rec.net/room/{datablob}", datablob_dest)
        run_asset_scripts(datablob_dest, subroom_folder)
    else:
        print(f"  WARNING: No DataBlob found in CurrentSave for SubRoom '{subroom_name}'")

    # Process past versions
    past_versions_folder = os.path.join(subroom_folder, "PastVersions")
    os.makedirs(past_versions_folder, exist_ok=True)

    saves_url = (
        f"https://rooms.rec.net/rooms/{room_id}/subrooms/{subroom_id}/saves/"
        f"no_unity_assets?unityAssetTarget=0&unityAssetVersion=5&skip=0&take=120&isDescendingCreatedAt=True"
    )
    print(f"  Fetching past versions from: {saves_url}")
    try:
        saves_response = requests.get(saves_url, headers=auth_headers, verify=False)
        saves_response.raise_for_status()
        saves_data = saves_response.json()

        # The result is a single {} containing a "Results" []
        if isinstance(saves_data, list):
            saves_data = saves_data[0] if saves_data else {}
        results = saves_data.get("Results", [])

        print(f"  Found {len(results)} past version(s).")
        for idx, save in enumerate(results):
            past_datablob = save.get("DataBlob")
            if not past_datablob:
                print(f"    Skipping past version {idx + 1}: no DataBlob.")
                continue
            past_datablob_filename = os.path.basename(past_datablob)
            past_datablob_dest = os.path.join(past_versions_folder, past_datablob_filename)
            download_file(f"https://cdn.rec.net/room/{past_datablob}", past_datablob_dest)

            # Save the past version JSON alongside the DataBlob
            past_json_filename = os.path.splitext(past_datablob_filename)[0] + ".json"
            past_json_dest = os.path.join(past_versions_folder, past_json_filename)
            with open(past_json_dest, "w", encoding="utf-8") as jf:
                json.dump(save, jf, indent=2)
            print(f"    Saved past version JSON: {past_json_dest}")

            run_asset_scripts(past_datablob_dest, past_versions_folder)

    except requests.RequestException as e:
        print(f"  ERROR fetching past versions for SubRoom '{subroom_name}': {e}")

def process_room(room_entry, auth_headers):
    """Process a single room entry from the input JSON."""
    room_id = room_entry.get("RoomId")
    room_name = sanitize_folder_name(room_entry.get("Name", f"Room_{room_id}"))

    print(f"\n{'='*60}")
    print(f"Processing Room: {room_name} (ID: {room_id})")
    print(f"{'='*60}")

    room_folder = room_name
    os.makedirs(room_folder, exist_ok=True)

    # Fetch full room details
    room_url = f"https://rooms.rec.net/rooms/{room_id}?include=767277"
    print(f"Fetching room data from: {room_url}")
    try:
        room_response = requests.get(room_url, headers=auth_headers, verify=False)
        room_response.raise_for_status()
        room_data = room_response.json()
    except requests.RequestException as e:
        print(f"ERROR fetching room data for '{room_name}': {e}")
        return

    # Write room JSON
    json_path = os.path.join(room_folder, f"{room_name}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(room_data, f, indent=2)
    print(f"Saved room JSON: {json_path}")

    # Download room image
    image_name = room_data.get("ImageName")
    if image_name:
        image_ext = os.path.splitext(image_name)[1] or ".png"
        image_path = os.path.join(room_folder, f"image{image_ext}")
        download_file(f"https://img.rec.net/{image_name}", image_path)
    else:
        print("WARNING: No ImageName found in room data.")

    # Download room DataBlob
    room_datablob = room_data.get("DataBlob")
    if room_datablob:
        room_datablob_filename = os.path.basename(room_datablob)
        download_file(
            f"https://cdn.rec.net/room/{room_datablob}",
            os.path.join(room_folder, room_datablob_filename)
        )
    else:
        print("WARNING: No DataBlob found in room data.")

    # Process SubRooms
    subrooms = room_data.get("SubRooms", [])
    print(f"\nFound {len(subrooms)} SubRoom(s).")
    for subroom in subrooms:
        process_subroom(subroom, room_id, room_folder, auth_headers)

def main():
    print("=== RRExporter ===\n")

    parser = argparse.ArgumentParser(description="RRExporter")
    parser.add_argument("--token", help="Bearer token for authentication")
    parser.add_argument("--json", dest="json_file", help="Path to the JSON file")
    args = parser.parse_args()

    if args.token:
        bearer_token = args.token.strip()
    else:
        print("Enter your Bearer token: ", end="", flush=True)
        bearer_token = sys.stdin.readline().strip()
    if not bearer_token:
        print("ERROR: Bearer token cannot be empty.")
        sys.exit(1)

    if args.json_file:
        json_file_path = args.json_file.strip().strip('"')
    else:
        json_file_path = input("Enter the path to the JSON file: ").strip().strip('"')
    if not os.path.isfile(json_file_path):
        print(f"ERROR: File not found: {json_file_path}")
        sys.exit(1)

    with open(json_file_path, "r", encoding="utf-8") as f:
        try:
            room_list = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse JSON file: {e}")
            sys.exit(1)

    if not isinstance(room_list, list):
        print("ERROR: JSON file must contain a top-level array [].")
        sys.exit(1)

    auth_headers = {"Authorization": f"Bearer {bearer_token}"}

    print(f"\nFound {len(room_list)} room(s) to process.\n")
    for room_entry in room_list:
        process_room(room_entry, auth_headers)

    print("\n\nAll rooms processed successfully.")

if __name__ == "__main__":
    main()
