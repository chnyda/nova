# Copyright 2013 OpenStack Foundation
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

from oslo_log import log as logging
from webob import exc

from nova.api.openstack.api_version_request \
    import MAX_PROXY_API_SUPPORT_VERSION
from nova.api.openstack import wsgi
import nova.conf
from nova import context as nova_context
from nova import exception
from nova.i18n import _
import nova.network
from nova.policies import tenant_networks as tn_policies
from nova import quota


CONF = nova.conf.CONF

QUOTAS = quota.QUOTAS
LOG = logging.getLogger(__name__)


def network_dict(network):
    # NOTE(danms): Here, network should be an object, which could have come
    # from neutron and thus be missing most of the attributes. Providing a
    # default to get() avoids trying to lazy-load missing attributes.
    return {"id": network.get("uuid", None) or network.get("id", None),
                        "cidr": str(network.get("cidr", None)),
                        "label": network.get("label", None)}


class TenantNetworkController(wsgi.Controller):
    def __init__(self):
        super(TenantNetworkController, self).__init__()
        self.network_api = nova.network.API()
        self._default_networks = []

    def _refresh_default_networks(self):
        self._default_networks = []
        if CONF.api.use_neutron_default_nets:
            try:
                self._default_networks = self._get_default_networks()
            except Exception:
                LOG.exception("Failed to get default networks")

    def _get_default_networks(self):
        project_id = CONF.api.neutron_default_tenant_id
        ctx = nova_context.RequestContext(user_id=None,
                                          project_id=project_id)
        networks = {}
        for n in self.network_api.get_all(ctx):
            networks[n['id']] = n['label']
        return [{'id': k, 'label': v} for k, v in networks.items()]

    @wsgi.Controller.api_version("2.1", MAX_PROXY_API_SUPPORT_VERSION)
    @wsgi.expected_errors(())
    def index(self, req):
        context = req.environ['nova.context']
        context.can(tn_policies.BASE_POLICY_NAME)
        networks = list(self.network_api.get_all(context))
        if not self._default_networks:
            self._refresh_default_networks()
        networks.extend(self._default_networks)
        return {'networks': [network_dict(n) for n in networks]}

    @wsgi.Controller.api_version("2.1", MAX_PROXY_API_SUPPORT_VERSION)
    @wsgi.expected_errors(404)
    def show(self, req, id):
        context = req.environ['nova.context']
        context.can(tn_policies.BASE_POLICY_NAME)
        try:
            network = self.network_api.get(context, id)
        except exception.NetworkNotFound:
            msg = _("Network not found")
            raise exc.HTTPNotFound(explanation=msg)
        return {'network': network_dict(network)}

    @wsgi.expected_errors(410)
    def delete(self, req, id):
        raise exc.HTTPGone()

    @wsgi.expected_errors(410)
    def create(self, req, body):
        raise exc.HTTPGone()
