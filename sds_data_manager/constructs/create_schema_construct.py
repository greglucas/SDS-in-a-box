"""Configure the schema stack."""

import pathlib

import aws_cdk
from aws_cdk import CustomResource
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python_alpha as lambda_alpha_
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import custom_resources as cr
from constructs import Construct


class CreateSchema(Construct):
    """Construct for creating schema creation lambda."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        db_secret_name: str,
        vpc: ec2.Vpc,
        vpc_subnets,
        rds_security_group,
        **kwargs,
    ) -> None:
        """Create schema stack.

        Parameters
        ----------
        scope : Construct
            The App object in which to create this Construct
        construct_id : str
            The ID (name) of the stack
        db_secret_name : str
            The DB secret name
        vpc : ec2.Vpc
            Virtual private cloud
        vpc_subnets : obj
            The VPC subnets
        rds_security_group : obj
            The RDS security group
        kwargs : dict
            Keyword arguments

        """
        super().__init__(scope, construct_id, **kwargs)

        schema_create_lambda = lambda_alpha_.PythonFunction(
            self,
            id="CreateMetadataSchema",
            function_name="create-schema",
            entry=str(
                pathlib.Path(__file__).parent.joinpath("..", "lambda_code").resolve()
            ),
            index="SDSCode/create_schema.py",
            handler="lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            timeout=aws_cdk.Duration.seconds(10),
            memory_size=1000,
            allow_public_subnet=True,
            vpc=vpc,
            vpc_subnets=vpc_subnets,
            security_groups=[rds_security_group],
            environment={
                "SECRET_NAME": db_secret_name,
            },
        )

        res_provider = cr.Provider(
            self, "crProvider", on_event_handler=schema_create_lambda
        )
        CustomResource(self, "cust_res", service_token=res_provider.service_token)

        rds_secret = secrets.Secret.from_secret_name_v2(
            self, "rds_secret", db_secret_name
        )
        rds_secret.grant_read(grantee=schema_create_lambda)
