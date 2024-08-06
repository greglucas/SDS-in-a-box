"""Test the indexer lambda stack."""

import pytest
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk.assertions import Template

from sds_data_manager.stacks.data_bucket_stack import DataBucketStack
from sds_data_manager.stacks.database_stack import SdpDatabase
from sds_data_manager.stacks.indexer_lambda_stack import IndexerLambda
from sds_data_manager.stacks.monitoring_stack import MonitoringStack
from sds_data_manager.stacks.networking_stack import NetworkingStack


@pytest.fixture()
def template(stack, env):
    """Indexer lambda setup."""
    data_bucket = DataBucketStack(stack, "indexer-data-bucket", env=env)
    networking_stack = NetworkingStack(stack, "Networking")
    rds_size = "SMALL"
    rds_class = "BURSTABLE3"
    rds_storage = 200
    database_stack = SdpDatabase(
        stack,
        "RDS",
        vpc=networking_stack.vpc,
        rds_security_group=networking_stack.rds_security_group,
        engine_version=rds.PostgresEngineVersion.VER_15_3,
        instance_size=ec2.InstanceSize[rds_size],
        instance_class=ec2.InstanceClass[rds_class],
        max_allocated_storage=rds_storage,
        username="imap",
        secret_name="sdp-database-creds-rds",  # noqa
        database_name="imapdb",
    )
    monitoring_stack = MonitoringStack(stack, construct_id="MonitoringStack")
    IndexerLambda(
        stack,
        "indexer-lambda",
        db_secret_name="test-secrets",  # noqa
        vpc=networking_stack.vpc,
        vpc_subnets=database_stack.rds_subnet_selection,
        rds_security_group=networking_stack.rds_security_group,
        data_bucket=data_bucket.data_bucket,
        sns_topic=monitoring_stack.sns_topic_notifications,
    )

    template = Template.from_stack(stack)

    return template


def test_indexer_role(template):
    """Ensure the template has appropriate IAM roles."""
    template.resource_count_is("AWS::IAM::Role", 4)
    # 2 for RDS + 1 for indexer lambda
    template.resource_count_is("AWS::Lambda::Function", 3)
