"""Fail-closed structured route checks for the non-scientific X6-R0.5 smoke."""
from __future__ import annotations
import json
from collections.abc import Mapping

class X6R05RouteError(ValueError): pass

def validate_management_default(record: Mapping[str, object]) -> dict[str, object]:
    if record.get("return_code") != 0 or not isinstance(record.get("stdout"), str):
        raise X6R05RouteError("management_default_command_failed")
    try:
        rows=json.loads(str(record["stdout"]))
    except json.JSONDecodeError as error:
        raise X6R05RouteError("management_default_malformed_json") from error
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise X6R05RouteError("management_default_missing_or_ambiguous")
    row=rows[0]
    if row.get("dst") not in ("default", None) or row.get("dev")!="eth0":
        raise X6R05RouteError("management_default_not_preserved_on_eth0")
    gateway=row.get("gateway")
    if not isinstance(gateway,str) or not gateway.startswith("172."):
        raise X6R05RouteError("management_default_not_docker_management")
    return row

def validate_route_get(record: Mapping[str, object], *, destination: str, via: str, dev: str, src: str) -> dict[str, object]:
    if record.get("return_code") != 0 or not isinstance(record.get("stdout"), str): raise X6R05RouteError("route_get_command_failed")
    try: rows=json.loads(str(record["stdout"]))
    except json.JSONDecodeError as error: raise X6R05RouteError("route_get_malformed_json") from error
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict): raise X6R05RouteError("route_get_missing_or_ambiguous")
    row=rows[0]
    if row.get("dst")!=destination or row.get("gateway")!=via or row.get("dev")!=dev or row.get("prefsrc")!=src: raise X6R05RouteError("route_get_unexpected_or_management_path")
    if row.get("dev")=="eth0" or str(row.get("gateway","")).startswith("172."): raise X6R05RouteError("route_get_management_path")
    return row
