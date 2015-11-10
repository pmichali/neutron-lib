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

import re

import netaddr
from oslo_log import log as logging
from oslo_utils import uuidutils
import six

from neutron_lib.common import constants
from neutron_lib.common import exceptions as n_exc


LOG = logging.getLogger(__name__)

ATTR_NOT_SPECIFIED = object()
# Defining a constant to avoid repeating string literal in several modules
SHARED = 'shared'

# Used by range check to indicate no limit for a bound.
UNLIMITED = None

# TODO(watanabe.isao): A fix like in neutron/db/models_v2.py needs to be
# done in other db modules, to reuse the following constants.
# Common definitions for maximum string field length
NAME_MAX_LEN = 255
TENANT_ID_MAX_LEN = 255
DESCRIPTION_MAX_LEN = 255
DEVICE_ID_MAX_LEN = 255
DEVICE_OWNER_MAX_LEN = 255


def _verify_dict_keys(expected_keys, target_dict, strict=True):
    """Allows to verify keys in a dictionary.

    :param expected_keys: A list of keys expected to be present.
    :param target_dict: The dictionary which should be verified.
    :param strict: Specifies whether additional keys are allowed to be present.
    :return: True, if keys in the dictionary correspond to the specification.
    """
    if not isinstance(target_dict, dict):
        msg = (_("Invalid input. '%(target_dict)s' must be a dictionary "
                 "with keys: %(expected_keys)s") %
               {'target_dict': target_dict, 'expected_keys': expected_keys})
        LOG.debug(msg)
        return msg

    expected_keys = set(expected_keys)
    provided_keys = set(target_dict.keys())

    predicate = expected_keys.__eq__ if strict else expected_keys.issubset

    if not predicate(provided_keys):
        msg = (_("Validation of dictionary's keys failed. "
                 "Expected keys: %(expected_keys)s "
                 "Provided keys: %(provided_keys)s") %
               {'expected_keys': expected_keys,
                'provided_keys': provided_keys})
        LOG.debug(msg)
        return msg


def is_attr_set(attribute):
    return not (attribute is None or attribute is ATTR_NOT_SPECIFIED)


def _validate_values(data, valid_values=None):
    if data not in valid_values:
        msg = (_("'%(data)s' is not in %(valid_values)s") %
               {'data': data, 'valid_values': valid_values})
        LOG.debug(msg)
        return msg


def _validate_not_empty_string_or_none(data, max_len=None):
    if data is not None:
        return _validate_not_empty_string(data, max_len=max_len)


def _validate_not_empty_string(data, max_len=None):
    msg = _validate_string(data, max_len=max_len)
    if msg:
        return msg
    if not data.strip():
        msg = _("'%s' Blank strings are not permitted") % data
        LOG.debug(msg)
        return msg


def _validate_string_or_none(data, max_len=None):
    if data is not None:
        return _validate_string(data, max_len=max_len)


def _validate_string(data, max_len=None):
    if not isinstance(data, six.string_types):
        msg = _("'%s' is not a valid string") % data
        LOG.debug(msg)
        return msg

    if max_len is not None and len(data) > max_len:
        msg = (_("'%(data)s' exceeds maximum length of %(max_len)s") %
               {'data': data, 'max_len': max_len})
        LOG.debug(msg)
        return msg


def _validate_boolean(data, valid_values=None):
    try:
        convert_to_boolean(data)
    except n_exc.InvalidInput:
        msg = _("'%s' is not a valid boolean value") % data
        LOG.debug(msg)
        return msg


def _validate_range(data, valid_values=None):
    """Check that integer value is within a range provided.

    Test is inclusive. Allows either limit to be ignored, to allow
    checking ranges where only the lower or upper limit matter.
    It is expected that the limits provided are valid integers or
    the value None.
    """

    min_value = valid_values[0]
    max_value = valid_values[1]
    try:
        data = int(data)
    except (ValueError, TypeError):
        msg = _("'%s' is not an integer") % data
        LOG.debug(msg)
        return msg
    if min_value is not UNLIMITED and data < min_value:
        msg = _("'%(data)s' is too small - must be at least "
                "'%(limit)d'") % {'data': data, 'limit': min_value}
        LOG.debug(msg)
        return msg
    if max_value is not UNLIMITED and data > max_value:
        msg = _("'%(data)s' is too large - must be no larger than "
                "'%(limit)d'") % {'data': data, 'limit': max_value}
        LOG.debug(msg)
        return msg


