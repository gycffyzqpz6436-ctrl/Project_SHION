import hashlib
import json
import struct
import unittest
from pathlib import Path
from app.characters.registry import CharacterRegistry


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_ROOT = ROOT / "app" / "static" / "assets" / "characters" / "shion"
ASSET_ROOT = CHARACTER_ROOT / "official" / "static_2d"


class CharacterAssetTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ASSET_ROOT / "asset_manifest.json").read_text(encoding="utf-8"))
        self.profile = json.loads((CHARACTER_ROOT / "profile.json").read_text(encoding="utf-8"))

    def test_shion_profile_resolves_owner_approved_static_renderer(self):
        self.assertEqual(self.profile["character_id"], "shion")
        self.assertEqual(self.profile["renderer"]["type"], "static_2d")
        self.assertEqual(self.profile["renderer"]["asset_set"], "official_static_2d_v1")
        self.assertEqual(self.profile["default_voice"]["preset_id"], "SHION Default")
        self.assertEqual(self.profile["default_voice"]["style"], "Bright")
        self.assertTrue(self.manifest["owner_approved"])
        self.assertEqual(self.manifest["status"], "official")
        resolved = CharacterRegistry(CHARACTER_ROOT.parent).get("shion")
        self.assertEqual(resolved["assets"]["avatar"], "/assets/characters/shion/official/static_2d/shion_avatar.png")
        self.assertEqual(resolved["canonical_reference"], "/docs/character/character_bible.md")

    def test_manifest_png_dimensions_alpha_and_hashes(self):
        self.assertEqual(set(self.manifest["assets"]), {"avatar", "panel", "master"})
        for role, metadata in self.manifest["assets"].items():
            relative = Path(metadata["path"])
            self.assertFalse(relative.is_absolute())
            self.assertNotIn("..", relative.parts)
            path = ASSET_ROOT / relative
            payload = path.read_bytes()
            self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[16:26])
            self.assertEqual((width, height), (metadata["width"], metadata["height"]))
            self.assertEqual(bit_depth, 8)
            self.assertEqual(color_type, 6, f"{role} must be RGBA PNG")
            self.assertTrue(metadata["alpha"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), metadata["sha256"])

    def test_presentation_states_resolve_to_declared_asset_roles(self):
        roles = set(self.manifest["assets"])
        for state in ("idle", "thinking", "generating", "speaking", "happy", "playful", "concerned"):
            self.assertIn(self.manifest["presentation_states"][state], roles)

    def test_missing_asset_fallback_is_retained(self):
        javascript = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('const fallbackCharacterAsset = "/assets/shion/avatar.svg"', javascript)
        self.assertIn("image.onerror", javascript)
        self.assertIn("Official 2D asset unavailable", html)


if __name__ == "__main__":
    unittest.main()
