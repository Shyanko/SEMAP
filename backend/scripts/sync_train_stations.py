from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.migrate import run_migrations
from app.train_stations import (
    BaiduQuotaExceeded,
    SEED_CSV,
    baidu_api_key,
    baidu_place_search,
    import_station_seed,
    in_china_bbox,
    missing_coordinate_station_rows,
    missing_coordinate_stations,
    parse_12306_station_names,
    reject_station_coordinate,
    save_station_coordinate_miss,
    save_station_coordinate,
    station_coverage,
    upsert_12306_stations,
)

STATION_NAME_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SEMAP train station sync/1.0 (https://semap.xyz)"


def fetch_12306_station_names() -> list[dict[str, Any]]:
    with httpx.Client(timeout=30, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        response = client.get(STATION_NAME_URL)
        response.raise_for_status()
    return parse_12306_station_names(response.text)


def result_matches_station(name: str, result: dict[str, Any]) -> bool:
    try:
        lat = float(result["lat"])
        lng = float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    if not in_china_bbox(lat, lng):
        return False

    address = result.get("address") or {}
    if address.get("country_code") and address["country_code"].lower() != "cn":
        return False

    display = " ".join(
        str(value)
        for value in [
            result.get("display_name"),
            result.get("name"),
            (result.get("namedetails") or {}).get("name"),
            address.get("railway"),
            address.get("station"),
        ]
        if value
    )
    targets = [name, f"{name}站", f"{name}火车站"]
    return any(target in display for target in targets)


def fill_missing_with_baidu(limit: int, delay_seconds: float) -> int:
    key = baidu_api_key()
    if limit <= 0 or not key:
        return 0

    rows = missing_coordinate_station_rows(limit, skipped_source="baidu_place")
    filled = 0
    with httpx.Client(timeout=20, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        for index, row in enumerate(rows):
            name = row["name"] or ""
            try:
                result = baidu_place_search(client, name, row["city"], key)
            except BaiduQuotaExceeded as error:
                print(f"百度地点检索停止：{error}")
                break
            except (httpx.HTTPError, ValueError, RuntimeError) as error:
                print(f"百度地点检索跳过：{name}，{error}")
                result = None
            if result:
                lat, lng, raw = result
                if raw.get("result"):
                    save_station_coordinate(name, lat, lng, "baidu_place", raw["query"], raw)
                    filled += 1
                else:
                    save_station_coordinate_miss(name, "baidu_place", raw["query"], raw)
            if index < len(rows) - 1:
                time.sleep(delay_seconds)
    return filled


def nominatim_search(client: httpx.Client, name: str) -> tuple[float, float, dict[str, Any]] | None:
    query = f"{name}火车站 中国"
    response = client.get(
        NOMINATIM_SEARCH_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": "5",
            "countrycodes": "cn",
            "addressdetails": "1",
            "namedetails": "1",
        },
    )
    response.raise_for_status()
    results = response.json()
    accepted = next((item for item in results if result_matches_station(name, item)), None)
    if not accepted:
        reject_station_coordinate(name, "nominatim", query, {"results": results})
        return None
    return float(accepted["lat"]), float(accepted["lon"]), {"query": query, "result": accepted}


def fill_missing_with_nominatim(limit: int, delay_seconds: float) -> int:
    if limit <= 0:
        return 0
    names = missing_coordinate_stations(limit)
    filled = 0
    with httpx.Client(timeout=30, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
        for index, name in enumerate(names):
            result = nominatim_search(client, name)
            if result:
                lat, lng, raw = result
                save_station_coordinate(name, lat, lng, "nominatim", raw["query"], raw)
                filled += 1
            if index < len(names) - 1:
                time.sleep(delay_seconds)
    return filled


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 12306 火车站名并补全站点坐标。")
    parser.add_argument("--seed-csv", type=Path, default=SEED_CSV)
    parser.add_argument("--baidu-limit", type=int, default=0)
    parser.add_argument("--baidu-delay", type=float, default=0.1)
    parser.add_argument("--nominatim-limit", type=int, default=0)
    parser.add_argument("--nominatim-delay", type=float, default=1.2)
    args = parser.parse_args()

    run_migrations()
    stations = fetch_12306_station_names()
    synced = upsert_12306_stations(stations)
    seeded = import_station_seed(args.seed_csv)
    baidu_filled = fill_missing_with_baidu(args.baidu_limit, args.baidu_delay)
    nominatim_filled = fill_missing_with_nominatim(args.nominatim_limit, args.nominatim_delay)
    coverage = station_coverage()

    print("火车站坐标同步完成")
    print(f"12306 站名：{synced}")
    print(f"种子坐标：{seeded}")
    print(f"百度地点检索补全：{baidu_filled}")
    print(f"Nominatim 补全：{nominatim_filled}")
    print(f"坐标覆盖：{coverage['verified']}/{coverage['total']}")
    print(f"缺失坐标：{coverage['missing']}")
    print(f"已拒绝结果：{coverage['rejected']}")


if __name__ == "__main__":
    main()
