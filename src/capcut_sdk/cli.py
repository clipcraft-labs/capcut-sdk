"""Small CLI facade; richer commands are added as resources are verified."""

import argparse
import json
import sys

from .client import CapCutClient
from .errors import ConfigurationError
from .operations import OPERATIONS
from .profiles import ProfileStore, config_from_environment
from .signing import CapCutSigner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capcut", description="Unofficial capture-backed CapCut API SDK")
    sub = parser.add_subparsers(dest="command")
    auth = sub.add_parser("auth", help="Manage local profiles")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    profile = auth_sub.add_parser("profile", help="Manage a local TOML profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("list")
    show = profile_sub.add_parser("show")
    show.add_argument("name", nargs="?", default="default")
    set_profile = profile_sub.add_parser("set")
    set_profile.add_argument("name", nargs="?", default="default")
    set_profile.add_argument("--device-id")
    set_profile.add_argument("--iid")
    set_profile.add_argument("--region")
    set_profile.add_argument("--language")
    set_profile.add_argument("--mode", choices=["offline", "live", "replay"])
    api = sub.add_parser("api", help="Inspect the SDK API surface")
    api.add_argument("action", choices=["status"], nargs="?", default="status")
    call = sub.add_parser("call", help="Call an OpenAPI operation directly")
    call.add_argument("--method", choices=["GET", "POST"], default="POST")
    call.add_argument("path")
    call.add_argument("body", type=argparse.FileType("r"), nargs="?")
    call.add_argument("--service", default=None)
    effects = sub.add_parser("effects", help="Query editing-effect resources and categories")
    effects_sub = effects.add_subparsers(dest="effects_command", required=True)
    search = effects_sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--offset", type=int, default=0)
    search.add_argument("--count", type=int, default=50, help="Number of results (default: 50)")
    words = effects_sub.add_parser("words")
    panels = sub.add_parser("panels", help="Query CapCut material panels (effects2=editing effects)")
    panels_sub = panels.add_subparsers(dest="panels_command", required=True)
    info = panels_sub.add_parser("info", help="List categories for a panel")
    info.add_argument(
        "--panel",
        default="effects2",
        help=("Internal panel identifier. effects2=editing effects, transitions=transitions, "
              "filter=filters, face-prop=body/face effects, subtitle-templates=caption templates, "
              "default=general materials."),
    )
    music = sub.add_parser("music", help="Query music collections and songs")
    music_sub = music.add_subparsers(dest="music_command", required=True)
    collections = music_sub.add_parser("collections", help="List music or sound-effect collections")
    collections.add_argument("--effects", action="store_true", help="List sound-effect music collections instead of songs/music")
    collections.add_argument("--only-commercial", action="store_true", help="Limit sound-effect collections to commercial-use items")
    songs = music_sub.add_parser("songs")
    songs.add_argument("collection_id")
    songs.add_argument("--offset", type=int, default=0)
    templates = sub.add_parser("templates", help="Query template collections and items")
    templates_sub = templates.add_subparsers(dest="templates_command", required=True)
    templates_sub.add_parser("collections")
    template_list = templates_sub.add_parser("list")
    template_list.add_argument("collection_id")
    template_list.add_argument("--cursor", default="0")
    aigc = sub.add_parser("aigc", help="Query AIGC helpers")
    aigc_sub = aigc.add_subparsers(dest="aigc_command", required=True)
    prompts = aigc_sub.add_parser("prompts")
    prompts.add_argument("models", nargs="+", help="Model names")
    prompts.add_argument("--scene", default="default", help="Client UI scene/context, usually default")
    config = sub.add_parser("config", help="Query remote configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    general = config_sub.add_parser("effect-general")
    general.add_argument("--scene", default="default", help="Client UI scene/context, usually default")
    config_sub.add_parser("remote-settings")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "api":
        print(json.dumps({"sdk": "capcut-api-sdk", "status": "alpha", "operations": [operation.__dict__ if hasattr(operation, "__dict__") else {"operation_id": operation.operation_id, "group": operation.group, "status": operation.status} for operation in OPERATIONS]}, ensure_ascii=False))
        return 0
    if args.command == "auth" and args.auth_command == "profile":
        store = ProfileStore()
        if args.profile_command == "list":
            print(json.dumps(store.names()))
        elif args.profile_command == "show":
            values = store.load(args.name)
            device = values.get("device", {})
            for key in ("device_id", "iid"):
                if key in device and len(str(device[key])) > 8:
                    device[key] = str(device[key])[:4] + "..." + str(device[key])[-4:]
            print(json.dumps(values, indent=2))
        else:
            values = store.load(args.name) if args.name in store.names() else store.default_profile()
            values.setdefault("device", {})
            values.setdefault("locale", {})
            values.setdefault("profile", {})
            for section, key, value in (
                ("device", "device_id", args.device_id),
                ("device", "iid", args.iid),
                ("locale", "region", args.region),
                ("locale", "language", args.language),
                ("profile", "mode", args.mode),
            ):
                if value is not None:
                    values[section][key] = value
            store.save(args.name, values)
            print(f"Saved profile: {args.name}")
        return 0
    if args.command in {"effects", "panels", "music", "templates", "aigc", "call", "config"}:
        try:
            config = config_from_environment()
        except (FileNotFoundError, KeyError) as exc:
            raise ConfigurationError("Unable to load the local CapCut profile") from exc
        if config.mode != "live":
            raise ConfigurationError("Live API commands require CAPCUT_MODE=live or profile mode=live")
        client = CapCutClient(config, signer=CapCutSigner())
        if args.command == "call":
            if args.method == "GET":
                result = client.raw.get(args.path, service=args.service)
            else:
                if args.body is None:
                    raise ConfigurationError("POST calls require a JSON body file")
                result = client.raw.post(args.path, json.load(args.body), service=args.service)
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == "config" and args.config_command == "effect-general":
            print(json.dumps(client.configuration.effect_general_config(scene=args.scene), ensure_ascii=False))
        elif args.command == "config":
            print(json.dumps(client.configuration.remote_settings(), ensure_ascii=False))
        elif args.command == "effects" and args.effects_command == "search":
            page = client.effects.search(args.query, offset=args.offset, count=args.count)
            print(json.dumps({"items": [item.raw for item in page.items], "next_offset": page.next_offset, "has_more": page.has_more}, ensure_ascii=False))
        elif args.command == "effects":
            words = client.effects.search_words()
            print(json.dumps({"default_word": words.default_word, "recommend_words": words.recommend_words, "hot_words": words.hot_words}, ensure_ascii=False))
        elif args.command == "panels":
            panel = client.panels.info(panel=args.panel)
            print(json.dumps({"categories": [category.raw for category in panel.categories]}, ensure_ascii=False))
        elif args.music_command == "collections":
            collections = client.music.collections(effects=args.effects, only_commercial=args.only_commercial)
            print(json.dumps([collection.raw for collection in collections], ensure_ascii=False))
        elif args.command == "music":
            page = client.music.songs(args.collection_id, offset=args.offset)
            print(json.dumps({"items": [song.raw for song in page.items], "next_offset": page.next_offset, "has_more": page.has_more}, ensure_ascii=False))
        elif args.templates_command == "collections":
            collections = client.templates.collections()
            print(json.dumps([collection.raw for collection in collections], ensure_ascii=False))
        elif args.command == "templates":
            page = client.templates.list(args.collection_id, cursor=args.cursor)
            print(json.dumps({"items": [item.raw for item in page.items], "next_cursor": page.next_cursor, "has_more": page.has_more}, ensure_ascii=False))
        else:
            prompts = client.aigc.random_prompts(args.models, scene=args.scene)
            print(json.dumps(prompts, ensure_ascii=False))
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
