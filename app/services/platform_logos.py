"""Platform-logo defaults and safe paths for the bundled SVG collection."""

from __future__ import annotations

from pathlib import Path


SVG_DIRECTORY = Path(__file__).resolve().parents[2] / "static" / "icons" / "platforms"
SVG_PREFIX = "icons/platforms/"
LEGACY_SVG_PREFIX = "icons/svg/"

# First guesses only: a saved Settings mapping always takes precedence.
DEFAULT_PLATFORM_LOGOS = {
    "atari2600": "atari_2600.svg",
    "atari5200": "atari_5200.svg",
    "atari7800": "atari_7800.svg",
    "nes": "nintendo_nes.svg",
    "snes": "nintendo_snes.svg",
    "n64": "nintendo_64_tall_alt.svg",
    "gamecube": "nintendo_gamecube.svg",
    "wii": "nintendo_wii.svg",
    "wiiu": "nintendo_wiiu.svg",
    "switch": "nintendo_switch.svg",
    "gameboy": "nintendo_gameboy.svg",
    "gba": "nintendo_gameboy_advance.svg",
    "nds": "nintendo_ds.svg",
    "3ds": "nintendo_3ds.svg",
    "genesis": "sega_genesis.svg",
    "saturn": "sega_saturn.svg",
    "dreamcast": "sega_dreamcast.svg",
    "ps1": "playstation_flat.svg",
    "ps2": "playstation_ps2.svg",
    "ps3": "playstation_ps3_tall.svg",
    "ps4": "playstation_ps4_compact.svg",
    "ps5": "playstation_ps5_compact.svg",
    "psp": "playstation_psp.svg",
    "vita": "playstation_vita.svg",
    "xbox": "xbox_original.svg",
    "xbox360": "xbox_360.svg",
    "xboxone": "xbox_one.svg",
    "xboxsx": "xbox_series.svg",
    "pc": "windows.svg",
}


def available_svg_paths() -> list[str]:
    """Every selectable, repo-bundled SVG as a path below ``/static``."""
    if not SVG_DIRECTORY.is_dir():
        return []
    return [SVG_PREFIX + path.name for path in sorted(SVG_DIRECTORY.glob("*.svg"))]


def available_svg_choices() -> list[dict[str, str]]:
    """Selectable paths with human-readable labels for the Settings control."""
    return [
        {"path": path, "name": Path(path).stem.replace("_", " ").replace("-", " ").title()}
        for path in available_svg_paths()
    ]


def normalise_svg_path(value: str) -> str | None:
    """Accept only SVG files supplied by this application, never arbitrary URLs."""
    value = (value or "").strip().replace("\\", "/")
    if value.startswith("/static/"):
        value = value.removeprefix("/static/")
    elif value.startswith("static/"):
        value = value.removeprefix("static/")
    # Existing mappings created before the dependency moved remain valid as
    # soon as the corresponding filename is installed in its new location.
    if value.startswith(LEGACY_SVG_PREFIX):
        value = SVG_PREFIX + value.removeprefix(LEGACY_SVG_PREFIX)
    return value if value in available_svg_paths() else None


def logo_path(platform_slug: str, saved_path: str | None = None) -> str | None:
    """The configured path, falling back to Shelf's first-guess mapping."""
    return normalise_svg_path(saved_path or "") or (
        SVG_PREFIX + DEFAULT_PLATFORM_LOGOS[platform_slug]
        if platform_slug in DEFAULT_PLATFORM_LOGOS else None
    )
