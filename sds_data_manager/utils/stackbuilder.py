"""Module with helper functions for creating standard sets of stacks."""

from pathlib import Path

import imap_data_access
from aws_cdk import App, Environment, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds

from sds_data_manager.constructs import (
    api_gateway_construct,
    backup_bucket_construct,
    batch_compute_resources,
    create_schema_construct,
    data_bucket_construct,
    database_construct,
    domain_construct,
    ecr_construct,
    efs_construct,
    ialirt_bucket_construct,
    ialirt_processing_construct,
    indexer_lambda_construct,
    instrument_lambdas,
    monitoring_construct,
    networking_construct,
    sds_api_manager_construct,
    sqs_construct,
)


def build_sds(
    scope: App,
    env: Environment,
    account_config: dict,
):
    """Build the entire SDS.

    Parameters
    ----------
    scope : Construct
        Parent construct.
    env : Environment
        Account and region
    account_config : dict
        Account configuration (domain_name and other account specific configurations)

    """
    networking_stack = Stack(scope, "NetworkingStack", env=env)
    networking = networking_construct.NetworkingConstruct(
        networking_stack, "Networking"
    )

    sdc_stack = Stack(scope, "SDCStack", env=env)
    data_bucket = data_bucket_construct.DataBucketConstruct(
        scope=sdc_stack, construct_id="DataBucket", env=env
    )

    monitoring = monitoring_construct.MonitoringConstruct(
        scope=sdc_stack,
        construct_id="MonitoringConstruct",
    )

    domain = None
    domain_name = account_config.get("domain_name", None)
    account_name = account_config["account_name"]
    if domain_name is not None:
        domain = domain_construct.DomainConstruct(
            scope=sdc_stack,
            construct_id="DomainConstruct",
            domain_name=domain_name,
            account_name=account_name,
        )

    api = api_gateway_construct.ApiGateway(
        scope=sdc_stack,
        construct_id="ApiGateway",
        domain_construct=domain,
    )
    api.deliver_to_sns(monitoring.sns_topic_notifications)

    # Get RDS properties from account_config
    rds_size = account_config.get("rds_size", "SMALL")
    rds_class = account_config.get("rds_class", "BURSTABLE3")
    rds_storage = account_config.get("rds_construct", 200)
    db_secret_name = "sdp-database-cred"  # noqa
    rds_construct = database_construct.SdpDatabase(
        scope=sdc_stack,
        construct_id="RDS",
        vpc=networking.vpc,
        rds_security_group=networking.rds_security_group,
        engine_version=rds.PostgresEngineVersion.VER_15_6,
        instance_size=ec2.InstanceSize[rds_size],
        instance_class=ec2.InstanceClass[rds_class],
        max_allocated_storage=rds_storage,
        username="imap_user",
        secret_name=db_secret_name,
        database_name="imap",
    )

    indexer_lambda_construct.IndexerLambda(
        scope=sdc_stack,
        construct_id="IndexerLambda",
        db_secret_name=db_secret_name,
        vpc=networking.vpc,
        vpc_subnets=rds_construct.rds_subnet_selection,
        rds_security_group=networking.rds_security_group,
        data_bucket=data_bucket.data_bucket,
        sns_topic=monitoring.sns_topic_notifications,
    )

    sds_api_manager_construct.SdsApiManager(
        scope=sdc_stack,
        construct_id="SdsApiManager",
        api=api,
        env=env,
        data_bucket=data_bucket.data_bucket,
        vpc=networking.vpc,
        rds_security_group=networking.rds_security_group,
        db_secret_name=db_secret_name,
    )

    # create EFS
    efs_instance = efs_construct.EFSConstruct(
        scope=sdc_stack, construct_id="EFSConstruct", vpc=networking.vpc
    )

    lambda_code_directory = Path(__file__).parent.parent / "lambda_code"
    lambda_code_directory_str = str(lambda_code_directory.resolve())

    # This valid instrument list is from imap-data-access package
    for instrument in imap_data_access.VALID_INSTRUMENTS:
        ecr = ecr_construct.EcrConstruct(
            scope=sdc_stack,
            construct_id=f"{instrument}Ecr",
            instrument_name=f"{instrument}",
        )

        batch_compute_resources.FargateBatchResources(
            scope=sdc_stack,
            construct_id=f"{instrument}BatchJob",
            vpc=networking.vpc,
            processing_step_name=instrument,
            data_bucket=data_bucket.data_bucket,
            repo=ecr.container_repo,
            db_secret_name=db_secret_name,
            efs_instance=efs_instance,
            account_name=account_name,
        )

    # Create SQS pipeline for each instrument and add it to instrument_sqs
    instrument_sqs = sqs_construct.SqsConstruct(
        scope=sdc_stack,
        construct_id="SqsConstruct",
        instrument_names=imap_data_access.VALID_INSTRUMENTS,
    ).instrument_queue

    instrument_lambdas.BatchStarterLambda(
        scope=sdc_stack,
        construct_id="BatchStarterLambda",
        env=env,
        data_bucket=data_bucket.data_bucket,
        code_path=lambda_code_directory_str,
        rds_construct=rds_construct,
        rds_security_group=networking.rds_security_group,
        subnets=rds_construct.rds_subnet_selection,
        vpc=networking.vpc,
        sqs_queue=instrument_sqs,
    )

    create_schema_construct.CreateSchema(
        scope=sdc_stack,
        construct_id="CreateSchemaConstruct",
        db_secret_name=db_secret_name,
        vpc=networking.vpc,
        vpc_subnets=rds_construct.rds_subnet_selection,
        rds_security_group=networking.rds_security_group,
    )

    # create lambda that mounts EFS and writes data to EFS
    efs_construct.EFSWriteLambda(
        scope=sdc_stack,
        construct_id="EFSWriteLambda",
        env=env,
        vpc=networking.vpc,
        data_bucket=data_bucket.data_bucket,
        efs_instance=efs_instance,
    )

    ialirt_stack = Stack(scope, "IalirtStack", env=env)
    # I-ALiRT IOIS ECR
    ialirt_ecr = ecr_construct.EcrConstruct(
        scope=ialirt_stack,
        construct_id="IalirtEcr",
        instrument_name="IalirtEcr",
    )

    # I-ALiRT IOIS S3 bucket
    ialirt_bucket = ialirt_bucket_construct.IAlirtBucketConstruct(
        scope=ialirt_stack, construct_id="IAlirtBucket", env=env
    )

    # All traffic to I-ALiRT is directed to listed container ports
    ialirt_ports = {"Primary": [8080, 8081], "Secondary": [80]}
    container_ports = {"Primary": 8080, "Secondary": 80}

    for primary_or_secondary in ialirt_ports:
        ialirt_processing_construct.IalirtProcessing(
            scope=ialirt_stack,
            construct_id=f"IalirtProcessing{primary_or_secondary}",
            vpc=networking.vpc,
            repo=ialirt_ecr.container_repo,
            processing_name=primary_or_secondary,
            ialirt_ports=ialirt_ports[primary_or_secondary],
            container_port=container_ports[primary_or_secondary],
            ialirt_bucket=ialirt_bucket.ialirt_bucket,
        )


def build_backup(scope: App, env: Environment, source_account: str):
    """Build backup bucket with permissions for replication from source_account.

    Parameters
    ----------
    scope : Construct
        Parent construct.
    env : Environment
        Account and region
    source_account : str
        Account number for source bucket for replication

    """
    # This is the S3 bucket used by upload_api_lambda
    backup_bucket_construct.BackupBucket(
        scope,
        "BackupBucket",
        source_account=source_account,
        env=env,
    )
