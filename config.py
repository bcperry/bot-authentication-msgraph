#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from pathlib import Path
from dotenv import load_dotenv

# Try to load .env from .azure/*/.env first, then fall back to root .env
azure_dir = Path(__file__).parent / ".azure"
if azure_dir.exists():
    # Find the first .env file in any subdirectory of .azure
    env_files = list(azure_dir.glob("*/.env"))
    if env_files:
        load_dotenv(env_files[0])
    else:
        load_dotenv()
else:
    load_dotenv()

""" Bot Configuration """


class DefaultConfig:
    """Bot Configuration"""

    PORT = 3978
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    APP_TYPE = os.environ.get("MicrosoftAppType", "SingleTenant")
    APP_TENANTID = os.environ.get("MicrosoftAppTenantId", "")
    CONNECTION_NAME = os.environ.get("ConnectionName", "")
