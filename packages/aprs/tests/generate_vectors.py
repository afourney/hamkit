# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Translate documented assertions, never parser output, into JSON projections.

Run from any directory. Unmapped assertions remain verbatim beside the projection;
they are deliberately not claimed as tested public-model fields.
"""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "docs/APRS_COMPLIANCE_VECTORS.md"
DEST = ROOT / "tests/vectors"
DIVERGENCES = ROOT / "tests/fap_divergences.json"
JSON = dict[str, Any]


def leaf_paths(value: Any, path: str = "$") -> set[str]:
    if isinstance(value, dict) and value:
        return {
            leaf
            for key, child in value.items()
            for leaf in leaf_paths(child, f"{path}.{key}")
        }
    return {path}


class Tracked(dict[str, Any]):
    """Record source fields consulted by the explicit projection mapping."""

    def __init__(self, value: JSON, used: set[str], path: str = "$"):
        super().__init__(value)
        self.used, self.path = used, path

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        path = f"{self.path}.{key}"
        if isinstance(value, dict):
            return Tracked(value, self.used, path)
        self.used.add(path)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def select(data: JSON, names: str) -> JSON:
    return {k: data[k] for k in names.split() if k in data}


def header(data: JSON) -> JSON:
    return {
        "source": data["source"],
        "destination": data["destination"],
        "path": [
            {"address": h["address"], "repeated": h["repeated_marker"]}
            for h in data["path"]
        ],
    }


def stamp(data: JSON) -> JSON:
    kind = {
        "DHM": (
            "dhm_local"
            if str(data.get("zone")).lower() in ("local", "sender-local")
            else "dhm_utc"
        ),
        "HMS": "hms_utc",
        "MDHM": "mdhm_utc",
    }[data["format"]]
    return {"kind": kind, **select(data, "day month hour minute second")}


def symbol(data: JSON) -> JSON:
    return {"table_id": data["table_id_raw"], "code": data["code"]}


def telemetry(data: JSON) -> JSON:
    result = select(data, "sequence sequence_raw")
    if "analog_raw" in data:
        result["analog"] = data["analog_raw"]
    if "digital_bits" in data:
        result["digital"] = [c == "1" for c in data["digital_bits"]]
    result["encoding"] = data.get("encoding", "classic").replace("-", "_")
    if result.get("sequence_raw") == "MIC":
        result["sequence"] = "MIC"
    return result


def weather(data: JSON) -> JSON:
    result = select(data, "software_code device_code")
    units = {
        "wind_direction_deg": ("wind_direction", "degrees"),
        "wind_speed_mph": ("wind_speed", "mph"),
        "wind_speed_knots": ("wind_speed", "knots"),
        "gust_mph": ("gust", "mph"),
        "temperature_f": ("temperature", "fahrenheit"),
        "humidity_percent": ("humidity", "percent"),
        "pressure_hpa": ("pressure", "hPa"),
        "snow_24h_inches": ("snow_24h", "inches"),
        "luminosity_w_m2": ("luminosity", "W/m2"),
        "rain_counter_raw": ("rain_counter", "count"),
    }
    for key, (name, unit) in units.items():
        if key in data:
            result[name] = {"value": data[key], "unit": unit}
    if "water_height" in data:
        w = data["water_height"]
        result["water_height"] = {
            "measurement": {
                "value": w["value"],
                "unit": {"ft": "feet", "m": "meters"}[w["unit"]],
            },
            "reference_datum": w["reference_datum"],
        }
    # Rain is sent in hundredths of an inch. Project that wire unit, like every
    # other reading; the source's millimetre conversions stay unmapped.
    for name in ("rain_1h", "rain_24h", "rain_since_midnight"):
        if f"{name}_hundredth_in" in data:
            hundredths = data[f"{name}_hundredth_in"]
            value = None if hundredths is None else hundredths / 100
            result[name] = {"value": value, "unit": "inches"}
    if "wind_speed_raw" in data:
        result["wind_speed"] = {
            "value": data["wind_speed_raw"],
            "unit": "disputed_knots_or_mph",
        }
    return result


def translate(e: JSON) -> JSON:
    """A subset in to_json_dict(include_defaults=True) shape; no model/parser calls."""
    result: JSON = {"type": "packet"}
    if "header" in e:
        result["header"] = header(e["header"])
    kind = e.get("kind")
    aliases = {
        "third-party": "third_party",
        "telemetry-definition": "telemetry_definition",
        "user-defined": "user_defined",
        "invalid-or-test": "invalid",
        "raw-weather": "raw_weather",
        "legacy-grid-beacon": "maidenhead",
        "non-aprs-beacon": "beacon",
        "unsupported-or-reserved": "opaque",
        "announcement": "bulletin",
        "group-bulletin": "bulletin",
        "nws-bulletin": "nws_bulletin",
    }
    if kind is None:
        return result
    p: JSON = {"type": aliases.get(kind, kind)}
    if kind == "weather" and "position" in e:
        p["type"] = "position"
    if e.get("format") == "mic-e":
        p["type"] = "mic_e"
    for name in ("comment", "messaging", "name", "alive"):
        if name in e:
            p[name] = e[name]
    if "position" in e and kind != "nmea":
        pos = e["position"]
        p.update(select(pos, "latitude_deg longitude_deg"))
        if "ambiguity_digits" in pos:
            p["ambiguity"] = pos["ambiguity_digits"]
    if "symbol" in e:
        p["symbol"] = symbol(e["symbol"])
    if "timestamp" in e:
        p["timestamp"] = stamp(e["timestamp"])
    if "compression" in e:
        c = e["compression"]
        p["compression"] = select(c, "fix nmea_source origin_code")
        if "csT_raw" in c:
            p["compression"]["raw"] = c["csT_raw"]
        if "ignored" in c:
            p["compression"]["ignored"] = c["ignored"]
    if "mic_e" in e:
        m = e["mic_e"]
        names = {
            "Off Duty": "off_duty",
            "En Route": "en_route",
            "In Service": "in_service",
            "Returning": "returning",
            "Committed": "committed",
            "Special": "special",
            "Priority": "priority",
            "Emergency": "emergency",
        }
        if m.get("position_comment") in names:
            p["message"] = names[m["position_comment"]]
        if str(m.get("position_comment", "")).startswith("Custom-"):
            p["message"] = m["position_comment"].lower().replace("-", "_")
        if str(m.get("position_comment")).lower() == "unknown":
            p["message"] = "unknown"
        if m.get("dti_fix") in ("current", "old"):
            p["fix"] = m["dti_fix"]
    ext: JSON = {}
    for old, new, fields in (
        ("motion", "motion", "course_deg speed_knots course_code speed_code zero_pair"),
        (
            "phg",
            "phg",
            "power_w height_haat_ft gain_dbi directivity_deg raw rate_per_hour",
        ),
        ("radio_range", "range", "miles"),
        ("df_signal", "signal", "s_units height_haat_ft gain_db directivity_deg"),
        (
            "df_bearing",
            "bearing",
            # usable/accuracy derive from a disputed Q mapping; see UNRESOLVED_SPEC.md.
            "bearing_deg hits_code range_code quality_code",
        ),
        (
            "area",
            "area",
            "shape_code color_code latitude_offset_code longitude_offset_code corridor_half_width_miles",
        ),
        ("signpost", "signpost", "label"),
    ):
        if old in e:
            ext[new] = select(e[old], fields)
    if "altitude" in e and kind != "nmea":
        alt = e["altitude"]
        unit = "feet" if "feet" in alt else "meters"
        enc = {
            "comment": "feet_extension",
            "compressed": "compressed",
            "mic-e": "mic_e",
            "mic-e-base91": "mic_e",
        }[alt.get("encoding", "comment")]
        ext["altitude"] = {
            "measurement": {"value": alt[unit], "unit": unit},
            "encoding": enc,
        }
    if "weather" in e:
        if kind == "weather" and "position" not in e:
            p.update(weather(e["weather"]))
        else:
            if kind == "weather":
                p["type"] = "position"
            ext["weather"] = weather(e["weather"])
    if "telemetry" in e:
        if kind == "telemetry":
            p.update(telemetry(e["telemetry"]))
        else:
            ext["telemetry"] = telemetry(e["telemetry"])
    if ext:
        p["extensions"] = ext
    if kind == "status":
        p["text"] = e["status_text"]
        if "grid" in e:
            p["grid"] = {"locator": e["grid"]["locator"]}
        if "beam_heading_deg" in e:
            p["beam"] = {"heading_deg": e["beam_heading_deg"], "erp_w": e["erp_w"]}
    if "message" in e and kind not in ("query", "telemetry-definition"):
        m = e["message"]
        p.update(select(m, "addressee text message_id"))
        if m.get("subtype") in ("ack", "rej"):
            p = {
                "type": "acknowledgment",
                "addressee": m["addressee"],
                "message_id": m.get("ack_id", m.get("reject_id")),
                "rejected": m["subtype"] == "rej",
            }
        if m.get("reply_ack_capable"):
            p["reply_ack"] = m.get("reply_ack_id") or ""
        if m.get("auto_answer"):
            p = {
                "type": "auto_answer",
                "addressee": m["addressee"],
                "text": m["text"][3:],
                "previous_ack": m.get("reply_ack_id"),
            }
        if p["type"] == "nws_bulletin":
            p["reference_id"] = p.pop("message_id", None)
        if p["type"] == "bulletin":
            p = {
                "type": "bulletin",
                "identifier": m["bulletin_id"],
                "text": m["text"],
                "group": m.get("group"),
            }
    if kind == "query":
        q = e["query"]
        p["name"] = q["type"]
        if "heard_station" in q:
            p["heard_station"] = q["heard_station"]
        if "message" in e:
            p["addressee"] = e["message"]["addressee"]
        if "radius_miles" in q:
            p["footprint"] = {
                "center": select(q, "latitude_deg longitude_deg"),
                "radius_miles": q["radius_miles"],
            }
    if kind == "capabilities":
        p["tokens"] = e["capabilities"]
    if kind == "telemetry-definition":
        d = e["telemetry_definition"]
        p["addressee"] = d["target"]
        tags = {
            "PARM": "telemetry_parameters",
            "UNIT": "telemetry_units",
            "EQNS": "telemetry_equations",
            "BITS": "telemetry_bits",
        }
        definition: JSON = {"type": tags[d["type"]]}
        if "channels" in d:
            channels = d["channels"]
            definition["channels"] = channels + [None] * (13 - len(channels))
        if "coefficients_abc" in d:
            definition["coefficients"] = [
                dict(zip(("a", "b", "c"), x)) for x in d["coefficients_abc"]
            ]
        if "sense_bits" in d:
            definition.update(
                sense=[x == "1" for x in d["sense_bits"]],
                project_title=d["project_title"],
            )
        p["definition"] = definition
    if kind == "third-party":
        p["packet"] = translate(e["inner"])
        p["packet"].pop("type", None)
    if kind in ("user-defined", "invalid-or-test"):
        p.update(select(e, "user_id user_type data"))
    if kind == "unsupported-or-reserved":
        p["information"] = e.get("dti", "") + e.get("raw_data", "")
    if "storm" in e:
        storm = e["storm"]
        p.setdefault("extensions", {})["storm"] = {
            # APRS101 storm codes; unknown source names fail generation.
            "kind": {
                "hurricane": "HC",
                "tropical-storm": "TS",
                "tropical-depression": "TD",
            }[storm["type"]],
            **select(
                storm,
                "predicted sustained_wind_knots peak_gust_knots central_pressure_hpa hurricane_radius_nm tropical_storm_radius_nm whole_gale_radius_nm",
            ),
        }
    if kind == "nmea" and "nmea" in e:
        n = e["nmea"]
        sentence: JSON = {"type": n["sentence"][2:].lower()}
        renames = {
            "time_utc_raw": "time_utc",
            "date_ddmmyy_raw": "date_ddmmyy",
            "dgps_age_raw": "dgps_age",
            "dgps_station_raw": "dgps_station",
        }
        sentence.update(
            {
                v: (n[k] or None) if k.startswith("dgps_") else n[k]
                for k, v in renames.items()
                if k in n
            }
        )
        sentence.update(
            select(
                n,
                "fix_quality fix_status satellites hdop geoid_separation_m magnetic_variation_direction",
            )
        )
        if n.get("magnetic_variation_raw"):
            sentence["magnetic_variation"] = float(n["magnetic_variation_raw"])
        if "position" in e:
            sentence["coordinates"] = select(
                e["position"], "latitude_deg longitude_deg"
            )
        if "waypoint" in e:
            sentence.update(
                name=e["waypoint"]["name"],
                coordinates=select(e["waypoint"], "latitude_deg longitude_deg"),
            )
        if "altitude" in e:
            sentence["altitude_msl_m"] = e["altitude"]["meters"]
        if "motion" in e:
            sentence.update(
                select(
                    e["motion"],
                    "speed_knots course_deg course_true_deg course_magnetic_deg speed_kmh_reported",
                )
            )
        p.pop("extensions", None)
        p.update(
            sentence=sentence,
            metadata={
                "talker": n["sentence"][:2],
                **select(n, "checksum_supplied checksum_valid fields_raw"),
            },
        )
        if "position_usable" in e:
            p["position_usable"] = e["position_usable"]
    if kind == "raw-weather":
        formats = {"Ultimeter 2000": "ultimeter_2000", "Ultimeter II": "ultimeter_ii"}
        p.update(information=e["raw_payload"])
        if e["vendor"] in formats:
            p["format"] = formats[e["vendor"]]
    if kind == "legacy-grid-beacon":
        p["grid"] = {"locator": e["grid"]["locator"]}
    if kind == "non-aprs-beacon" and "raw_text" in e:
        p["text"] = e["raw_text"]
    if "nts" in e:
        # The source explicitly identifies the NTS record and its positional fields.
        n = e["nts"]
        fields = n["fields"]
        schemas = {
            "N#": (
                "nts_header",
                "number precedence handling originator check place time date",
            ),
            "NA": ("nts_address", ""),
            "NP": ("nts_phone", "number"),
            "NT": ("nts_text", "text"),
            "NS": ("nts_signature", "text"),
            "NR": ("nts_routing", "received_from received_at sent_to sent_at"),
        }
        if n["record_type"] in {"N1", "N2", "N3", "N4", "N5", "N6"}:
            schemas[n["record_type"]] = ("nts_text", "text")
        if n["record_type"] in schemas:
            tag, field_names = schemas[n["record_type"]]
            record = {"type": tag, **dict(zip(field_names.split(), fields))}
            if tag == "nts_address":
                record["lines"] = fields
            if tag == "nts_text":
                record["line"] = int(n["record_type"][1])
            p = {
                "type": "radiogram",
                "addressee": e["message"]["addressee"],
                "record": record,
                "message_id": e["message"].get("message_id"),
            }
    if p.get("type") == "message" and p.get("message_id") is None:
        text = p.get("text", "")
        response = None
        if text.startswith("Directs= "):
            response = {"type": "direct_stations", "stations": text[9:].split()}
        elif match := re.fullmatch(
            r"([A-Za-z0-9-]+) HEARD: ((?:[0-9]+|\.)(?: (?:[0-9]+|\.)){7})", text
        ):
            response = {
                "type": "heard_station",
                "station": match[1],
                "counts": [None if c == "." else int(c) for c in match[2].split()],
            }
        elif re.fullmatch(r"[A-Za-z0-9-]+>[A-Za-z0-9,*-]+:", text):
            source, route = text[:-1].split(">")
            dest, *hops = route.split(",")
            response = {
                "type": "trace",
                "header": {
                    "source": source,
                    "destination": dest,
                    "path": [
                        {"address": h.rstrip("*"), "repeated": h.endswith("*")}
                        for h in hops
                    ],
                },
            }
        if response is not None:
            p = {"type": "response", "addressee": p["addressee"], "response": response}
    result["payload"] = p
    return result


def fap_projection(e: JSON, packet: str) -> JSON:
    """Map only explicit captured FAP values; no implicit defaults or guessed units."""
    f, h = e["fap_fields"], e["fap_header"]
    normal: JSON = {
        "header": {
            "source": h["source"],
            "destination": h["destination"],
            "path": [
                {"address": x["Call"], "repeated_marker": x["WasDigied"]}
                for x in (h.get("digipeaters") or [])
            ],
        }
    }
    normal["kind"] = {
        "location": "position",
        "wx": "weather",
        "beacon": "non-aprs-beacon",
        "telemetry-message": "telemetry-definition",
    }.get(f.get("Type"), f.get("Type"))

    renames = {
        "Format": "format",
        "Comment": "comment",
        "Messaging": "messaging",
        "Alive": "alive",
        "Status": "status_text",
    }
    normal.update({v: f[k] for k, v in renames.items() if f.get(k) is not None})
    if normal.get("format") == "mice":
        normal["format"] = "mic-e"
    name_key = "ObjectName" if normal["kind"] == "object" else "ItemName"
    if f.get(name_key):
        normal["name"] = f[name_key].rstrip(" ")
    if f.get("Latitude") is not None or f.get("Longitude") is not None:
        normal["position"] = {
            v: f[k]
            for k, v in {
                "Latitude": "latitude_deg",
                "Longitude": "longitude_deg",
                "PosAmbiguity": "ambiguity_digits",
            }.items()
            if f.get(k) is not None
        }
    if f.get("SymbolTable") is not None and f.get("SymbolCode") is not None:
        normal["symbol"] = {"table_id_raw": f["SymbolTable"], "code": f["SymbolCode"]}
    if f.get("Message") is not None:
        m = f["Message"]
        normal["message"] = {
            "addressee": m["Destination"],
            "text": m["Text"],
            "message_id": m.get("ID") or None,
        }
        if (m.get("AckID") or m.get("RejID")) and not m.get("Text"):
            normal["message"].update(
                subtype="rej" if m.get("RejID") else "ack",
                ack_id=m.get("AckID") or m.get("RejID"),
            )
        elif m.get("AckID"):
            normal["message"].update(reply_ack_capable=True, reply_ack_id=m["AckID"])
    # FAP has distinct units/options; unsupported fields stay in source_expected.
    if normal.get("kind") == "query":
        normal.pop("kind")
    if normal.get("kind") == "status" and "status_text" not in normal:
        normal.pop("kind")
    if normal.get("kind") == "capabilities":
        # The source packet supplies token order; the captured map supplies values.
        capabilities = f["Capabilities"]
        names = [
            token.split("=", 1)[0] for token in packet.partition(":")[2][1:].split(",")
        ]
        normal["capabilities"] = [
            {"name": name, "value": capabilities[name] or None} for name in names
        ]
    if normal.get("kind") == "telemetry-definition":
        text = normal["message"]["text"]
        name, _, rest = text.partition(".")
        name = name.upper()
        values = rest.split(",")
        definition: JSON = {"target": normal["message"]["addressee"], "type": name}
        if name in ("PARM", "UNIT"):
            definition["channels"] = [v or None for v in values]
        elif name == "EQNS" and len(values) % 3 == 0:
            definition["coefficients_abc"] = [
                [float(x) for x in values[i : i + 3]] for i in range(0, len(values), 3)
            ]
        elif name == "BITS":
            definition.update(sense_bits=values[0], project_title=",".join(values[1:]))
        normal["telemetry_definition"] = definition
    result = translate(normal)
    payload = result.get("payload", {})
    comment = payload.get("comment", "")
    if (
        payload.get("type") == "mic_e"
        and comment[:1] in ("]", ">")
        and packet.partition(":")[2][9:10] == comment[:1]
    ):
        # Split the captured marker into its public field without losing text.
        # A broken fixed-width body must not be reinterpreted by this migration.
        payload["device_code"], payload["comment"] = comment[0], comment[1:]
    if payload.get("type") not in (
        "position",
        "mic_e",
        "object",
        "item",
        "weather",
        "telemetry",
        "nmea",
    ):
        payload.pop("comment", None)
        payload.pop("messaging", None)
        payload.pop("alive", None)
    for source, target, factor in (
        ("Speed", "speed_knots", 1 / 1.852),
        ("Course", "course_deg", 1),
    ):
        if f.get(source) is not None:
            payload.setdefault("extensions", {}).setdefault("motion", {})[target] = (
                f[source] * factor
            )
    if f.get("RadioRange") is not None:
        payload.setdefault("extensions", {})["range"] = {
            "miles": f["RadioRange"] / 1.609344
        }
    if f.get("TelemetryData") is not None:
        t = f["TelemetryData"]
        analog = list(t["Vals"])
        if payload.get("type") != "telemetry" and re.search(
            r"\|(?:[\x21-\x7b]{2}){2,7}\|", packet.partition(":")[2]
        ):
            # FAP pads omitted base91 channels to five null-capable slots;
            # the public schema stores only the transmitted analog channels.
            while analog and analog[-1] is None:
                analog.pop()
        mapped = {"sequence": t["Seq"], "analog": analog}
        if t["Bits"]:
            mapped["digital"] = [x == "1" for x in t["Bits"]]
        if payload.get("type") == "telemetry":
            payload.update(mapped)
        else:
            payload.setdefault("extensions", {})["telemetry"] = mapped
    if f.get("PHG") and re.fullmatch(r"[0-9][0-9:;][0-9][0-8][0-9A-Z]?", f["PHG"]):
        code = f["PHG"]
        phg: JSON = {
            "power_w": int(code[0]) ** 2,
            "height_haat_ft": 10 * 2 ** (ord(code[1]) - 48),
            "gain_dbi": int(code[2]),
            "directivity_deg": int(code[3]) * 45 if code[3] != "0" else None,
        }
        if len(code) == 5:
            phg["rate_per_hour"] = int(code[4], 36)
        payload.setdefault("extensions", {})["phg"] = phg
    if f.get("Altitude") is not None and f.get("Format") in (
        "uncompressed",
        "compressed",
        "mic-e",
        "mice",
    ):
        encoding = {
            "uncompressed": "feet_extension",
            "compressed": "compressed",
            "mic-e": "mic_e",
            "mice": "mic_e",
        }[f["Format"]]
        unit = "meters" if encoding == "mic_e" else "feet"
        altitude = f["Altitude"] if unit == "meters" else f["Altitude"] / 0.3048
        payload.setdefault("extensions", {})["altitude"] = {
            "encoding": encoding,
            "measurement": {"unit": unit, "value": altitude},
        }
    if f.get("Wx") is not None:
        wx = f["Wx"]
        mapped_wx = {}
        vendor = packet.partition(":")[2].startswith(("$ULTW", "!!"))
        for key, target, unit, scale, offset in (
            ("WindDirection", "wind_direction", "degrees", 1, 0),
            (
                "WindSpeed",
                "wind_speed",
                "m/s" if vendor else "mph",
                1 if vendor else 1 / 0.44704,
                0,
            ),
            (
                "WindGust",
                "gust",
                "m/s" if vendor else "mph",
                1 if vendor else 1 / 0.44704,
                0,
            ),
            (
                "Temp",
                "temperature",
                "celsius" if vendor else "fahrenheit",
                1 if vendor else 1.8,
                0 if vendor else 32,
            ),
            ("Humidity", "humidity", "percent", 1, 0),
            ("Pressure", "pressure", "hPa", 1, 0),
            (
                "Rain1h",
                "rain_1h",
                "mm" if vendor else "inches",
                1 if vendor else 1 / 25.4,
                0,
            ),
            (
                "Rain24h",
                "rain_24h",
                "mm" if vendor else "inches",
                1 if vendor else 1 / 25.4,
                0,
            ),
            (
                "RainMidnight",
                "rain_since_midnight",
                "mm" if vendor else "inches",
                1 if vendor else 1 / 25.4,
                0,
            ),
            (
                "Snow24h",
                "snow_24h",
                "mm" if vendor else "inches",
                1 if vendor else 1 / 25.4,
                0,
            ),
            ("Luminosity", "luminosity", "W/m2", 1, 0),
        ):
            if wx.get(key) is not None:
                # Convert captured expectations, never values from the decoder.
                # No rounding: the original physical measurement is preserved.
                mapped_wx[target] = {"value": wx[key] * scale + offset, "unit": unit}
        if normal.get("format") == "compressed":
            # FAP flattens the compressed weather wind pair into Course/Speed.
            # Our schema places that same pair inside extensions.weather.
            motion = payload.get("extensions", {}).pop("motion", {})
            for key, target, unit in (
                ("course_deg", "wind_direction", "degrees"),
                ("speed_knots", "wind_speed", "knots"),
            ):
                if key in motion:
                    mapped_wx[target] = {"value": motion[key], "unit": unit}
        if payload.get("type") == "weather":
            payload.update(mapped_wx)
        else:
            payload.setdefault("extensions", {})["weather"] = mapped_wx
        if vendor:
            payload.pop("type")
            result["payload"] = {
                "type": "raw_weather",
                "format": "ultimeter_2000",
                "information": packet.partition(":")[2],
                "weather": payload,
            }
    if f.get("Format") == "nmea":
        # Keep the snapshot's values (including rounded course and absent symbol)
        # in typed NMEA fields. Missing time/fix fields are not invented.
        sentence: JSON = {"type": packet.partition(":")[2][3:6].lower()}
        if normal.get("position"):
            sentence["coordinates"] = select(
                normal["position"], "latitude_deg longitude_deg"
            )
        for key, target, scale in (
            ("Altitude", "altitude_msl_m", 1),
            ("Speed", "speed_knots", 1 / 1.852),
            ("Course", "course_deg", 1),
        ):
            if f.get(key) is not None:
                sentence[target] = f[key] * scale
        table, code = f.get("SymbolTable"), f.get("SymbolCode")
        result["payload"] = {
            "type": "nmea",
            "sentence": sentence,
            "symbol": (
                {"table_id": table, "code": code}
                if table is not None and code is not None
                else None
            ),
            "metadata": {"checksum_valid": f["ChecksumOK"]},
        }
    return result


def diverge(row: JSON, divergences: JSON) -> None:
    """Replace FAP-specific interpretations with the reviewed public expectation.

    Each override names its reasons; source_expected keeps FAP's own values.
    """
    assert row["profile"] == "compatibility-fap", row["id"]
    entry = divergences["rows"][row["id"]]
    row["divergence"] = [divergences["reasons"][key] for key in entry["reasons"]]
    if "accept" in entry:
        assert row.pop("rejection"), row["id"]
        row["expected"] = {
            "type": "packet",
            "original_wire": row["packet"],
            **entry["accept"],
        }
        return
    for path, value in entry.get("set", {}).items():
        *parents, key = path.removeprefix("$.").split(".")
        target = row["expected"]
        for name in parents:
            target = target[name]
        assert key in target, (row["id"], path)
        target[key] = value
    for prefix in entry.get("drop_unmapped", []):
        # Facts from FAP's interpretation that the public expectation rejects.
        row["unmapped"] = [p for p in row["unmapped"] if not p.startswith(prefix)]
    for path in entry.get("remove", []):
        *parents, key = path.removeprefix("$.").split(".")
        target = row["expected"]
        for name in parents:
            target = target[name]
        del target[key]


def nest_legacy_position(result: JSON, packet: str) -> None:
    """Use the existing wrapper for source assertions identifying a position."""
    payload = result.get("payload", {})
    if payload.get("type") == "position":
        body = packet.partition(":")[2]
        prefix, marker, _ = body.partition("!")
        if marker and prefix and not body.startswith(("!", "=", "/", "@")):
            # The source supplies all position values. The wire supplies only
            # the literal prefix, which the finalized public schema preserves.
            payload.pop("type")
            result["payload"] = {
                "type": "legacy_position",
                "prefix": prefix,
                "position": payload,
            }


def records() -> list[JSON]:
    result = []
    defaults: JSON = {}
    divergences = json.loads(DIVERGENCES.read_text())
    for block in re.findall(r"```json\n(.*?)\n```", SOURCE.read_text(), re.DOTALL):
        case = json.loads(block)
        if "fap_field_defaults" in case:
            defaults = case["fap_field_defaults"]
        if "id" not in case:
            continue
        if case["profile"] == "compatibility-fap":
            case["expected"]["fap_fields"] = {
                **defaults,
                **case["expected"]["fap_fields"],
            }
        steps = case.get("steps", [case])
        for step in steps:
            row = {k: case[k] for k in ("id", "title", "profile", "source")}
            if "steps" in case:
                row["id"] += f".{step['step']}"
                row["sequence"] = case["id"]
            row["packet"] = step["packet"]
            raw = row["packet"].encode("latin-1")
            assert len(raw) == step["packet_length_bytes"], row["id"]
            if "packet_hex" in step:
                assert raw == bytes.fromhex(step["packet_hex"])
            row["outcome"] = case.get("outcome", "stateful")
            row["source_expected"] = copy.deepcopy(step["expected"])
            if "options" in case:
                row["options"] = case["options"]
            if case.get("note"):
                row["note"] = case["note"]
            for key in ("scope_note", "extension_tags"):
                if key in case:
                    row[key] = case[key]
            if "steps" in case:
                row["expected"] = {"type": "packet"}
                row["state_expected"] = copy.deepcopy(step["expected"])
            elif row["outcome"].startswith("reject"):
                row["expected"] = {"original_wire": row["packet"]}
                row[
                    "rejection"
                ] = "Malformed or a Packet with nonconforming diagnostics; exact diagnostic wording is not specified by the source."
            else:
                used: set[str] = set()
                tracked = Tracked(step["expected"], used)
                row["expected"] = (
                    fap_projection(tracked, row["packet"])
                    if row["profile"] == "compatibility-fap"
                    else translate(tracked)
                )
                nest_legacy_position(row["expected"], row["packet"])
                row["unmapped"] = sorted(leaf_paths(step["expected"]) - used)
                if "payload" not in row["expected"]:
                    row[
                        "unresolved"
                    ] = "Source has no mapped payload expectation; retain the original assertions for adapter completion."
            if row["id"] in divergences["rows"]:
                diverge(row, divergences)
            result.append(row)
    assert set(divergences["rows"]) <= {row["id"] for row in result}
    return result


def main() -> None:
    rows = records()
    for family in sorted({r["id"].split("-")[0] for r in rows}):
        selected = [r for r in rows if r["id"].startswith(family + "-")]
        (DEST / (family.lower() + ".jsonl")).write_text(
            "".join(
                json.dumps(r, ensure_ascii=True, separators=(",", ":")) + "\n"
                for r in selected
            )
        )
    print(dict(Counter(r["id"].split("-")[0] for r in rows)))


if __name__ == "__main__":
    main()
