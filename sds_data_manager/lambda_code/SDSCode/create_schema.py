"""Creates RDS PostgreSQL database schema.

Called by a custom resource in the CDK code once the RDS is created/updated.
https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.custom_resources/README.html
"""

import logging

from SDSCode.database import database as db
from SDSCode.database.models import Base
from SDSCode.dependency_config import all_dependents

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Entry point to the create schema lambda."""
    logger.info("Creating RDS tables")
    logger.info(event)

    # Create tables
    Base.metadata.create_all(db.get_engine())

    with db.Session() as session:
        session.add_all(all_dependents)
        session.commit()
