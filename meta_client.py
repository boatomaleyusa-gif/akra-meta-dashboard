import json
import hashlib
import os
import time
from pathlib import Path
from datetime import datetime

import pandas as pd


API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
CREATIVE_FETCH_LIMIT = 100
CREATIVE_BATCH_SIZE = 50
IMAGE_HASH_FETCH_LIMIT = 50
MAX_SAFE_RETRIES = 1
RATE_LIMIT_MESSAGE = "Meta API rate limit reached. Please wait and try again."
READ_ONLY_META_OPERATIONS = {
    "fetch_insights",
    "fetch_creatives",
    "fetch_images",
}
DANGEROUS_META_WRITE_ACTIONS = {
    "pause_campaign",
    "update_budget",
    "create_campaign",
    "create_adset",
    "create_ad",
}
INSIGHT_FIELDS = [
    "date_start",
    "date_stop",
    "ad_id",
    "campaign_name",
    "adset_name",
    "ad_name",
    "spend",
    "impressions",
    "reach",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "frequency",
    "actions",
    "cost_per_action_type",
]
LEAD_ACTION_TYPES = {
    "lead",
    "onsite_conversion.lead",
}
GROUPED_LEAD_ACTION_TYPE = "onsite_conversion.lead_grouped"
INBOX_ACTION_TYPES = {
    "onsite_conversion.messaging_conversation_started_7d",
}


def load_meta_ads_data(project_root, date_from=None, date_to=None, date_preset=None):
    """Fetch read-only ad-level insights when Meta credentials are available."""
    try:
        import requests
    except ImportError as error:
        raise RuntimeError(
            "Missing dependency. Run: pip install -r requirements.txt"
        ) from error

    credential_config = _meta_credential_config(project_root)
    if not credential_config:
        return None

    access_token = credential_config.get("META_ACCESS_TOKEN")
    ad_account_ids = credential_config.get("META_AD_ACCOUNT_IDS") or credential_config.get(
        "META_AD_ACCOUNT_ID"
    )
    if not access_token:
        raise RuntimeError("Meta credentials are incomplete: META_ACCESS_TOKEN is missing.")
    if not ad_account_ids:
        raise RuntimeError(
            "Meta credentials are incomplete: META_AD_ACCOUNT_ID or META_AD_ACCOUNT_IDS is missing."
        )

    date_config = _date_config(date_from, date_to, date_preset, credential_config)
    normalized_ad_account_ids = _split_ad_account_ids(ad_account_ids)
    print(f"META_AD_ACCOUNT_COUNT={len(normalized_ad_account_ids)}", flush=True)
    rows = []
    creative_data = {}
    optional_rate_limited = False
    for ad_account_id in normalized_ad_account_ids:
        print("FETCHING META AD ACCOUNT", flush=True)
        account_rows = _fetch_ad_insights(requests, access_token, ad_account_id, date_config)
        rows.extend(account_rows)
        account_creative_data, account_rate_limited = _fetch_ad_creatives(
            requests, access_token, ad_account_id, account_rows
        )
        creative_data.update(account_creative_data)
        optional_rate_limited = optional_rate_limited or account_rate_limited
    _write_action_type_debug(rows, Path(project_root) / "reports" / "meta_action_types_debug.csv")
    if not rows:
        df = pd.DataFrame(columns=_normalized_columns())
    else:
        df = pd.DataFrame([_normalize_insight(row, creative_data) for row in rows])
    df.attrs["date_range_label"] = date_config["label"]
    if optional_rate_limited:
        df.attrs["data_source_warning"] = RATE_LIMIT_MESSAGE
    return df


def meta_credentials_cache_key(project_root):
    credential_config = _meta_credential_config(project_root)
    account_ids = ""
    source = ""
    if credential_config:
        account_ids = credential_config.get("META_AD_ACCOUNT_IDS") or credential_config.get(
            "META_AD_ACCOUNT_ID", ""
        )
        source = credential_config.get("_META_CREDENTIAL_SOURCE", "")
    env_path = Path(project_root) / ".env"
    env_mtime = env_path.stat().st_mtime if env_path.exists() else 0
    return hashlib.sha256(f"{source}|{account_ids}|{env_mtime}".encode("utf-8")).hexdigest()


