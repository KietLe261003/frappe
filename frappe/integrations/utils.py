# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import datetime
import json
from typing import Any, cast
from urllib.parse import parse_qs

from pydantic import BaseModel, HttpUrl

import frappe
from frappe.integrations.doctype.oauth_client.oauth_client import OAuthClient
from frappe.utils import get_request_session


<<<<<<< HEAD
def make_request(method, url, auth=None, headers=None, data=None, json=None, params=None):
=======
class OAuth2DynamicClientMetadata(BaseModel):
	"""
	OAuth 2.0 Dynamic Client Registration Metadata.

	As defined in RFC7591 - OAuth 2.0 Dynamic Client Registration Protocol
	https://datatracker.ietf.org/doc/html/rfc7591#section-2
	"""

	#  Used to identify the client to the authorization server
	redirect_uris: list[HttpUrl]
	token_endpoint_auth_method: str | None = "client_secret_basic"
	grant_types: list[str] | None = ["authorization_code"]
	response_types: list[str] | None = ["code"]

	#  Client identifiers shown to user
	client_name: str
	scope: str
	client_uri: HttpUrl | None = None
	logo_uri: HttpUrl | None = None

	#  Client contact and other information for the client
	contacts: list[str] | None = None
	tos_uri: HttpUrl | None = None
	policy_uri: HttpUrl | None = None
	software_id: str | None = None
	software_version: str | None = None

	#  JSON Web Key Set (JWKS) not used here
	jwks_uri: HttpUrl | None = None
	jwks: dict | None = None


def make_request(method: str, url: str, auth=None, headers=None, data=None, json=None, params=None):
>>>>>>> 3a47801598 (feat(OAuth2): support RFC 7591)
	auth = auth or ""
	data = data or {}
	headers = headers or {}

	try:
		s = get_request_session()
		response = frappe.flags.integration_request = s.request(
			method, url, data=data, auth=auth, headers=headers, json=json, params=params
		)
		response.raise_for_status()

		# Check whether the response has a content-type, before trying to check what it is
		if content_type := response.headers.get("content-type"):
			if content_type == "text/plain; charset=utf-8":
				return parse_qs(response.text)
			elif content_type.startswith("application/") and content_type.split(";")[0].endswith("json"):
				return response.json()
			elif response.text:
				return response.text
		return
	except Exception as exc:
		frappe.log_error()
		raise exc


def make_get_request(url, **kwargs):
	return make_request("GET", url, **kwargs)


def make_post_request(url, **kwargs):
	return make_request("POST", url, **kwargs)


def make_put_request(url, **kwargs):
	return make_request("PUT", url, **kwargs)


def make_patch_request(url, **kwargs):
	return make_request("PATCH", url, **kwargs)


def make_delete_request(url, **kwargs):
	return make_request("DELETE", url, **kwargs)


def create_request_log(
	data,
	integration_type=None,
	service_name=None,
	name=None,
	error=None,
	request_headers=None,
	output=None,
	**kwargs,
):
	"""
	DEPRECATED: The parameter integration_type will be removed in the next major release.
	Use is_remote_request instead.
	"""
	if integration_type == "Remote":
		kwargs["is_remote_request"] = 1

	elif integration_type == "Subscription Notification":
		kwargs["request_description"] = integration_type

	reference_doctype = reference_docname = None
	if "reference_doctype" not in kwargs:
		if isinstance(data, str):
			data = json.loads(data)

		reference_doctype = data.get("reference_doctype")
		reference_docname = data.get("reference_docname")

	integration_request = frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": service_name,
			"request_headers": get_json(request_headers),
			"data": get_json(data),
			"output": get_json(output),
			"error": get_json(error),
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			**kwargs,
		}
	)

	if name:
		integration_request.flags._name = name

	integration_request.insert(ignore_permissions=True)
	frappe.db.commit()

	return integration_request


def get_json(obj):
	return obj if isinstance(obj, str) else frappe.as_json(obj, indent=1)


def json_handler(obj):
	if isinstance(obj, datetime.date | datetime.timedelta | datetime.datetime):
		return str(obj)


def validate_dynamic_client_metadata(client: OAuth2DynamicClientMetadata):
	invalidation_reasons = []
	if len(client.redirect_uris) == 0:
		invalidation_reasons.append("redirect_uris is required")

	if client.token_endpoint_auth_method not in ["client_secret_basic"]:
		invalidation_reasons.append("only client_secret_basic token_endpoint_auth_method is supported")

	if client.grant_types and not set(client.grant_types).issubset({"authorization_code", "refresh_token"}):
		invalidation_reasons.append("only authorization_code and refresh_token grant types are supported")

	if client.response_types and not all(rt == "code" for rt in client.response_types):
		invalidation_reasons.append("only 'code' response_type is supported")

	if not frappe.conf.developer_mode and any(c.scheme != "https" for c in client.redirect_uris):
		invalidation_reasons.append("redirect_uris must be https")

	if invalidation_reasons:
		return ",\n".join(invalidation_reasons)

	return None


def create_new_oauth_client(client: OAuth2DynamicClientMetadata):
	doc = cast(OAuthClient, frappe.get_doc({"doctype": "OAuth Client"}))
	redirect_uris = [str(uri) for uri in client.redirect_uris]

	doc.app_name = client.client_name
	doc.scopes = client.scope
	doc.redirect_uris = "\n".join(redirect_uris)
	doc.default_redirect_uri = redirect_uris[0]
	doc.response_type = "Code"
	doc.grant_type = "Authorization Code"
	doc.skip_authorization = False

	if client.client_uri:
		doc.client_uri = client.client_uri.encoded_string()
	if client.logo_uri:
		doc.logo_uri = client.logo_uri.encoded_string()
	if client.tos_uri:
		doc.tos_uri = client.tos_uri.encoded_string()
	if client.policy_uri:
		doc.policy_uri = client.policy_uri.encoded_string()
	if client.contacts:
		doc.contacts = "\n".join(client.contacts)
	if client.software_id:
		doc.software_id = client.software_id
	if client.software_version:
		doc.software_version = client.software_version

	doc.save(ignore_permissions=True)
	return doc


def get_oauth_settings():
	"""Return OAuth settings."""
	settings: dict[str, Any] = frappe._dict({"skip_authorization": None})
	if frappe.get_cached_value("OAuth Settings", "OAuth Settings", "skip_authorization"):
		settings["skip_authorization"] = "Auto"  # based on legacy OAuth Provider Settings value

	elif value := frappe.get_cached_value(
		"OAuth Provider Settings", "OAuth Provider Settings", "skip_authorization"
	):
		settings["skip_authorization"] = value

	return settings
