#!/usr/bin/env python3
import argparse
import os
import re
import sys
import urllib.request
import urllib.error

ALNUM = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

def extract_ids(text: str):
    ids = []
    i = 0
    while True:
        j = text.find(".jpg", i)
        if j == -1:
            break

        # Walk backward from the character immediately before ".htr"
        k = j - 1
        while k >= 0 and text[k] in ALNUM:
            k -= 1

        prefix = text[k+1:j]  # alnum run directly before ".htr"
        if prefix:  # only accept if there was at least 1 alnum char
            ids.append(prefix + ".jpg")

        i = j + 4  # move past ".htr"
    return ids

def download(url: str, out_path: str, timeout: int = 30, overwrite: bool = False):
    if (not overwrite) and os.path.exists(out_path):
        return "exists"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "htr-downloader/1.0"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)
        return "ok"
    except urllib.error.HTTPError as e:
        return f"http_error:{e.code}"
    except Exception as e:
        return f"error:{type(e).__name__}"

def main():
    ap = argparse.ArgumentParser(description="Find <alnum>+.htr references and download them from cdn.rec.net")
    ap.add_argument("file", help="Path to input file to scan")
    ap.add_argument("-o", "--out", default="downloads", help="Output directory (default: downloads)")
    ap.add_argument("--keep-duplicates", action="store_true", help="Download even if the same .htr appears multiple times")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    ap.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds (default: 30)")
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        raw = f.read()

    # Decode leniently so it works on random/binary-ish files too
    text = raw.decode("utf-8", errors="ignore")

    found = extract_ids(text)
    if not args.keep_duplicates:
        # preserve order while deduping
        seen = set()
        found = [x for x in found if not (x in seen or seen.add(x))]

    if not found:
        print("No <alnum>+.jpg matches found.")
        return 0

    print(f"Found {len(found)} unique .jpg references.")
    base = "https://img.rec.net/"

    ok = 0
    for name in found:
        url = base + name
        out_path = os.path.join(args.out, name)
        status = download(url, out_path, timeout=args.timeout, overwrite=args.overwrite)
        print(f"{status:>14}  {url}  ->  {out_path}")
        if status == "ok" or status == "exists":
            ok += 1

    print(f"Done. Successful/exists: {ok}/{len(found)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
