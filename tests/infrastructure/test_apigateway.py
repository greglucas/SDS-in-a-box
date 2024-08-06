"""Test the API gateway stack."""

from pathlib import Path

import pytest
from aws_cdk import Duration, aws_lambda, aws_sns
from aws_cdk.assertions import Match, Template

from sds_data_manager.stacks.api_gateway_stack import ApiGateway, APILambda
from sds_data_manager.stacks.networking_stack import NetworkingStack


@pytest.fixture()
def template(stack):
    """Return a template for the API gateway stack."""
    test_func = aws_lambda.Function(
        stack,
        "test-function",
        code=aws_lambda.Code.from_inline("def handler(event, context):\n    pass"),
        handler="handler",
        runtime=aws_lambda.Runtime.PYTHON_3_9,
    )
    test_sns_topic = aws_sns.Topic(stack, "test-sns-topic")
    apigw = ApiGateway(
        stack,
        construct_id="ApigwTest",
    )
    apigw.deliver_to_sns(sns_topic=test_sns_topic)
    apigw.add_route("test-route", "GET", test_func)
    template = Template.from_stack(stack)
    return template


@pytest.fixture()
def lambda_template(stack):
    """Return a template for the API lambda stack."""
    lambda_code_directory = (
        Path(__file__).parent.parent.parent / "sds_data_manager/lambda_code"
    )
    spin_table_code = lambda_code_directory / "spin_table_api.py"
    vpc = NetworkingStack(stack, "networking-stack")
    APILambda(
        stack,
        "SpinLambda",
        lambda_name="test-lambda",
        code_path=spin_table_code,
        lambda_handler="lambda_handler",
        timeout=Duration.seconds(60),
        rds_security_group=vpc.rds_security_group,
        db_secret_name="test-creds",  # noqa
        vpc=vpc.vpc,
    )

    template = Template.from_stack(stack)
    return template


def test_apigw_routes(template):
    """Ensure that the template has the appropriate routes."""
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    # One path resource
    template.resource_count_is("AWS::ApiGateway::Resource", 1)
    template.has_resource_properties(
        "AWS::ApiGateway::Resource",
        props={"PathPart": "test-route"},
    )

    # One GET method on that resource
    template.resource_count_is("AWS::ApiGateway::Method", 1)
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        props={"HttpMethod": "GET"},
    )


def test_cloudwatch_alarm(template):
    """Ensure that the template has a CloudWatch alarm configured."""
    template.resource_count_is("AWS::CloudWatch::Alarm", 1)
    template.has_resource_properties(
        "AWS::CloudWatch::Alarm",
        props={
            "ComparisonOperator": "GreaterThanThreshold",
            "EvaluationPeriods": 60,
            "ActionsEnabled": True,
            "AlarmActions": [
                {"Fn::ImportValue": None, "Ref": Match.string_like_regexp("sns")}
            ],
            "DatapointsToAlarm": 1,
            "Dimensions": [{"Name": "ApiName", "Value": Match.any_value()}],
            "MetricName": "Latency",
            "Namespace": "AWS/ApiGateway",
            "Period": 60,
            "Statistic": "Maximum",
            "Threshold": 10000,
            "TreatMissingData": "notBreaching",
        },
    )


def test_api_lambda(lambda_template):
    """Ensure that the lambda template is configured properly."""
    lambda_template.resource_count_is("AWS::Lambda::Function", 1)
    lambda_template.resource_count_is("AWS::IAM::Role", 1)
    lambda_template.resource_count_is("AWS::IAM::Policy", 1)
    lambda_template.has_resource_properties(
        "AWS::Lambda::Function",
        props={
            "Handler": "spin_table_api.lambda_handler",
            "FunctionName": "test-lambda",
            "Timeout": 60,
        },
    )
