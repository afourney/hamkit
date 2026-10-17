# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Private compatibility views for historical receiver policies.

The public codec remains loss-conscious and profile-independent. These adapters
express the corpus's older receiver conventions without changing public models,
rewriting archived packets, or consulting expected fixture values.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from . import _data as d
from . import _extensions, _messages, _mic_e
from . import _models as m
from ._codec import parse_packet, parse_payload
from ._errors import APRSError
from ._json import to_json_dict


def _relaxed_telemetry(raw: bytes) -> d.Telemetry:
    parts = raw[2:].split(b",")
    if len(parts) < 2 or not parts[0].isdigit():
        raise ValueError("invalid telemetry sequence")
    values: list[float | None] = [None] * 5
    for i, v in enumerate(parts[1:6]):
        v = v.strip()
        if not v:
            continue
        if not re.fullmatch(rb"-?(?:\d*\.)?\d+", v):
            if v == b"-" or v.endswith(b"."):
                raise ValueError("invalid telemetry value")
            break
        values[i] = float(v)
    bits = parts[6].strip()[:8] if len(parts) > 6 else b""
    digital = tuple(c == 49 for c in bits) if re.fullmatch(rb"[01]{8}", bits) else ()
    return d.Telemetry(
        tuple(values), digital, sequence=int(parts[0]), encoding="compatibility"
    )


def _mic_e_compat(raw: bytes, header: m.Header, broken: bool):
    body = raw[1:]
    mangled = False
    if (
        broken
        and len(body) >= 7
        and body[6:7] in (b"/", b"\\")
        and body[7:8] not in (b"/", b"\\")
    ):
        body = body[:5] + b" " + body[5:]
        mangled = True
    # The old receiver reads comment telemetry before DAO and accepts a
    # short apostrophe hex block as channels 1 and 3.
    tail = body[8:]
    extra, tail = _extensions.read(tail, d.Symbol(chr(body[7]), chr(body[6])))
    altitude = None
    match = re.search(rb"([!-{]{3})\}", tail)
    if match:
        from ._position_codec import base91

        altitude = d.Altitude(
            d.Measurement(base91(match[1]) - 10000, "meters"), "mic_e"
        )
        tail = tail[: match.start()] + tail[match.end() :]
    telemetry = extra.telemetry
    match = re.match(rb"'([0-9A-Fa-f]{10}|[0-9A-Fa-f]{4})", tail)
    short = False
    if match:
        values = tuple(bytes.fromhex(match[1].decode()))
        short = len(values) == 2
        if short:
            values = (values[0], 0, values[1])
        telemetry = d.Telemetry(values, encoding="compatibility")
        tail = tail[match.end() :].lstrip(b" ")
    base = _mic_e.read(raw[:1] + body[:8], header, [])
    e = replace(
        extra,
        motion=None if mangled else base.extensions.motion,
        altitude=altitude or extra.altitude,
        telemetry=telemetry,
    )
    from ._position_codec import dao_offset

    p = replace(
        base,
        extensions=e,
        latitude_deg=dao_offset(base.latitude_deg, e.dao, "latitude"),
        longitude_deg=dao_offset(base.longitude_deg, e.dao, "longitude"),
        comment=tail.decode("utf8", errors="replace"),
    )
    return p, mangled, short


def _weather_view(w: dict[str, Any]) -> dict[str, Any]:
    w = dict(w)
    for name in (
        "wind_speed",
        "gust",
        "temperature",
        "rain_1h",
        "rain_24h",
        "rain_since_midnight",
        "snow_24h",
    ):
        reading = w.get(name)
        if reading is None:
            continue
        reading = dict(reading)
        v = reading["value"]
        unit = reading["unit"]
        if name in ("wind_speed", "gust"):
            if unit in ("mph", "disputed_knots_or_mph"):
                factor = 0.44704
            elif unit == "knots":
                factor = 1852 / 3600
            elif unit == "km/h":
                factor = 1 / 3.6
            else:
                factor = 1
            reading.update(value=None if v is None else v * factor, unit="m/s")
        elif name == "temperature" and unit == "fahrenheit":
            reading.update(value=None if v is None else (v - 32) / 1.8, unit="celsius")
        elif unit == "inches":
            reading.update(value=None if v is None else v * 25.4, unit="mm")
        w[name] = reading
    return w


