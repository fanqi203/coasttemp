import json
import sys
import time
import urllib.request
import urllib.error

STATIONS_JS = "multi_state_stations.js"
OUT_JS = "multi_state_temp_cache.js"


def load_stations():
    """Parse multi_state_stations.js and return the stationData list."""
    with open(STATIONS_JS, "r", encoding="utf-8") as f:
        text = f.read()

    prefix = "var stationData ="
    idx = text.find(prefix)
    if idx == -1:
        raise RuntimeError("Could not find 'var stationData =' in %s" % STATIONS_JS)

    s = text[idx + len(prefix):].strip()
    if s.endswith(";"):
        s = s[:-1].strip()

    # Now s should be valid JSON (the array literal)
    return json.loads(s)


def fetch_dv(site_no, start, end):
    """Fetch daily temperature DV series for one site and date range."""
    base = "https://waterservices.usgs.gov/nwis/dv/"
    params = (
        f"?format=json&sites={site_no}"
        f"&parameterCd=00010&startDT={start}&endDT={end}"
    )
    url = base + params

    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    ts_arr = (data.get("value") or {}).get("timeSeries") or []
    if not ts_arr or not ts_arr[0].get("values"):
        return [], []

    vals = ts_arr[0]["values"][0].get("value") or []
    labels, temps = [], []
    for v in vals:
        if not v:
            continue
        val = v.get("value")
        if val in (None, "", " "):
            continue
        dt = v.get("dateTime", "")
        labels.append(dt[:10])
        try:
            temps.append(float(val))
        except ValueError:
            continue

    return labels, temps


def main():
    stations = load_stations()
    cache = {}
    no_dv = []

    for s in stations:
        site = s.get("site_no")
        if not site:
            continue

        # Only stations that have some temperature record and coordinates
        if not s.get("temp_begin") or not s.get("temp_end"):
            continue
        if s.get("lat") is None or s.get("lon") is None:
            continue

        start = s.get("temp_begin")
        end = s.get("temp_end")
        if not start or not end:
            continue

        print(f"Fetching {site} {start} to {end}...", file=sys.stderr)
        try:
            labels, temps = fetch_dv(site, start, end)
        except Exception as e:  # noqa: BLE001 - simple script
            print(f"  ERROR for {site}: {e}", file=sys.stderr)
            continue

        if labels:
            cache[site] = {"labels": labels, "temps": temps}
        else:
            no_dv.append(site)
        time.sleep(0.2)  # be polite to the USGS service

    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("var staticTempCache = ")
        json.dump(cache, f, separators=(",", ":"))
        f.write(";\n")
        f.write("var staticTempNoDv = ")
        json.dump(no_dv, f, separators=(",", ":"))
        f.write(";\n")

    print(
        f"Wrote {len(cache)} site(s) with DV temp and {len(no_dv)} with no DV to {OUT_JS}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

