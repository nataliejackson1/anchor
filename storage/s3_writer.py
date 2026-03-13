"""
S3 Writer — serializes CalendarEvent list to Parquet and uploads to S3.

Parquet file is partitioned by run date:
  s3://{bucket}/calendar/events/run_date=2026-03-12/events.parquet
"""

import io
import logging
import os
from datetime import datetime

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ingestion.calendar_schema import CalendarEvent
from config import settings

log = logging.getLogger(__name__)


def write_parquet_to_s3(events: list[CalendarEvent]) -> str:
    """
    Convert events to Parquet and write to S3.
    Returns the S3 path written to.
    """
    if not events:
        log.warning("No events to write — skipping S3 upload")
        return ""

    #  model → flat dicts → df
    rows = []
    for e in events:
        row = e.model_dump()
        row["attendees"] = ", ".join(e.attendees)
        row["tags"] = ", ".join(e.tags)
        rows.append(row)

    df = pd.DataFrame(rows)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["end_time"]   = pd.to_datetime(df["end_time"], utc=True)

    table = pa.Table.from_pandas(df)
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    buffer.seek(0)

    # Build S3 path with run-date partition
    run_date = datetime.now().strftime("%Y-%m-%d")

    #TODO: have sources in separate directories before paritioning? (i.e. google, school calendar, etc)
    s3_key = f"calendar/events/run_date={run_date}/events.parquet"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
    s3.upload_fileobj(buffer, settings.s3_bucket, s3_key)

    full_path = f"s3://{settings.s3_bucket}/{s3_key}"
    log.info(f"Uploaded {len(events)} events to {full_path}")
    return full_path
