# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT
import os
import io
import tempfile
import requests
import logging

from typing import Callable

logger = logging.getLogger(__name__.rsplit(".", 1)[0])


def download_temp_and_process(url: str, process_fn: Callable[[str], None]) -> None:
    """
    Download a file at the given url, and save it to a temporary file.
    Once downloaded, call process_fn( tempfile_path ) which takes the
    path of the temporary file as the argument. Once done, clean up the
    temporary file.
    """
    BYTES_10MB = 1024 * 1024 * 10

    try:
        # Download the amateur radio database dump to a tmp file and parse it
        (fh, tmpfile) = tempfile.mkstemp()
        logger.debug(f"Created temp file '{tmpfile}' to receive download.")
        logger.info(f"Downloading: {url}")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()

            mb_progress = 0
            bytes_progress = 0

            # Stream the file
            logger.info(f"Download progress: {mb_progress}Mb")
            for chunk in r.iter_content(chunk_size=8192):
                os.write(fh, chunk)

                # Print download progress
                bytes_progress += len(chunk)
                while bytes_progress > BYTES_10MB:
                    bytes_progress -= BYTES_10MB
                    mb_progress += 10
                    logger.info(f"Download progress: {mb_progress}Mb")

            logger.info(
                f"Download progress: {mb_progress + (bytes_progress/(1024.0*1024.0))}Mb"
            )

        os.close(fh)
        process_fn(tmpfile)
    finally:
        logger.debug(f"Deleting temp file '{tmpfile}'.")
        os.unlink(tmpfile)
