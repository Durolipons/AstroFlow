"""Interpretation editor screen.

This screen exposes the JSON-backed interpretation library in a simple form so
an astrologer can rewrite the library text without touching the engine code.
Only the wording lives here; all astrology calculations remain in ``core/``.
"""

from __future__ import annotations

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core.interpretation_store import (
    configure_interpretation_library,
    default_interpretation_library,
    interpretation_library_path,
    load_interpretation_library,
    save_interpretation_library,
)


_CATEGORY_LABELS = {
    "sign_text": "Sun sign keywords",
    "aspect_text": "Aspect keywords",
    "planet_role": "Planet roles",
    "sky_aspect_text": "Sky aspect wording",
    "planet_sky_note": "Sky planet notes",
    "sign_sky_note": "Sign sky notes",
    # --- Natal combination libraries ---
    "planet_sign": "Planet in sign",
    "planet_house": "Planet in house",
    "sun_moon": "Sun / Moon blend",
    "aspect_pair": "Planet-pair aspect",
    "angle_sign": "Angle in sign",
    "planet_sign_retro": "Retrograde by sign",
    "house_ruler": "House ruler",
    # --- Full-chart poetic synthesis ---
    "synthesis_section_headings": "Synthesis section headings",
    "synthesis_narrative_bridges": "Synthesis narrative bridges",
    "planetary_archetypal_imagery": "Planetary archetypal imagery",
    "synthesis_strengths": "Synthesis strengths",
    "synthesis_growth_language": "Synthesis growth language",
    "forecast_synthesis": "Forecast synthesis",
    "synthesis_conclusions": "Synthesis conclusions",
    # --- Astro-Clock forecast libraries ---
    "forecast_ingress": "Forecast ingress",
    "forecast_station": "Forecast station",
    "forecast_phase": "Forecast lunation",
    "sign_forecast": "Sign forecasts",
    "forecast_planet_in_sign": "Forecast planet in sign",
    "forecast_sign_aspect": "Forecast sign aspect",
    "forecast_lunation_in_sign": "Lunation in sign",
    "forecast_lunation_area": "Lunation life area",
    "forecast_retrograde": "Forecast retrograde",
    "transit_natal": "Transit to natal",
    "eclipse_layer": "Eclipse context",
    # --- Forecast narrative wording ---
    "forecast_period_intro": "Forecast period introductions",
    "forecast_transition": "Forecast transitions",
    "forecast_invitation": "Forecast practical invitations",
    "forecast_quiet": "Forecast quiet periods",
    # --- Elemental & Modal analysis ---
    "element_keywords": "Element keywords",
    "element_balance": "Element balance",
    "modality_balance": "Modality balance",
    # --- Vedic astrology ---
    "nakshatra_text": "Nakshatra descriptions",
    "dasha_text": "Dasha periods",
    "vedic_glossary": "Vedic glossary (plain English)",
    "planet_dosha": "Planet doshas (Ayurveda)",
    # --- Chinese astrology ---
    "chinese_zodiac": "Chinese zodiac animals",
    "chinese_element": "Chinese elements",
    "yin_yang": "Yin-Yang polarities",
}
_LABEL_TO_CATEGORY = {label: key for key, label in _CATEGORY_LABELS.items()}
_CATEGORY_ORDER = tuple(_CATEGORY_LABELS.keys())


class InterpretationEditorScreen(Screen):
    """Editable view of AstroFlow's interpretation wording."""

    category_spinner = ObjectProperty(None)
    entry_spinner = ObjectProperty(None)
    key_input = ObjectProperty(None)
    value_input = ObjectProperty(None)
    status_label = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._library = None
        self._category = "sign_text"
        self._selected_key = ""
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self._reload_library()
        self._sync_category_spinner()
        self._sync_entry_spinner()

    def go_home(self):
        self.manager.current = "home"

    def select_category(self, label: str) -> None:
        category = _LABEL_TO_CATEGORY.get(label, self._category)
        if category == self._category and self.category_spinner is not None:
            return
        self._category = category
        self._selected_key = ""
        self._sync_entry_spinner()

    def select_entry(self, key: str) -> None:
        if key == self._selected_key:
            return
        self._selected_key = key
        self._fill_editor(key)

    def save_entry(self):
        """Persist the current key/value pair to the active library file."""
        if self._library is None:
            self._reload_library()

        key = (self.key_input.text if self.key_input is not None else "").strip()
        raw_value = self.value_input.text if self.value_input is not None else ""
        if not key:
            self._set_status("The entry key cannot be blank.")
            return
        if raw_value.strip() == "":
            self._set_status("The interpretation text cannot be blank.")
            return

        data = self._category_dict()
        if self._selected_key and self._selected_key != key:
            data.pop(self._selected_key, None)
        data[key] = raw_value
        save_interpretation_library(self._library, interpretation_library_path())
        self._selected_key = key
        self._sync_entry_spinner(select_key=key)
        self._set_status(f"Saved {self._category}:{key}")

    def reload_library(self):
        """Discard unsaved edits and reload the JSON file from disk."""
        self._reload_library()
        self._selected_key = ""
        self._sync_entry_spinner()
        self._set_status("Reloaded the interpretation library.")

    def restore_defaults(self):
        """Replace the editable file with AstroFlow's built-in defaults."""
        self._library = default_interpretation_library()
        save_interpretation_library(self._library, interpretation_library_path())
        self._selected_key = ""
        self._sync_entry_spinner()
        self._set_status("Restored the default interpretation library.")

    # -- internals ----------------------------------------------------------
    def _reload_library(self):
        configure_interpretation_library(interpretation_library_path())
        self._library = load_interpretation_library()
        if self._library is None:
            self._library = default_interpretation_library()

    def _category_dict(self):
        return getattr(self._library, self._category)

    def _sync_category_spinner(self):
        if self.category_spinner is None:
            return
        labels = [ _CATEGORY_LABELS[name] for name in _CATEGORY_ORDER ]
        self.category_spinner.values = labels
        self.category_spinner.text = _CATEGORY_LABELS[self._category]

    def _sync_entry_spinner(self, select_key: str = ""):
        if self._library is None:
            self._reload_library()
        data = self._category_dict()
        keys = sorted(data.keys(), key=lambda item: item.lower())
        if self.entry_spinner is not None:
            self.entry_spinner.values = keys if keys else ["(no entries)"]
            if select_key and select_key in data:
                self.entry_spinner.text = select_key
            elif self._selected_key and self._selected_key in data:
                self.entry_spinner.text = self._selected_key
            elif keys:
                self.entry_spinner.text = keys[0]
            else:
                self.entry_spinner.text = "(no entries)"

        if keys:
            chosen = select_key if select_key in data else (
                self._selected_key if self._selected_key in data else keys[0]
            )
            self._selected_key = chosen
            self._fill_editor(chosen)
        else:
            self._selected_key = ""
            self._fill_editor("")

    def _fill_editor(self, key: str):
        data = self._category_dict()
        value = data.get(key, "")
        if self.key_input is not None:
            self.key_input.text = key
        if self.value_input is not None:
            self.value_input.text = value

    def _set_status(self, text: str) -> None:
        if self.status_label is not None:
            self.status_label.text = text