def _validate_no_whitespace(data):
    """Validates that input has no whitespace."""
    if re.search(r'\s', data):
        msg = _("'%s' contains whitespace") % data
        LOG.debug(msg)
        raise n_exc.InvalidInput(error_message=msg)
    return data


def _validate_mac_address(data, valid_values=None):
    try:
        valid_mac = netaddr.valid_mac(_validate_no_whitespace(data))
    except Exception:
        valid_mac = False

    if valid_mac:
        valid_mac = not netaddr.EUI(data) in map(netaddr.EUI,
                    constants.INVALID_MAC_ADDRESSES)
    # TODO(arosen): The code in this file should be refactored
    # so it catches the correct exceptions. _validate_no_whitespace
    # raises AttributeError if data is None.
    if not valid_mac:
        msg = _("'%s' is not a valid MAC address") % data
        LOG.debug(msg)
        return msg


def _validate_mac_address_or_none(data, valid_values=None):
    if data is not None:
        return _validate_mac_address(data, valid_values)


def _validate_ip_address(data, valid_values=None):
    try:
        netaddr.IPAddress(_validate_no_whitespace(data))
        # The followings are quick checks for IPv6 (has ':') and
        # IPv4.  (has 3 periods like 'xx.xx.xx.xx')
        # NOTE(yamamoto): netaddr uses libraries provided by the underlying
        # platform to convert addresses.  For example, inet_aton(3).
        # Some platforms, including NetBSD and OS X, have inet_aton
        # implementation which accepts more varying forms of addresses than
        # we want to accept here.  The following check is to reject such
        # addresses.  For Example:
        #   >>> netaddr.IPAddress('1' * 59)
        #   IPAddress('199.28.113.199')
        #   >>> netaddr.IPAddress(str(int('1' * 59) & 0xffffffff))
        #   IPAddress('199.28.113.199')
        #   >>>
        if ':' not in data and data.count('.') != 3:
            raise ValueError()
    except Exception:
        msg = _("'%s' is not a valid IP address") % data
        LOG.debug(msg)
        return msg


def _validate_ip_pools(data, valid_values=None):
    """Validate that start and end IP addresses are present.

    In addition to this the IP addresses will also be validated
    """
    if not isinstance(data, list):
        msg = _("Invalid data format for IP pool: '%s'") % data
        LOG.debug(msg)
        return msg

    expected_keys = ['start', 'end']
    for ip_pool in data:
        msg = _verify_dict_keys(expected_keys, ip_pool)
        if msg:
            return msg
        for k in expected_keys:
            msg = _validate_ip_address(ip_pool[k])
            if msg:
                return msg


def _validate_fixed_ips(data, valid_values=None):
    if not isinstance(data, list):
        msg = _("Invalid data format for fixed IP: '%s'") % data
        LOG.debug(msg)
        return msg

    ips = []
    for fixed_ip in data:
        if not isinstance(fixed_ip, dict):
            msg = _("Invalid data format for fixed IP: '%s'") % fixed_ip
            LOG.debug(msg)
            return msg
        if 'ip_address' in fixed_ip:
            # Ensure that duplicate entries are not set - just checking IP
            # suffices. Duplicate subnet_id's are legitimate.
            fixed_ip_address = fixed_ip['ip_address']
            if fixed_ip_address in ips:
                msg = _("Duplicate IP address '%s'") % fixed_ip_address
                LOG.debug(msg)
            else:
                msg = _validate_ip_address(fixed_ip_address)
            if msg:
                return msg
            ips.append(fixed_ip_address)
        if 'subnet_id' in fixed_ip:
            msg = _validate_uuid(fixed_ip['subnet_id'])
            if msg:
                return msg


