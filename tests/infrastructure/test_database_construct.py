"""Test the database stack."""

import pytest
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk.assertions import Match, Template

from sds_data_manager.constructs.database_construct import SdpDatabase
from sds_data_manager.constructs.networking_construct import NetworkingConstruct


@pytest.fixture()
def template(stack):
    """Return a database template."""
    networking_construct = NetworkingConstruct(stack, "Networking")
    rds_size = "SMALL"
    rds_class = "BURSTABLE3"
    rds_storage = 200
    SdpDatabase(
        stack,
        "RDS",
        vpc=networking_construct.vpc,
        engine_version=rds.PostgresEngineVersion.VER_15_3,
        instance_size=ec2.InstanceSize[rds_size],
        instance_class=ec2.InstanceClass[rds_class],
        max_allocated_storage=rds_storage,
        username="imap",
        secret_name="sdp-database-creds-rds",  # noqa
        database_name="imapdb",
    )
    template = Template.from_stack(stack)

    return template


def test_database_construct(template):
    """Test the database infrastructure stack."""
    # Ensure that the template has the appropriate secrets manager."""
    template.resource_count_is("AWS::SecretsManager::Secret", 1)
    # Ensure that the template has the appropriate secret target attachement
    template.resource_count_is("AWS::SecretsManager::SecretTargetAttachment", 1)
    # Ensure that the template has the appropriate db subnet group
    template.resource_count_is("AWS::RDS::DBSubnetGroup", 1)
    # Ensure that the template has the appropriate DB instance
    template.resource_count_is("AWS::RDS::DBInstance", 1)

    # Ensure that the template has the appropriate RDS resource properties
    template.has_resource_properties(
        "AWS::RDS::DBInstance",
        props={
            "AllocatedStorage": "100",
            "CopyTagsToSnapshot": True,
            "DBInstanceClass": "db.t3.small",
            "DBName": "imapdb",
            "DBSubnetGroupName": {
                "Ref": Match.string_like_regexp("RdsInstanceSubnetGroup*")
            },
            "DeletionProtection": False,
            "Engine": "postgres",
            "EngineVersion": "15.3",
            "MaxAllocatedStorage": 200,
            "PubliclyAccessible": True,
            "StorageType": "gp2",
        },
    )