def _meta_credential_config(project_root):
    return (
        _streamlit_secrets_config()
        or _environment_config()
        or _dotenv_config(Path(project_root) / ".env")
    )


def _streamlit_secrets_config():
    try:
        import streamlit as st
    except ImportError:
        return {}

    try:
        secrets = st.secrets
        config = _config_from_mapping(secrets)
        meta_section = secrets.get("meta", {}) if hasattr(secrets, "get") else {}
        section_config = _config_from_mapping(meta_section)
    except Exception:
        return {}

    merged_config = {**section_config, **config}
    return _with_source(merged_config, "streamlit_secrets")


def _environment_config():
    config = {
        "META_ACCESS_TOKEN": os.environ.get("META_ACCESS_TOKEN", ""),
        "META_AD_ACCOUNT_IDS": os.environ.get("META_AD_ACCOUNT_IDS", ""),
        "META_AD_ACCOUNT_ID": os.environ.get("META_AD_ACCOUNT_ID", ""),
        "META_DATE_FROM": os.environ.get("META_DATE_FROM", ""),
        "META_DATE_TO": os.environ.get("META_DATE_TO", ""),
        "META_DATE_PRESET": os.environ.get("META_DATE_PRESET", ""),
    }
    return _with_source(config, "environment")


def _dotenv_config(env_path):
    if not env_path.exists():
        return {}

    try:
        from dotenv import dotenv_values
    except ImportError as error:
        raise RuntimeError(
            "Missing dependency. Run: pip install -r requirements.txt"
        ) from error

    return _with_source(dotenv_values(env_path), "dotenv")


def _config_from_mapping(mapping):
    keys = {
        "META_ACCESS_TOKEN",
        "META_AD_ACCOUNT_IDS",
        "META_AD_ACCOUNT_ID",
        "META_DATE_FROM",
        "META_DATE_TO",
        "META_DATE_PRESET",
    }
    return {key: str(mapping.get(key, "") or "") for key in keys if hasattr(mapping, "get")}


def _with_source(config, source):
    if not config:
        return {}
    if not (
        config.get("META_ACCESS_TOKEN")
        or config.get("META_AD_ACCOUNT_IDS")
        or config.get("META_AD_ACCOUNT_ID")
    ):
        return {}
    return {**config, "_META_CREDENTIAL_SOURCE": source}


def require_write_approval(action_name, approved=False):
    """Placeholder gate for future MCP write actions.

    The current dashboard only uses read-only Meta API calls. Future MCP tools for
    campaign pauses, budget updates, or entity creation must call this gate after
    receiving explicit user confirmation and before any Meta write request.
    """
    if action_name not in DANGEROUS_META_WRITE_ACTIONS:
        raise ValueError(f"Unknown Meta write action: {action_name}")
    if not approved:
        raise PermissionError(
            f"Meta write action '{action_name}' requires explicit user approval."
        )
    return True


def _date_config(date_from=None, date_to=None, date_preset=None, env_config=None):
    env_config = env_config or {}
    date_from = date_from or env_config.get("META_DATE_FROM")
    date_to = date_to or env_config.get("META_DATE_TO")
    date_preset = date_preset or env_config.get("META_DATE_PRESET") or "last_7d"

    if date_from and date_to:
        print(f"Using custom date range: {date_from} to {date_to}", flush=True)
        return {
            "params": {"time_range": f'{{"since":"{date_from}","until":"{date_to}"}}'},
            "label": f"Report Date Range: {_format_date(date_from)} - {_format_date(date_to)}",
        }

    print(f"Using preset: {date_preset}", flush=True)
    return {
        "params": {"date_preset": date_preset},
        "label": f"Report Date Range: {date_preset}",
    }


def _split_ad_account_ids(ad_account_ids):
    return [
        _normalize_ad_account_id(ad_account_id)
        for ad_account_id in ad_account_ids.split(",")
        if ad_account_id.strip()
    ]


def _normalize_ad_account_id(ad_account_id):
    ad_account_id = ad_account_id.strip()
    if ad_account_id.startswith("act_"):
        return ad_account_id
    return f"act_{ad_account_id}"


