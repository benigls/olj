import dlt

from .config import DATASET_NAME, PIPELINE_NAME


def get_pipeline():
    return dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination="postgres",
        dataset_name=DATASET_NAME,
    )
