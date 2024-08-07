"""CDK stack to create a Lambda Layer."""

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class LambdaLayerConstruct(Construct):
    """Lambda Layer Construct."""

    def __init__(
        self, scope: Construct, id: str, layer_dependencies_dir: str, **kwargs
    ) -> None:
        """Create layer stack.

        In layer code directory, there should exist a requirements.txt file
        which is used to install the dependencies for the lambda layer.


        Parameters
        ----------
        scope : obj
            Parent construct
        id : str
            A unique string identifier for this construct
        layer_dependencies_dir : str
            Directory containing the lambda layer requirements.txt file
        kwargs : dict
            Keyword arguments
        """
        super().__init__(scope, id, **kwargs)

        code_bundle = lambda_.Code.from_asset(
            layer_dependencies_dir,
            bundling=cdk.BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                command=[
                    "bash",
                    "-c",
                    (
                        "pip install -r requirements.txt -t /asset-output/python && "
                        "cp -au . /asset-output/python"
                    ),
                ],
            ),
        )

        self.layer = lambda_.LayerVersion(
            self,
            id=f"{id}-Layer",
            code=code_bundle,
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
        )