def _fetch_ad_insights(requests, access_token, ad_account_id, date_config):
    print("CALLING META API", flush=True)
    url = f"{BASE_URL}/{ad_account_id}/insights"
    params = {
        "access_token": access_token,
        "level": "ad",
        "time_increment": 1,
        "fields": ",".join(INSIGHT_FIELDS),
        "limit": 1000,
    }
    params.update(date_config["params"])

    rows = []
    while url:
        try:
            response = _get_with_backoff(requests, url, params=params, timeout=120)
        except requests.RequestException as error:
            print("META API ERROR", flush=True)
            print(f"Connection failed: {error.__class__.__name__}", flush=True)
            raise RuntimeError("Meta API connection failed before a response was received") from error

        print(f"Response status code: {response.status_code}", flush=True)
        if _is_app_rate_limit_response(response):
            print("META API RATE LIMITED", flush=True)
            raise RuntimeError(RATE_LIMIT_MESSAGE)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            print("META API ERROR", flush=True)
            raise RuntimeError(
                f"Meta API request failed with status {response.status_code}: "
                f"{_safe_meta_error_message(response)}"
            ) from error
        payload = response.json()
        rows.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
        params = None
    return rows


def _safe_meta_error_message(response):
    try:
        payload = response.json()
    except ValueError:
        return "Meta returned a non-JSON error response."
    error_payload = payload.get("error", {}) if isinstance(payload, dict) else {}
    message = error_payload.get("message") or "Meta returned an error response."
    code = error_payload.get("code")
    subcode = error_payload.get("error_subcode")
    details = [f"code {code}" if code is not None else "", f"subcode {subcode}" if subcode else ""]
    suffix = ", ".join(detail for detail in details if detail)
    if suffix:
        return f"{message} ({suffix})"
    return message


def _get_with_backoff(requests, url, params=None, timeout=30):
    retry_count = 0
    while True:
        response = requests.get(url, params=params, timeout=timeout)
        if not _should_retry_response(response) or retry_count >= MAX_SAFE_RETRIES:
            return response
        retry_count += 1
        retry_after = _retry_after_seconds(response)
        print(
            f"Meta API transient response {response.status_code}; retrying once after {retry_after}s",
            flush=True,
        )
        time.sleep(retry_after)


def _should_retry_response(response):
    if _is_app_rate_limit_response(response):
        return False
    return response.status_code in {429, 500, 502, 503, 504}


def _retry_after_seconds(response):
    retry_after = response.headers.get("Retry-After", "")
    try:
        return min(max(int(retry_after), 1), 5)
    except (TypeError, ValueError):
        return 2


def _is_app_rate_limit_response(response):
    if response.status_code not in {403, 429}:
        return False
    error_payload = _meta_error_payload(response)
    return (
        error_payload.get("code") == 4
        and error_payload.get("error_subcode") == 1504022
    )


def _meta_error_payload(response):
    try:
        payload = response.json()
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    error_payload = payload.get("error", {})
    return error_payload if isinstance(error_payload, dict) else {}


def _fetch_ad_creatives(requests, access_token, ad_account_id, rows):
    ad_ids = _top_ad_ids_by_spend(rows, CREATIVE_FETCH_LIMIT)
    creative_data = {}
    rate_limited = False
    if not ad_ids:
        return creative_data, rate_limited

    print(
        f"FETCHING CREATIVE PREVIEWS: {len(ad_ids)} ads by top spend "
        f"(limit {CREATIVE_FETCH_LIMIT})",
        flush=True,
    )
    fields = (
        "id,name,creative{"
        "id,name,thumbnail_url,image_url,object_story_spec,effective_object_story_id"
        "}"
    )
    image_hashes = set()
    for ad_id_batch in _chunks(ad_ids, CREATIVE_BATCH_SIZE):
        url = f"{BASE_URL}/"
        params = {
            "access_token": access_token,
            "ids": ",".join(ad_id_batch),
            "fields": fields,
        }
        try:
            response = _get_with_backoff(requests, url, params=params, timeout=30)
        except requests.RequestException as error:
            print(
                f"Creative preview batch fetch failed: {error.__class__.__name__}",
                flush=True,
            )
            for ad_id in ad_id_batch:
                creative_data[ad_id] = {}
            continue

        if _is_app_rate_limit_response(response):
            print("Creative preview fetch stopped: Meta API rate limit reached", flush=True)
            for ad_id in ad_id_batch:
                creative_data[ad_id] = {}
            rate_limited = True
            break

        if response.status_code != 200:
            print(
                f"Creative preview batch fetch failed: status {response.status_code}",
                flush=True,
            )
            for ad_id in ad_id_batch:
                creative_data[ad_id] = {}
            continue

        payload = response.json()
        for ad_id in ad_id_batch:
            ad_payload = payload.get(ad_id, {})
            creative = ad_payload.get("creative") or {}
            object_story_spec = creative.get("object_story_spec") or {}
            image_hash = _object_story_image_hash(object_story_spec)
            if image_hash and not (creative.get("thumbnail_url") or creative.get("image_url")):
                image_hashes.add(image_hash)
            effective_story_id = creative.get("effective_object_story_id", "")
            creative_data[ad_id] = {
                "creative_id": creative.get("id", ""),
                "creative_name": creative.get("name", ""),
                "thumbnail_url": creative.get("thumbnail_url", ""),
                "image_url": creative.get("image_url", ""),
                "object_story_image_hash": image_hash,
                "creative_preview_url": _creative_preview_url(effective_story_id),
            }

    image_urls, image_rate_limited = _fetch_ad_images(
        requests, access_token, ad_account_id, image_hashes
    )
    rate_limited = rate_limited or image_rate_limited
    for creative in creative_data.values():
        if creative.get("thumbnail_url") or creative.get("image_url"):
            continue
        image_hash = creative.get("object_story_image_hash")
        if image_hash:
            creative["image_url"] = image_urls.get(image_hash, "")
    return creative_data, rate_limited


