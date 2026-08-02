import json
import unittest

import httpx

from capcut_sdk import CapCutClient, CapCutSigner, CatalogResource, DeviceProfile, SDKConfig
from capcut_sdk.models import Effect
from capcut_sdk.transport import HttpTransport


class SDKTests(unittest.TestCase):
    def test_capcut_signer_emits_required_headers(self):
        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"))
        headers = CapCutSigner().headers(query="aid=359289", body=b"{}", config=config)
        self.assertEqual(set(headers), {"X-Khronos", "X-SS-STUB", "X-Gorgon", "X-Ladon", "X-Argus", "X-SS-DP", "TDID"})
        self.assertEqual(headers["X-SS-DP"], "359289")

    def test_effect_model(self):
        effect = Effect.from_dict({"common_attr": {"id": "1", "title": "synthetic", "extra": '{"is_vip":true}'}})
        self.assertEqual((effect.id, effect.title, effect.is_vip), ("1", "synthetic", True))

    def test_catalog_resource_normalizes_effect(self):
        effect = Effect.from_dict({"common_attr": {"id": "1", "title": "synthetic", "extra": '{"is_vip":false}'}, "resource_id": "2", "effect_id": "3", "resource": {"file_url": "https://cdn.example/effect.zip", "md5": "abc"}})
        resource = CatalogResource.from_effect(effect, panel="effects2", category_id="4", category_key="hot")
        self.assertEqual((resource.id, resource.resource_id, resource.effect_id), ("1", "2", "3"))
        self.assertEqual(resource.category.panel, "effects2")
        self.assertEqual((resource.download_url, resource.file_md5), ("https://cdn.example/effect.zip", "abc"))

    def test_catalog_resource_infers_desktop_render_kind(self):
        cases = [
            ({"common_attr": {"id": "1", "effect_type": 7}}, "effect"),
            ({"common_attr": {"id": "1", "effect_type": 8}, "special_effect": {}}, "body-effect"),
            ({"common_attr": {"id": "1", "effect_type": 12}, "filter": {}}, "filter"),
            ({"common_attr": {"id": "1", "effect_type": 19}}, "transition"),
            ({"common_attr": {"id": "1", "effect_type": 48}, "subtitle_template": {}}, "caption-template"),
            ({"common_attr": {"id": "1", "effect_type": 2}, "sticker": {}}, "sticker"),
        ]
        for raw, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(CatalogResource.from_effect(Effect.from_dict(raw)).kind, expected)

    def test_default_panel_uses_typed_sticker_payload(self):
        effect = Effect.from_dict({"common_attr": {"id": "1", "effect_type": 2}, "sticker": {}})
        self.assertEqual(CatalogResource.from_effect(effect, panel="default").kind, "sticker")

    def test_catalog_resource_normalizes_desktop_item_urls(self):
        effect = Effect.from_dict({"common_attr": {
            "id": "1", "title": "synthetic", "md5": "desktop-md5",
            "download_info": {"url": "", "format": ""},
            "item_urls": ["https://cdn.example/desktop-effect.zip"],
        }})
        resource = CatalogResource.from_effect(effect)
        self.assertEqual(
            (resource.download_url, resource.file_md5),
            ("https://cdn.example/desktop-effect.zip", "desktop-md5"),
        )

    def test_catalog_resource_normalizes_stock_video_download_and_duration(self):
        effect = Effect.from_dict({
            "common_attr": {
                "id": "5", "title": "stock", "effect_type": 5,
                "download_info": {"url": "https://cdn.example/video.mp4", "format": "mp4"},
            },
            "video": {"duration": 7},
        })
        resource = CatalogResource.from_effect(effect)
        self.assertEqual((resource.kind, resource.download_url, resource.duration), (
            "stock-video", "https://cdn.example/video.mp4", 7,
        ))

    def test_catalog_resource_preserves_render_semantics(self):
        animation = CatalogResource.from_effect(Effect.from_dict({
            "common_attr": {"id": "13", "effect_type": 13, "extra": '{"effect_duration":2000}'},
            "animation": {"animation_type": "video_group"},
        }))
        mask = CatalogResource.from_effect(Effect.from_dict({
            "common_attr": {"id": "97", "effect_type": 97, "extra": '{"complex_video_mask":"line"}'},
        }))
        self.assertEqual(animation.metadata["animation_type"], "group")
        self.assertEqual(animation.metadata["default_duration_ms"], 2000)
        self.assertEqual(mask.metadata["resource_type"], "line")

    def test_catalog_resource_infers_panel_kind(self):
        effect = Effect.from_dict({"common_attr": {"id": "1", "title": "synthetic"}})
        self.assertEqual(CatalogResource.from_effect(effect, panel="transitions").kind, "transition")
        self.assertEqual(CatalogResource.from_effect(effect, panel="filter").kind, "filter")
        self.assertEqual(CatalogResource.from_effect(effect, panel="subtitle-templates").kind, "caption-template")

    def test_effect_list_uses_next_offset(self):
        def handler(request: httpx.Request):
            self.assertEqual(request.url.path, "/artist/v1/effect/get_resources_by_category_id")
            self.assertEqual(json.loads(request.content)["offset"], 7)
            return httpx.Response(200, json={"ret": "0", "errmsg": "success", "data": {"has_more": True, "next_offset": 57, "effect_item_list": [{"common_attr": {"id": "1", "title": "synthetic"}}]}})

        device = DeviceProfile("dummy-device", "dummy-iid")
        config = SDKConfig(device=device, service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        page = CapCutClient(config, transport=transport).effects.list(offset=7)
        self.assertEqual(page.next_offset, 57)
        self.assertTrue(page.has_more)
        self.assertEqual(page.items[0].title, "synthetic")

    def test_effect_dependencies_resolve_by_exact_ids(self):
        def handler(request: httpx.Request):
            body = json.loads(request.content)
            self.assertEqual(request.url.path, "/artist/v1/effect/mget_artist_item")
            self.assertEqual(body["id_list"], ["11", "22"])
            return httpx.Response(200, json={"ret": "0", "data": {"effect_item_list": [
                {"common_attr": {"id": "11", "title": "dependency one"}},
                {"common_attr": {"id": "22", "title": "dependency two"}},
            ]}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        items = CapCutClient(config, transport=transport).effects.get_by_ids(["11", "22"])
        self.assertEqual([item.id for item in items], ["11", "22"])

    def test_panel_info_and_search(self):
        def handler(request: httpx.Request):
            if request.url.path.endswith("get_panel_info"):
                return httpx.Response(200, json={"ret": "0", "data": {"categories": [{"category_id": 1, "category_key": "hot", "category_name": "synthetic"}]}})
            if request.url.path.endswith("get_search_words"):
                return httpx.Response(200, json={"ret": "0", "data": {"default_word": "blur", "recommend_words": ["blur"], "hot_words": [{"word": "blur"}]}})
            return httpx.Response(200, json={"ret": "0", "data": {"has_more": False, "next_offset": 1, "effect_item_list": [{"common_attr": {"id": "2", "title": "synthetic synthetic"}}]}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        client = CapCutClient(config, transport=transport)
        self.assertEqual(client.panels.info().categories[0].category_key, "hot")
        self.assertEqual(client.effects.search("blur").items[0].title, "synthetic synthetic")
        self.assertEqual(client.effects.search_words().default_word, "blur")

    def test_music_collections_and_songs(self):
        def handler(request: httpx.Request):
            if request.url.path.endswith("get_collections"):
                return httpx.Response(200, json={"ret": "0", "data": {"collections": [{"id": 1, "name": "synthetic BGM", "collection_type": 0}]}})
            return httpx.Response(200, json={"ret": "0", "data": {"songs": [{"id": 2, "title": "synthetic synthetic", "author": "synthetic", "duration": 10}], "has_more": False, "next_offset": 1}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        client = CapCutClient(config, transport=transport)
        self.assertEqual(client.music.collections()[0].name, "synthetic BGM")
        self.assertEqual(client.music.songs(1).items[0].title, "synthetic synthetic")

    def test_music_exact_id_falls_back_to_collection_scan(self):
        requested_collections = []

        def handler(request: httpx.Request):
            if request.url.path.endswith("get_collections"):
                return httpx.Response(200, json={"ret": "0", "data": {"collections": [
                    {"id": 10, "name": "first", "collection_type": 0},
                    {"id": 20, "name": "second", "collection_type": 0},
                ]}})
            body = json.loads(request.content)
            requested_collections.append(str(body["id"]))
            songs = [{"id": 99, "title": "exact", "author": "synthetic"}] if str(body["id"]) == "20" else []
            return httpx.Response(200, json={"ret": "0", "data": {
                "songs": songs, "has_more": False, "next_offset": body["offset"] + len(songs),
            }})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        match = CapCutClient(config, transport=transport).music.find_song_by_id("99")
        self.assertIsNotNone(match)
        song, collection = match
        self.assertEqual((song.id, collection.id, requested_collections), ("99", "20", ["10", "20"]))

    def test_template_collections_and_cursor_page(self):
        def handler(request: httpx.Request):
            if request.url.path.endswith("get_collections"):
                return httpx.Response(200, json={"ret": "0", "data": {"collections": [{"id": 10001, "display_name": "synthetic"}]}})
            return httpx.Response(200, json={"ret": "0", "data": {"item_list": [{"id": 5, "title": "synthetic"}], "new_cursor": 12, "has_more": True}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        client = CapCutClient(config, transport=transport)
        self.assertEqual(client.templates.collections()[0].display_name, "synthetic")
        page = client.templates.list(10001)
        self.assertEqual((page.items[0].title, page.next_cursor, page.has_more), ("synthetic", "12", True))

    def test_aigc_random_prompts(self):
        def handler(request: httpx.Request):
            return httpx.Response(200, json={"ret": "0", "data": {"model2prompt_list": {"artistic_text": ["synthetic"]}}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        prompts = CapCutClient(config, transport=transport).aigc.random_prompts(["artistic_text"], scene="test")
        self.assertEqual(prompts, {"artistic_text": ["synthetic"]})

    def test_raw_client_preserves_untyped_operation(self):
        def handler(request: httpx.Request):
            self.assertEqual(request.url.path, "/artist/v1/unknown")
            return httpx.Response(200, json={"ret": "0", "data": {"value": 1}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        response = CapCutClient(config, transport=transport).raw.post("/artist/v1/unknown", {"value": 1})
        self.assertEqual(response["data"]["value"], 1)

    def test_raw_client_supports_get(self):
        def handler(request: httpx.Request):
            self.assertEqual(request.method, "GET")
            return httpx.Response(200, json={"ret": "0", "data": {"value": 2}})

        config = SDKConfig(device=DeviceProfile("dummy-device", "dummy-iid"), service="example.invalid")
        transport = HttpTransport(config, client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.assertEqual(CapCutClient(config, transport=transport).raw.get("/service/settings/v3/")["data"]["value"], 2)
