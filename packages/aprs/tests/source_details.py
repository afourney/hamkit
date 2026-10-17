# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Assert source facts outside JSON fields using models, evidence and receiver policy.

No expected fixture value is used to compute the actual view. These are derived
units, presentation conventions and historical interpretations, not extra API.
"""

import re

from hamkit import aprs as a


def symbol(s):
    return {
        "table": s.table,
        "overlay": s.overlay,
        "code": s.code,
        "table_id_raw": s.table_id,
    }


def grid(g):
    return {
        "locator": g.locator,
        "bounds_deg": {
            "latitude": list(g.bounds.latitude),
            "longitude": list(g.bounds.longitude),
        },
        "center_deg": [g.center.latitude_deg, g.center.longitude_deg],
    }


def weather(w):
    r = {}

    def convert(name, key, factor=1, offset=0):
        m = getattr(w, name)
        if m is not None:
            r[key] = None if m.value is None else m.value * factor + offset

    convert("temperature", "temperature_c", 1 / 1.8, -32 / 1.8)
    convert("gust", "gust_mps", 0.44704)
    convert("pressure", "pressure_tenth_hpa", 10)
    for name in ("rain_1h", "rain_24h", "rain_since_midnight", "snow_24h"):
        convert(name, name + "_mm", 25.4)
    if w.wind_speed:
        if w.wind_speed.unit == "disputed_knots_or_mph":
            v = w.wind_speed.value
            r["wind_speed_mps_interpretations"] = {
                k: None if v is None else v * f
                for k, f in [("APRS101_p27_knots", 1852 / 3600), ("FAP_mph", 0.44704)]
            }
        else:
            convert(
                "wind_speed",
                "wind_speed_mps",
                1852 / 3600 if w.wind_speed.unit == "knots" else 0.44704,
            )
    if w.water_height:
        m = w.water_height.measurement
        r["water_height"] = {
            "field": "F" if m.unit == "feet" else "f",
            "raw": f"{m.value:g}",
            "meters": m.value * (0.3048 if m.unit == "feet" else 1),
        }
    if w.wind_direction and w.wind_speed and w.wind_direction.raw and w.wind_speed.raw:
        r["wind_raw"] = (w.wind_direction.raw + b"/" + w.wind_speed.raw).decode()
    return r


def core(packet, raw, profile):
    assert isinstance(packet, a.Packet)
    p = packet.payload
    if isinstance(p, a.LegacyPosition):
        p = (
            p.position
            if profile == "historical-1.0"
            else a.Beacon(raw.partition(b":")[2].decode("latin1"))
        )
    body = raw.partition(b":")[2]
    h = packet.header
    r = {}
    if hasattr(p, "symbol") and p.symbol is not None:
        r["symbol"] = symbol(p.symbol)
    if hasattr(p, "extensions"):
        e = p.extensions
        if e.motion:
            v = e.motion
            r["motion"] = {
                "speed_kmh": None if v.speed_knots is None else v.speed_knots * 1.852,
                "raw": v.raw.decode() if v.raw else None,
                "station_fixed": v.zero_pair == "fixed",
                "zero_pair_meaning": (
                    "unknown-or-not-relevant"
                    if v.zero_pair == "unavailable"
                    else v.zero_pair
                ),
            }
        if e.altitude:
            v = e.altitude
            r["altitude"] = {
                "meters": v.measurement.value
                * (0.3048 if v.measurement.unit == "feet" else 1),
                "reference": v.reference,
            }
        if e.phg:
            v = e.phg
            r["phg"] = {
                "range_miles_1_0": v.range_miles,
                "display_radius_miles_1_1": v.display_radius_miles,
                "omnidirectional": v.directivity_deg is None,
            }
        if e.range:
            r["radio_range"] = {"km": e.range.miles * 1.609344}
        if e.bearing:
            v = e.bearing
            r["df_bearing"] = {
                "manual": v.manual,
                "range_miles": v.range_miles,
                "usable": v.quality_code > 0,
                "accuracy_less_than_deg": (None, 240, 120, 64, 32, 16, 8, 4, 2, 1)[
                    v.quality_code
                ],
                "nrq_raw": f"{v.hits_code}{v.range_code}{v.quality_code}",
                "nrq_meaningful": bool(v.hits_code or v.range_code or v.quality_code),
            }
        if e.area:
            v = e.area
            r["area"] = {
                "shape": (
                    "open-circle",
                    "line-down-right",
                    "open-ellipse",
                    "open-triangle",
                    "open-box",
                    "filled-circle",
                    "line-down-left",
                    "filled-ellipse",
                    "filled-triangle",
                    "filled-box",
                )[v.shape_code],
                "color": (
                    "black",
                    "blue",
                    "green",
                    "cyan",
                    "red",
                    "violet",
                    "yellow",
                    "gray",
                )[v.color_code % 8],
                "intensity": "low" if v.color_code >= 8 else "high",
                "latitude_offset_deg": v.latitude_offset_deg,
                "longitude_offset_deg": v.longitude_offset_deg,
                "transmitted_anchor": (
                    "center"
                    if v.transmitted_anchor == "circle_center"
                    else "lower-left"
                    if v.shape_code == 6
                    else "lower-right"
                ),
            }
        if e.weather:
            r["weather"] = weather(e.weather)
        if e.telemetry:
            r["telemetry"] = {
                "digital_channels_B1_to_B8": [
                    int(b) if b is not None else None for b in e.telemetry.digital
                ]
            }
    if isinstance(p, a.Weather):
        r["weather"] = weather(p)
    if isinstance(p, a.Telemetry):
        r["telemetry"] = {
            "digital_channels_B1_to_B8": [
                int(b) if b is not None else None for b in p.digital
            ]
        }
    if hasattr(p, "compression") and p.compression:
        r["compression"] = {"type_value": p.compression.type_value}
    if hasattr(p, "ambiguity_extent"):
        extent = p.ambiguity_extent
        r["position"] = {
            "is_null_position": getattr(p, "is_null_position", False),
            "representative": "cell-center",
        }
        if extent:
            r["position"]["cell_bounds_deg"] = {
                "latitude": list(extent.latitude),
                "longitude": list(extent.longitude),
            }
    if isinstance(p, (a.Object, a.Item)):
        r["name_raw"] = body[1:10].decode() if isinstance(p, a.Object) else p.name
    if hasattr(p, "timestamp") and p.timestamp:
        from hamkit.aprs._fields import encode_timestamp

        r["timestamp"] = {"raw": encode_timestamp(p.timestamp).decode()}
    if isinstance(p, a.MicE):
        dest = h.destination.split("-")[0]
        bits = "".join(
            "1" if "A" <= c <= "K" or "P" <= c <= "Z" else "0" for c in dest[:3]
        )
        custom = any("A" <= c <= "K" for c in dest[:3])
        standard = any("P" <= c <= "Z" for c in dest[:3])
        r["mic_e"] = {
            "position_comment_bits": bits,
            "position_comment_set": (
                "mixed" if custom and standard else "custom" if custom else "standard"
            ),
            "longitude_offset": 100 if dest[4] >= "P" else 0,
            "type_marker": p.device_code[:1] if p.device_code else None,
        }
        match = re.match(r"([A-R]{2}[0-9]{2}[A-X]{2})(/)([A-Za-z])", p.comment)
        if match:
            r["grid_locator"] = match[1]
            r["grid_symbol"] = symbol(a.Symbol(match[2], match[3]))
    if isinstance(p, a.NMEA):
        r["position_usable"] = p.position_usable
        if isinstance(p.sentence, a.GGA):
            r["altitude"] = {"reference": "mean-sea-level"}
        if isinstance(p.sentence, a.RMC):
            r["motion"] = {
                "speed_kmh": (
                    p.sentence.speed_knots * 1.852
                    if p.sentence.speed_knots is not None
                    else None
                )
            }
    elif isinstance(p, a.RawWeather):
        r["decoded_measurements"] = None
        r["position_usable"] = False
    elif isinstance(p, (a.Maidenhead, a.Beacon)):
        r["position_usable"] = False
    else:
        r["position_usable"] = hasattr(p, "latitude_deg")
    if isinstance(p, (a.Status, a.Maidenhead)) and p.grid:
        r["grid"] = grid(p.grid)
    if re.fullmatch(r"[A-R]{2}\d{2}[A-X]{2}", h.destination):
        r["destination_grid"] = grid(a.Grid(h.destination))
    r["status_fallback_permitted"] = isinstance(p, a.Beacon)
    paths = [hop.address for hop in h.path]
    r["policy"] = {
        "forward_to_aprs_is": not any(x in ("RFONLY", "NOGATE") for x in paths),
        "archive_allowed": b"!x!" not in body and "NOARCH" not in paths,
    }
    for i, hop in enumerate(paths):
        if re.fullmatch("q[A-Z][A-Za-z]", hop):
            r["aprs_is"] = {"q_construct_raw": hop, "following_path": paths[i + 1 :]}
            break
    r["normalized_tnc2"] = str(h) + ":" + body.decode("latin1")
    r["destination_semantics"] = (
        "APRS-address"
        if h.destination.startswith(("AP", "GPS", "SPC", "SYM", "AIR", "DF", "ZIP"))
        or h.destination
        in {
            "ALL",
            "BEACON",
            "CQ",
            "DGPS",
            "DRILL",
            "DX",
            "ID",
            "JAVA",
            "MAIL",
            "MICE",
            "QST",
            "QTH",
            "RTCM",
            "SKY",
            "SPACE",
            "TEL",
            "TEST",
            "TLM",
            "WX",
        }
        else "alternate-net"
    )
    ssid = h.destination.rpartition("-")[2]
    if ssid.isdigit():
        v = int(ssid)
        r["destination_ssid"] = v
        r["historical_generic_path"] = (
            "VIA",
            *[f"WIDE{i}-{i}" for i in range(1, 8)],
            "North",
            "South",
            "East",
            "West",
            "North + WIDE",
            "South + WIDE",
            "East + WIDE",
            "West + WIDE",
        )[v]
    if isinstance(p, a.ThirdParty):
        r["inner"] = core(p.packet, body[1:], profile)
        r["inner_packet"] = body[1:].decode("latin1")
        r["message_origin"] = p.packet.header.source
    if body.startswith(b":"):
        address = body[1:10].decode()
        content = body[11:].decode("latin1")
        text, sep, identifier = content.partition("{")
        number, _brace, _ack = identifier.partition("}")
        m = {
            "addressee_raw": address,
            "addressee": address.rstrip(),
            "message_id": number if sep else None,
            "text": text,
            "ack_requested": bool(sep) and not isinstance(p, a.NWSBulletin),
            "message_id_raw": identifier if sep else None,
            "group_address": address.rstrip() in ("CQ", "ALL", "QST"),
        }
        if content.startswith(("ack", "rej")):
            v = content[3:]
            m.update(ack_id_raw=v, embedded_reply_ack_id=v.partition("}")[2] or None)
        if address.startswith("NWS-"):
            m["reference_id"] = identifier or None
        r["message"] = m
        if isinstance(p, a.TelemetryDefinition):
            r["telemetry_definition"] = {"values_raw": content[5:].split(",")}
    if isinstance(p, a.Query):
        r["query"] = {
            "directed": p.addressee is not None,
            "recognized": p.name
            in {
                "APRS",
                "IGATE",
                "WX",
                "APRSD",
                "APRSH",
                "APRSM",
                "APRSO",
                "APRSP",
                "APRSS",
                "APRST",
                "PING",
            },
            "ack_requested": False,
        }
        if p.footprint:
            r["query"]["radius_km"] = p.footprint.radius_miles * 1.609344
    return r


def at(value, path):
    for key in path.removeprefix("$.").split("."):
        value = value[key]
    return value


def check_core(row):
    from packets.test_corpus import differences

    raw = row["packet"].encode("latin1")
    from packets.test_corpus import parse_row

    actual = core(parse_row(row, raw), raw, row["profile"])
    errors = []
    for path in row.get("unmapped", []):
        try:
            value = at(actual, path)
        except (KeyError, TypeError):
            errors.append(path + ": no derived assertion")
            continue
        errors.extend(differences(value, at(row["source_expected"], path), path))
    return errors


def check_public_phg(row, packet):
    """Express source fields from public models, without a historical decoder."""
    from packets.test_corpus import differences

    p = packet.payload
    if isinstance(p, a.LegacyPosition):
        p = p.position
    assert isinstance(p, a.Position) and p.extensions.phg is not None
    phg = p.extensions.phg
    assert phg.raw is not None
    code = phg.raw.decode("ascii")
    if phg.rate_per_hour is not None:
        code += "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[phg.rate_per_hour]
    facts = {
        "Capabilities": None,
        "ChecksumOK": None,
        "DaoDatumByte": None,
        "GPSFixStatus": None,
        "MBits": "",
        "MiceMangled": False,
        "ObjectName": "",
        "PosResolution": (18.52, 185.2, 1852, 18520, 111120)[p.ambiguity],
        "RawTimestamp": "",
        "Warnings": None,
        "PHG": code,
    }
    # Fail if future PHG rows need additional source-field derivations.
    assert p.extensions.dao is None and p.compression is None and p.timestamp is None
    actual = {"fap_fields": facts}
    paths = [*row.get("unmapped", []), "$.fap_fields.PHG"]
    errors = []
    for path in paths:
        errors.extend(
            differences(at(actual, path), at(row["source_expected"], path), path)
        )
    if p.extensions.telemetry is not None:
        # FAP has five slots even when the wire omits trailing channels. Assert
        # those source nulls as well as the variable-length public JSON array.
        analog = list(p.extensions.telemetry.analog)
        analog += [None] * (5 - len(analog))
        errors.extend(
            differences(
                analog,
                row["source_expected"]["fap_fields"]["TelemetryData"]["Vals"],
                "$.fap_fields.TelemetryData.Vals",
            )
        )
    return errors


def check_rejection(row):
    from generate_vectors import header, translate
    from packets.test_corpus import differences

    raw = row["packet"].encode("latin1")
    source = row["source_expected"]
    if row["profile"] == "compatibility-fap":
        return []  # The rejection itself is asserted; FAP's partial fields are not.
    p = a.parse_packet(raw)
    errors = []
    if "header" in source:
        assert p.header is not None
        errors.extend(
            differences(
                a.to_json_dict(p.header, include_defaults=True),
                header(source["header"]),
                "$.header",
            )
        )
    if "kind" in source:
        expected = translate(source)
        # Empty NMEA optional variation direction has the existing None form.
        n = expected.get("payload", {}).get("sentence", {})
        if n.get("magnetic_variation_direction") == "":
            n["magnetic_variation_direction"] = None
        errors.extend(differences(a.to_json_dict(p, include_defaults=True), expected))
    if "partial" in source:
        assert isinstance(p, a.Malformed)
        recovered = p.recovered["payload"]
        from hamkit.aprs._position_codec import ambiguity

        partial = {
            "position": {
                "latitude_deg": recovered.get("latitude_deg"),
                "longitude_deg": recovered.get("longitude_deg"),
                "ambiguity_digits": ambiguity(raw.partition(b":")[2][8:16]),
            }
        }
        errors.extend(differences(partial, source["partial"], "$.partial"))
    if "compression_type_value" in source:
        assert isinstance(p, a.Packet) and p.payload.compression is not None
        assert p.payload.compression.raw[-1] - 33 == source["compression_type_value"]
    # These booleans describe receiver usability, not fabricated measurements.
    for flag in (
        "position_usable",
        "message_valid",
        "telemetry_valid",
        "weather_valid",
        "inner_packet_valid",
    ):
        if flag in source:
            invalid = isinstance(p, a.Malformed) or any(
                d.code == "nonconforming" for d in p.diagnostics
            )
            if isinstance(p, a.Packet) and isinstance(p.payload, a.NMEA):
                invalid = p.payload.position_usable is False
            errors.extend(differences(not invalid, source[flag], "$." + flag))
    return errors
