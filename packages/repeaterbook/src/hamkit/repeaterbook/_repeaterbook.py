# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT
import os
import io
import tempfile
import zipfile
import logging
import sqlite3
import shutil
import errno
import json
import time

from typing import NamedTuple, List, Any
from haversine import haversine, inverse_haversine, Unit, Direction
from ._common import download_temp_and_process

logger = logging.getLogger(__name__.rsplit(".", 1)[0])


class Repeater(NamedTuple):
    callsign: str | None
    downlink_freq: float | None
    downlink_tone: str | None
    uplink_freq: float | None
    uplink_tone: str | None
    nearest_city: str | None
    landmark: str | None
    county: str | None
    state: str | None
    state_id: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    precise: float | None
    use: str | None
    operational_status: str | None
    fm_analog: bool | None
    ares: bool | None
    races: bool | None
    skywarn: bool | None
    canwarn: bool | None
    allstar_node: str | None
    echoLink_node: str | None
    irlp_node: str | None
    wires_node: str | None
    dmr: bool | None
    dmr_color_code: str | None
    dmr_id: str | None
    dstar: bool | None
    nxdn: bool | None
    apco_p25: bool | None
    p25_nac: str | None
    m17: bool | None
    m17_can: str | None
    tetra: bool | None
    tetra_mcc: str | None
    tetra_mnc: str | None
    system_fusion: bool | None
    ysf_dg_id_uplink: str | None
    ysf_dg_is_downlink: str | None
    ysf_dsc: str | None
    notes: str | None
    last_update: str | None
    distance: float | None


