import json
import unittest

import httpx

from capcut_sdk import CapCutClient, CapCutSigner, DeviceProfile, SDKConfig
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
