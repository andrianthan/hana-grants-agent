#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.hanna_stack import HannaStack

app = cdk.App()
HannaStack(app, "HannaGrantsStack",
    env=cdk.Environment(region="us-west-1"))
app.synth()