def _validate_nameservers(data, valid_values=None):
    if not hasattr(data, '__iter__'):
        msg = _("Invalid data format for nameserver: '%s'") % data
        LOG.debug(msg)
        return msg

    hosts = []
    for host in data:
        # This must be an IP address only
        msg = _validate_ip_address(host)
        if msg:
            msg = _("'%(host)s' is not a valid nameserver. %(msg)s") % {
                'host': host, 'msg': msg}
            LOG.debug(msg)
            return msg
        if host in hosts:
            msg = _("Duplicate nameserver '%s'") % host
            LOG.debug(msg)
            return msg
        hosts.append(host)


def _validate_hostroutes(data, valid_values=None):
    if not isinstance(data, list):
        msg = _("Invalid data format for hostroute: '%s'") % data
        LOG.debug(msg)
        return msg

    expected_keys = ['destination', 'nexthop']
    hostroutes = []
    for hostroute in data:
        msg = _verify_dict_keys(expected_keys, hostroute)
        if msg:
            return msg
        msg = _validate_subnet(hostroute['destination'])
        if msg:
            return msg
        msg = _validate_ip_address(hostroute['nexthop'])
        if msg:
            return msg
        if hostroute in hostroutes:
            msg = _("Duplicate hostroute '%s'") % hostroute
            LOG.debug(msg)
            return msg
        hostroutes.append(hostroute)


def _validate_ip_address_or_none(data, valid_values=None):
    if data is not None:
        return _validate_ip_address(data, valid_values)


def _validate_subnet(data, valid_values=None):
    msg = None
    try:
        net = netaddr.IPNetwork(_validate_no_whitespace(data))
        if '/' not in data or (net.version == 4 and str(net) != data):
            msg = _("'%(data)s' isn't a recognized IP subnet cidr,"
                    " '%(cidr)s' is recommended") % {"data": data,
                                                     "cidr": net.cidr}
        else:
            return
    except Exception:
        msg = _("'%s' is not a valid IP subnet") % data
    if msg:
        LOG.debug(msg)
    return msg


def _validate_subnet_list(data, valid_values=None):
    if not isinstance(data, list):
        msg = _("'%s' is not a list") % data
        LOG.debug(msg)
        return msg

    if len(set(data)) != len(data):
        msg = _("Duplicate items in the list: '%s'") % ', '.join(data)
        LOG.debug(msg)
        return msg

    for item in data:
        msg = _validate_subnet(item)
        if msg:
            return msg


def _validate_subnet_or_none(data, valid_values=None):
    if data is not None:
        return _validate_subnet(data, valid_values)


def _validate_regex(data, valid_values=None):
    try:
        if re.match(valid_values, data):
            return
    except TypeError:
        pass

    msg = _("'%s' is not a valid input") % data
    LOG.debug(msg)
    return msg


def _validate_regex_or_none(data, valid_values=None):
    if data is not None:
        return _validate_regex(data, valid_values)


def _validate_subnetpool_id(data, valid_values=None):
    if data != constants.IPV6_PD_POOL_ID:
        return _validate_uuid_or_none(data, valid_values)


def _validate_subnetpool_id_or_none(data, valid_values=None):
    if data is not None:
        return _validate_subnetpool_id(data, valid_values)


def _validate_uuid(data, valid_values=None):
    if not uuidutils.is_uuid_like(data):
        msg = _("'%s' is not a valid UUID") % data
        LOG.debug(msg)
        return msg


def _validate_uuid_or_none(data, valid_values=None):
    if data is not None:
        return _validate_uuid(data)


def _validate_uuid_list(data, valid_values=None):
    if not isinstance(data, list):
        msg = _("'%s' is not a list") % data
        LOG.debug(msg)
        return msg

    for item in data:
        msg = _validate_uuid(item)
        if msg:
            return msg

    if len(set(data)) != len(data):
        msg = _("Duplicate items in the list: '%s'") % ', '.join(data)
        LOG.debug(msg)
        return msg