def _receiver_rejects(raw: bytes, p: m.Packet | m.Malformed, options: dict) -> bool:
    envelope, sep, body = raw.partition(b":")
    source, arrow, route = envelope.partition(b">")
    fields = route.split(b",")
    if not sep or not arrow or not re.fullmatch(rb"[A-Za-z0-9-]{1,9}", source):
        return True
    if not re.fullmatch(rb"[A-Za-z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?", fields[0]):
        return True
    seen_q = False
    for hop in fields[1:]:
        hop = hop.removesuffix(b"*")
        if re.fullmatch(rb"q[A-Z][A-Z]", hop):
            seen_q = True
        if not re.fullmatch(rb"[A-Za-z0-9-]{1,9}", hop) and not (
            seen_q and re.fullmatch(rb"[A-Za-z0-9-]+", hop)
        ):
            return True
    if body.startswith((b"{", b"$GPVTG")):
        return True
    if (
        isinstance(p, m.Packet)
        and isinstance(p.payload, m.NMEA)
        and p.payload.position_usable is False
    ):
        return True
    if isinstance(p, m.Malformed):
        return True
    if isinstance(p.payload, m.Beacon) and body[:1] not in (b" ", b"h", b"U"):
        return True
    if options.get("ax25") and any(
        x.code == "nonconforming" and ".header" in x.path for x in p.diagnostics
    ):
        return True
    return isinstance(p.payload, m.Opaque)


