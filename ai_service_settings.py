"""Separate local test/custom connections and redact the test connection for UI."""

CONNECTION_KEYS = ("aiBaseUrl", "aiModel", "aiApiKey")
EMPTY_CONNECTION = {"aiBaseUrl": "https://api.openai.com/v1", "aiModel": "gpt-4o-mini", "aiApiKey": ""}


def public_settings(settings):
    result = {key: value for key, value in settings.items()
              if key not in ("_aiDefaultTest", "_aiCustom")}
    if settings.get("aiServiceMode", "default") != "custom":
        result.pop("aiApiKey", None)
        result.pop("aiBaseUrl", None)
    return result


def switch_service(settings, mode):
    if mode not in ("default", "custom", "official"):
        raise ValueError("Unknown AI service mode")
    result = dict(settings)
    previous = settings.get("aiServiceMode", "default")
    if mode == previous:
        return result
    previous_key = "_aiCustom" if previous == "custom" else "_aiDefaultTest"
    next_key = "_aiCustom" if mode == "custom" else "_aiDefaultTest"
    if previous != 'official':
        result[previous_key] = {key: settings.get(key, EMPTY_CONNECTION[key]) for key in CONNECTION_KEYS}
    result.update(EMPTY_CONNECTION if mode=='official' else settings.get(next_key) or EMPTY_CONNECTION)
    if mode=='official':result.update(aiBaseUrl='',aiModel='',aiApiKey='')
    result["aiServiceMode"] = mode
    return result