def _validate_dict_item(key, key_validator, data):
    # Find conversion function, if any, and apply it
    conv_func = key_validator.get('convert_to')
    if conv_func:
        data[key] = conv_func(data.get(key))
    # Find validator function
    # TODO(salv-orlando): Structure of dict attributes should be improved
    # to avoid iterating over items
    val_func = val_params = None
    for (k, v) in six.iteritems(key_validator):
        if k.startswith('type:'):
            # ask forgiveness, not permission
            try:
                val_func = validators[k]
            except KeyError:
                msg = _("Validator '%s' does not exist.") % k
                LOG.debug(msg)
                return msg
            val_params = v
            break
    # Process validation
    if val_func:
        return val_func(data.get(key), val_params)


def _validate_dict(data, key_specs=None):
    if not isinstance(data, dict):
        msg = _("'%s' is not a dictionary") % data
        LOG.debug(msg)
        return msg
    # Do not perform any further validation, if no constraints are supplied
    if not key_specs:
        return

    # Check whether all required keys are present
    required_keys = [key for key, spec in six.iteritems(key_specs)
                     if spec.get('required')]

    if required_keys:
        msg = _verify_dict_keys(required_keys, data, False)
        if msg:
            return msg

    # Perform validation and conversion of all values
    # according to the specifications.
    for key, key_validator in [(k, v) for k, v in six.iteritems(key_specs)
                               if k in data]:
        msg = _validate_dict_item(key, key_validator, data)
        if msg:
            return msg


def _validate_dict_or_none(data, key_specs=None):
    if data is not None:
        return _validate_dict(data, key_specs)


def _validate_dict_or_empty(data, key_specs=None):
    if data != {}:
        return _validate_dict(data, key_specs)


def _validate_dict_or_nodata(data, key_specs=None):
    if data:
        return _validate_dict(data, key_specs)


def _validate_non_negative(data, valid_values=None):
    try:
        data = int(data)
    except (ValueError, TypeError):
        msg = _("'%s' is not an integer") % data
        LOG.debug(msg)
        return msg

    if data < 0:
        msg = _("'%s' should be non-negative") % data
        LOG.debug(msg)
        return msg


def convert_to_boolean(data):
    if isinstance(data, six.string_types):
        val = data.lower()
        if val == "true" or val == "1":
            return True
        if val == "false" or val == "0":
            return False
    elif isinstance(data, bool):
        return data
    elif isinstance(data, int):
        if data == 0:
            return False
        elif data == 1:
            return True
    msg = _("'%s' cannot be converted to boolean") % data
    raise n_exc.InvalidInput(error_message=msg)


def convert_to_boolean_if_not_none(data):
    if data is not None:
        return convert_to_boolean(data)


def convert_to_int(data):
    try:
        return int(data)
    except (ValueError, TypeError):
        msg = _("'%s' is not a integer") % data
        raise n_exc.InvalidInput(error_message=msg)


def convert_to_int_if_not_none(data):
    if data is not None:
        return convert_to_int(data)
    return data


def convert_to_positive_float_or_none(val):
    # NOTE(salv-orlando): This conversion function is currently used by
    # a vendor specific extension only at the moment  It is used for
    # port's RXTX factor in neutron.plugins.vmware.extensions.qos.
    # It is deemed however generic enough to be in this module as it
    # might be used in future for other API attributes.
    if val is None:
        return
    try:
        val = float(val)
        if val < 0:
            raise ValueError()
    except (ValueError, TypeError):
        msg = _("'%s' must be a non negative decimal.") % val
        raise n_exc.InvalidInput(error_message=msg)
    return val


def convert_kvp_str_to_list(data):
    """Convert a value of the form 'key=value' to ['key', 'value'].

    :raises: n_exc.InvalidInput if any of the strings are malformed
                                (e.g. do not contain a key).
    """
    kvp = [x.strip() for x in data.split('=', 1)]
    if len(kvp) == 2 and kvp[0]:
        return kvp
    msg = _("'%s' is not of the form <key>=[value]") % data
    raise n_exc.InvalidInput(error_message=msg)


