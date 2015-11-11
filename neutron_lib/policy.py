# Copyright (c) 2012 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import collections
import re

from oslo_config import cfg
from oslo_policy import policy


POLICY_ENFORCER = None

ADMIN_CTX_POLICY = 'context_is_admin'
ADVSVC_CTX_POLICY = 'context_is_advsvc'


def reset():
    global POLICY_ENFORCER
    if POLICY_ENFORCER:
        POLICY_ENFORCER.clear()
        POLICY_ENFORCER = None


def init(conf=cfg.CONF, policy_file=None):
    """Init an instance of the Enforcer class."""

    global POLICY_ENFORCER
    if not POLICY_ENFORCER:
        POLICY_ENFORCER = policy.Enforcer(conf, policy_file=policy_file)
        POLICY_ENFORCER.load_rules(True)


def refresh(policy_file=None):
    """Reset policy and init a new instance of Enforcer."""
    reset()
    init(policy_file=policy_file)


def check_is_admin(context):
    """Verify context has admin rights according to policy settings."""
    init()
    # the target is user-self
    credentials = context.to_dict()
    if ADMIN_CTX_POLICY not in POLICY_ENFORCER.rules:
        return False
    return POLICY_ENFORCER.enforce(ADMIN_CTX_POLICY, credentials, credentials)


def check_is_advsvc(context):
    """Verify context has advsvc rights according to policy settings."""
    init()
    # the target is user-self
    credentials = context.to_dict()
    if ADVSVC_CTX_POLICY not in POLICY_ENFORCER.rules:
        return False
    return POLICY_ENFORCER.enforce(ADVSVC_CTX_POLICY, credentials, credentials)
