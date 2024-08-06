"""Test the create schema stack."""

import pytest
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk.assertions import Match, Template

from sds_data_manager.stacks.create_schema_stack import CreateSchema
from sds_data_manager.stacks.database_stack import SdpDatabase
from sds_data_manager.stacks.networking_stack import NetworkingStack


@pytest.fixture()
def template(stack):
    """Return the networking stack."""
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

    CreateSchema(
        stack,
        construct_id="CreateSchema",
        db_secret_name="0123456789",  # noqa
        vpc=networking_stack.vpc,
        vpc_subnets=database_stack.rds_subnet_selection,
        rds_security_group=networking_stack.rds_security_group,
    )
    template = Template.from_stack(stack)

    return template


def test_create_schema(template):
    """Ensure that the template has the appropriate lambdas."""
    # there is a lambda for creating the schema and another lambda
    # that gets created for the "Provider Framework Event".
    template.resource_count_is("AWS::Lambda::Function", 2)
    template.resource_count_is("AWS::IAM::Policy", 2)
    template.resource_count_is("AWS::IAM::Role", 2)
    template.resource_count_is("AWS::CloudFormation::CustomResource", 1)

    # Lambda properties
    template.has_resource_properties(
        "AWS::Lambda::Function",
        props={
            "FunctionName": "create-schema",
            "Runtime": "python3.9",
            "Handler": "SDSCode.create_schema.lambda_handler",
            "MemorySize": 1000,
            "Timeout": 10,
            "Role": {
                "Fn::GetAtt": [
                    Match.string_like_regexp("CreateMetadataSchemaServiceRole*"),
                    "Arn",
                ]
            },
        },
    )
