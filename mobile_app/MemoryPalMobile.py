"""
MemoryPal mobile prototype.

This Kivy version is intentionally smaller than the desktop app. It keeps the
main learning loop touch-friendly while leaving platform-specific file picking,
recording, and app-store packaging for the real mobile build.
"""

import re
from difflib import SequenceMatcher

from kivy.app import App
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def smart_score(response, expected):
    response = clean(response).lower()
    expected = clean(expected).lower()
    if not response:
        return "Type an answer first."
    ratio = SequenceMatcher(None, response, expected).ratio()
    response_words = set(re.findall(r"[a-z0-9]+", response))
    expected_words = set(re.findall(r"[a-z0-9]+", expected))
    overlap = len(response_words & expected_words) / max(1, len(expected_words))
    score = round(max(ratio, overlap) * 100)
    if score >= 82:
        bucket = "Easy"
    elif score >= 64:
        bucket = "Good"
    elif score >= 42:
        bucket = "Review"
    else:
        bucket = "Again"
    return f"{score}% close - {bucket}"


def repetition_steps(count, start, span):
    start_index = min(max(start, 1), count) - 1
    span = min(max(span, 1), count)
    steps = []
    current = []
    for offset in range(span):
        index = start_index - offset
        if index < 0:
            break
        current.append(index)
        steps.append(list(current))
    if current and current[-1] > 0:
        steps.append(list(range(current[-1], -1, -1)))
    return steps


class MemoryState:
    def __init__(self):
        self.cards = [
            {"question": "What does active recall mean?", "answer": "Trying to remember before checking the answer."},
            {"question": "Why use spaced review?", "answer": "Hard material comes back sooner and easy material comes back later."},
        ]
        self.resources = ["Notes, audio, images, and video cues will live here."]


class MemoryDialog(ModalView):
    def __init__(self, title, body, **kwargs):
        super().__init__(size_hint=(0.86, None), height=dp(230), background_color=(0, 0, 0, 0.35), **kwargs)
        card = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        with card.canvas.before:
            Color(0.08, 0.12, 0.20, 1)
            self._surface = RoundedRectangle(radius=[dp(22)], pos=card.pos, size=card.size)
        card.bind(pos=self._sync_surface, size=self._sync_surface)
        title_label = Label(text=title, font_size=dp(22), bold=True, size_hint_y=None, height=dp(38))
        body_label = Label(text=body, font_size=dp(15), halign="left", valign="middle")
        body_label.bind(size=lambda label, size: setattr(label, "text_size", (size[0], None)))
        ok_button = Button(
            text="OK",
            size_hint_y=None,
            height=dp(50),
            background_normal="",
            background_color=(0.30, 0.55, 1.0, 1),
            on_release=lambda _btn: self.dismiss(),
        )
        card.add_widget(title_label)
        card.add_widget(body_label)
        card.add_widget(ok_button)
        self.add_widget(card)

    def _sync_surface(self, widget, _value):
        self._surface.pos = widget.pos
        self._surface.size = widget.size


def show_dialog(title, body):
    MemoryDialog(title, body).open()


class BaseScreen(Screen):
    def page(self):
        outer = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        nav = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        for label, target in [("Today", "dashboard"), ("Capture", "capture"), ("Review", "review"), ("Repeat", "repeat"), ("Resources", "resources")]:
            nav.add_widget(Button(text=label, on_release=lambda _btn, name=target: self.switch(name)))
        outer.add_widget(nav)
        scroll = ScrollView()
        body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(12))
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)
        outer.add_widget(scroll)
        return outer, body

    def switch(self, name):
        self.manager.current = name


class DashboardScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        root, body = self.page()
        state = self.manager.state
        body.add_widget(Label(text="MemoryPal", font_size=dp(28), size_hint_y=None, height=dp(48)))
        body.add_widget(Label(text=f"{len(state.cards)} cards ready", size_hint_y=None, height=dp(36)))
        body.add_widget(Label(text="Short sessions, clear prompts, and quick feedback.", size_hint_y=None, height=dp(36)))
        self.add_widget(root)


class CaptureScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        root, body = self.page()
        body.add_widget(Label(text="New Card", font_size=dp(24), size_hint_y=None, height=dp(44)))
        question = TextInput(hint_text="Question / title", multiline=False, size_hint_y=None, height=dp(52))
        answer = TextInput(hint_text="Answer", size_hint_y=None, height=dp(140))
        body.add_widget(question)
        body.add_widget(answer)

        def save(_button):
            if not clean(question.text):
                show_dialog("Add a question", "Each study bit needs a question or title before it can be saved.")
                return
            self.manager.state.cards.insert(0, {"question": clean(question.text), "answer": clean(answer.text) or "Self-check card"})
            question.text = ""
            answer.text = ""
            show_dialog("Card saved", "This card is ready for review, repetition, and smart checking.")

        body.add_widget(Button(text="Save card", size_hint_y=None, height=dp(54), on_release=save))
        self.add_widget(root)


