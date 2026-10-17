# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Small application receiver exercising sequence semantics through public models.

State belongs to the consuming application; the codec API remains stateless.
"""

from hamkit import aprs as a


class Receiver:
    def __init__(self, local="N0CALL"):
        self.local = local
        self.entities = {}
        self.delivered = set()
        self.bulletins = {}
        self.status = {}
        self.fallback = {}
        self.positions = {}
        self.definitions = {}

    def receive(self, packet):
        assert isinstance(packet, a.Packet)
        p, source = packet.payload, packet.header.source
        if isinstance(p, (a.Object, a.Item)):
            name = p.name.rstrip(" ")
            self.entities[name] = p
            return dict(
                name=name,
                owner=source,
                alive=p.alive,
                visible=p.alive,
                latitude_deg=p.latitude_deg,
                record_retained=name in self.entities,
                entity_key=name,
                entity_count=len(self.entities),
                **{
                    "type_of_" + key: "item" if isinstance(v, a.Item) else "object"
                    for key, v in self.entities.items()
                },
            )
        if isinstance(p, a.Message):
            if p.addressee != self.local:
                return {"message_id": p.message_id, "piggyback_ack": p.reply_ack}
            self.delivered.add((source, p.message_id, p.text))
            ack = a.Acknowledgment(source, p.message_id, reply_ack=p.reply_ack)
            return dict(
                deliveries=len(self.delivered),
                ack_to=source,
                ack_payload=a.serialize_payload(ack).decode(),
                pending_reply_ack=p.message_id,
                **(
                    {"outbound_message_" + p.reply_ack + "_acked": True}
                    if p.reply_ack
                    else {}
                ),
            )
        if isinstance(p, a.TelemetryDefinition):
            definitions = self.definitions.setdefault(p.addressee, {})
            d = p.definition
            definitions[type(d)] = d
            if isinstance(d, (a.TelemetryParameters, a.TelemetryUnits)):
                names = [f"A{i+1}" for i in range(5)] + [f"B{i+1}" for i in range(8)]
                return {
                    name
                    + (
                        ""
                        if isinstance(d, a.TelemetryParameters)
                        else "_unit"
                        if i < 5
                        else "_label"
                    ): v
                    for i, (name, v) in enumerate(zip(names, d.channels))
                }
            if isinstance(d, a.TelemetryEquations):
                return {
                    f"A{i+1}_coefficients": [v.a, v.b, v.c]
                    for i, v in enumerate(d.coefficients)
                    if v is not None
                }
            return {
                "sense_bits": "".join("1" if b else "0" for b in d.sense),
                "project": d.project_title,
            }
        if isinstance(p, a.Telemetry):
            definitions = self.definitions.get(source, {})
            result = {"raw_analog": list(p.analog)}
            eq = definitions.get(a.TelemetryEquations)
            units = definitions.get(a.TelemetryUnits)
            bits = definitions.get(a.TelemetryBits)
            if eq:
                for i, (v, c) in enumerate(zip(p.analog, eq.coefficients)):
                    if v is None or c is None:
                        continue
                    value = c.a * v * v + c.b * v + c.c
                    result[f"A{i+1}_calibrated"] = value
                    if units and units.channels[i] == "v/100":
                        result[f"A{i+1}_volts"] = value / 100
                    if units and units.channels[i] == "deg.F":
                        result[f"A{i+1}_fahrenheit"] = value
            if bits:
                result.update(
                    {
                        f"B{i+1}_label_active": b == sense
                        for i, (b, sense) in enumerate(zip(p.digital, bits.sense))
                        if b is not None
                    }
                )
            return result
        if isinstance(p, a.Bulletin):
            self.bulletins[source + "/" + p.identifier] = p.text
            return {"bulletins": dict(self.bulletins)}
        if isinstance(p, a.Status):
            self.status[source] = p.text
            return {"status": p.text}
        if isinstance(p, a.Beacon):
            self.fallback[source] = p.text
            return {
                "fallback_status": p.text,
                "status": self.status.get(source, p.text),
                "fallback_status_does_not_replace_explicit": source in self.status,
            }
        if isinstance(p, a.Position):
            self.positions[source] = p.coordinates
            return {
                "station_latitude_deg": p.latitude_deg,
                "station_longitude_deg": p.longitude_deg,
            }
        if isinstance(p, a.Weather):
            c = self.positions.get(source)
            t = p.temperature
            return {
                "weather_latitude_deg": c.latitude_deg if c else None,
                "weather_longitude_deg": c.longitude_deg if c else None,
                "temperature_c": (
                    (t.value - 32) / 1.8 if t.unit == "fahrenheit" else t.value
                ),
                "position_inherited_not_transmitted": True,
            }
        raise AssertionError(type(p))
