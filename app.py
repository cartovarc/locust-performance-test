#!/usr/bin/env python3
import aws_cdk as cdk

from locus_performance.locus_performance_stack import LocusPerformanceStack


app = cdk.App()
LocusPerformanceStack(app, "LocusPerformanceStack")

app.synth()