def view(
    raw: bytes, profile: str, options: dict | None = None
) -> tuple[dict[str, Any], bool]:
    options = options or {}
    packet = parse_packet(
        raw,
        profile=(
            "rf" if profile == "strict-envelope" or options.get("ax25") else "monitor"
        ),
    )
    result: dict[str, Any] = to_json_dict(packet, include_defaults=True)
    rejected = (
        isinstance(packet, m.Malformed)
        or isinstance(packet, m.Packet)
        and any(x.code == "nonconforming" for x in packet.diagnostics)
    )
    if profile != "compatibility-fap":
        if (
            isinstance(packet, m.Packet)
            and isinstance(packet.payload, m.LegacyPosition)
            and profile != "historical-1.0"
        ):
            result["payload"] = to_json_dict(
                m.Beacon(raw.partition(b":")[2].decode("latin1")), include_defaults=True
            )
        if (
            isinstance(packet, m.Packet)
            and isinstance(packet.payload, m.LegacyPosition)
            and profile == "historical-1.0"
        ):
            result["payload"] = to_json_dict(
                packet.payload.position, include_defaults=True
            )
        return result, rejected
    _envelope, _, body = raw.partition(b":")
    header = packet.header
    if header is None:
        return result, True
    payload: m.Payload | m.Malformed | None = (
        packet.payload if isinstance(packet, m.Packet) else None
    )
    short = False
    try:
        if body[:1] in (b"`", b"'"):
            payload, _mangled, short = _mic_e_compat(
                body, header, options.get("accept_broken_mice", False)
            )
        elif body.startswith(b"T#"):
            payload = _relaxed_telemetry(body)
        elif body[:1] == b":" and body[11:16].upper() in (
            b"PARM.",
            b"UNIT.",
            b"EQNS.",
            b"BITS.",
        ):
            payload = _messages.definition(
                body[1:10].decode().rstrip(), body[11:16].upper() + body[16:]
            )
        elif isinstance(packet, m.Malformed) and (
            body[:1] in (b"@", b"/", b">")
            and body[1:8] == b"000000z"
            or body[:1] == b";"
            and body[10:11] in (b"*", b"_")
            and body[11:18] == b"000000z"
        ):
            # Invalid timestamps are warnings in FAP; decode the intact fields.
            if body[:1] in (b"@", b"/"):
                payload = parse_payload((b"=" if body[:1] == b"@" else b"!") + body[8:])
            elif body[:1] == b">":
                payload = _messages.status(body[8:], [])
            elif body[:1] == b";":
                position = parse_payload(b"!" + body[18:])
                if isinstance(position, m.Position):
                    data = to_json_dict(position, include_defaults=True)
                    data.update(
                        type="object",
                        name=body[1:10].decode().rstrip(),
                        alive=body[10:11] == b"*",
                    )
                    data.pop("messaging", None)
                    result = {
                        "type": "packet",
                        "header": to_json_dict(header, include_defaults=True),
                        "payload": data,
                        "original_wire": raw.decode("latin1"),
                    }
                    payload = None
        elif isinstance(packet, m.Malformed) and body.startswith(b"$GPGLL,"):
            from ._nmea_codec import _coordinates

            values = body.split(b",")[1:]
            if len(values) == 4:
                coords = _coordinates([v.decode() for v in values])
                assert coords is not None
                result = {
                    "type": "packet",
                    "header": to_json_dict(header, include_defaults=True),
                    "payload": {
                        "type": "nmea",
                        "sentence": {
                            "type": "gll",
                            "coordinates": to_json_dict(coords),
                        },
                    },
                    "original_wire": raw.decode("latin1"),
                }
                payload = None
    except (APRSError, ValueError, IndexError):
        return result, True
    if isinstance(payload, m.Malformed):
        return result, True
    if payload is not None:
        result = {
            "type": "packet",
            "header": to_json_dict(header, include_defaults=True),
            "payload": to_json_dict(payload, include_defaults=True),
            "original_wire": raw.decode("latin1"),
        }
    if result.get("type") != "packet":
        return result, True
    p = result.get("payload", {})
    if p.get("type") == "legacy_position":
        p = result["payload"] = p["position"]
        p["type"] = "position"
    if p.get("type") == "raw_weather" and p.get("weather"):
        p = result["payload"] = p["weather"]
        p["type"] = "weather"
    if p.get("type") == "nmea":
        p["symbol"] = None
        if p["sentence"].get("course_deg") is not None:
            p["sentence"]["course_deg"] = round(p["sentence"]["course_deg"])
    if p.get("type") == "mic_e":
        if short:
            assert (
                isinstance(payload, m.MicE) and payload.extensions.telemetry is not None
            )
            p["extensions"]["telemetry"]["analog"] = list(
                payload.extensions.telemetry.analog
            )
        if (
            p.get("extensions", {}).get("telemetry")
            and p["extensions"]["telemetry"].get("sequence") is None
        ):
            p["extensions"]["telemetry"]["sequence"] = 0
    if p.get("type") == "telemetry":
        p["comment"] = ""
    if "comment" in p and not p.get("extensions", {}).get("phg"):
        p["comment"] = p["comment"].strip()
    if p.get("type") == "object":
        p["name"] = p["name"].rstrip()
    compression = p.get("compression")
    if compression:
        motion = p.get("extensions", {}).get("motion")
        if motion and motion.get("course_deg") == 0:
            motion["course_deg"] = 360
    weather = (
        p if p.get("type") == "weather" else p.get("extensions", {}).get("weather")
    )
    if weather is not None:
        code = (weather.get("software_code") or "") + (weather.get("device_code") or "")
        if re.fullmatch(r"[XV]\d{3}", code):
            weather["software_code"] = weather["device_code"] = None
        tail = p.get("comment", "")
        while tail:
            match = re.match(r"(Os|[LFXV])([. ]{3,4}|-?\d+(?:\.\d+)?)", tail)
            if not match:
                break
            tag, field = match.groups()
            if tag == "Os":
                weather["snow_24h"] = {
                    "value": None if field.strip(". ") == "" else float(field) * 0.01,
                    "unit": "inches",
                }
            elif tag == "L":
                weather["luminosity"] = {
                    "value": None if field.strip(". ") == "" else float(field),
                    "unit": "W/m2",
                }
            tail = tail[match.end() :]
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,4}", tail):
            weather["software_code"], weather["device_code"] = tail[0], tail[1:]
            tail = ""
        if tail != p.get("comment", ""):
            p["comment"] = tail
            if p.get("type") == "weather":
                weather["comment"] = tail
        converted = _weather_view(weather)
        if p.get("type") == "weather":
            result["payload"] = converted
        else:
            p["extensions"]["weather"] = converted
            if compression:
                wind = weather.get("wind_direction")
                speed = weather.get("wind_speed")
                p["extensions"]["motion"] = (
                    {"course_deg": wind["value"], "speed_knots": speed["value"]}
                    if wind and speed
                    else None
                )
                converted["wind_direction"] = converted["wind_speed"] = None
    if (
        isinstance(payload, m.Position)
        and payload.symbol.code == "_"
        and payload.extensions.weather is None
    ):
        p["extensions"]["weather"] = {}
        p["comment"] = ""
    result["header"]["destination"] = result["header"]["destination"].upper()
    if options.get("ax25"):
        result["header"]["source"] = result["header"]["source"].upper()
    rejected = _receiver_rejects(raw, packet, options)
    if result.get("type") == "packet" and isinstance(packet, m.Malformed):
        rejected = False
    return result, rejected