def _top_ad_ids_by_spend(rows, limit):
    spend_by_ad_id = {}
    for row in rows:
        ad_id = row.get("ad_id")
        if not ad_id:
            continue
        spend_by_ad_id[ad_id] = spend_by_ad_id.get(ad_id, 0) + _to_float(row.get("spend"))
    return [
        ad_id
        for ad_id, _ in sorted(
            spend_by_ad_id.items(), key=lambda item: item[1], reverse=True
        )[:limit]
    ]


def _object_story_image_hash(object_story_spec):
    link_data = object_story_spec.get("link_data") or {}
    return link_data.get("image_hash", "")


def _fetch_ad_images(requests, access_token, ad_account_id, image_hashes):
    image_urls = {}
    rate_limited = False
    if not image_hashes:
        return image_urls, rate_limited

    selected_hashes = sorted(image_hashes)[:IMAGE_HASH_FETCH_LIMIT]
    print(f"FETCHING CREATIVE IMAGE HASHES: {len(selected_hashes)} images", flush=True)
    for image_hash_batch in _chunks(selected_hashes, CREATIVE_BATCH_SIZE):
        url = f"{BASE_URL}/{ad_account_id}/adimages"
        params = {
            "access_token": access_token,
            "hashes": json.dumps(image_hash_batch),
            "fields": "hash,url,url_128",
        }
        try:
            response = _get_with_backoff(requests, url, params=params, timeout=30)
        except requests.RequestException as error:
            print(
                f"Creative image hash fetch failed: {error.__class__.__name__}",
                flush=True,
            )
            continue

        if _is_app_rate_limit_response(response):
            print("Creative image hash fetch stopped: Meta API rate limit reached", flush=True)
            rate_limited = True
            break

        if response.status_code != 200:
            print(
                f"Creative image hash fetch failed: status {response.status_code}",
                flush=True,
            )
            continue

        for image in response.json().get("data", []):
            image_hash = image.get("hash")
            if image_hash:
                image_urls[image_hash] = image.get("url") or image.get("url_128", "")
    return image_urls, rate_limited


def _chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _creative_preview_url(effective_story_id):
    if not effective_story_id:
        return ""
    return f"https://www.facebook.com/{effective_story_id}"


