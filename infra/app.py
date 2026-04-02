#!/usr/bin/env python3
"""AWS CDK entry point for InstantNews infrastructure."""

import os
import aws_cdk as cdk
from stack import InstantNewsStack

app = cdk.App()

InstantNewsStack(
    app,
    "InstantNewsStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
    ),
    domain_name=app.node.try_get_context("domain") or "instnews.net",
)

app.synth()