def facts(raw: bytes, options: dict | None = None) -> dict[str, Any]:
    """Historical receiver facts not represented as stored public-model fields.

    These include display resolution, raw timestamps, and optional vendor sensors.
    Kept separate so a receiver policy cannot alter the public JSON contract.
    """
    options = options or {}
    projected, _ = view(raw, "compatibility-fap", options)
    p = projected.get("payload", {})
    packet = parse_packet(raw)
    body = raw.partition(b":")[2]
    ext = p.get("extensions", {})
    comp = p.get("compression")
    dao = ext.get("dao")
    sym = p.get("symbol") or {}
    result = {
        "Capabilities": None,
        "ChecksumOK": None,
        "DaoDatumByte": (
            dao["datum_byte"].upper() if dao and dao.get("encoding") else None
        ),
        "GPSFixStatus": None,
        "MBits": "",
        "MiceMangled": False,
        "ObjectName": p.get("name", "") if p.get("type") == "object" else "",
        "ItemName": p.get("name", "") if p.get("type") == "item" else "",
        "PosResolution": None,
        "RawTimestamp": "",
        "Warnings": None,
        "PosAmbiguity": (
            p.get("ambiguity") if "latitude_deg" in p and comp is None else None
        ),
        "SymbolCode": sym.get("code"),
    }
    if p.get("type") == "capabilities":
        result["Capabilities"] = {t["name"]: t["value"] or "" for t in p["tokens"]}
    if "latitude_deg" in p:
        result["PosResolution"] = (
            0.291
            if comp
            else (18.52, 185.2, 1852, 18520, 111120)[p.get("ambiguity", 0)]
        )
    if comp and not comp["ignored"]:
        result["GPSFixStatus"] = int(comp["fix"] == "current")
    if dao and dao.get("encoding"):
        result["PosResolution"] = 1.852 if dao["encoding"] == "decimal" else 0.1852
    if body[:1] in (b"`", b"'"):
        assert packet.header is not None
        dest = packet.header.destination.split("-")[0]
        result["MBits"] = "".join(
            "1" if "A" <= c <= "K" or "P" <= c <= "Z" else "0" for c in dest[:3]
        )
        _, result["MiceMangled"], _ = _mic_e_compat(
            body, packet.header, options.get("accept_broken_mice", False)
        )
    if options.get("raw_timestamp") and body[:1] in (b"/", b"@"):
        result["RawTimestamp"] = body[1:7].decode()
    if (body[:1] in (b"/", b"@", b">") and body[1:8] == b"000000z") or (
        body[:1] == b";" and body[11:18] == b"000000z"
    ):
        result["Warnings"] = [
            {
                "Code": "timestamp_inv",
                "Msg": "invalid "
                + ("object " if body[:1] == b";" else "")
                + "timestamp: invalid day: 00",
            }
        ]
    if isinstance(packet, m.Packet) and isinstance(packet.payload, m.NMEA):
        n = packet.payload
        result["ChecksumOK"] = n.metadata.checksum_valid
        fields = n.metadata.fields_raw
        from . import _nmea as sentences

        if isinstance(n.sentence, sentences.RMC):
            indices = (2, 4)
        elif isinstance(n.sentence, sentences.GGA):
            indices = (1, 3)
        else:
            indices = (0, 2)
        result["PosResolution"] = max(
            1852 * 10 ** (-len(fields[i].partition(b".")[2])) for i in indices
        )
        if isinstance(n.sentence, sentences.RMC) and not options.get("raw_timestamp"):
            date = n.sentence.date_ddmmyy
            time = n.sentence.time_utc
            # The historical receiver uses the conventional 1980 pivot.
            year = int(date[4:6])
            year += 1900 if year >= 80 else 2000
            result[
                "Timestamp"
            ] = f"{year:04d}-{date[2:4]}-{date[:2]}T{time[:2]}:{time[2:4]}:{time[4:6]}Z"
    elif body.startswith(b"$GPGLL,"):
        fields = tuple(body.split(b",")[1:])
        result["PosResolution"] = max(
            1852 * 10 ** (-len(fields[i].partition(b".")[2])) for i in (0, 2)
        )
    if body.startswith(b":"):
        content = body[11:]
        result["Message"] = {
            "RejID": content[3:].decode() if content.startswith(b"rej") else ""
        }
    wx = p if p.get("type") == "weather" else ext.get("weather")
    if wx is not None:
        extra = {
            "BatteryVoltage": None,
            "HumidityIn": None,
            "Radiation": None,
            "Software": (wx.get("software_code") or "") + (wx.get("device_code") or ""),
            "TempIn": None,
            "WaterLevel": None,
        }
        match = (
            re.search(rb"F(-?\d{3,4})(?![\d.])", body)
            if not body.startswith((b"$ULTW", b"!!"))
            else None
        )
        if match:
            extra["WaterLevel"] = int(match[1]) * 0.03048
        match = re.search(rb"X(\d{3})", body)
        if match:
            code = int(match[1])
            extra["Radiation"] = (code // 10) * 10 ** (code % 10)
        match = re.search(rb"V(\d{3})", body)
        if match:
            extra["BatteryVoltage"] = int(match[1]) / 10
        if body.startswith(b"!!"):
            fields = tuple(body[i : i + 4] for i in range(2, len(body), 4))
            if len(fields) > 5 and re.fullmatch(rb"[0-9A-Fa-f]{4}", fields[5]):
                value = int(fields[5], 16)
                value = value - 65536 if value >= 32768 else value
                extra["TempIn"] = round((value / 10 - 32) / 1.8, 1)
            if len(fields) > 7 and re.fullmatch(rb"[0-9A-Fa-f]{4}", fields[7]):
                value = int(fields[7], 16) // 10
                if 1 <= value <= 100:
                    extra["HumidityIn"] = value
        result["Wx"] = extra
    return result


def rejected_facts(raw: bytes, options: dict | None = None) -> dict[str, Any]:
    """Recover the historical receiver's facts up to its rejecting field.

    Unlike the public Malformed recovery, this view follows the old receiver's
    validation order. It preserves useful partial observations without making a
    partially valid public dataclass or inventing missing fields.
    """
    from datetime import datetime
    from functools import reduce
    from operator import xor

    from . import _position_codec as pc
    from ._fields.position import decode_coordinate
    from ._nmea_codec import _coordinate

    options = options or {}
    h: dict[str, Any] = {"source": "", "destination": "", "digipeaters": None}
    f: dict[str, Any] = {
        key: None
        for key in (
            "Latitude",
            "Longitude",
            "PosAmbiguity",
            "PosResolution",
            "SymbolTable",
            "SymbolCode",
            "Speed",
            "Course",
            "Altitude",
            "Messaging",
            "RadioRange",
            "Alive",
            "Message",
            "Wx",
            "TelemetryData",
            "Capabilities",
            "DaoDatumByte",
            "GPSFixStatus",
            "ChecksumOK",
            "Warnings",
        )
    }
    f.update(
        {
            key: ""
            for key in (
                "Type",
                "Format",
                "PHG",
                "RawTimestamp",
                "ObjectName",
                "ItemName",
                "Status",
                "MBits",
                "Comment",
            )
        }
    )
    f["MiceMangled"] = False
    result = {"fap_header": h, "fap_fields": f}
    envelope, colon, body = raw.partition(b":")
    source, arrow, route = envelope.partition(b">")
    if not colon or not arrow:
        return result
    h["source"] = source.decode("latin1")
    ax25 = rb"[A-Z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?"
    if not re.fullmatch(ax25 if options.get("ax25") else rb"[A-Za-z0-9-]{1,9}", source):
        return result
    fields = route.split(b",")
    if options.get("ax25") and len(fields) > 9:
        return result
    if not re.fullmatch(ax25, fields[0].upper()):
        return result
    h["destination"] = fields[0].decode().upper()
    hops = []
    seen_q = False
    for field in fields[1:]:
        call = field.removesuffix(b"*")
        if not call:
            return result
        if re.fullmatch(rb"q[A-Z][A-Za-z]", call):
            seen_q = True
        pattern = (
            ax25
            if options.get("ax25")
            else rb"[A-Za-z0-9-]+"
            if seen_q
            else rb"[A-Za-z0-9-]{1,9}"
        )
        if not re.fullmatch(pattern, call):
            return result
        hops.append({"Call": call.decode(), "WasDigied": field.endswith(b"*")})
        h["digipeaters"] = hops
    if not body:
        return result
    header = m.Header(h["source"], h["destination"])
    if body.startswith(b"$"):
        f.update(Type="location", Format="nmea")
        if not body.startswith(b"$GP"):
            return result
        data, star, checksum = body.rstrip().partition(b"*")
        if star and re.fullmatch(rb"[0-9A-Fa-f]{2}", checksum):
            if reduce(xor, data[1:], 0) != int(checksum, 16):
                return result
            f["ChecksumOK"] = True
        fields = data.split(b",")
        kind = fields[0]
        if kind not in (b"$GPRMC", b"$GPGGA", b"$GPGLL"):
            return result
        required = {b"$GPRMC": 10, b"$GPGGA": 15, b"$GPGLL": 5}[kind]
        if len(fields) < required:
            return result
        if kind == b"$GPRMC":
            if fields[2] != b"A":
                return result
            time = fields[1].partition(b".")[0]
            date = fields[9]
            if not re.fullmatch(rb"\d{6}", time) or not re.fullmatch(rb"\d{6}", date):
                return result
            year = int(date[4:])
            year += 1900 if year >= 80 else 2000
            try:
                stamp = datetime(
                    year,
                    int(date[2:4]),
                    int(date[:2]),
                    int(time[:2]),
                    int(time[2:4]),
                    int(time[4:]),
                )
            except ValueError:
                return result
            f["Timestamp"] = stamp.isoformat() + "Z"
            lat_index, lon_index = 3, 5
        elif kind == b"$GPGGA":
            if fields[6] == b"0":
                return result
            lat_index, lon_index = 2, 4
        else:
            lat_index, lon_index = 1, 3
        try:
            f["Latitude"] = _coordinate(
                fields[lat_index].decode(), fields[lat_index + 1].decode(), 2
            )
            f["Longitude"] = _coordinate(
                fields[lon_index].decode(), fields[lon_index + 1].decode(), 3
            )
        except (APRSError, UnicodeError):
            pass
        return result
    if body[:1] in (b"`", b"'"):
        f.update(Type="location", Format="mice")
        data = body[1:]
        if (
            options.get("accept_broken_mice")
            and len(data) >= 7
            and data[6:7] in (b"/", b"\\")
            and data[7:8] not in (b"/", b"\\")
        ):
            f["MiceMangled"] = True
            data = data[:5] + b" " + data[5:]
        if len(data) < 8:
            return result
        try:
            p = _mic_e.read(body[:1] + data[:6] + b">/", header, [])
        except APRSError:
            return result
        f.update(
            Latitude=p.latitude_deg,
            Longitude=p.longitude_deg,
            PosAmbiguity=p.ambiguity,
            PosResolution=(18.52, 185.2, 1852, 18520, 111120)[p.ambiguity],
            SymbolTable=chr(data[7]),
            SymbolCode=chr(data[6]),
        )
        dest = header.destination.split("-")[0]
        f["MBits"] = "".join(
            "1" if "A" <= c <= "K" or "P" <= c <= "Z" else "0" for c in dest[:3]
        )
        if any(c < 32 for c in data):
            return result
        motion = p.extensions.motion
        assert motion is not None and motion.speed_knots is not None
        f.update(Speed=motion.speed_knots * 1.852, Course=motion.course_deg)
        return result
    if body.startswith(b";"):
        f["Type"] = "object"
        if len(body) < 31:
            return result
        f["ObjectName"] = body[1:10].decode("latin1")
        if body[10:11] not in (b"*", b"_"):
            return result
        f["Alive"] = body[10:11] == b"*"
        position = body[18:]
    elif body[:1] in (b"!", b"=", b"/", b"@"):
        f["Type"] = "location"
        f["Messaging"] = body[:1] in (b"=", b"@")
        position = body[8:] if body[:1] in (b"/", b"@") else body[1:]
    else:
        if body.startswith(b":"):
            f["Type"] = "message"
        elif body.startswith(b")"):
            f["Type"] = "item"
        elif body.startswith(b"T#"):
            f["Type"] = "telemetry"
        return result
    f["Format"] = (
        "compressed"
        if position[:1] in b"/\\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        else "uncompressed"
    )
    if f["Format"] == "compressed":
        return result
    if not re.match(rb"[0-9 ]{4}\.[0-9 ]{2}[NS]", position):
        return result
    try:
        ambiguity = pc.ambiguity(position[:8])
        f["Latitude"] = pc.center(
            decode_coordinate(position[:8].replace(b" ", b"0"), "latitude"), ambiguity
        )
        f["PosAmbiguity"] = ambiguity
        if len(position) > 8:
            f["SymbolTable"] = chr(position[8])
        if not re.fullmatch(rb"[/\\0-9A-Z]", position[8:9]):
            return result
        if len(position) >= 18:
            _, f["Longitude"], _ = pc.coordinates(position[:8], position[9:18])
    except APRSError:
        pass
    return result
