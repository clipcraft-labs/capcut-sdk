import unittest

from capcut_method2.signatures import (
    business_sign,
    x_argus,
    x_gorgon,
    x_gorgon_material,
    x_gorgon_mix,
    x_khronos,
    x_ladon,
    x_ss_stub,
)


class SignatureTests(unittest.TestCase):
    def test_business_sign_matches_native_probe_vector(self):
        self.assertEqual(
            business_sign("url", "3", "9.1.0", "1700000000", "device"),
            "ed3cad8571b6955dbdf65e54fae7203c",
        )

    def test_x_ss_stub_is_uppercase_body_md5(self):
        self.assertEqual(
            x_ss_stub('{"category_id":"18885"}'),
            "292FE15E060F9639945FE2F9C9D31C6D",
        )

    def test_x_ss_stub_accepts_bytes(self):
        self.assertEqual(x_ss_stub(b""), "D41D8CD98F00B204E9800998ECF8427E")

    def test_x_khronos_uses_explicit_timestamp(self):
        self.assertEqual(x_khronos(1785477237), "1785477237")

    def test_x_ladon_matches_recovered_native_intermediates(self):
        self.assertEqual(
            x_ladon(
                1785481313,
                1369207606,
                359289,
                random_bytes=bytes.fromhex("e95d1a2c"),
            ),
            "6V0aLN20SYnQ6MfcVahvNasZWCbKhK+cVx4AgZnmYgm5iiA9",
        )

    def test_x_ladon_rejects_invalid_random_prefix(self):
        with self.assertRaises(ValueError):
            x_ladon(1, 2, 3, random_bytes=b"bad")

    def test_x_argus_matches_native_complete_vector(self):
        self.assertEqual(
            x_argus(
                (
                    r"aid=359289\&device_id=1000000000000000001"
                    r"\&iid=2000000000000000001\&dummy=1"
                ),
                '{"dummy":1}',
                1785482891,
                device_id="1000000000000000001",
                random_bytes=bytes.fromhex("7ff5d405"),
                protobuf_random=259245261,
                request_random=236,
                header_random=bytes.fromhex("1d83a6283e"),
                padding_seed=0x1D4F4C00,
            ),
            (
                "f/U01Y6tvZu5V++FgkhUaVhK+LYGJEtShzY+CKqVx9dunUwLGSpzR77B66/"
                "z4gRp6JOPb/Ngj5LpdwkLJVlAh/LyOQd2GWVahiC2VOTBLUtterKaB9E1Yi"
                "qTRDd09vSfAjBMO00OaPBKeyuwG1/TrSI1F/JTMYOBjYmqT6mOaes4R8Xn8"
                "3PtOlX8pJROfjdmkHQNbvQdzs5vJweLiZUQLENFgmYkdPYTLRhRJpRWhRHj"
                "nl9qNCzHTrbWJ/8mRUrBqpG2sfw3hbNymp2NbFgxfCZjMqRQzhOrkE4+Ujg"
                "F1QCWXA=="
            ),
        )

    def test_x_argus_rejects_invalid_entropy_sizes(self):
        with self.assertRaises(ValueError):
            x_argus("", b"", 1, device_id="dummy", random_bytes=b"bad")
        with self.assertRaises(ValueError):
            x_argus("", b"", 1, device_id="dummy", header_random=b"bad")

    def test_x_argus_matches_second_native_entropy_vector(self):
        self.assertEqual(
            x_argus(
                (
                    r"aid=359289\&device_id=1000000000000000001"
                    r"\&iid=2000000000000000001\&dummy=1"
                ),
                '{"dummy":1}',
                1785482467,
                device_id="1000000000000000001",
                random_bytes=bytes.fromhex("2ccff849"),
                protobuf_random=942447610,
                request_random=235,
                header_random=bytes.fromhex("49ed712f3e"),
                padding_seed=0x2F620C00,
            ),
            (
                "LM+2inwzHXEAsg77bq/D1SzeqdA11FGgsweS5bwS9T+MqWjzg3I83cCTQ46"
                "7/hrVfBFWlVNKcL/1qZpS6fhWuVtzepw2t2pn+qiJQEQg+mK7sfSmX3NBM"
                "r60A3tlsO1H/FOAYw6FtkrOMeIPi61yDxTqRtAeoOFN0i4h3o1H8BUMZ4Mb"
                "5JYcFE/7TgsgxmE/DMVQAKJII72ic/IEXAG1E2lc65uFTv1wyRFQGfcVYl0"
                "hZ1KWpakrBaYC9/1rY9d0wmXU71+hHuuMQCxNEKf1o6YPxrruxKiwsGPiwG"
                "gGl3/SJQ=="
            ),
        )

    def test_x_gorgon_material_matches_native_dummy_trace(self):
        self.assertEqual(
            x_gorgon_material(
                (
                    "aid=359289&device_id=1000000000000000001"
                    "&iid=2000000000000000001&dummy=1"
                ),
                '{"dummy":1}',
                "",
                1785477237,
                stub="3D2E04F4EE32BEDDB757E8E3C149F627",
            ).hex(),
            "569499cb3d2e04f400000000240606056a6c3875",
        )

    def test_x_gorgon_material_rejects_malformed_stub(self):
        with self.assertRaises(ValueError):
            x_gorgon_material("", b"", b"", 0, stub="not-a-stub")

    def test_x_gorgon_material_cookie_slot_is_zero(self):
        without_cookie = x_gorgon_material("a=1", b"", b"", 1)
        with_cookie = x_gorgon_material("a=1", b"", b"dummy_cookie=1", 1)
        self.assertEqual(with_cookie, without_cookie)
        self.assertEqual(with_cookie[8:12], bytes(4))

    def test_x_gorgon_material_without_stub_has_zero_body_slot(self):
        material = x_gorgon_material("a=1", b"body", b"", 1)
        self.assertEqual(material[4:8], bytes(4))

    def test_x_gorgon_mixer_matches_native_intermediate_vector(self):
        self.assertEqual(
            x_gorgon_mix(
                bytes.fromhex("569499cb3d2e04f400000000240606056a6c3bd2"),
                bytes.fromhex("c00a8080"),
            ).hex(),
            "02301b778615f0dc88d0616e78a03150d06553f6",
        )

    def test_x_gorgon_matches_native_complete_vector(self):
        self.assertEqual(
            x_gorgon(
                (
                    "aid=359289&device_id=1000000000000000001"
                    "&iid=2000000000000000001&dummy=1"
                ),
                '{"dummy":1}',
                "",
                1785478098,
                stub="3D2E04F4EE32BEDDB757E8E3C149F627",
                prefix=bytes.fromhex("c00a8080"),
            ),
            "8404c00a808002301b778615f0dc88d0616e78a03150d06553f6",
        )

    def test_x_gorgon_matches_second_native_prefix_shape(self):
        self.assertEqual(
            x_gorgon(
                (
                    "aid=359289&device_id=1000000000000000001"
                    "&iid=2000000000000000001&dummy=1"
                ),
                '{"dummy":1}',
                "",
                1785479227,
                stub="3D2E04F4EE32BEDDB757E8E3C149F627",
                prefix=bytes.fromhex("40130000"),
            ),
            "840440130000a3925e4d1ef03996f9baaa316d5137106a41a11d",
        )

    def test_x_gorgon_rejects_invalid_sizes(self):
        with self.assertRaises(ValueError):
            x_gorgon_mix(bytes(19), bytes(4))
        with self.assertRaises(ValueError):
            x_gorgon_mix(bytes(20), bytes(3))


if __name__ == "__main__":
    unittest.main()