def _normalize_insight(row, creative_data=None):
    actions = row.get("actions", [])
    creative_data = creative_data or {}
    creative = creative_data.get(row.get("ad_id"), {})
    inbox_messages = _sum_action_values(actions, INBOX_ACTION_TYPES)
    leads = _lead_count(actions)
    results = inbox_messages + leads
    result_type = _result_type(leads, inbox_messages)
    spend = _to_float(row.get("spend"))

    cost_per_result = _safe_divide(spend, results)
    cost_per_inbox = _safe_divide(spend, inbox_messages)
    cost_per_lead = _safe_divide(spend, leads)

    return {
        "date": row.get("date_start"),
        "ad_id": row.get("ad_id", ""),
        "campaign": row.get("campaign_name", ""),
        "adset": row.get("adset_name", ""),
        "ad": row.get("ad_name", ""),
        "creative_id": creative.get("creative_id", ""),
        "creative_name": creative.get("creative_name", ""),
        "thumbnail_url": creative.get("thumbnail_url", ""),
        "image_url": creative.get("image_url", ""),
        "object_story_image_hash": creative.get("object_story_image_hash", ""),
        "creative_preview_url": creative.get("creative_preview_url", ""),
        "spend": spend,
        "impressions": _to_float(row.get("impressions")),
        "reach": _to_float(row.get("reach")),
        "clicks": _to_float(row.get("clicks")),
        "results": results,
        "result_type": result_type,
        "inbox_messages": inbox_messages,
        "leads": leads,
        "cost_per_result": cost_per_result,
        "cost_per_inbox": cost_per_inbox,
        "cost_per_lead": cost_per_lead,
    }


def _sum_action_values(actions, action_types):
    return sum(
        _to_float(action.get("value"))
        for action in actions
        if action.get("action_type") in action_types
    )


def _lead_count(actions):
    grouped_leads = _sum_action_values(actions, {GROUPED_LEAD_ACTION_TYPE})
    if grouped_leads > 0:
        return grouped_leads
    return _sum_action_values(actions, LEAD_ACTION_TYPES)


def _result_type(leads, inbox_messages):
    if leads > 0 and inbox_messages > 0:
        return "mixed"
    if leads > 0:
        return "leads"
    if inbox_messages > 0:
        return "inbox_messages"
    return "none"


def _write_action_type_debug(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    action_totals = {}
    cost_values = {}

    for row in rows:
        for action in row.get("actions", []):
            action_type = action.get("action_type", "")
            if not action_type:
                continue
            action_totals[action_type] = action_totals.get(action_type, 0) + _to_float(
                action.get("value")
            )

        for action_cost in row.get("cost_per_action_type", []):
            action_type = action_cost.get("action_type", "")
            if not action_type:
                continue
            cost_values.setdefault(action_type, []).append(_to_float(action_cost.get("value")))

    debug_rows = []
    for action_type, total_value in sorted(action_totals.items()):
        print(f"ACTION_TYPE {action_type}: total_value={total_value}", flush=True)
        debug_rows.append(
            {
                "source": "actions",
                "action_type": action_type,
                "total_value": total_value,
                "count": "",
                "average_cost": "",
                "min_cost": "",
                "max_cost": "",
            }
        )

    for action_type, values in sorted(cost_values.items()):
        total_cost = sum(values)
        average_cost = _safe_divide(total_cost, len(values))
        print(
            f"COST_PER_ACTION_TYPE {action_type}: count={len(values)}, "
            f"average_cost={average_cost}, min_cost={min(values)}, max_cost={max(values)}",
            flush=True,
        )
        debug_rows.append(
            {
                "source": "cost_per_action_type",
                "action_type": action_type,
                "total_value": "",
                "count": len(values),
                "average_cost": average_cost,
                "min_cost": min(values),
                "max_cost": max(values),
            }
        )

    try:
        pd.DataFrame(debug_rows).to_csv(output_path, index=False)
        print(f"Action type debug saved: {output_path}", flush=True)
    except PermissionError:
        print(f"Action type debug not saved; permission denied: {output_path}", flush=True)


def _to_float(value):
    if value in (None, ""):
        return 0
    return float(value)


def _safe_divide(numerator, denominator):
    if denominator == 0:
        return 0
    return numerator / denominator


def _format_date(value):
    parsed_date = datetime.strptime(value, "%Y-%m-%d")
    return f"{parsed_date.strftime('%B')} {parsed_date.day}, {parsed_date.year}"


def _normalized_columns():
    return [
        "date",
        "ad_id",
        "campaign",
        "adset",
        "ad",
        "creative_id",
        "creative_name",
        "thumbnail_url",
        "image_url",
        "object_story_image_hash",
        "creative_preview_url",
        "spend",
        "impressions",
        "reach",
        "clicks",
        "results",
        "result_type",
        "inbox_messages",
        "leads",
        "cost_per_result",
        "cost_per_inbox",
        "cost_per_lead",
    ]
