#!/usr/bin/env python3
"""Temporary app for testing a Lambda and RDS."""

from pathlib import Path

from aws_cdk import App, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_rds as rds

from sds_data_manager.constructs import lambda_layer_construct

app = App()

rds_stack = Stack(app, "RdsStack")
# One public and one private subnet?
vpc = ec2.Vpc(rds_stack, "RDSVpc", max_azs=2, nat_gateways=0)

# Define the security group for the RDS instance
rds_security_group = ec2.SecurityGroup(
    rds_stack,
    "RdsDBSecurityGroup",
    vpc=vpc,
    description="Allow Lambda to access RDS",
    allow_all_outbound=True,
)

# Define the security group for the Lambda function
lambda_security_group = ec2.SecurityGroup(
    rds_stack,
    "LambdaDBSecurityGroup",
    vpc=vpc,
    description="Lambda security group",
    allow_all_outbound=True,
)

# Allow inbound connections from Lambda to RDS on Postgres port 5432
rds_security_group.add_ingress_rule(
    peer=lambda_security_group,
    connection=ec2.Port.tcp(5432),
    description="Allow Lambda to connect to RDS",
)

db = rds.DatabaseInstance(
    rds_stack,
    "RdsInstance",
    database_name="GregTestDB",
    credentials=rds.Credentials.from_generated_secret("greg"),
    engine=rds.DatabaseInstanceEngine.postgres(
        version=rds.PostgresEngineVersion.VER_15_6
    ),
    instance_type=ec2.InstanceType.of(
        ec2.InstanceClass["BURSTABLE3"], ec2.InstanceSize["MICRO"]
    ),
    vpc=vpc,
    vpc_subnets=ec2.SubnetSelection(
        # TODO: Make this private, using public for testing purposes
        # subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        subnet_type=ec2.SubnetType.PUBLIC
    ),
    security_groups=[rds_security_group],
    iam_authentication=True,
    publicly_accessible=True,
    deletion_protection=False,
    removal_policy=RemovalPolicy.DESTROY,
)


layer_code_directory = (Path(__file__).parent / "lambda_layer/python").resolve()

layer = lambda_layer_construct.LambdaLayerConstruct(
    scope=rds_stack,
    id="DatabaseDependencies",
    layer_dependencies_dir=str(layer_code_directory),
).layer

# Create an IAM Role that will be used by Lambda
lambda_role = iam.Role(
    rds_stack,
    "GregLambdaRole",
    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        ),
        iam.ManagedPolicy.from_aws_managed_policy_name("AmazonRDSFullAccess"),
    ],
)

# Attach RDS connection permissions to the IAM role
db.grant_connect(lambda_role, "GregLambdaRole")


func = lambda_.Function(
    rds_stack,
    "RdsTester",
    vpc=vpc,
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="rds-tester.handler",
    code=lambda_.Code.from_asset("sds_data_manager/lambda_code"),
    layers=[layer],
    role=lambda_role,
    security_groups=[lambda_security_group],
    environment={
        "HOST": db.db_instance_endpoint_address,
        "PORT": db.db_instance_endpoint_port,
        "USER": "GregLambdaRole",  # TODO: Do we need a specific user?
        "REGION": "us-east-1",
        "DBNAME": "GregTestDB",
    },
    architecture=lambda_.Architecture.ARM_64,
    timeout=Duration.seconds(30),
)

# NOTE: We added an explicit role above so can ignore this for now.
# https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.IAMPolicy.html
# func.add_to_role_policy(
#     statement=iam.PolicyStatement(
#         actions=["rds-db:connect"],
#         resources=["arn:aws:rds-db:us-east-1:174369828756:dbuser:*/*"],
#         # resources=[db.instance_arn],
#     )
# )
# This automatically handles the `rds-db:connect` IAM permission.
# db.grant_connect(func, "greg")


app.synth()