class RepeaterBook(object):
    def __init__(self, db_filename: str):
        if not os.path.isfile(db_filename):
            raise FileNotFoundError(
                errno.ENOENT,
                (
                    f"The RepeaterBook database file '{db_filename}' was not found.\n"
                    f"To download the database, use the static method:\n"
                    f"    RepeaterBook.download('{db_filename}')"
                ),
            )
        self._db_filename = db_filename

    def find_nearest(self, lat, lon, max_distance=80):
        # Give us a "box" we can query with
        origin = (lat, lon)

        north = inverse_haversine(
            origin, max_distance, Direction.NORTH, unit=Unit.KILOMETERS
        )[0]
        south = inverse_haversine(
            origin, max_distance, Direction.SOUTH, unit=Unit.KILOMETERS
        )[0]
        east = inverse_haversine(
            origin, max_distance, Direction.EAST, unit=Unit.KILOMETERS
        )[1]
        west = inverse_haversine(
            origin, max_distance, Direction.WEST, unit=Unit.KILOMETERS
        )[1]

        # If we've gone all the way around, things get messy. Just open it up to everything.
        if south > north:
            north = 90
            south = -90
        if west > east:
            west = -180
            east = 180

        # Connect to the SQLite database
        conn = sqlite3.connect(self._db_filename)
        cursor = conn.cursor()

        # SQL query to select a short-list of candidates
        cursor.execute(
            """SELECT 
            Callsign,
            Downlink_Freq,
            Downlink_Tone,
            Uplink_Freq,
            Uplink_Tone,
            Nearest_City,
            Landmark,
            County,
            State,
            State_ID,
            Country,
            Latitude,
            Longitude,
            Precise,
            Use,
            Operational_Status,
            FM_Analog,
            ARES,
            RACES,
            SKYWARN,
            CANWARN,
            AllStar_Node,
            EchoLink_Node,
            IRLP_Node,
            Wires_Node,
            DMR,
            DMR_Color_Code,
            DMR_ID,
            DStar,
            NXDN,
            APCO_P25,
            P25_NAC,
            M17,
            M17_CAN,
            Tetra,
            Tetra_MCC,
            Tetra_MNC,
            System_Fusion,
            YSF_DG_ID_Uplink,
            YSF_DG_IS_Downlink,
            YSF_DSC,
            Notes,
            Last_Update
            FROM Repeaters
            WHERE 
                (Latitude BETWEEN ? AND ?) AND
                (Longitude BETWEEN ? AND ?);
            """,
            (south, north, west, east),
        )

        # Do the search
        results = []
        rows = cursor.fetchall()
        for row in rows:
            args = [v for v in row]
            args.append(haversine(origin, (row[11], row[12]), unit=Unit.KILOMETERS))

            repeater = Repeater(*args)

            # Check the distance
            if repeater.distance > max_distance:
                continue

            # Append the result
            results.append(repeater)

        conn.close()

        # Sort the results by distance
        results.sort(key=lambda x: x.distance)
        return results

    # Download and create the database
    @staticmethod
    def download(
        db_filename: str,
        sources: List[str],
        overwrite: bool = False,
    ) -> None:
        """
        Download the RepeaterBook data and load it into a local sqlite database for querying.

        Parameters:
            db_filename:  The location of the sqlite database to create.
            sources:      A list of URIs to download, or local file paths. Each URI or file
                          must resolve to a json file that uses the RepeaterBook format.
                          E.g.,
                            ["https://www.repeaterbook.com/api/export.php?state=Washington"]
                          Or
                            ["./cache/Washington.json"]

                                  Repeated calls to repeaterbook.com are internally rate-limited to
                                  one per minute.

                          CAUTION: each call to RepeaterBook will return a limited number
                                   of records (at this time 3500). It is best to gather only
                                   what you need, such as one state.
                                   DO NOT MAKE FREQUENT CALLS, or you will be rate-limited or
                                   blocked.

                          For details see: https://www.repeaterbook.com/wiki/doku.php?id=api

            overwrite:    If true, overwrite any existing file (Default: False)
        """

        # Check if we are overwriting the file
        if os.path.isfile(db_filename):
            if overwrite == False:
                raise FileExistsError(
                    errno.EEXIST,
                    (
                        f"The file '{db_filename}' aleady exists. Operation aborted. "
                        "Set overwrite=True to overwrite overwrite existing files."
                    ),
                )
            elif not os.access(db_filename, os.W_OK):
                raise PermissionError(errno.EPERM, "Permission denied", db_filename)
        else:
            # Check if we can write to the intended destination
            with open(db_filename, "wb") as fh:
                pass
            os.unlink(db_filename)

        # Create it a temp database, then rename it to the final database
        try:
            (fh, tmpfile) = tempfile.mkstemp(suffix=".db")
            os.close(fh)
            RepeaterBook.__download(tmpfile, sources)
            logger.debug(f"Renaming '{tmpfile}' to '{db_filename}'")
            shutil.move(tmpfile, db_filename)
        finally:
            # Clean up any debris
            if os.path.isfile(tmpfile):
                os.unlink(tmpfile)

    @staticmethod
    def __download(db_filename: str, sources: List[str]):
        logger.debug(f"Creating RepeaterBook database '{db_filename}'")

        # Create the database
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()

        # Create the "EN" table
        cursor.execute(
            """  
            CREATE TABLE IF NOT EXISTS Repeaters (  
                Id INTEGER PRIMARY KEY,
                Callsign TEXT,
                Downlink_Freq REAL,
                Downlink_Tone TEXT,
                Uplink_Freq REAL,
                Uplink_Tone TEXT,
                Nearest_City TEXT,
                Landmark TEXT,
                County TEXT,
                State TEXT,
                State_ID TEXT,
                Country TEXT,
                Latitude REAL,
                Longitude REAL,
                Precise BOOLEAN,
                Use TEXT,
                Operational_Status TEXT,
                FM_Analog BOOLEAN,
                ARES BOOLEAN,
                RACES BOOLEAN,
                SKYWARN BOOLEAN,
                CANWARN BOOLEAN,
                AllStar_Node TEXT,
                EchoLink_Node TEXT,
                IRLP_Node TEXT,
                Wires_Node TEXT,
                DMR BOOLEAN,
                DMR_Color_Code TEXT,
                DMR_ID TEXT,
                DStar BOOLEAN,
                NXDN BOOLEAN,
                APCO_P25 BOOLEAN,
                P25_NAC TEXT,
                M17 BOOLEAN,
                M17_CAN TEXT,
                Tetra BOOLEAN,
                Tetra_MCC TEXT,
                Tetra_MNC TEXT,
                System_Fusion BOOLEAN,
                YSF_DG_ID_Uplink TEXT,
                YSF_DG_IS_Downlink TEXT,
                YSF_DSC TEXT,
                Notes TEXT,
                Last_Update TEXT
            );  
            """
        )

        cursor.execute("CREATE INDEX callsign_index ON Repeaters (Callsign);")
        cursor.execute("CREATE INDEX lat_lon_index ON Repeaters (Latitude, Longitude);")

        last_fetch_time = 0
        for source in sources:
            # Work locally if it's a local path
            if os.path.isfile(source):
                RepeaterBook.__process_json(source, cursor)
            else:
                # Rate limit
                sleep_time = 60 - (time.time() - last_fetch_time)
                if sleep_time > 0:
                    logger.info(f"Sleeping for {sleep_time}s")
                    time.sleep(sleep_time)

                download_temp_and_process(
                    source, lambda x: RepeaterBook.__process_json(x, cursor)
                )

                last_fetch_time = time.time()

        # Finalize things
        conn.commit()
        conn.close()

    @staticmethod
    def __process_json(filepath: str, db_cursor: Any) -> None:
        logger.info(f"Processing '{filepath}'")

        with open(filepath, "rt") as fh:
            records = json.loads(fh.read())
            for record in records.get("results", []):
                RepeaterBook.__insert_record(db_cursor, record)

    @staticmethod
    def __insert_record(db_cursor, record):
        def _real_or_None(s):
            if s is None:
                return None
            elif isinstance(s, str) and s.strip() == "":
                return None
            else:
                return float(s)

        def _bool_or_None(s):
            if s is None:
                return None
            if isinstance(s, str):
                if s.strip().lower() in ["yes", "true", "t", "1"]:
                    return True
                elif s.strip().lower() in ["no", "false", "f", "0"]:
                    return False
                else:
                    return None

        def _strip_or_None(s):
            if s is None:
                return None
            return s.strip()

        db_cursor.execute(
            """INSERT INTO Repeaters (
            Callsign,
            Downlink_Freq,
            Downlink_Tone,
            Uplink_Freq,
            Uplink_Tone,
            Nearest_City,
            Landmark,
            County,
            State,
            State_ID,
            Country,
            Latitude,
            Longitude,
            Precise,
            Use,
            Operational_Status,
            FM_Analog,
            ARES,
            RACES,
            SKYWARN,
            CANWARN,
            AllStar_Node,
            EchoLink_Node,
            IRLP_Node,
            Wires_Node,
            DMR,
            DMR_Color_Code,
            DMR_ID,
            DStar,
            NXDN,
            APCO_P25,
            P25_NAC,
            M17,
            M17_CAN,
            Tetra,
            Tetra_MCC,
            Tetra_MNC,
            System_Fusion,
            YSF_DG_ID_Uplink,
            YSF_DG_IS_Downlink,
            YSF_DSC,
            Notes,
            Last_Update
        ) VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? );""",
            (
                _strip_or_None(record.get("Callsign")),
                _real_or_None(record.get("Frequency")),
                _strip_or_None(record.get("TSQ")),
                _real_or_None(record.get("Input Freq")),
                _strip_or_None(record.get("PL")),
                _strip_or_None(record.get("Nearest City")),
                _strip_or_None(record.get("Landmark")),
                _strip_or_None(record.get("County")),
                _strip_or_None(record.get("State")),
                _strip_or_None(record.get("State ID")),
                _strip_or_None(record.get("Country")),
                _real_or_None(record.get("Lat")),
                _real_or_None(record.get("Long")),
                _real_or_None(record.get("Precise")),
                _strip_or_None(record.get("Use")),
                _strip_or_None(record.get("Operational Status")),
                _bool_or_None(record.get("FM Analog")),
                _bool_or_None(record.get("ARES")),
                _bool_or_None(record.get("RACES")),
                _bool_or_None(record.get("SKYWARN")),
                _bool_or_None(record.get("CANWARN")),
                _strip_or_None(record.get("AllStar Node")),
                _strip_or_None(record.get("EchoLink Node")),
                _strip_or_None(record.get("IRLP Node")),
                _strip_or_None(record.get("Wires Node")),
                _bool_or_None(record.get("DMR")),
                _strip_or_None(record.get("DMR Color Code")),
                _strip_or_None(record.get("DMR ID")),
                _bool_or_None(record.get("D-Star")),
                _bool_or_None(record.get("NXDN")),
                _bool_or_None(record.get("APCO P-25")),
                _strip_or_None(record.get("P-25 NAC")),
                _bool_or_None(record.get("M17")),
                _strip_or_None(record.get("M17 CAN")),
                _bool_or_None(record.get("Tetra")),
                _strip_or_None(record.get("Tetra MCC")),
                _strip_or_None(record.get("Tetra MNC")),
                _bool_or_None(record.get("System Fusion")),
                _strip_or_None(record.get("YSF DG ID Uplink")),
                _strip_or_None(record.get("YSF DG IS Downlink")),
                _strip_or_None(record.get("YSF DSC")),
                _strip_or_None(record.get("Notes")),
                _strip_or_None(record.get("Last Update")),
            ),
        )
