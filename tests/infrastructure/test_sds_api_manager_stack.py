"""Test the SDS API manager stack."""

import pytest
from aws_cdk.assertions import Template

from sds_data_manager.stacks.api_gateway_stack import ApiGateway
from sds_data_manager.stacks.data_bucket_stack import DataBucketStack
from sds_data_manager.stacks.networking_stack import NetworkingStack
from sds_data_manager.stacks.sds_api_manager_stack import SdsApiManager


@pytest.fixture()
def template(stack, env):
    """Return the data bucket stack."""
    data_bucket = DataBucketStack(stack, "indexer-data-bucket", env=env)
    networking_stack = NetworkingStack(stack, "Networking")
    apigw = ApiGateway(
        stack,
        construct_id="Api-manager-ApigwTest",
    )
    SdsApiManager(
        stack,
        "api-manager",
        env=env,
        api=apigw,
        data_bucket=data_bucket.data_bucket,
        vpc=networking_stack.vpc,
        rds_security_group=networking_stack.rds_security_group,
        db_secret_name="test-secrets",  # noqa
    )

    template = Template.from_stack(stack)
    return template


def test_indexer_role(template):
    """Ensure that the template has appropriate IAM roles."""
    template.resource_count_is("AWS::IAM::Role", 8)
    # Ensure that the template has appropriate lambda count
    template.resource_count_is("AWS::Lambda::Function", 6)
