import pytest

from app.train_stations import (
    AmapQuotaExceeded,
    BaiduQuotaExceeded,
    amap_place_search,
    amap_result_matches_station,
    baidu_place_search,
    baidu_result_matches_station,
)


def test_baidu_result_matches_station_by_name():
    result = {
        "name": "云梦东站",
        "address": "湖北省孝感市云梦县",
        "location": {"lat": 31.0479946, "lng": 113.7788677},
        "detail_info": {"tag": "交通设施;火车站"},
    }

    assert baidu_result_matches_station("云梦东", result) is True


def test_baidu_result_rejects_foreign_coordinate():
    result = {
        "name": "大阪站",
        "address": "日本大阪府",
        "location": {"lat": 34.702485, "lng": 135.495951},
        "detail_info": {"tag": "交通设施;火车站"},
    }

    assert baidu_result_matches_station("大板", result) is False


def test_baidu_result_rejects_unmatched_station_name():
    result = {
        "name": "云梦站",
        "address": "湖北省孝感市云梦县",
        "location": {"lat": 31.0362, "lng": 113.752},
        "detail_info": {"tag": "交通设施;火车站"},
    }

    assert baidu_result_matches_station("云梦东", result) is False


def test_baidu_result_rejects_bus_station():
    result = {
        "name": "房山东大桥",
        "address": "831路;836路;839路",
        "location": {"lat": 39.699467, "lng": 115.997242},
        "detail_info": {"tag": "交通设施;公交车站", "classified_poi_tag": "交通设施;公交车站"},
    }

    assert baidu_result_matches_station("房山东", result) is False


def test_baidu_result_rejects_subway_station():
    result = {
        "name": "重庆东站",
        "address": "重庆市南岸区",
        "location": {"lat": 29.484885, "lng": 106.672364},
        "detail_info": {"tag": "交通设施;地铁站", "classified_poi_tag": "交通设施;地铁站"},
    }

    assert baidu_result_matches_station("重庆东", result) is False


def test_baidu_result_requires_station_name_in_poi_name():
    result = {
        "name": "太原南站",
        "address": "山西省太原市小店区北营北路",
        "location": {"lat": 37.791433, "lng": 112.61114},
        "detail_info": {"tag": "交通设施;火车站", "classified_poi_tag": "交通设施;火车站;高铁站"},
    }

    assert baidu_result_matches_station("北营", result) is False


class BaiduResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "status": 0,
            "results": [
                {
                    "name": "云梦东站",
                    "address": "湖北省孝感市云梦县",
                    "location": {"lat": 31.0479946, "lng": 113.7788677},
                    "detail_info": {"tag": "交通设施;火车站"},
                }
            ],
        }


class BaiduClient:
    def __init__(self):
        self.params = None

    def get(self, _url, params):
        self.params = params
        return BaiduResponse()


def test_baidu_place_search_uses_city_and_gcj02():
    client = BaiduClient()

    lat, lng, raw = baidu_place_search(client, "云梦东", "孝感", "ak")

    assert (lat, lng) == (31.0479946, 113.7788677)
    assert client.params["query"] == "云梦东站"
    assert client.params["region"] == "孝感"
    assert client.params["region_limit"] == "true"
    assert client.params["ret_coordtype"] == "gcj02ll"
    assert raw["coordinateSystem"] == "gcj02"


class BaiduQuotaResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"status": 302, "message": "天配额超限，限制访问"}


class BaiduQuotaClient:
    def get(self, _url, params):
        return BaiduQuotaResponse()


def test_baidu_place_search_detects_quota_limit():
    with pytest.raises(BaiduQuotaExceeded):
        baidu_place_search(BaiduQuotaClient(), "北京", "北京", "ak")


def test_amap_result_matches_station_by_name_and_typecode():
    result = {
        "name": "云梦东站",
        "type": "交通设施服务;火车站;火车站",
        "typecode": "150200",
        "location": "113.7788677,31.0479946",
    }

    assert amap_result_matches_station("云梦东", result) is True


def test_amap_result_rejects_unmatched_station_name():
    result = {
        "name": "太原南站",
        "type": "交通设施服务;火车站;火车站",
        "typecode": "150200",
        "location": "112.61114,37.791433",
    }

    assert amap_result_matches_station("北营", result) is False


def test_amap_result_rejects_non_railway_poi():
    result = {
        "name": "房山东大桥",
        "type": "交通设施服务;公交车站;公交车站相关",
        "typecode": "150700",
        "location": "115.997242,39.699467",
    }

    assert amap_result_matches_station("房山东", result) is False


class AmapResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "status": "1",
            "pois": [
                {
                    "name": "云梦东站",
                    "type": "交通设施服务;火车站;火车站",
                    "typecode": "150200",
                    "location": "113.7788677,31.0479946",
                }
            ],
        }


class AmapClient:
    def __init__(self):
        self.params = None

    def get(self, _url, params):
        self.params = params
        return AmapResponse()


def test_amap_place_search_uses_city_and_gcj02():
    client = AmapClient()

    lat, lng, raw = amap_place_search(client, "云梦东", "孝感", "key")

    assert (lat, lng) == (31.0479946, 113.7788677)
    assert client.params["keywords"] == "云梦东站"
    assert client.params["region"] == "孝感"
    assert client.params["city_limit"] == "true"
    assert client.params["types"] == "150200"
    assert raw["coordinateSystem"] == "gcj02"


class AmapQuotaResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "0", "info": "DAILY_QUERY_OVER_LIMIT"}


class AmapQuotaClient:
    def get(self, _url, params):
        return AmapQuotaResponse()


def test_amap_place_search_detects_quota_limit():
    with pytest.raises(AmapQuotaExceeded):
        amap_place_search(AmapQuotaClient(), "北京", "北京", "key")