def convert_kvp_list_to_dict(kvp_list):
    """Convert a list of 'key=value' strings to a dict.

    :raises: n_exc.InvalidInput if any of the strings are malformed
                                (e.g. do not contain a key) or if any
                                of the keys appear more than once.
    """
    if kvp_list == ['True']:
        # No values were provided (i.e. '--flag-name')
        return {}
    kvp_map = {}
    for kvp_str in kvp_list:
        key, value = convert_kvp_str_to_list(kvp_str)
        kvp_map.setdefault(key, set())
        kvp_map[key].add(value)
    return dict((x, list(y)) for x, y in six.iteritems(kvp_map))


def convert_none_to_empty_list(value):
    return [] if value is None else value


def convert_none_to_empty_dict(value):
    return {} if value is None else value


def convert_to_list(data):
    if data is None:
        return []
    elif hasattr(data, '__iter__') and not isinstance(data, six.string_types):
        return list(data)
    else:
        return [data]


HEX_ELEM = '[0-9A-Fa-f]'
UUID_PATTERN = '-'.join([HEX_ELEM + '{8}', HEX_ELEM + '{4}',
                         HEX_ELEM + '{4}', HEX_ELEM + '{4}',
                         HEX_ELEM + '{12}'])
# Note: In order to ensure that the MAC address is unicast the first byte
# must be even.
MAC_PATTERN = "^%s[aceACE02468](:%s{2}){5}$" % (HEX_ELEM, HEX_ELEM)

# Dictionary that maintains a list of validation functions
validators = {'type:dict': _validate_dict,
              'type:dict_or_none': _validate_dict_or_none,
              'type:dict_or_empty': _validate_dict_or_empty,
              'type:dict_or_nodata': _validate_dict_or_nodata,
              'type:fixed_ips': _validate_fixed_ips,
              'type:hostroutes': _validate_hostroutes,
              'type:ip_address': _validate_ip_address,
              'type:ip_address_or_none': _validate_ip_address_or_none,
              'type:ip_pools': _validate_ip_pools,
              'type:mac_address': _validate_mac_address,
              'type:mac_address_or_none': _validate_mac_address_or_none,
              'type:nameservers': _validate_nameservers,
              'type:non_negative': _validate_non_negative,
              'type:range': _validate_range,
              'type:regex': _validate_regex,
              'type:regex_or_none': _validate_regex_or_none,
              'type:string': _validate_string,
              'type:string_or_none': _validate_string_or_none,
              'type:not_empty_string': _validate_not_empty_string,
              'type:not_empty_string_or_none':
              _validate_not_empty_string_or_none,
              'type:subnet': _validate_subnet,
              'type:subnet_list': _validate_subnet_list,
              'type:subnet_or_none': _validate_subnet_or_none,
              'type:subnetpool_id': _validate_subnetpool_id,
              'type:subnetpool_id_or_none': _validate_subnetpool_id_or_none,
              'type:uuid': _validate_uuid,
              'type:uuid_or_none': _validate_uuid_or_none,
              'type:uuid_list': _validate_uuid_list,
              'type:values': _validate_values,
              'type:boolean': _validate_boolean}

# Define constants for base resource name
NETWORK = 'network'
NETWORKS = '%ss' % NETWORK
PORT = 'port'
PORTS = '%ss' % PORT
SUBNET = 'subnet'
SUBNETS = '%ss' % SUBNET
SUBNETPOOL = 'subnetpool'
SUBNETPOOLS = '%ss' % SUBNETPOOL

# Identify the attribute used by a resource to reference another resource

RESOURCE_FOREIGN_KEYS = {
    NETWORKS: 'network_id'
}

PLURALS = {NETWORKS: NETWORK,
           PORTS: PORT,
           SUBNETS: SUBNET,
           SUBNETPOOLS: SUBNETPOOL,
           'dns_nameservers': 'dns_nameserver',
           'host_routes': 'host_route',
           'allocation_pools': 'allocation_pool',
           'fixed_ips': 'fixed_ip',
           'extensions': 'extension'}
