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

from typing import NamedTuple, Any
from ._common import download_temp_and_process

ULS_AMAT_URL = "https://data.fcc.gov/download/pub/uls/complete/l_amat.zip"
ULS_GMRS_URL = "https://data.fcc.gov/download/pub/uls/complete/l_gmrs.zip"

EN_DATA_FILENAME = "EN.dat"
AM_DATA_FILENAME = "AM.dat"

logger = logging.getLogger(__name__.rsplit(".", 1)[0])


class ULS(object):
    def __init__(db_path=None):
        pass

    # Download and create the database
    @staticmethod
    def download():
        # Create it a temp database, then rename it to the final database
        try:
            (fh, tmpfile) = tempfile.mkstemp(suffix=".db")
            os.close(fh)
            ULS.__download(tmpfile)
            logger.debug(f"Renaming '{tmpfile}' to 'uls.db'")
            shutil.move(tmpfile, "uls.db")
        finally:
            # Clean up any debris
            if os.path.isfile(tmpfile):
                os.unlink(tmpfile)

    @staticmethod
    def __download(db_filename):
        logger.debug(f"Creating ULS database '{db_filename}'")

        # Create the database
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()

        # Create the "EN" table
        cursor.execute(
            """  
CREATE TABLE IF NOT EXISTS EN (  
    Service VARCHAR(5),
    Unique_System_Identifier VARCHAR(9),  
    ULS_File_Number VARCHAR(14),  
    EBF_Number VARCHAR(30),  
    Call_Sign VARCHAR(10),  
    Entity_Type VARCHAR(2),  
    Licensee_ID VARCHAR(9),  
    Entity_Name VARCHAR(200),  
    First_Name VARCHAR(20),  
    MI VARCHAR(1),  
    Last_Name VARCHAR(20),  
    Suffix VARCHAR(3),  
    Phone VARCHAR(10),  
    Fax VARCHAR(10),  
    Email VARCHAR(50),  
    Street_Address VARCHAR(60),  
    City VARCHAR(20),  
    State VARCHAR(2),  
    Zip_Code VARCHAR(9),  
    PO_Box VARCHAR(20),  
    Attention_Line VARCHAR(35),  
    SGIN VARCHAR(3),  
    FCC_Registration_Number VARCHAR(10),  
    Applicant_Type_Code VARCHAR(1),  
    Applicant_Type_Code_Other VARCHAR(40),  
    Status_Code VARCHAR(1),  
    Status_Date VARCHAR(10), -- Assuming ISO 8601 format 'YYYY-MM-DD'  
    GHz_License_Type_3_7 VARCHAR(1),  
    Linked_Unique_System_Identifier VARCHAR(9),  
    Linked_Call_Sign VARCHAR(10)  
);  
"""
        )

        # Create the "AM" table
        cursor.execute(
            """  
CREATE TABLE IF NOT EXISTS AM (
    Unique_System_Identifier VARCHAR(9),
    ULS_File_Number VARCHAR(14),
    EBF_Number VARCHAR(30),
    Call_Sign VARCHAR(10),
    Operator_Class VARCHAR(1),
    Group_Code VARCHAR(1),
    Region_Code VARCHAR(1),
    Trustee_Call_Sign VARCHAR(10),
    Trustee_Indicator VARCHAR(1),
    Physician_Certification VARCHAR(1),
    VE_Signature VARCHAR(1),
    Systematic_Call_Sign_Change VARCHAR(1),
    Vanity_Call_Sign_Change VARCHAR(1),
    Vanity_Relationship VARCHAR(12),
    Previous_Call_Sign VARCHAR(10),
    Previous_Operator_Class VARCHAR(1),
    Trustee_Name VARCHAR(50)
);
"""
        )

        # Create the main view
        cursor.execute(
            """
CREATE VIEW IF NOT EXISTS LicenseView AS
SELECT
    EN.Service,
    EN.Unique_System_Identifier,
    EN.ULS_File_Number,
    EN.Call_Sign,
    EN.Entity_Type,
    EN.Entity_Name,
    EN.First_Name,
    EN.MI AS Middle_Initial,
    EN.Last_Name,
    EN.Street_Address,
    EN.City,
    EN.State,
    EN.Zip_Code,
    EN.Status_Code,
    EN.Status_Date,
    EN.Linked_Call_Sign,
    AM.Operator_Class,
    AM.Group_Code,
    AM.Region_Code
FROM EN
    LEFT OUTER JOIN AM ON EN.Unique_System_Identifier = AM.Unique_System_Identifier;
"""
        )

        # Create indexes to keep things running smoothly
        cursor.execute("CREATE INDEX en_callsign_index ON EN (Call_Sign);")
        cursor.execute("CREATE INDEX am_callsign_index ON AM (Call_Sign);")
        cursor.execute(
            "CREATE UNIQUE INDEX en_id_index ON EN (Unique_System_Identifier);"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX am_id_index ON AM (Unique_System_Identifier);"
        )

        # Now populate the tables
        download_temp_and_process(
            ULS_AMAT_URL, lambda x: ULS.__process_uls_zip(x, cursor, "AMAT")
        )
        download_temp_and_process(
            ULS_GMRS_URL, lambda x: ULS.__process_uls_zip(x, cursor, "GMRS")
        )

        # Finalize things
        conn.commit()
        conn.close()

    @staticmethod
    def __process_uls_zip(filepath: str, db_cursor: Any, service_name: str) -> None:
        logger.info(f"Processing '{filepath}'")

        with zipfile.ZipFile(filepath, "r") as zh:
            # Ok, now open the zip file and read the EM table
            logger.debug(f"Reading '{EN_DATA_FILENAME}' in '{filepath}'")
            line_number = 0
            with zh.open(EN_DATA_FILENAME) as file:
                for line in io.TextIOWrapper(file, encoding="utf-8"):
                    line_number += 1
                    record = line.strip().split("|")[1:]
                    if len(record) != 29:
                        logger.info(
                            f"Line {line_number} of {EN_DATA_FILENAME} has the wrong number of EN columns. Skipping."
                        )
                        continue
                    ULS.__insert_en_record(db_cursor, [service_name] + record)
                    if line_number % 100000 == 0:
                        logger.info(
                            f"Read lines {line_number-100000+1} to {line_number}"
                        )
                logger.info(f"Done reading {line_number} lines.")

            # Ok, now open the zip file and read the AM table
            if AM_DATA_FILENAME in zh.namelist():
                with zh.open(AM_DATA_FILENAME) as file:
                    logger.debug(f"Reading '{AM_DATA_FILENAME}' in '{filepath}'")
                    line_number = 0
                    for line in io.TextIOWrapper(file, encoding="utf-8"):
                        line_number += 1
                        record = line.strip().split("|")[1:]
                        if len(record) != 17:
                            logger.info(
                                f"Line {line_number} of {AM_DATA_FILENAME} has the wrong number of AM columns. Skipping."
                            )
                            continue
                        ULS.__insert_am_record(db_cursor, record)
                        if line_number % 100000 == 0:
                            logger.info(
                                f"Read lines {line_number-100000+1} to {line_number}"
                            )
                    logger.info(f"Done reading {line_number} lines.")

    @staticmethod
    def __insert_en_record(db_cursor, record):
        db_cursor.execute(
            """ 
            INSERT INTO EN (  
                Service,
                Unique_System_Identifier,
                ULS_File_Number,
                EBF_Number,
                Call_Sign,
                Entity_Type,  
                Licensee_ID,
                Entity_Name,
                First_Name,
                MI,
                Last_Name,
                Suffix,
                Phone,
                Fax,
                Email,
                Street_Address,  
                City,
                State,
                Zip_Code,
                PO_Box,
                Attention_Line,
                SGIN,
                FCC_Registration_Number,
                Applicant_Type_Code,
                Applicant_Type_Code_Other,
                Status_Code,
                Status_Date,
                GHz_License_Type_3_7,
                Linked_Unique_System_Identifier,  
                Linked_Call_Sign  
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);  
            """,
            record,
        )

    @staticmethod
    def __insert_am_record(db_cursor, record):
        db_cursor.execute(
            """  
            INSERT INTO AM (  
                Unique_System_Identifier,
                ULS_File_Number,
                EBF_Number,
                Call_Sign,
                Operator_Class,  
                Group_Code,
                Region_Code,
                Trustee_Call_Sign,
                Trustee_Indicator,
                Physician_Certification,
                VE_Signature,  
                Systematic_Call_Sign_Change,
                Vanity_Call_Sign_Change,
                Vanity_Relationship,
                Previous_Call_Sign,  
                Previous_Operator_Class,
                Trustee_Name  
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);  
            """,
            record,
        )


# class ITU_Prefix(NamedTuple):
#    prefix: str
#    country_name: str
#    country_code: str