class ReviewScreen(BaseScreen):
    card_index = NumericProperty(0)

    def on_enter(self):
        self.render()

    def render(self):
        self.clear_widgets()
        root, body = self.page()
        state = self.manager.state
        if not state.cards:
            body.add_widget(Label(text="Add a card first.", size_hint_y=None, height=dp(44)))
            self.add_widget(root)
            return
        card = state.cards[self.card_index % len(state.cards)]
        response = TextInput(hint_text="Your answer", size_hint_y=None, height=dp(140))
        result = Label(text="Answer first, then check or reveal.", size_hint_y=None, height=dp(44))
        body.add_widget(Label(text=card["question"], font_size=dp(22), size_hint_y=None, height=dp(80)))
        body.add_widget(response)
        body.add_widget(result)
        body.add_widget(Button(text="Smart Check", size_hint_y=None, height=dp(54), on_release=lambda _btn: setattr(result, "text", smart_score(response.text, card["answer"]))))
        body.add_widget(Button(text="Reveal", size_hint_y=None, height=dp(54), on_release=lambda _btn: setattr(result, "text", card["answer"])))
        body.add_widget(Button(text="Next", size_hint_y=None, height=dp(54), on_release=self.next_card))
        self.add_widget(root)

    def next_card(self, _button):
        self.card_index += 1
        self.render()


class RepeatScreen(BaseScreen):
    round_index = NumericProperty(0)
    steps = ListProperty([])

    def on_enter(self):
        self.round_index = 0
        self.steps = repetition_steps(len(self.manager.state.cards), len(self.manager.state.cards), min(3, len(self.manager.state.cards))) if self.manager.state.cards else []
        self.render()

    def render(self):
        self.clear_widgets()
        root, body = self.page()
        cards = self.manager.state.cards
        if not self.steps:
            body.add_widget(Label(text="Add cards first.", size_hint_y=None, height=dp(44)))
            self.add_widget(root)
            return
        indexes = self.steps[self.round_index]
        label = "-".join(str(index + 1) for index in indexes)
        body.add_widget(Label(text=f"Repeat {label}", font_size=dp(24), size_hint_y=None, height=dp(52)))
        for index in indexes:
            body.add_widget(Label(text=f"{index + 1}. {cards[index]['question']}", size_hint_y=None, height=dp(44)))
        answer = TextInput(hint_text="Write the answer sequence", size_hint_y=None, height=dp(140))
        result = Label(text=f"Round {self.round_index + 1} of {len(self.steps)}", size_hint_y=None, height=dp(44))
        body.add_widget(answer)
        body.add_widget(result)
        expected = "\n".join(cards[index]["answer"] for index in indexes)
        body.add_widget(Button(text="Smart Check", size_hint_y=None, height=dp(54), on_release=lambda _btn: setattr(result, "text", smart_score(answer.text, expected))))
        body.add_widget(Button(text="Reveal", size_hint_y=None, height=dp(54), on_release=lambda _btn: setattr(result, "text", expected)))
        row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(8))
        row.add_widget(Button(text="Previous", on_release=lambda _btn: self.move(-1)))
        row.add_widget(Button(text="Next", on_release=lambda _btn: self.move(1)))
        body.add_widget(row)
        self.add_widget(root)

    def move(self, delta):
        self.round_index = min(max(self.round_index + delta, 0), len(self.steps) - 1)
        self.render()


class ResourcesScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        root, body = self.page()
        body.add_widget(Label(text="Resources", font_size=dp(24), size_hint_y=None, height=dp(48)))
        for item in self.manager.state.resources:
            body.add_widget(Label(text=item, size_hint_y=None, height=dp(60)))
        self.add_widget(root)


class MemoryPalMobile(App):
    def build(self):
        manager = ScreenManager(transition=FadeTransition(duration=0.12))
        manager.state = MemoryState()
        manager.add_widget(DashboardScreen(name="dashboard"))
        manager.add_widget(CaptureScreen(name="capture"))
        manager.add_widget(ReviewScreen(name="review"))
        manager.add_widget(RepeatScreen(name="repeat"))
        manager.add_widget(ResourcesScreen(name="resources"))
        manager.current = "dashboard"
        return manager


if __name__ == "__main__":
    MemoryPalMobile().run()
